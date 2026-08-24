#!/usr/bin/env python3
"""Render a restrained editorial text lock-up over story-led match footage.

The first version looked like a product UI panel: a large opaque rounded box,
three equally boxed rows, and too much dark mass over the athlete. Story video
needs the opposite hierarchy. This renderer leaves the footage visible and
uses typography, a short accent rail, outline and shadow to provide contrast.

There are four semantic variants, but they share one grid and one palette:

``timeline``
    An injury/return milestone. The event is the focal point.
``player``
    An opponent identity. Name first, rank/metric second.
``stat``
    One hard number such as a ranking or ace count.
``chapter``
    A structural turn such as "three rounds, three gates".

The PNG is intentionally rendered near 2x its final display width. The reel
pipeline scales it down with Lanczos so Chinese strokes stay crisp.
"""

from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


REPO = Path(__file__).resolve().parents[1]
BOLD = REPO / "assets" / "fonts" / "NotoSansSC-Bold-sub.ttf"
REGULAR = REPO / "assets" / "fonts" / "NotoSansSC-Regular-sub.ttf"
DISPLAY = REPO / "assets" / "fonts" / "SmileySans-Oblique.ttf"

# 0.56 * 1080 = 605px in the finished reel. 1200px therefore gives almost a
# true 2x source while leaving enough room for the longest opponent name.
WIDTH, HEIGHT = 1200, 292
ACCENT = (184, 233, 134, 255)
WHITE = (247, 250, 248, 255)
MUTED = (220, 231, 225, 255)
INK = (5, 14, 11, 238)
SHADOW = (0, 0, 0, 150)
VARIANTS = {"timeline", "player", "stat", "chapter"}


def display_units(text: str) -> float:
    """Approximate how much horizontal room a mixed Chinese/Latin line needs."""
    units = 0.0
    for char in text.strip():
        if char.isspace():
            units += 0.35
        elif unicodedata.east_asian_width(char) in {"W", "F", "A"}:
            units += 1.0
        else:
            units += 0.58
    return units


def _validate(kicker: str, headline: str, detail: str, metric: str,
              variant: str) -> tuple[str, str, str, str]:
    values = tuple(value.strip() for value in (kicker, headline, detail, metric))
    kicker, headline, detail, metric = values
    if not kicker or not headline or not detail:
        raise SystemExit("kicker、headline、detail 都必须填写")
    if variant not in VARIANTS:
        raise SystemExit(f"variant 只能是 {sorted(VARIANTS)}")
    for field, value in (("kicker", kicker), ("headline", headline),
                         ("detail", detail), ("metric", metric)):
        if "\n" in value:
            raise SystemExit(f"{field} 只能一行；屏幕信息不是第二套字幕")
        # The bundled subset font does not contain the full-width pipe. More
        # importantly, pipes encourage writers to cram two fields into one.
        if "｜" in value or "|" in value:
            raise SystemExit(f"{field} 不要用竖线拼字段；请拆到 metric/detail")
    budgets = {"kicker": 18.0, "headline": 10.5,
               "metric": 11.0, "detail": 23.0}
    for field, value in (("kicker", kicker), ("headline", headline),
                         ("metric", metric), ("detail", detail)):
        if value and display_units(value) > budgets[field]:
            raise SystemExit(
                f"{field} 太长（{display_units(value):.1f}>{budgets[field]}）："
                "一屏只留一个记忆点，完整解释交给旁白")
    return kicker, headline, detail, metric


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
               *, font: ImageFont.FreeTypeFont, fill: tuple[int, ...],
               stroke: int) -> None:
    """Draw a soft shadow plus a tight dark halo for variable match footage."""
    x, y = xy
    draw.text((x + 5, y + 7), text, font=font, fill=SHADOW,
              stroke_width=stroke + 2, stroke_fill=(0, 0, 0, 95))
    draw.text((x, y), text, font=font, fill=fill,
              stroke_width=stroke, stroke_fill=INK)


def render(kicker: str, headline: str, detail: str, out: Path, *,
           metric: str = "", variant: str = "timeline") -> Path:
    kicker, headline, detail, metric = _validate(
        kicker, headline, detail, metric, variant)

    out.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    # A separate shadow layer produces a faint editorial "lift" without the
    # heavy rectangular backing the account owner explicitly rejected.
    rail_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rail = ImageDraw.Draw(rail_layer)
    rail.rounded_rectangle((20, 32, 31, 252), radius=6, fill=ACCENT)
    glow = rail_layer.filter(ImageFilter.GaussianBlur(9))
    image.alpha_composite(glow)
    image.alpha_composite(rail_layer)
    draw = ImageDraw.Draw(image)

    x = 62
    kicker_font = _font(BOLD, 35)
    headline_size = 92 if variant == "stat" else 84
    headline_font = _font(DISPLAY if variant in {"stat", "chapter"} else BOLD,
                          headline_size)
    metric_font = _font(DISPLAY, 52)
    detail_font = _font(REGULAR, 40)

    _draw_text(draw, (x, 18), kicker, font=kicker_font,
               fill=ACCENT, stroke=2)
    headline_y = 72
    headline_fill = ACCENT if variant == "stat" else WHITE
    _draw_text(draw, (x, headline_y), headline, font=headline_font,
               fill=headline_fill, stroke=5)

    if metric:
        box = draw.textbbox((x, headline_y), headline, font=headline_font,
                            stroke_width=5)
        metric_x = min(box[2] + 34, WIDTH - 330)
        _draw_text(draw, (metric_x, headline_y + 25), metric,
                   font=metric_font, fill=ACCENT, stroke=3)

    # The short hairline connects the evidence line to the headline without
    # enclosing either in a UI-looking panel.
    draw.rounded_rectangle((x, 218, x + 54, 223), radius=2,
                           fill=(184, 233, 134, 225))
    _draw_text(draw, (x + 72, 198), detail, font=detail_font,
               fill=MUTED, stroke=3)

    image.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kicker", required=True)
    ap.add_argument("--headline", required=True)
    ap.add_argument("--metric", default="")
    ap.add_argument("--detail", required=True)
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="timeline")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = render(args.kicker, args.headline, args.detail, Path(args.out),
                 metric=args.metric, variant=args.variant)
    print(f"已渲 {out}（{WIDTH}×{HEIGHT}，RGBA，无大底板）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
