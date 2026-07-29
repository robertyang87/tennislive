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
from tennislive.video.subtitle_text import drop_punctuation

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


_PUNCT = "。？！；，、——…："


def group_lines(words, vo_text):
    """把词级时间戳聚成字幕行：优先在原文标点处断行，长行 18 字强拆。"""
    plain = vo_text or ""
    lines, cur, chars, pos = [], [], 0, 0
    for i, (st, du, tx) in enumerate(words):
        cur.append((st, du, tx))
        chars += len(tx)
        idx = plain.find(tx, pos)
        if idx >= 0:
            pos = idx + len(tx)
        nxt = plain[pos] if pos < len(plain) else "。"
        at_punct = nxt in _PUNCT
        nxt_gap = (words[i + 1][0] - (st + du)) if i + 1 < len(words) else 9.9
        if (at_punct and chars >= 5) or chars >= 18 or nxt_gap > 0.55 \
                or i == len(words) - 1:
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


def _outline_text(d, xy, text, font, fill, oc=(0, 0, 0), w=5, anchor="mm"):
    x, y = xy
    for dx in range(-w, w + 1):
        for dy in range(-w, w + 1):
            if dx * dx + dy * dy <= w * w:
                d.text((x + dx, y + dy), text, font=font, fill=oc, anchor=anchor)
    d.text((x, y), text, font=font, fill=fill, anchor=anchor)


def render_chrome(scene, brand="网球时差"):
    """b-roll 镜头的透明浮层：品牌点标 + 赛事名 + 底部说明（+可选开场大字）。"""
    from PIL import Image, ImageDraw, ImageFont
    cjk = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_brand = ImageFont.truetype(cjk, 36)
    lg_path = ROOT / "assets" / "logo" / "brand" / "icon.png"
    if lg_path.exists():
        lg = Image.open(lg_path).convert("RGBA").resize((62, 62), Image.LANCZOS)
        img.paste(lg, (44, 40), lg)
        d.text((118, 71), brand, font=f_brand, fill=(255, 255, 255), anchor="lm")
    else:
        d.ellipse([48, 58, 68, 78], fill=(245, 190, 40))
        d.text((82, 68), brand, font=f_brand, fill=(255, 255, 255), anchor="lm")
    sec = scene.get("section") or {}
    en, zh = sec.get("en", ""), sec.get("zh", "")
    label_y = 170
    logo = scene.get("logo")
    if logo and (ROOT / logo).exists():
        lg = Image.open(ROOT / logo)
        lw = 340
        lg = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
        lx, ly = (W - lw) // 2, 210
        if lg.mode == "RGBA":
            img.paste(lg, (lx, ly), lg)
        else:  # 白底 logo 垫白色圆角卡
            pad = 24
            card = Image.new("RGBA", (lw + pad * 2, lg.height + pad * 2), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle([0, 0, card.width, card.height], radius=28,
                                 fill=(255, 255, 255, 235))
            card.paste(lg.convert("RGB"), (pad, pad))
            img.paste(card, (lx - pad, ly - pad), card)
        label_y = ly + lg.height + 90
    if en or zh:
        label = f"{en} · {zh}" if en and zh else (en or zh)
        _outline_text(d, (W / 2, label_y), label, ImageFont.truetype(cjk, 44),
                      (245, 190, 40), w=4)
    big = scene.get("big_chrome", "")
    if big:
        _outline_text(d, (W / 2, int(H * 0.36)), big,
                      ImageFont.truetype(cjk, 170), (255, 255, 255), w=8)
        sub = scene.get("big_chrome_sub", "")
        if sub:
            _outline_text(d, (W / 2, int(H * 0.36) + 140), sub,
                          ImageFont.truetype(cjk, 52), (245, 190, 40), w=5)
    cap = scene.get("caption", "")
    if cap:
        _outline_text(d, (W / 2, H - 330), cap, ImageFont.truetype(cjk, 58),
                      (255, 255, 255), w=5)
    out = TMP / f"chrome_{scene['id']}.png"
    img.save(out)
    return out


def scene_cuts(sc):
    """镜头的 EDL：cuts 列表优先，broll/broll_start 兼容为单切。"""
    if sc.get("cuts"):
        return [(c["src"], float(c.get("start", 0)),
                 float(c["dur"]) if c.get("dur") else None)
                for c in sc["cuts"]]
    if sc.get("broll"):
        return [(sc["broll"], float(sc.get("broll_start", 0)), None)]
    return None


def build_broll_video(cuts, total, chrome, dst):
    """多切 EDL → 9:16 全出血硬切拼接，最后叠透明浮层。None 时长的切自动补满。"""
    fixed = sum(c[2] for c in cuts if c[2])
    flex = [i for i, c in enumerate(cuts) if not c[2]]
    fill = max(0.8, (total - fixed) / len(flex)) if flex else 0
    cmd = ["ffmpeg", "-v", "error", "-y"]
    parts = []
    for i, (src, start, dur) in enumerate(cuts):
        d_i = dur if dur else fill
        path = str(ROOT / src if not str(src).startswith("/") else src)
        if str(src).lower().endswith((".jpg", ".jpeg", ".png")):
            # 照片切片：loop 成片段，轻推近做运动
            nf = int(round(d_i * FPS))
            cmd += ["-loop", "1", "-t", f"{d_i:.3f}", "-i", path]
            parts.append(
                f"[{i}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
                f"crop={W * 2}:{H * 2},setsar=1,zoompan=z='1+0.07*on/{nf}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={W}x{H}:fps={FPS},"
                f"settb=AVTB,setpts=PTS-STARTPTS,"
                f"eq=brightness=-0.04:saturation=1.05[v{i}]")
        else:
            cmd += ["-ss", f"{start:.2f}", "-t", f"{d_i:.3f}", "-i", path]
            parts.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},setsar=1,fps={FPS},settb=AVTB,setpts=PTS-STARTPTS,"
                f"eq=brightness=-0.04:saturation=1.05[v{i}]")
    n = len(cuts)
    cmd += ["-i", str(chrome)]
    fc = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(n)) + \
        f"concat=n={n}:v=1[cat];[cat]trim=0:{total:.3f},setpts=PTS-STARTPTS[ct];" + \
        f"[ct][{n}:v]overlay=0:0,format=yuv420p"
    cmd += ["-filter_complex", fc, "-an", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", str(dst)]
    subprocess.run(cmd, check=True)


def build_scene_ambient(cuts, total, dst):
    """从各切片抽原声拼成环境音轨（声浪/音乐），失败返回 None。"""
    segs = []
    fixed = sum(c[2] for c in cuts if c[2])
    flex = [i for i, c in enumerate(cuts) if not c[2]]
    fill = max(0.8, (total - fixed) / len(flex)) if flex else 0
    for i, (src, start, dur) in enumerate(cuts):
        d_i = dur if dur else fill
        seg = dst.parent / f"{dst.stem}_amb{i}.wav"
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{d_i:.3f}",
             "-i", str(ROOT / src if not str(src).startswith("/") else src),
             "-vn", "-ac", "1", "-ar", "48000", str(seg)], capture_output=True)
        if r.returncode == 0 and seg.exists() and seg.stat().st_size > 1000:
            segs.append(seg)
    if not segs:
        return None
    lst = dst.parent / f"{dst.stem}_amb.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segs), "utf-8")
    fade = (f"apad=whole_dur={total:.3f},atrim=0:{total:.3f},"
            f"afade=t=in:d=0.6,afade=t=out:st={max(0, total - 0.8):.3f}:d=0.8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-af", fade,
                    "-t", f"{total:.3f}", str(dst)],
                   check=True, cwd=str(dst.parent))
    return dst


BED_SRC = "assets/local/broll/wim2026_montage_0-120s.mp4"


def build_bed_ambient(k, total, dst):
    """无素材镜头的低音量氛围床：从官方蒙太奇轮换取段，带淡入淡出。"""
    src = ROOT / BED_SRC
    if not src.exists():
        return None
    offset = 40 + (k * 13) % 55
    fade = (f"apad=whole_dur={total:.3f},atrim=0:{total:.3f},"
            f"afade=t=in:d=0.6,afade=t=out:st={max(0, total - 0.8):.3f}:d=0.8")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(offset),
                        "-t", f"{total:.3f}", "-i", str(src), "-vn",
                        "-ac", "1", "-ar", "48000", "-af", fade, str(dst)],
                       capture_output=True)
    return dst if r.returncode == 0 and dst.exists() else None


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
    scenes = [s for s in scenes if not s.get("skip")]
    plan = []
    for i, sc in enumerate(scenes):
        vo = sc.get("vo", "").strip()
        frame = SRC / "frames" / f"{sc['id']}.png"
        if not frame.exists():
            sys.exit(f"缺帧：{frame}")
        hold = float(sc.get("hold", 0))   # 声浪呼吸口：解说结束后画面+现场声继续
        if vo:
            mp3 = TMP / f"vo_{i:02d}.mp3"
            words = synth(vo, mp3)
            d = adur(mp3) + GAP + hold
            plan.append(dict(idx=i, id=sc["id"], frame=frame, mp3=mp3, words=words,
                             dur=d, vo=vo))
            print(f"  [{sc['id']}] 配音 {d - GAP - hold:.2f}s + 间隙{'+呼吸' if hold else ''} → 画面 {d:.2f}s，{len(words)} 词")
        else:
            plan.append(dict(idx=i, id=sc["id"], frame=frame, mp3=None, words=[],
                             dur=NOVO_DUR + hold))
            print(f"  [{sc['id']}] 无配音 → 画面 {NOVO_DUR + hold}s")

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
    CARD_TYPES = {"title", "grid", "triptych", "collage", "section"}
    for p, st0 in zip(plan, starts):
        sc = scenes[p["idx"]]
        # 静态信息卡自带文字层级，不烧跟读字幕；字幕只上视频/大图镜头
        if not scene_cuts(sc) and sc.get("type") in CARD_TYPES:
            continue
        for (a, b, text) in group_lines(p["words"], p.get("vo", "")):
            # 烧进画面的字幕不写标点，全站统一——见 video/subtitle_text.py。
            # 去标点放在**切完行之后**：group_lines 还要靠原文的标点断句。
            shown = drop_punctuation(text)
            if not shown:
                continue
            lines_out.append(
                f"Dialogue: 0,{fmt_ass_t(st0 + a)},{fmt_ass_t(st0 + b + 0.15)},Sub,"
                f"{highlight(ass_escape(shown))}")
    ass.write_text(header + "\n".join(lines_out) + "\n", "utf-8")
    print(f"字幕 {len(lines_out)} 行 → {ass}")

    # 3) 每镜运动片段（时长 = 画面时长 + 叠化余量）
    clips = []
    for k, p in enumerate(plan):
        c = p["dur"] + (XFADE if k < len(plan) - 1 else 0)
        nf = int(round(c * FPS))
        clip = TMP / f"c_{k:02d}.mp4"
        sc = scenes[p["idx"]]
        cuts = scene_cuts(sc)
        if cuts:
            chrome = render_chrome(sc)
            build_broll_video(cuts, c, chrome, clip)
            p["ambient"] = build_scene_ambient(cuts, p["dur"], TMP / f"amb_{k:02d}.wav")
            p["amb_vol"] = 0.55
            if p["ambient"] is None:  # 纯照片切片无原声 → 垫氛围床
                p["ambient"] = build_bed_ambient(k, p["dur"], TMP / f"bed_{k:02d}.wav")
                p["amb_vol"] = 0.3
            kind = f"b-roll×{len(cuts)}"
        else:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(p["frame"]),
                 "-t", f"{c:.3f}", "-vf", motion_filter(k, nf),
                 "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                 str(clip)], check=True)
            # 静帧镜头也垫氛围床，声音永不硬断
            p["ambient"] = build_bed_ambient(k, p["dur"], TMP / f"bed_{k:02d}.wav")
            p["amb_vol"] = 0.28
            kind = "静帧"
        clips.append(clip)
        print(f"  片段 {k + 1}/{len(plan)} {p['id']} {c:.2f}s [{kind}]")

    # 4) 声轨拼装：解说为主，现场声浪 sidechain 闪避垫底，整体 loudnorm
    seg_files = []
    for j, p in enumerate(plan):
        d = p["dur"]
        seg = TMP / f"a_{j:02d}.wav"
        vo_p, amb = p["mp3"], p.get("ambient")
        if vo_p and amb:
            fc = (f"[1:a]apad=whole_dur={d:.3f},atrim=0:{d:.3f},"
                  f"aresample=48000,pan=mono|c0=c0,asplit=2[vo1][vo2];"
                  f"[0:a]aresample=48000[amb0];"
                  f"[amb0][vo1]sidechaincompress=threshold=0.015:ratio=12:"
                  f"attack=30:release=600[duck];[duck]volume={p.get('amb_vol', 0.55)}[db];"
                  f"[db][vo2]amix=inputs=2:duration=first:normalize=0")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(amb),
                            "-i", str(vo_p), "-filter_complex", fc,
                            "-t", f"{d:.3f}", "-ar", "48000", "-ac", "1",
                            str(seg)], check=True)
        elif vo_p:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vo_p),
                            "-af", f"apad=whole_dur={d:.3f}", "-t", f"{d:.3f}",
                            "-ar", "48000", "-ac", "1", str(seg)], check=True)
        elif amb:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(amb),
                            "-af", f"volume=0.7,apad=whole_dur={d:.3f}",
                            "-t", f"{d:.3f}", "-ar", "48000", "-ac", "1",
                            str(seg)], check=True)
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
