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

# 0.60 * 1080 = 648px in the finished reel. 1200px therefore gives a crisp
# source while leaving enough room for the longest opponent name.
WIDTH, HEIGHT = 1200, 340

# Court blue + tennis-ball yellow is a more recognisable tennis palette than
# the first muted sage treatment.  The two chromatic colours have fixed jobs:
# blue introduces the label, yellow marks the fact worth remembering.  They
# never compete inside the same text level.
COURT_BLUE = (91, 218, 255, 255)
TENNIS_YELLOW = (225, 255, 74, 255)
WHITE = (255, 253, 244, 255)
MUTED = (218, 231, 235, 255)
INK = (4, 18, 36, 242)
SHADOW = (0, 0, 0, 165)
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


def _fit_font(path: Path, preferred: int, minimum: int, text: str,
              max_width: int, *, stroke: int = 0) -> ImageFont.FreeTypeFont:
    """Keep a one-line field inside its lane without silently wrapping it."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1), 0))
    for size in range(preferred, minimum - 1, -2):
        font = _font(path, size)
        box = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if box[2] - box[0] <= max_width:
            return font
    return _font(path, minimum)


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
    rail.rounded_rectangle((18, 30, 37, 312), radius=9,
                           fill=TENNIS_YELLOW)
    rail.rounded_rectangle((18, 30, 37, 112), radius=9, fill=COURT_BLUE)
    glow = rail_layer.filter(ImageFilter.GaussianBlur(11))
    image.alpha_composite(glow)
    image.alpha_composite(rail_layer)
    draw = ImageDraw.Draw(image)

    x = 70
    kicker_font = _fit_font(BOLD, 56, 48, kicker, WIDTH - x - 28,
                            stroke=3)
    metric_font = _fit_font(DISPLAY, 76, 66, metric, 400, stroke=4)
    metric_width = 0
    if metric:
        metric_box = draw.textbbox((0, 0), metric, font=metric_font,
                                   stroke_width=4)
        metric_width = metric_box[2] - metric_box[0]
    headline_size = 144 if variant == "stat" else (132 if variant == "chapter"
                                                    else 130)
    headline_path = DISPLAY if variant in {"stat", "chapter"} else BOLD
    headline_room = WIDTH - x - 28
    if metric:
        headline_room -= metric_width + 42
    headline_font = _fit_font(headline_path, headline_size, 104, headline,
                              headline_room, stroke=6)
    detail_font = _fit_font(REGULAR, 60, 50, detail, WIDTH - x - 112,
                            stroke=4)

    _draw_text(draw, (x, 14), kicker, font=kicker_font,
               fill=COURT_BLUE, stroke=3)
    headline_y = 77
    headline_fill = TENNIS_YELLOW if variant == "stat" else WHITE
    _draw_text(draw, (x, headline_y), headline, font=headline_font,
               fill=headline_fill, stroke=6)

    if metric:
        box = draw.textbbox((x, headline_y), headline, font=headline_font,
                            stroke_width=6)
        metric_x = box[2] + 34
        _draw_text(draw, (metric_x, headline_y + 31), metric,
                   font=metric_font, fill=TENNIS_YELLOW, stroke=4)

    # The short hairline connects the evidence line to the headline without
    # enclosing either in a UI-looking panel.
    draw.rounded_rectangle((x, 274, x + 72, 281), radius=3,
                           fill=(225, 255, 74, 235))
    draw.rounded_rectangle((x, 274, x + 22, 281), radius=3,
                           fill=(91, 218, 255, 245))
    _draw_text(draw, (x + 94, 246), detail, font=detail_font,
               fill=MUTED, stroke=4)

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
    print(f"已渲 {out}（{WIDTH}×{HEIGHT}，大字版 RGBA，无大底板）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
