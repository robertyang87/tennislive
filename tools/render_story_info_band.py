#!/usr/bin/env python3
"""Render a restrained editorial text lock-up over story-led match footage.

The first version looked like a product UI panel: a large opaque rounded box,
three equally boxed rows, and too much dark mass over the athlete. Story video
needs the opposite hierarchy. This renderer leaves the footage visible and
uses typography, a short accent rail, outline and shadow to provide contrast.

2026-09-05 the palette moved onto the account's own brand system. The second
version had used court blue + tennis yellow — two chromatic accents that
matched nothing else in the film (cover, chapter cards and outro page are all
ink green / brand green / near-white). The account owner asked for the text
stickers to be redesigned to look better; the fix is coherence, not
decoration: **one accent colour** (brand green, the same `#c6f65a` as the
cover scoreboard's won-set digits), near-white for names, a light grey-green
for evidence, ink-green halos. Digits in the score field use the `TL Score`
face so a "1-5" here matches the "1-5" printed on the cover scoreboard.

There are four semantic variants, but they share one grid and one palette:

``timeline``
    An injury/return milestone. The event is the focal point.
``player``
    An opponent identity (or a match-up). Name first, score/rank second.
``stat``
    One hard number such as a ranking or ace count.
``chapter``
    A structural turn such as "three rounds, three gates".

The PNG is intentionally rendered near 2x its final display width. The reel
pipeline scales it down with Lanczos so Chinese strokes stay crisp.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


REPO = Path(__file__).resolve().parents[1]
BOLD = REPO / "assets" / "fonts" / "NotoSansSC-Bold-sub.ttf"
REGULAR = REPO / "assets" / "fonts" / "NotoSansSC-Regular-sub.ttf"
DISPLAY = REPO / "assets" / "fonts" / "SmileySans-Oblique.ttf"
# 比分数字和封面比分板、顶栏是同一支（`tools/build_fonts.py` 的 `TL Score`）：
# 「1-5」在贴图上和在比分板上长得一样，才不像两套系统。它只带 ASCII，
# 所以只有数字串走它，汉字仍走 Noto。
SCORE = REPO / "assets" / "fonts" / "TLScore-Bold.ttf"

# 0.60 * 1080 = 648px in the finished reel. 1200px therefore gives a crisp
# source while leaving enough room for the longest opponent name.
WIDTH, HEIGHT = 1200, 340

# 品牌那套色（`tennislive.video.outro_page` / 封面 / 章节卡同一套）：
# 一屏只留一个强调色。绿只给标签、短轨和硬数据；名字暖白；证据行冷灰白；
# 描边和阴影用墨绿而不是纯黑，压在球场蓝上不发脏。
BRAND_GREEN = (198, 246, 90, 255)     # #c6f65a
WHITE = (244, 251, 247, 255)          # #f4fbf7
MUTED = (213, 226, 219, 255)          # #d5e2db，和视频顶栏第二行同一档（别再往暗调）
INK = (4, 18, 13, 242)                # #04120d
SHADOW = (0, 0, 0, 165)
VARIANTS = {"timeline", "player", "stat", "chapter"}

# 比分/数字串：数字开头、数字结尾，中间允许连字符/冒号/点/斜杠（1-5、40-30、
# 6-3、13:11、7.5）。只有这种串换成 TL Score，「决胜盘」「赛点」照旧 Noto。
_SCORE_RUN = re.compile(r"\d[\d\-–:./]*\d|\d")


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
               stroke: int, anchor: str = "la",
               shadow_layer: Image.Image | None = None) -> None:
    """一行字 = 软投影（另一层，最后整体高斯模糊）＋ 细描边 ＋ 字。

    2026-09-05 之前是 6px 硬描边 ＋ 硬偏移阴影——压在球场上像贴纸。现在描边只有
    1~2px（保住浅色字压在白球衣/亮天上的边），主要靠模糊过的软阴影托住可读性。
    """
    x, y = xy
    if shadow_layer is not None:
        ImageDraw.Draw(shadow_layer).text(
            (x + 2, y + 5), text, font=font, fill=SHADOW, anchor=anchor,
            stroke_width=stroke + 3, stroke_fill=SHADOW)
    draw.text((x, y), text, font=font, fill=fill,
              stroke_width=stroke, stroke_fill=INK, anchor=anchor)


def metric_runs(metric: str) -> list[tuple[str, bool]]:
    """把 metric 切成 (片段, 是不是数字串)：数字串走 TL Score，其余走 Noto。"""
    runs: list[tuple[str, bool]] = []
    pos = 0
    for m in _SCORE_RUN.finditer(metric):
        if m.start() > pos:
            runs.append((metric[pos:m.start()], False))
        runs.append((m.group(0), True))
        pos = m.end()
    if pos < len(metric):
        runs.append((metric[pos:], False))
    return runs


def _metric_fonts(size: int) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    # TL Score 的字面比 Noto 同字号略矮，抬 20% 让数字成为这一截的主体
    # （「决胜盘」是标签，「1-5」才是要记住的那个数）。
    return _font(BOLD, size), _font(SCORE, int(round(size * 1.2)))


def _metric_width(draw: ImageDraw.ImageDraw, metric: str, size: int,
                  *, stroke: int) -> int:
    cjk, score = _metric_fonts(size)
    total = 0
    for chunk, is_score in metric_runs(metric):
        f = score if is_score else cjk
        box = draw.textbbox((0, 0), chunk, font=f, stroke_width=stroke, anchor="ls")
        total += box[2] - box[0]
    return total


def _fit_metric_size(draw: ImageDraw.ImageDraw, metric: str, preferred: int,
                     minimum: int, max_width: int, *, stroke: int) -> int:
    for size in range(preferred, minimum - 1, -2):
        if _metric_width(draw, metric, size, stroke=stroke) <= max_width:
            return size
    return minimum


#: 描边宽度：只保边，不当底板。
_STROKE_HEAD, _STROKE_SMALL = 2, 1
#: 软阴影的模糊半径（整层一次模糊）。
_SHADOW_BLUR = 7


def render(kicker: str, headline: str, detail: str, out: Path, *,
           metric: str = "", variant: str = "timeline") -> Path:
    kicker, headline, detail, metric = _validate(
        kicker, headline, detail, metric, variant)

    out.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    # 短轨只有一个颜色（品牌绿）——原来蓝黄两截是两个强调色，和一屏一个强调色
    # 那条规矩打架，也和封面/章节卡的绿不是一家。轨下垫一层它自己的软光。
    rail_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(rail_layer).rounded_rectangle((20, 34, 34, 306), radius=7,
                                                 fill=BRAND_GREEN)
    image.alpha_composite(rail_layer.filter(ImageFilter.GaussianBlur(10)))
    image.alpha_composite(rail_layer)

    # 所有字先画在同一张阴影层上，最后整层模糊一次再垫到字底下——比每个字各
    # 带一个硬偏移的黑影干净得多，压在亮底上也不发脏。
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    x = 66
    kicker_font = _fit_font(BOLD, 44, 36, kicker, WIDTH - x - 28, stroke=_STROKE_SMALL)
    metric_width = metric_size = 0
    if metric:
        metric_size = _fit_metric_size(draw, metric, 60, 44, 430, stroke=_STROKE_SMALL)
        metric_width = _metric_width(draw, metric, metric_size, stroke=_STROKE_SMALL)
    # 主标题一律得意黑（和封面钩子、章节卡同一副脸）；变体只改字号。
    headline_size = {"stat": 134, "chapter": 126}.get(variant, 122)
    headline_room = WIDTH - x - 28 - ((metric_width + 36) if metric else 0)
    headline_font = _fit_font(DISPLAY, headline_size, 92, headline, headline_room,
                              stroke=_STROKE_HEAD)
    head_box = draw.textbbox((x, 86), headline, font=headline_font,
                             stroke_width=_STROKE_HEAD)
    if head_box[2] - x > headline_room:
        # 缩到最小号还装不下：别静默伸出画布右边（第一版「决胜盘 1-5 赛点」就是
        # 这么被切成「赛」的）。metric 短一点，或者把后半句挪进 detail。
        raise SystemExit(
            f"headline「{headline}」加 metric「{metric}」一行装不下"
            f"（缩到 {headline_font.size}px 仍宽 {head_box[2] - x} > {headline_room}）："
            "metric 写短一点，或者把后半句挪进 detail")
    detail_font = _fit_font(REGULAR, 50, 40, detail, WIDTH - x - 104, stroke=_STROKE_SMALL)

    _draw_text(draw, (x, 30), kicker, font=kicker_font, fill=BRAND_GREEN,
               stroke=_STROKE_SMALL, shadow_layer=shadow)
    _draw_text(draw, (x, 86), headline, font=headline_font, fill=WHITE,
               stroke=_STROKE_HEAD, shadow_layer=shadow)
    if metric:
        ascent, _descent = headline_font.getmetrics()
        baseline = 86 + ascent
        mx = head_box[2] + 36
        cjk, score = _metric_fonts(metric_size)
        # 数字串和汉字共用一条基线（anchor="ls"），两种字体才对得齐。
        for chunk, is_score in metric_runs(metric):
            f = score if is_score else cjk
            _draw_text(draw, (mx, baseline), chunk, font=f, fill=BRAND_GREEN,
                       stroke=_STROKE_SMALL, anchor="ls", shadow_layer=shadow)
            mx = draw.textbbox((mx, baseline), chunk, font=f,
                               stroke_width=_STROKE_SMALL, anchor="ls")[2]
    # The short hairline connects the evidence line to the headline without
    # enclosing either in a UI-looking panel.
    draw.rounded_rectangle((x, 271, x + 56, 276), radius=2, fill=BRAND_GREEN)
    _draw_text(draw, (x + 76, 246), detail, font=detail_font, fill=MUTED,
               stroke=_STROKE_SMALL, shadow_layer=shadow)

    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(_SHADOW_BLUR)))
    image.alpha_composite(text_layer)
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
