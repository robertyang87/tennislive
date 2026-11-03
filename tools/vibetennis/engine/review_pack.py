#!/usr/bin/env python3
"""渲前审片包：整片渲之前，把每个镜头渲几张静帧拼成总览图，先给所有者看。

来路（EP05 场地快慢，73 个提交、推了三版）：法网看台缺一块、温网顶棚有孔、地球固定高度、
澳网顶棚没收开……全是整段渲完（15~55 分钟一轮）才被所有者看出来的；而这些问题
**一张静帧几秒钟就看得出**。所以顺序改成：

    plan.py 排好时间轴 → review_pack.py 出总览图 → 发给所有者 → 改到他点头 → render3d.sh 整片渲

取帧规则（按 r3d/timeline.json）：每一节取开头、中间、结尾前各一张；每句字幕取两张——开口后 1.5 秒
（字幕要指的那个东西该在画面里了）和这一句管的那段中间。相距不到 0.5 秒的去重。

    python3 tools/vibetennis/engine/review_pack.py tools/vibetennis/episodes/<slug> [--lang zh] [--only venues,q]

产物：<集>/review/<语言>/s_*.jpg 和 <集>/review/review_<语言>_N.jpg（每张 4×4 格，格上标节名与秒数）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent


def pick_times(timeline: dict, only: set[str] | None) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for sec in timeline["sections"]:
        if only and sec["name"] not in only:
            continue
        t0, t1 = float(sec["t0"]), float(sec["t1"])
        for t in (t0 + 0.4, (t0 + t1) / 2, t1 - 0.4):
            out.append((round(t, 2), sec["name"]))
        lines = sorted((float(at), key) for key, at in (sec.get("lines") or {}).items())
        for i, (at, key) in enumerate(lines):
            nxt = lines[i + 1][0] if i + 1 < len(lines) else t1
            # 每句两张：开口后 1.5 秒（字幕要指的东西该出来了）和这一句管的那段中间
            for t in (min(at + 1.5, nxt - 0.2), (at + nxt) / 2 + 0.75):
                out.append((round(min(t, t1 - 0.2), 2), f"{sec['name']}·{key}"))
    out.sort()
    dedup: list[tuple[float, str]] = []
    for t, lab in out:
        if dedup and t - dedup[-1][0] < 0.5:
            continue
        dedup.append((t, lab))
    return dedup


def montage(shots: list[tuple[Path, str]], out_prefix: Path, cols: int = 4, rows: int = 4) -> list[Path]:
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    tw, th = 480, 270
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 22)
    except OSError:
        font = ImageFont.load_default()
    pages, per = [], cols * rows
    for pi in range(0, len(shots), per):
        sheet = Image.new("RGB", (cols * tw, rows * th), (8, 10, 18))
        d = ImageDraw.Draw(sheet)
        for k, (img, lab) in enumerate(shots[pi:pi + per]):
            x, y = (k % cols) * tw, (k // cols) * th
            sheet.paste(Image.open(img).convert("RGB").resize((tw, th)), (x, y))
            d.rectangle([x, y, x + tw, y + 30], fill=(0, 0, 0))
            d.text((x + 8, y + 3), lab, fill=(255, 230, 120), font=font)
        p = out_prefix.with_name(f"{out_prefix.name}_{pi // per + 1}.jpg")
        sheet.save(p, quality=85)
        pages.append(p)
    return pages


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", type=Path)
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--port", default="8766")
    ap.add_argument("--only", default="", help="只看这几节（逗号分隔的 section 名）")
    args = ap.parse_args()
    ep = args.episode.resolve()
    timeline = json.loads((ep / "r3d" / "timeline.json").read_text(encoding="utf-8"))
    only = {s for s in args.only.split(",") if s} or None
    times = pick_times(timeline, only)
    if not times:
        print("一张都没挑出来——--only 的节名对不上 timeline.json", file=sys.stderr)
        return 1
    subprocess.run(["bash", str(ENGINE / "serve.sh"), str(ep), args.port], check=True)
    out = ep / "review" / args.lang
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("s_*.jpg"):  # 上一轮的不许混进这一轮的总览
        old.unlink()
    env = {**__import__("os").environ, "VT_LANG": args.lang}
    subprocess.run(["node", str(ENGINE / "still.js"), args.port, str(out), *[f"{t}" for t, _ in times]],
                   check=True, env=env)
    shots = []
    for t, lab in times:
        p = out / f"s_{f'{t:.2f}'.rjust(7, '0')}.jpg"
        if not p.is_file():
            print(f"缺帧 {p.name}", file=sys.stderr)
            return 1
        shots.append((p, f"{t:6.2f}s  {lab}"))
    pages = montage(shots, ep / "review" / f"review_{args.lang}")
    print(f"{len(shots)} 张静帧 → " + "、".join(str(p) for p in pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
