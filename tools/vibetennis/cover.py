#!/usr/bin/env python3
"""vibetennis 封面：一张单独的 3:4 高清海报（不进视频）。

走仓库同一套 solo 海报模板（`build_match_reel.resolve_cover_payload` → `render_poster`
→ `tools/versus_poster.py`），台头药丸自动印「网球时差 · vibetennis」，品牌图标、钩子字号、
留白和别的栏目一模一样。`--scale 2`（默认）出 2160×2880，版式不变、像素翻倍
（账号所有者 2026-10-30：「缺一张 3:4 的高清封面」）。

⚠️ 所有者同日更正：**封面不放进视频开头、不合进视频**。这张图只用作推送第一屏
（`poster.jpg`）和各平台上传时的封面，成片保持母片原样。

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

from common import POSTER_NAME, load_spec  # noqa: E402


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--scale", type=int, default=2, help="海报像素倍率，2＝2160×2880")
    args = ap.parse_args()
    spec = load_spec(args.slug)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    poster = render_poster_hd(spec, outdir / POSTER_NAME, args.scale)
    from PIL import Image  # noqa: PLC0415
    print(f"[封面] 3:4 高清海报 {Image.open(poster).size} → {poster}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
