#!/usr/bin/env python3
"""四大满贯竖屏片 v2 原型：声音做主时钟，字幕逐句跟读，运镜交替，叠化转场。

对照 tools/build_grand_slam_short.py（v1）的关键差异：
- v1 分镜时长写死，配音 atempo 至多 1.8x 压进画面、超长截断；v2 先合成配音，
  画面时长 = 配音时长 + 呼吸间隙，永不变速、永不截断。
- v1 字幕 SRT 按计划整秒估算且不烧录；v2 用 edge-tts WordBoundary 词级时间戳
  生成 ASS 逐句字幕烧进画面，说到哪亮到哪。
- v1 每镜黑场淡出淡入；v2 相邻镜头 0.45s 交叉叠化，无黑场。
- v1 全片同方向缓推；v2 推近/拉远/横摇按镜头轮换。
- v1 无响度处理（实测 -20dB）；v2 loudnorm -16 LUFS、48k 立体声。
"""
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "grand-slam-vertical"
OUT = ROOT / "output" / "grand-slam-vertical-v2"
TMP = OUT / "_work"
FPS = 30
W, H = 1080, 1920
XFADE = 0.45          # 镜间叠化时长
GAP = 0.35            # 每段配音后的呼吸间隙
NOVO_DUR = 2.8        # 无配音镜头（球场名片）的停留时长
VOICE = "zh-CN-YunjianNeural"
RATE = "+8%"
ACCENT_ASS = "&H28BEF5&"  # 品牌黄 #F5BE28 的 BGR
KEYWORDS = ("澳网", "法网", "温网", "美网", "红土", "草地", "硬地", "大满贯")


def synth(text: str, dst: Path):
    """合成一段配音，返回词级时间戳 [(start, dur, word), ...]（秒）。"""
    words = []

    async def run():
        c = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
        with open(dst, "wb") as f:
            async for ch in c.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    words.append((ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]))

    asyncio.run(run())
    return words


def adur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def group_lines(words, punct_gaps):
    """把词级时间戳聚成字幕行：标点/停顿断行，行长 6–16 字。"""
    lines, cur, chars = [], [], 0
    for i, (st, du, tx) in enumerate(words):
        cur.append((st, du, tx))
        chars += len(tx)
        nxt_gap = (words[i + 1][0] - (st + du)) if i + 1 < len(words) else 9.9
        if chars >= 16 or (chars >= 6 and nxt_gap > 0.28) or i == len(words) - 1:
            text = "".join(w[2] for w in cur)
            lines.append((cur[0][0], cur[-1][0] + cur[-1][1], text))
            cur, chars = [], 0
    return lines


def ass_escape(t):
    return t.replace("{", "").replace("}", "")


def highlight(text):
    for kw in KEYWORDS:
        if kw in text:
            text = text.replace(kw, "{\\c" + ACCENT_ASS + "}" + kw + "{\\c&HFFFFFF&}")
    return text


def fmt_ass_t(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def motion_filter(idx, nframes):
    """三种运镜轮换；输入先放大 2x 抑制 zoompan 抖动。"""
    base = f"scale={W*2}:{H*2},zoompan="
    if idx % 3 == 0:   # 推近
        z = f"z='1+0.09*on/{nframes}'"
        xy = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif idx % 3 == 1:  # 拉远
        z = f"z='1.09-0.09*on/{nframes}'"
        xy = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    else:               # 横摇（轻推为底）
        z = "z='1.07'"
        xy = f"x='(iw-iw/zoom)*on/{nframes}':y='ih/2-(ih/zoom/2)'"
    return f"{base}{z}:{xy}:d={nframes}:s={W}x{H}:fps={FPS},format=yuv420p"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    spec = json.loads((ROOT / "data" / "grand_slam_video.json").read_text("utf-8"))
    scenes = spec["scenes"]

    # 1) 配音先行：合成 + 词级时间戳 + 真实时长 → 每镜画面时长
    plan = []
    for i, sc in enumerate(scenes):
        vo = sc.get("vo", "").strip()
        frame = SRC / "frames" / f"{sc['id']}.png"
        if not frame.exists():
            sys.exit(f"缺帧：{frame}")
        if vo:
            mp3 = TMP / f"vo_{i:02d}.mp3"
            words = synth(vo, mp3)
            d = adur(mp3) + GAP
            plan.append(dict(idx=i, id=sc["id"], frame=frame, mp3=mp3, words=words, dur=d))
            print(f"  [{sc['id']}] 配音 {d - GAP:.2f}s + 间隙 → 画面 {d:.2f}s，{len(words)} 词")
        else:
            plan.append(dict(idx=i, id=sc["id"], frame=frame, mp3=None, words=[], dur=NOVO_DUR))
            print(f"  [{sc['id']}] 无配音 → 画面 {NOVO_DUR}s")

    starts, acc = [], 0.0
    for p in plan:
        starts.append(acc)
        acc += p["dur"]
    total = acc
    print(f"总时长 {total:.1f}s（v1 为 170s）")

    # 2) ASS 逐句字幕（词时间戳 + 镜头起点偏移）
    ass = OUT / "captions.ass"
    header = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, BorderStyle
Style: Sub,Noto Sans CJK SC,62,&HFFFFFF&,&H000000&,&H66000000&,1,4,2,2,60,60,470,1

[Events]
Format: Layer, Start, End, Style, Text
"""
    lines_out = []
    for p, st0 in zip(plan, starts):
        for (a, b, text) in group_lines(p["words"], None):
            lines_out.append(
                f"Dialogue: 0,{fmt_ass_t(st0 + a)},{fmt_ass_t(st0 + b + 0.15)},Sub,"
                f"{highlight(ass_escape(text))}")
    ass.write_text(header + "\n".join(lines_out) + "\n", "utf-8")
    print(f"字幕 {len(lines_out)} 行 → {ass}")

    # 3) 每镜运动片段（时长 = 画面时长 + 叠化余量）
    clips = []
    for k, p in enumerate(plan):
        c = p["dur"] + (XFADE if k < len(plan) - 1 else 0)
        nf = int(round(c * FPS))
        clip = TMP / f"c_{k:02d}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(p["frame"]),
             "-t", f"{c:.3f}", "-vf", motion_filter(k, nf),
             "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
             str(clip)], check=True)
        clips.append(clip)
        print(f"  片段 {k + 1}/{len(plan)} {p['id']} {c:.2f}s")

    # 4) 声轨拼装：配音 + 间隙/静音，整体 loudnorm
    concat_parts = []
    for p in plan:
        if p["mp3"]:
            concat_parts.append((p["mp3"], p["dur"]))
        else:
            concat_parts.append((None, p["dur"]))
    filter_a, inputs_a, idx = [], [], 0
    for src, d in concat_parts:
        if src:
            inputs_a += ["-i", str(src)]
            filter_a.append(f"[{idx}:a]apad,atrim=0:{d:.3f}[a{idx}]")
            idx += 1
        else:
            filter_a.append(
                f"anullsrc=r=48000:cl=mono,atrim=0:{d:.3f}[a{len(inputs_a) // 2 + 900}]")
    # 简化：静音段用 lavfi 单独生成文件再 concat，避免复杂 filtergraph
    seg_files = []
    for j, (src, d) in enumerate(concat_parts):
        seg = TMP / f"a_{j:02d}.wav"
        if src:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
                            "-af", f"apad=whole_dur={d:.3f}", "-t", f"{d:.3f}",
                            "-ar", "48000", "-ac", "1", str(seg)], check=True)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "anullsrc=r=48000:cl=mono", "-t", f"{d:.3f}",
                            str(seg)], check=True)
        seg_files.append(seg)
    alist = TMP / "alist.txt"
    alist.write_text("".join(f"file '{s.name}'\n" for s in seg_files), "utf-8")
    voall = TMP / "vo_all.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(alist), "-c", "copy", str(voall)],
                   check=True, cwd=str(TMP))
    vofinal = TMP / "vo_final.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(voall),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000",
                    "-ac", "2", str(vofinal)], check=True)

    # 5) 交叉叠化链 + 字幕烧录 + 混流
    n = len(clips)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    cmd += ["-i", str(vofinal)]
    fg, prev, acc_d = [], "[0:v]", plan[0]["dur"]
    for k in range(1, n):
        out = f"[v{k}]" if k < n - 1 else "[vx]"
        fg.append(f"{prev}[{k}:v]xfade=transition=fade:duration={XFADE}:"
                  f"offset={acc_d:.3f}{out}")
        prev = out
        acc_d += plan[k]["dur"]
    ass_path = str(ass).replace("'", r"\'")
    fg.append(f"[vx]subtitles=filename='{ass_path}'[vs]")
    cmd += ["-filter_complex", ";".join(fg), "-map", "[vs]", "-map", f"{n}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(OUT / "grand-slam-v2.mp4")]
    print("最终合成（叠化 + 字幕 + 混流）…")
    subprocess.run(cmd, check=True)
    print(f"完成：{OUT / 'grand-slam-v2.mp4'}  总时长 {total:.1f}s")


if __name__ == "__main__":
    main()
