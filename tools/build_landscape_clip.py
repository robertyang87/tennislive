#!/usr/bin/env python3
"""横屏原片 ＋ 中英双语字幕：给「不裁切」的现场片单独开的一条小路。

账号所有者 2026-09-25（拉沃尔杯两队出场）：「单独出一个视频，配上中英文字幕，
而且是**横屏的，不裁切画面**」「要用**比较小且精美**的中英文字体字幕」。

为什么不走现有三条线（都量过，不是嫌麻烦）：

- 三条线的画布都是竖的（`tests/test_vertical_canvas.py`），而这条要的恰恰是
  「原画面一个像素不裁」——16:9 的源片塞进竖版，要么裁、要么留大块空白
- 赛后开麦那条的闸是为**采访**长的：人脸封面审计、解读卡、比赛核验（`match`）、
  第二份 ASR……出场仪式没有对阵、没有问答，只能处处写豁免
- 赛场之上要冷开场、技战术、比分板回贴——仪式片一条都不沾

所以这条路只做三件事：**取字幕切行 → 下源片 → 等比缩放到 1920×1080（不裁，
比例不对就上下/左右补黑）＋ 烧双语字幕**。下载、取自动字幕、切行都直接借
`build_interview_clip` 的函数（cookie、client 梯子、json3 缓存那些坑都在那边
踩完了），**别在这儿再抄一份会分叉的**。

字幕的样子（「小且精美」）：

    英文  Noto Sans          31px  白  ← 上行，原文
    中文  Noto Sans CJK SC   36px  白  ← 下行，主读行

账号所有者看过第一版预览：「中文在下吧」「中文字体不好看」——第一版是
中文宋体（Noto Serif CJK）在上，笔画细、在 1080p 画面上发虚，换成黑体放到下行。
随后给了一张参照截图（拉沃尔杯官方片自带的字幕）：中英都是常规无衬线体、
字号相近、纯白、没有底框只有一点柔影——英文跟着从意大利衬线体换成 Noto Sans，
字号 27 → 31。

没有底框，只有一圈 1px 的半透明描边加一点柔影——底框在 1080p 横屏上会切出
一条黑带，恰恰把「不裁切」换成了「被挡住」。两行贴着画面底边 46px。

用法：
    python tools/build_landscape_clip.py --spec specs/landscape/<slug>.json --stage subs
    python tools/build_landscape_clip.py --spec specs/landscape/<slug>.json --stage render
    python tools/build_landscape_clip.py --spec specs/landscape/<slug>.json --stage preview \\
        --frame some.jpg --out preview.png   # 本地看字幕长什么样，不联网
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OUTDIR = ROOT / "output" / "landscape"

CANVAS_W, CANVAS_H = 1920, 1080
#: 字幕可用宽：两边各留 160px，一行不许超过它——libass 超宽会自己折行，
#: 折在哪儿没人管（采访线 `_LINE_PX` 那段注释记过同一个坑）。
LINE_PX = CANVAS_W - 160 - 160

FONT_FILES = {
    "zh": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "en": "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
}
#: ASS 的 Fontname 要写字体**自己声明的名字**，写错 libass 不报错、悄悄回退。
ASS_FONT = {"zh": "Noto Sans CJK SC", "en": "Noto Sans"}
FONT_SIZE = {"zh": 36, "en": 31}
#: 两行之间和离底边的距离（px）
MARGIN_BOTTOM = 46
LINE_GAP = 8

_FONT_CACHE: dict[tuple[str, int], object] = {}


def measure(kind: str, text: str) -> float:
    """量一行字的宽度（px），PIL 的 advance 就是 libass 水平排版用的量。"""
    key = (kind, FONT_SIZE[kind])
    if key not in _FONT_CACHE:
        from PIL import ImageFont  # noqa: PLC0415

        path = FONT_FILES[kind]
        if not Path(path).exists():
            raise SystemExit(
                f"量宽度要 {path}，没有。sudo apt-get install -y fonts-noto-cjk fonts-noto-core\n"
                "**别拿回退字体凑合**：回退不报错，量出来的和渲出来的对不上。")
        _FONT_CACHE[key] = ImageFont.truetype(path, FONT_SIZE[kind])
    return _FONT_CACHE[key].getlength(text)


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for k in ("slug", "url", "start", "end"):
        if k not in spec:
            raise SystemExit(f"{path}: 缺 `{k}`")
    if not spec["end"] > spec["start"] >= 0:
        raise SystemExit(f"{path}: 窗口 {spec['start']}~{spec['end']} 不成立")
    return spec


def line_problems(spec: dict) -> list[str]:
    """字幕行的机械闸：时间在窗口里、不重叠、两行都有、都装得下一行。"""
    probs: list[str] = []
    lines = spec.get("lines") or []
    if not lines:
        return ["`lines` 是空的——先跑 --stage subs，照日志把英文和中文填进 spec"]
    prev_end = spec["start"]
    for i, ln in enumerate(lines):
        a, b = float(ln.get("start", -1)), float(ln.get("end", -1))
        en, zh = (ln.get("en") or "").strip(), (ln.get("zh") or "").strip()
        tag = f"第 {i} 行（{a:.2f}~{b:.2f}）"
        if not (spec["start"] <= a < b <= spec["end"]):
            probs.append(f"{tag} 不在窗口 {spec['start']}~{spec['end']} 里，或起止倒了")
        if a < prev_end - 1e-6:
            probs.append(f"{tag} 和上一行重叠（上一行到 {prev_end:.2f}）")
        prev_end = max(prev_end, b)
        if not en or not zh:
            probs.append(f"{tag} 中英两行都要有：en={en!r} zh={zh!r}")
            continue
        if "\n" in en or "\n" in zh:
            probs.append(f"{tag} 一条字幕里不许手动换行")
        for kind, text in (("en", en), ("zh", zh)):
            if (w := measure(kind, text)) > LINE_PX:
                probs.append(f"{tag} {kind} 宽 {w:.0f}px > {LINE_PX}px，会被 libass 折行：{text}")
    return probs


def _ts(x: float) -> str:
    x = max(0.0, x)
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "（").replace("}", "）")


def build_ass(spec: dict) -> str:
    """英文在上、中文在下，都贴着底边。时间轴相对剪辑起点。"""
    en_margin = MARGIN_BOTTOM + FONT_SIZE["zh"] + LINE_GAP + 4
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CANVAS_W}
PlayResY: {CANVAS_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ZH,{ASS_FONT['zh']},{FONT_SIZE['zh']},&H00FFFFFF,&H00FFFFFF,&H80000000,&H90000000,0,0,0,0,100,100,1,0,1,1.0,1.2,2,160,160,{MARGIN_BOTTOM},1
Style: EN,{ASS_FONT['en']},{FONT_SIZE['en']},&H00FFFFFF,&H00FFFFFF,&H80000000,&H90000000,0,0,0,0,100,100,0.3,0,1,1.0,1.2,2,160,160,{en_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    t0 = float(spec["start"])
    fade = r"{\blur1\fad(120,120)}"
    ev = []
    for ln in spec.get("lines") or []:
        a, b = _ts(float(ln["start"]) - t0), _ts(float(ln["end"]) - t0)
        ev.append(f"Dialogue: 0,{a},{b},EN,,0,0,0,,{fade}{_esc(ln['en'].strip())}")
        ev.append(f"Dialogue: 0,{a},{b},ZH,,0,0,0,,{fade}{_esc(ln['zh'].strip())}")
    return head + "\n".join(ev) + "\n"


def _fit_filter() -> str:
    """等比缩放进 1920×1080，**不裁**：比例不对就补黑边，居中。"""
    return (f"scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=decrease:"
            f"flags=lanczos,pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")


def _ass_filter(ass: Path) -> str:
    p = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return f"ass='{p}'"


def stage_subs(spec: dict, outdir: Path) -> None:
    from build_interview_clip import fetch_words, segment  # noqa: PLC0415

    words = fetch_words(spec["url"], outdir, spec)
    rows = segment(words, float(spec["start"]), float(spec["end"]),
                   budget=LINE_PX, width=lambda t: measure("en", t))
    (outdir / "lines.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if words:
        print(f"[字幕] 最后一个词落在 {words[-1][0]:.2f}s")
    print(f"[字幕] 自动字幕 {len(words)} 个词，窗口 {spec['start']}~{spec['end']} 切出 {len(rows)} 行：")
    # 直接打成 spec 里 `lines` 的形状：拷过去填 `zh` 就行
    for r in rows:
        print("  " + json.dumps({"start": r["a"], "end": r["b"], "en": r["en"], "zh": ""},
                                ensure_ascii=False) + ",")


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def encode(src: Path, ass: Path, out: Path, start: float, end: float) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
           "-i", str(src),
           "-vf", f"{_fit_filter()},{_ass_filter(ass)},format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", str(out)]
    print("[编码]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def check_film(film: Path, spec: dict) -> dict:
    """查产物，不查信号：画布、时长、有没有音轨。"""
    info = probe(film)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    want = float(spec["end"]) - float(spec["start"])
    probs = []
    if not v or (v["width"], v["height"]) != (CANVAS_W, CANVAS_H):
        probs.append(f"画布不是 {CANVAS_W}×{CANVAS_H}：{v}")
    if a is None:
        probs.append("没有音轨——原声是这条片子的一半")
    if abs(dur - want) > 0.6:
        probs.append(f"时长 {dur:.2f}s，窗口是 {want:.2f}s")
    if probs:
        raise SystemExit("成片不合格：\n  " + "\n  ".join(probs))
    print(f"[验片] {film.name} {CANVAS_W}×{CANVAS_H} {dur:.2f}s 有音轨 ✅")
    return {"duration": round(dur, 3), "width": CANVAS_W, "height": CANVAS_H}


def stage_render(spec: dict, outdir: Path) -> Path:
    from build_interview_clip import yt_download  # noqa: PLC0415
    from build_match_reel import spec_sources  # noqa: PLC0415

    if probs := line_problems(spec):
        raise SystemExit("字幕行不合格：\n  " + "\n  ".join(probs))
    # 过一遍 reel 那条线的源片闸（`_reject_signed_source_urls`：换签名令牌拉受控流
    # 那条路禁掉）。判据 `test_下载源片一律走spec_sources`。
    url = spec_sources({"source_url": spec["url"]})[""]
    src = yt_download(url, outdir / "source.mp4",
                      "bv*[height<=1080]+ba/b[height<=1080]", spec)
    info = probe(src)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    print(f"[源片] {src.name} {v['width']}×{v['height']} {float(info['format']['duration']):.1f}s")
    ass = outdir / "_subs.ass"
    ass.write_text(build_ass(spec), encoding="utf-8")
    film = outdir / f"{spec['slug']}.mp4"
    encode(src, ass, film, float(spec["start"]), float(spec["end"]))
    meta = check_film(film, spec)
    meta.update({"source_url": url, "source_width": v["width"],
                 "source_height": v["height"], "lines": len(spec["lines"])})
    (outdir / "render.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return film


def stage_preview(spec: dict, frame: Path, out: Path, at: float | None) -> Path:
    """本地看字幕长什么样：拿一张图当画面，烧某一时刻的那一行。不联网。"""
    lines = spec.get("lines") or []
    if not lines:
        raise SystemExit("spec 里没有 lines，没东西可预览")
    t = at if at is not None else float(lines[0]["start"]) + 0.3
    ass = out.with_suffix(".ass")
    ass.write_text(build_ass(spec), encoding="utf-8")
    rel = t - float(spec["start"])
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{rel + 0.5:.2f}", "-i", str(frame),
         "-vf", f"{_fit_filter()},{_ass_filter(ass)}", "-ss", f"{rel:.2f}",
         "-frames:v", "1", str(out)], check=True)
    ass.unlink(missing_ok=True)
    print(f"[预览] {out}（t={t:.2f}）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--stage", choices=["subs", "check", "render", "preview"], required=True)
    ap.add_argument("--frame", help="preview：当画面用的图")
    ap.add_argument("--out", help="preview：输出 png")
    ap.add_argument("--at", type=float, help="preview：源片上的秒数")
    args = ap.parse_args()
    spec = load_spec(Path(args.spec))
    outdir = OUTDIR / spec["slug"]
    outdir.mkdir(parents=True, exist_ok=True)
    if args.stage == "subs":
        stage_subs(spec, outdir)
    elif args.stage == "check":
        if probs := line_problems(spec):
            print("字幕行不合格：\n  " + "\n  ".join(probs))
            return 1
        print(f"[检查] {len(spec['lines'])} 行，全部装得下、不重叠 ✅")
    elif args.stage == "render":
        stage_render(spec, outdir)
    else:
        if not (args.frame and args.out):
            raise SystemExit("preview 要 --frame 和 --out")
        stage_preview(spec, Path(args.frame), Path(args.out), args.at)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
