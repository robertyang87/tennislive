#!/usr/bin/env python3
"""Render a compact, consistent information band for story-led match footage.

Unlike a beat card, this component is not a floating block of display text.  It
has a fixed grid and a translucent backing so the viewer can read one hierarchy
at a glance without competing with the subtitles or occupying the whole rally.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


REPO = Path(__file__).resolve().parents[1]
BOLD = REPO / "assets" / "fonts" / "NotoSansSC-Bold-sub.ttf"
REGULAR = REPO / "assets" / "fonts" / "NotoSansSC-Regular-sub.ttf"
WIDTH, HEIGHT = 864, 232


def render(kicker: str, headline: str, detail: str, out: Path) -> Path:
    if not kicker.strip() or not headline.strip() or not detail.strip():
        raise SystemExit("kicker、headline、detail 都必须填写")

    out.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # One restrained panel, one accent colour, three stable type levels.
    draw.rounded_rectangle((2, 2, WIDTH - 2, HEIGHT - 2), radius=30,
                           fill=(6, 20, 15, 222),
                           outline=(184, 233, 134, 118), width=2)
    draw.rounded_rectangle((0, 22, 10, HEIGHT - 22), radius=5,
                           fill=(184, 233, 134, 255))

    kicker_font = ImageFont.truetype(str(BOLD), 28)
    headline_font = ImageFont.truetype(str(BOLD), 58)
    detail_font = ImageFont.truetype(str(REGULAR), 30)
    x = 48
    draw.text((x, 24), kicker.strip(), font=kicker_font,
              fill=(184, 233, 134, 255))
    draw.text((x, 65), headline.strip(), font=headline_font,
              fill=(247, 250, 248, 255), stroke_width=1,
              stroke_fill=(0, 0, 0, 120))
    draw.text((x, 151), detail.strip(), font=detail_font,
              fill=(205, 219, 211, 255))
    image.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kicker", required=True)
    ap.add_argument("--headline", required=True)
    ap.add_argument("--detail", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = render(args.kicker, args.headline, args.detail, Path(args.out))
    print(f"已渲 {out}（{WIDTH}×{HEIGHT}，RGBA）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
