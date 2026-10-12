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

2026-10-12 the default lock-up is the corner label used on the Medvedev
24-titles film: top-right placement, a brand-green rail on the RIGHT edge,
every line right-aligned. Row order is the white headline (optional green
highlight), a small muted kicker, a large set-coloured metric when there is
one, then a small muted detail. ``layout="classic"`` keeps the older
left-or-right stack, including ``split_metric``. Shipping a story_text PNG
that is not right-rail and right-aligned fails ``story_corner_label_problems``.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
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
# 比分独立一行时多留一行高度；默认同行画布保持原样。
SPLIT_METRIC_HEIGHT = 440

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

# 整场比分的一盘：`6-3`、`7-6`、`7-6(6)`。**不认别的**——认宽了会把
# 「决胜盘 1-5」这种「这一刻的局分」也当成整场比分去按盘上色，而那一档
# 没有「赢没赢」可言。
_SET_TOKEN = re.compile(r"^(\d+)-(\d+)(?:\((\d+)\))?$")
#: 按盘画时两盘之间的间隔（整场比分走 advance 宽度，不走墨迹框）。
_SET_GAP = 18


@dataclass(frozen=True)
class SetScore:
    """一盘的结构化比分。颜色只从这里算，不接受手写的绿/白标记。

    ``games`` 是屏幕上从左到右的两个局数。``featured`` 指出这一屏的主角是
    左边还是右边：只有主角赢下的那一盘涂品牌黄绿，丢掉的盘留白。抢七括号
    里的小分只参与写成 ``7-6(5)``，不参与上色，也不能拿来把输盘涂绿。
    """

    games: tuple[int, int]
    featured: str = "left"
    tiebreak: int | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.games, tuple) or len(self.games) != 2
                or any(type(n) is not int for n in self.games)):
            raise TypeError("games 必须是两个整数，不能附带颜色标记")
        if any(n < 0 for n in self.games):
            raise ValueError("局数不能是负的")
        if self.featured not in {"left", "right"}:
            raise ValueError("featured 只能是 left 或 right")
        if self.tiebreak is not None and type(self.tiebreak) is not int:
            raise TypeError("抢七小分必须是整数")
        if self.tiebreak is not None and self.tiebreak < 0:
            raise ValueError("抢七小分不能是负的")

    @property
    def won(self) -> bool:
        left, right = self.games
        mine, theirs = (left, right) if self.featured == "left" else (right, left)
        return mine > theirs

    def token(self) -> str:
        left, right = self.games
        text = f"{left}-{right}"
        if self.tiebreak is not None:
            text += f"({self.tiebreak})"
        return text


def score_line(sets: Sequence[SetScore]) -> tuple[str, list[bool]]:
    """结构化盘分 → （屏幕上的比分串，每一盘主角是否赢了）。

    赢没赢是算出来的。调用方不能另传一份颜色，字符串里也不认 ``*`` / 标签。
    """
    if isinstance(sets, (str, bytes)) or not sets:
        raise SystemExit("sets 要的是一组 SetScore，不能是手写标记或空表")
    tokens: list[str] = []
    wins: list[bool] = []
    for item in sets:
        if not isinstance(item, SetScore):
            raise SystemExit("sets 的每一盘必须是 SetScore，不能手写哪一盘涂绿")
        tokens.append(item.token())
        wins.append(item.won)
    return " ".join(tokens), wins


def set_score_wins(metric: str) -> list[bool] | None:
    """`4-6 6-3 6-4` → `[False, True, True]`；不是纯整场比分串就返回 None。

    只在**没有** ``sets`` 时走这条。它把左边那个数当成主角的局数——旧合同
    的 metric 就是这么写的。新的角标把盘分交给 ``SetScore``，主角可以在
    右边，颜色跟着结构化数据走，不跟着「左边更大」。

    ⚠️ 认得窄是故意的：`决胜盘 1-5 赛点` 这种「画面上这一刻的局分」必须
    落回老路径（整块一个强调色），按盘上色对它没有意义。
    """
    tokens = metric.split()
    if not tokens:
        return None
    wins: list[bool] = []
    for token in tokens:
        matched = _SET_TOKEN.match(token)
        if not matched:
            return None
        wins.append(int(matched.group(1)) > int(matched.group(2)))
    return wins


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


def _validate_highlight(highlight: str) -> str:
    """绿字后缀：主标题里这一屏要记住的那一个词。空字符串表示整行暖白。"""
    highlight = highlight.strip()
    if not highlight:
        return ""
    if "\n" in highlight:
        raise SystemExit("highlight 只能一行；屏幕信息不是第二套字幕")
    if "｜" in highlight or "|" in highlight:
        raise SystemExit("highlight 不要用竖线拼字段；请拆到 metric/detail")
    if display_units(highlight) > 12:
        raise SystemExit(
            f"highlight 太长（{display_units(highlight):.1f}>12）："
            "绿字只留这一屏要记住的那一个词")
    return highlight


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


def _set_line(metric: str, set_wins: list[bool] | None) -> bool:
    """这一行是不是按盘画的整场比分。结构化盘分优先于从字符串猜。"""
    return set_wins is not None or set_score_wins(metric) is not None


def _metric_width(draw: ImageDraw.ImageDraw, metric: str, size: int,
                  *, stroke: int, set_wins: list[bool] | None = None) -> int:
    cjk, score = _metric_fonts(size)
    if _set_line(metric, set_wins):
        # 整场比分按盘画，盘之间要真的留出间隔——所以量的是 **advance 宽度**
        # （`textlength`）不是墨迹框（`textbbox`）：空格的墨迹框宽度是 0，
        # 拿墨迹框摞下去，三盘会挤成一串。
        _score = _font(SCORE, int(round(size * 1.2)))
        tokens = metric.split()
        total = sum(int(round(draw.textlength(t, font=_score))) for t in tokens)
        return total + _SET_GAP * (len(tokens) - 1)
    total = 0
    for chunk, is_score in metric_runs(metric):
        f = score if is_score else cjk
        box = draw.textbbox((0, 0), chunk, font=f, stroke_width=stroke, anchor="ls")
        total += box[2] - box[0]
    return total


def _fit_metric_size(draw: ImageDraw.ImageDraw, metric: str, preferred: int,
                     minimum: int, max_width: int, *, stroke: int,
                     set_wins: list[bool] | None = None) -> int:
    for size in range(preferred, minimum - 1, -2):
        if _metric_width(draw, metric, size, stroke=stroke, set_wins=set_wins) <= max_width:
            return size
    return minimum


#: 描边宽度：只保边，不当底板。
_STROKE_HEAD, _STROKE_SMALL = 2, 1
#: 软阴影的模糊半径（整层一次模糊）。
_SHADOW_BLUR = 7


def _render_corner(kicker: str, headline: str, detail: str, out: Path, *,
                   metric: str, align: str, highlight: str,
                   set_wins: list[bool] | None = None) -> Path:
    """右轨、右对齐、四行以内：主标题、小坐标、大比分、小说明。

    字号按成片 0.54 倍缩小后对齐梅德韦杰夫 24 冠那张贴图：主标题约 32px、
    日期约 17px、比分约 36px。画布仍是 1200×340，和没有 metric 的旧卡一样高，
    右上角贴上去不会比旧贴图更高。
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    height = HEIGHT
    image = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    rail_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rail_box = ((20, 34, 34, height - 34) if align == "left"
                else (WIDTH - 34, 34, WIDTH - 20, height - 34))
    ImageDraw.Draw(rail_layer).rounded_rectangle(rail_box, radius=7,
                                                 fill=BRAND_GREEN)
    image.alpha_composite(rail_layer.filter(ImageFilter.GaussianBlur(10)))
    image.alpha_composite(rail_layer)

    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    probe = ImageDraw.Draw(Image.new("RGBA", image.size, (0, 0, 0, 0)))
    x = 66
    lane = WIDTH - x - 28
    head_text = f"{headline} · {highlight}" if highlight else headline
    head_font = _fit_font(BOLD, 58, 40, head_text, lane, stroke=_STROKE_HEAD)
    kicker_font = _fit_font(REGULAR, 32, 24, kicker, lane, stroke=_STROKE_SMALL)
    detail_font = _fit_font(REGULAR, 46, 32, detail, lane, stroke=_STROKE_SMALL)
    metric_size = 0
    score_font = None
    if metric:
        metric_size = _fit_metric_size(probe, metric, 56, 44, lane, stroke=_STROKE_SMALL,
                                       set_wins=set_wins)
        score_font = _metric_fonts(metric_size)[1]

    def block_h(text: str, font: ImageFont.FreeTypeFont, stroke: int) -> int:
        box = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
        return box[3] - box[1]

    row_heights = [
        block_h(head_text, head_font, _STROKE_HEAD),
        block_h(kicker, kicker_font, _STROKE_SMALL),
    ]
    if metric and score_font is not None:
        sample = metric.split()[0] if _set_line(metric, set_wins) else metric[:1] or "0"
        row_heights.append(block_h(sample, score_font, _STROKE_SMALL))
    row_heights.append(block_h(detail, detail_font, _STROKE_SMALL))
    gaps = len(row_heights) - 1
    inner_top, inner_bot = 36, height - 36
    spare = inner_bot - inner_top - sum(row_heights)
    gap = max(8, min(16, spare // gaps)) if spare > 0 and gaps else 4
    used = sum(row_heights) + gap * gaps
    y = inner_top + max(0, (inner_bot - inner_top - used) // 2)

    right_rows: list[tuple[Image.Image, Image.Image]] = []

    def row_canvas():
        if align == "left":
            return ImageDraw.Draw(text_layer), shadow
        row = Image.new("RGBA", image.size, (0, 0, 0, 0))
        row_shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        right_rows.append((row, row_shadow))
        return ImageDraw.Draw(row), row_shadow

    head_draw, head_shadow = row_canvas()
    _draw_text(head_draw, (x, y), headline, font=head_font, fill=WHITE,
               stroke=_STROKE_HEAD, shadow_layer=head_shadow)
    if highlight:
        advance = round(head_draw.textlength(headline, font=head_font))
        sep = " · "
        sep_x = x + advance
        _draw_text(head_draw, (sep_x, y), sep, font=head_font, fill=WHITE,
                   stroke=_STROKE_HEAD, shadow_layer=head_shadow)
        sep_w = round(head_draw.textlength(sep, font=head_font))
        _draw_text(head_draw, (sep_x + sep_w, y), highlight, font=head_font,
                   fill=BRAND_GREEN, stroke=_STROKE_HEAD, shadow_layer=head_shadow)
    y += row_heights[0] + gap

    kick_draw, kick_shadow = row_canvas()
    _draw_text(kick_draw, (x, y), kicker, font=kicker_font, fill=MUTED,
               stroke=_STROKE_SMALL, shadow_layer=kick_shadow)
    y += row_heights[1] + gap

    if metric:
        metric_draw, metric_shadow = row_canvas()
        cjk, score = _metric_fonts(metric_size)
        wins = set_wins if set_wins is not None else set_score_wins(metric)
        if wins is not None:
            mx = x
            for token, won in zip(metric.split(), wins):
                _draw_text(metric_draw, (mx, y), token, font=score,
                           fill=BRAND_GREEN if won else WHITE,
                           stroke=_STROKE_SMALL, anchor="la",
                           shadow_layer=metric_shadow)
                mx += round(metric_draw.textlength(token, font=score)) + _SET_GAP
        else:
            mx = x
            for chunk, is_score in metric_runs(metric):
                font = score if is_score else cjk
                _draw_text(metric_draw, (mx, y), chunk, font=font, fill=BRAND_GREEN,
                           stroke=_STROKE_SMALL, anchor="la",
                           shadow_layer=metric_shadow)
                mx = metric_draw.textbbox(
                    (mx, y), chunk, font=font, stroke_width=_STROKE_SMALL, anchor="la")[2]
        y += row_heights[2] + gap

    detail_draw, detail_shadow = row_canvas()
    _draw_text(detail_draw, (x, y), detail, font=detail_font, fill=MUTED,
               stroke=_STROKE_SMALL, shadow_layer=detail_shadow)

    if align == "right":
        for row, row_shadow in right_rows:
            bounds = row.getbbox()
            if bounds:
                # 每行实际墨迹右缘统一为 1134；右轨左缘 1166，留 32px。
                dx = WIDTH - x - bounds[2]
                text_layer.alpha_composite(row, (dx, 0))
                shadow.alpha_composite(row_shadow, (dx, 0))

    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(_SHADOW_BLUR)))
    image.alpha_composite(text_layer)
    image.save(out)
    return out


def render(kicker: str, headline: str, detail: str, out: Path, *,
           metric: str = "", variant: str = "timeline", align: str = "right",
           split_metric: bool = False, layout: str = "corner",
           highlight: str = "", sets: Sequence[SetScore] | None = None) -> Path:
    set_wins: list[bool] | None = None
    if sets is not None:
        formatted, set_wins = score_line(sets)
        if metric.strip() and metric.strip() != formatted:
            raise SystemExit(
                f"metric「{metric.strip()}」和结构化盘分「{formatted}」不一致；"
                "颜色只从 SetScore 算，不要另写一串或手写绿白")
        metric = formatted
    kicker, headline, detail, metric = _validate(
        kicker, headline, detail, metric, variant)
    highlight = _validate_highlight(highlight)
    if align not in {"left", "right"}:
        raise SystemExit("align 只能是 left 或 right")
    if layout not in {"corner", "classic"}:
        raise SystemExit("layout 只能是 corner 或 classic")
    if split_metric and not metric:
        raise SystemExit("split_metric 必须填写 metric，比分才能独立成行")
    # split_metric 是旧四行合同的显式开关。默认 corner 不能把它的字号和行序换掉。
    if split_metric:
        layout = "classic"
    if layout == "corner":
        return _render_corner(kicker, headline, detail, out, metric=metric,
                              align=align, highlight=highlight, set_wins=set_wins)

    out.parent.mkdir(parents=True, exist_ok=True)
    height = SPLIT_METRIC_HEIGHT if split_metric else HEIGHT
    image = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))

    # 短轨只有一个颜色（品牌绿）——原来蓝黄两截是两个强调色，和一屏一个强调色
    # 那条规矩打架，也和封面/章节卡的绿不是一家。轨下垫一层它自己的软光。
    rail_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rail_box = ((20, 34, 34, height - 34) if align == "left"
                else (WIDTH - 34, 34, WIDTH - 20, height - 34))
    ImageDraw.Draw(rail_layer).rounded_rectangle(rail_box, radius=7,
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
        # 独立行按原60px上限绘制，不缩字去挤；默认同行继续沿用旧字号预算。
        metric_size = _fit_metric_size(draw, metric, 60, 60 if split_metric else 44,
                                      WIDTH - x - 28 if split_metric else 430,
                                      stroke=_STROKE_SMALL, set_wins=set_wins)
        metric_width = _metric_width(draw, metric, metric_size, stroke=_STROKE_SMALL,
                                     set_wins=set_wins)
        if split_metric and metric_width > WIDTH - x - 28:
            raise SystemExit("metric 独立行仍放不下；请缩短文字，不缩小比分字号")
    # 主标题一律得意黑（和封面钩子、章节卡同一副脸）；变体只改字号。
    headline_size = {"stat": 134, "chapter": 126}.get(variant, 122)
    headline_room = WIDTH - x - 28 - ((metric_width + 36) if metric and not split_metric else 0)
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
    detail_font = _fit_font(REGULAR, 50, 40, detail, WIDTH - x - 28, stroke=_STROKE_SMALL)

    # **绿色只给「这一屏最该被记住的那一样」。** 有 metric 时那一样在 metric 上
    # （整场比分＝赢下的那几盘，其余＝那个硬数据），kicker 退成白色——它是坐标，
    # 不是记忆点，和 metric 一起涂绿就是一屏两个强调色。没有 metric 时绿退回
    # 给 kicker，免得整张卡除了短轨一点强调都没有。
    kicker_fill = WHITE if metric else BRAND_GREEN
    # 右对齐只移动每一行完整的字形层；默认主标题与 metric 同一行，分行则各自对齐。
    # 不翻转图片或文字，也不改变默认左对齐的绘制/阴影路径。
    right_rows: list[tuple[Image.Image, Image.Image]] = []
    def row_canvas():
        if align == "left":
            return draw, shadow
        row = Image.new("RGBA", image.size, (0, 0, 0, 0))
        row_shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        right_rows.append((row, row_shadow))
        return ImageDraw.Draw(row), row_shadow

    kicker_draw, kicker_shadow = row_canvas()
    _draw_text(kicker_draw, (x, 30), kicker, font=kicker_font, fill=kicker_fill,
               stroke=_STROKE_SMALL, shadow_layer=kicker_shadow)
    head_draw, head_shadow = row_canvas()
    _draw_text(head_draw, (x, 86), headline, font=headline_font, fill=WHITE,
               stroke=_STROKE_HEAD, shadow_layer=head_shadow)
    if metric:
        ascent, _descent = headline_font.getmetrics()
        baseline = 300 if split_metric else 86 + ascent
        mx = x if split_metric else head_box[2] + 36
        metric_draw, metric_shadow = row_canvas() if split_metric else (head_draw, head_shadow)
        cjk, score = _metric_fonts(metric_size)
        wins = set_wins if set_wins is not None else set_score_wins(metric)
        if wins is not None:
            # **整场比分按盘上色**：主角赢下的那几盘给品牌黄绿，丢掉的盘白色。
            # 有 ``sets`` 时赢没赢从 SetScore 算（主角可以在右边）；只有
            # metric 字符串时，左边那个数就是主角。不认手写的颜色标记。
            for token, won in zip(metric.split(), wins):
                _draw_text(metric_draw, (mx, baseline), token, font=score,
                           fill=BRAND_GREEN if won else WHITE,
                           stroke=_STROKE_SMALL, anchor="ls", shadow_layer=metric_shadow)
                mx += int(round(draw.textlength(token, font=score))) + _SET_GAP
        else:
            # 数字串和汉字共用一条基线（anchor="ls"），两种字体才对得齐。
            for chunk, is_score in metric_runs(metric):
                f = score if is_score else cjk
                _draw_text(metric_draw, (mx, baseline), chunk, font=f, fill=BRAND_GREEN,
                           stroke=_STROKE_SMALL, anchor="ls", shadow_layer=metric_shadow)
                mx = draw.textbbox((mx, baseline), chunk, font=f,
                                   stroke_width=_STROKE_SMALL, anchor="ls")[2]
    # 证据行直接对齐主标题的左缘，**不再垫一截绿色短横线**（账号所有者
    # 2026-09-11 给的参考样式里没有它）：短轨已经把这一块的左缘立住了，
    # 再加一截同色短横就是第二个绿元素，而绿现在有明确的语义（赢下的盘）。
    detail_draw, detail_shadow = row_canvas()
    _draw_text(detail_draw, (x, 340 if split_metric else 246), detail, font=detail_font, fill=MUTED,
               stroke=_STROKE_SMALL, shadow_layer=detail_shadow)

    if align == "right":
        for row, row_shadow in right_rows:
            bounds = row.getbbox()
            if bounds:
                # 每行实际墨迹右缘统一为1134；右轨左缘1166，留32px呼吸。
                dx = WIDTH - x - bounds[2]
                text_layer.alpha_composite(row, (dx, 0))
                shadow.alpha_composite(row_shadow, (dx, 0))

    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(_SHADOW_BLUR)))
    image.alpha_composite(text_layer)
    image.save(out)
    return out


_LEGACY_CORNER_LABEL = REPO / "data" / "legacy_corner_label.json"


def legacy_corner_label_slugs() -> frozenset[str]:
    """已发的左轨贴图。只许减不许加，判据在 tests/test_corner_label_style.py。"""
    if not _LEGACY_CORNER_LABEL.is_file():
        return frozenset()
    data = json.loads(_LEGACY_CORNER_LABEL.read_text(encoding="utf-8"))
    return frozenset(str(slug) for slug in (data.get("slugs") or []))


def _green_count(image: Image.Image) -> int:
    raw = image.tobytes()
    count = 0
    for offset in range(0, len(raw), 4):
        red, green, blue, alpha = raw[offset:offset + 4]
        if (alpha > 180 and green > 180 and green > red > blue
                and (green - blue) > 70):
            count += 1
    return count


def png_corner_label_problem(path: Path) -> str | None:
    """右缘品牌绿短轨，且文字右缘收在右轨左侧。对得上返回 None。

    只认几何，不认行序：已经用 ``--align right`` 渲过的旧四行卡也能过。
    左轨、或者字还从左边起排的，过不了。
    """
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    width, height = rgba.size
    if width < 200 or height < 80:
        return f"{path.name} 不是贴图画布"

    def sx(value: int) -> int:
        return max(0, min(width, round(value * width / WIDTH)))

    left = rgba.crop((sx(18), 30, sx(40), max(31, height - 30)))
    right = rgba.crop((sx(WIDTH - 40), 30, sx(WIDTH - 16), max(31, height - 30)))
    left_n = _green_count(left)
    right_n = _green_count(right)
    if right_n < 200:
        return f"{path.name} 右缘没有品牌绿短轨（绿像素 {right_n}）"
    if left_n > max(80, right_n * 0.25):
        return f"{path.name} 左缘还有一条短轨（左 {left_n} / 右 {right_n}）"
    alpha = rgba.getchannel("A").point(lambda a: 255 if a >= 170 else 0)
    text = alpha.crop((sx(48), 0, sx(WIDTH - 48), height))
    box = text.getbbox()
    if not box:
        return f"{path.name} 没有文字墨迹"
    ink_right = sx(48) + box[2]
    target = width - round(66 * width / WIDTH)
    slack = round(28 * width / WIDTH)
    if abs(ink_right - target) > slack:
        return (f"{path.name} 文字没有右对齐"
                f"（墨迹右缘 {ink_right}，应收在 {target} 附近）")
    return None


def story_corner_label_problems(spec: dict, *, honor_legacy: bool = True) -> list[str]:
    """每张 story_text 都要落在右上角，并且 PNG 是右轨右对齐。

    没有贴图的片子不报。已发左轨片挂在 ``data/legacy_corner_label.json``，
    ``honor_legacy=False`` 用来证明那张表里的片子确实还不合格式。
    """
    slug = str(spec.get("slug") or "")
    if honor_legacy and slug in legacy_corner_label_slugs():
        return []
    problems: list[str] = []
    for index, raw in enumerate(spec.get("segments") or []):
        inset = (raw or {}).get("inset") or {}
        if str(inset.get("kind") or "") != "story_text":
            continue
        where = f"第 {index + 1} 段"
        if inset.get("corner") != "tr":
            problems.append(
                f"{where} story_text 必须写 corner=tr（右上角），"
                f"拿到的是 {inset.get('corner')!r}")
        image = str(inset.get("image") or "")
        if not image or not Path(image).is_file():
            continue
        message = png_corner_label_problem(Path(image))
        if message:
            problems.append(f"{where} {message}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kicker", required=True)
    ap.add_argument("--headline", required=True)
    ap.add_argument("--highlight", default="",
                    help="主标题右侧的品牌绿后缀，例如「警告」")
    ap.add_argument("--metric", default="")
    ap.add_argument("--detail", required=True)
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="timeline")
    ap.add_argument("--layout", choices=["corner", "classic"], default="corner")
    ap.add_argument("--align", choices=["left", "right"], default="right")
    ap.add_argument("--split-metric", action="store_true",
                    help="走 classic 四行：比分独立成第三行；不是默认角标")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = render(args.kicker, args.headline, args.detail, Path(args.out),
                 metric=args.metric, variant=args.variant, align=args.align,
                 split_metric=args.split_metric, layout=args.layout,
                 highlight=args.highlight)
    height = SPLIT_METRIC_HEIGHT if args.split_metric else HEIGHT
    print(f"已渲 {out}（{WIDTH}×{height}，大字版 RGBA，无大底板）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
