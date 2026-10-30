#!/usr/bin/env python3
"""vibetennis 封面：3:4 高清海报 + 成片开头的 16:9 封面帧。

- **3:4 海报**走仓库同一套 solo 海报模板（`build_match_reel.resolve_cover_payload`
  → `render_poster` → `tools/versus_poster.py`），台头药丸自动印「网球时差 · vibetennis」，
  品牌图标、钩子字号、留白和别的栏目一模一样。`--scale 2`（默认）出 2160×2880，
  版式不变、像素翻倍（账号所有者 2026-10-30：「缺一张 3:4 的高清封面」）。
- **16:9 封面帧**是成片的第一屏（和赛场之上一样，封面先停 1.2 秒、不配音）：
  背景是同一场景按 1920×1080 原生渲染的那一帧，压暗虚化；3:4 海报居中整张放上去，
  不裁海报上的字。

用法（仓库根目录）：

    PYTHONPATH=src:tools python3 tools/vibetennis/cover.py --slug vibetennis-live-faster-2026 \
        --outdir output/2026-10-30/vibetennis/vibetennis-live-faster-2026
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import CANVAS, COVER_FRAME_NAME, POSTER_NAME, ROOT, load_spec  # noqa: E402


def render_poster_hd(spec: dict, out: Path, scale: int = 2) -> Path:
    import tempfile

    import versus_poster  # noqa: PLC0415
    from build_match_reel import render_poster, resolve_cover_payload  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as work:
        payload, layout = resolve_cover_payload(spec["cover"], Path(work), sources=None,
                                                primary="", spec=spec)
        old = versus_poster.POSTER_SCALE
        versus_poster.POSTER_SCALE = scale
        try:
            render_poster(payload, out, layout)
        finally:
            versus_poster.POSTER_SCALE = old
    return out


def cover_frame(poster: Path, background: Path, out: Path) -> Path:
    from PIL import Image, ImageEnhance, ImageFilter  # noqa: PLC0415

    W, H = CANVAS
    bg = Image.open(background).convert("RGB").resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(18))).enhance(0.45)
    card = Image.open(poster).convert("RGB")
    ch = H - 0          # 海报整张放进来，上下贴边
    cw = round(card.width * ch / card.height)
    card = card.resize((cw, ch), Image.LANCZOS)
    bg.paste(card, ((W - cw) // 2, 0))
    bg.save(out, quality=95)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--scale", type=int, default=2, help="海报像素倍率，2＝2160×2880")
    ap.add_argument("--background", default="",
                    help="16:9 封面帧的背景；默认 portrait.image 旁边的 *-16x9.jpg")
    args = ap.parse_args()
    spec = load_spec(args.slug)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    poster = render_poster_hd(spec, outdir / POSTER_NAME, args.scale)
    portrait = ROOT / spec["cover"]["portrait"]["image"]
    bg = Path(args.background) if args.background else portrait.with_name(
        portrait.stem + "-16x9" + portrait.suffix)
    if not bg.is_file():
        raise SystemExit(f"找不到 16:9 背景帧 {bg}")
    frame = cover_frame(poster, bg, outdir / COVER_FRAME_NAME)
    from PIL import Image  # noqa: PLC0415
    print(f"[封面] 海报 {Image.open(poster).size} → {poster}")
    print(f"[封面] 片头封面帧 {Image.open(frame).size} → {frame}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
