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

2026-10-21 confirmed V14: original fonts, subtitle-style outline/shadow,
no panel, winner names green and loser names white, shared date/event baseline,
centered vs, won-set digits bold and lost-set digits light. Tiebreak points are
bare small superscripts by the losing game count. Full five-set scores fit by
actual glyph width. Default hold is at most15s, bounded by the associated clip.

The PNG is intentionally rendered near 2x its final display width. The reel
pipeline scales it down with Lanczos so Chinese strokes stay crisp.

2026-10-12 the default lock-up is the corner label used on the Medvedev
24-titles film: top-right placement, a brand-green rail on the RIGHT edge,
every line right-aligned. Row order is the white topic alone (when there
is one), then one line with the date and the event/place (``2026.10.11 · ATP1000 上海``),
then the score, then the people. A label with no topic starts on that
date line. Every text run uses the
same face as the top-left brand title (``SmileySans-Oblique``); score
digits stay on ``TL Score``. ``layout="classic"`` keeps the older
left-or-right stack, including ``split_metric``. Shipping a story_text PNG
that is not right-rail and right-aligned fails ``story_corner_label_problems``.
A new spec must also carry ``inset.label`` with topic, date, place, people,
and either a full-match score or an event; ``story_label_field_problems``
fails ``--dry-run`` when any of those is missing. Already-shipped stickers
that predate the fields sit in ``data/legacy_label_fields.json``.
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
DISPLAY = REPO / "assets" / "fonts" / "SmileySans-Oblique.ttf"
#: 角标上除比分数字以外的每一行，和左上角「网球时差 · 栏目」是同一支。
LABEL_FONT = DISPLAY
# 比分数字和封面比分板、顶栏是同一支（`tools/build_fonts.py` 的 `TL Score`）：
# 「1-5」在贴图上和在比分板上长得一样，才不像两套系统。它只带 ASCII。
# 角标上其余每一行（主题、地点、日期、人物、罚款）走 LABEL_FONT，
# 和左上角「网球时差 · 栏目」是同一个文件。
SCORE = REPO / "assets" / "fonts" / "TLScore-Bold.ttf"
SCORE_LIGHT = REPO / "assets" / "fonts" / "TLScore-Light.ttf"

# 2026-10-21 follow-up: topic97→89; score115→106→98; metadata/people unchanged.
STORY_LABEL_WIDTH = 0.60
STORY_LABEL_PAD = 0.043
STORY_LABEL_MAX_SECONDS = 15.0
CORNER_TOPIC_SIZE, CORNER_META_SIZE, CORNER_SCORE_SIZE = 89, 73, 98
CORNER_PEOPLE_SIZE = 73
CORNER_LANE = 637
CORNER_OUTLINE = (20, 30, 24, 255)
CORNER_STROKE, CORNER_SHADOW_OFFSET = 7, 2
CORNER_GAP, CORNER_SCORE_GAP = 20, 17

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
# 整场决胜抢十单独记号；不能当成普通一盘末尾的上标小分。
_MATCH_DECIDER_TOKEN = re.compile(r"\[(\d+)-(\d+)\]")
#: 按盘画时两盘之间的间隔（整场比分走 advance 宽度，不走墨迹框）。
_SET_GAP = 18


@dataclass(frozen=True)
class _ScoreToken:
    left: str
    right: str
    tiebreak: str | None = None
    match_decider: bool = False


def _parse_set_token(token: str) -> _ScoreToken | None:
    """Ordinary set/tiebreak or a bracketed match decider, never the same notation."""
    matched = _SET_TOKEN.fullmatch(token)
    if matched:
        return _ScoreToken(*matched.groups())
    matched = _MATCH_DECIDER_TOKEN.fullmatch(token)
    if matched:
        return _ScoreToken(*matched.groups(), match_decider=True)
    return None


def _parse_score_tokens(metric: str) -> list[_ScoreToken] | None:
    tokens = metric.split()
    if not tokens:
        return None
    parsed: list[_ScoreToken] = []
    for token in tokens:
        item = _parse_set_token(token)
        if item is None:
            return None
        parsed.append(item)
    return parsed


@dataclass(frozen=True)
class SetScore:
    """一盘的结构化比分。屏幕上的数字从这里来，不接受手写的绿/白标记。

    ``games`` 是从左到右的两个局数。颜色不看主角在哪一侧：每一盘里更大的
    那个局数是品牌黄绿，更小的那个是白，连字符和抢七括号也是白。
    ``featured`` 只说明这一屏在讲谁，不参与上色。
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


def score_line(sets: Sequence[SetScore]) -> str:
    """结构化盘分 → 屏幕上的比分串。颜色另从每个局数的大小算，不在这里。"""
    if isinstance(sets, (str, bytes)) or not sets:
        raise SystemExit("sets 要的是一组 SetScore，不能是手写标记或空表")
    tokens: list[str] = []
    for item in sets:
        if not isinstance(item, SetScore):
            raise SystemExit("sets 的每一盘必须是 SetScore，不能手写哪一个数涂绿")
        tokens.append(item.token())
    return " ".join(tokens)


def set_number_runs(token: str) -> list[tuple[str, bool]] | None:
    """一盘拆成 (片段, 这一截是不是更大的那个局数)。

    `6-4` → 6 黄绿、连字符白、4 白。`2-6` 反过来。`7-6(5)` 里括号连同
    小分整段留白，不因为括号里的数更大就涂绿。平局两个局数都白。
    `[10-6]` 是整场决胜抢十，方括号保持白色，两个分数各自按大小上色。
    不是这些完整比分 token 就返回 None。
    """
    parsed = _parse_set_token(token)
    if parsed is None:
        return None
    left, right = int(parsed.left), int(parsed.right)
    runs = [
        (parsed.left, left > right),
        ("-", False),
        (parsed.right, right > left),
    ]
    if parsed.tiebreak is not None:
        runs.append((f"({parsed.tiebreak})", False))
    if parsed.match_decider:
        runs = [("[", False), *runs, ("]", False)]
    return runs


def score_number_colors(metric: str) -> list[list[tuple[str, bool]]] | None:
    """整场比分拆成每一盘的上色片段。掺了别的字就返回 None，整行退回一个强调色。"""
    tokens = metric.split()
    if not tokens:
        return None
    parsed: list[list[tuple[str, bool]]] = []
    for token in tokens:
        runs = set_number_runs(token)
        if runs is None:
            return None
        parsed.append(runs)
    return parsed


def set_score_wins(metric: str) -> list[bool] | None:
    """`4-6 6-3 6-4` → `[False, True, True]`；不是纯整场比分串就返回 None。

    这里的布尔值只表示「左边的局数是不是更大」，用来认出「这是整场比分」。
    上色不看它：每一侧的局数各自着色，见 ``score_number_colors``。

    ⚠️ 认得窄是故意的：`决胜盘 1-5 赛点` 这种「画面上这一刻的局分」必须
    落回老路径（整块一个强调色），按局数上色对它没有意义。
    """
    parsed = _parse_score_tokens(metric)
    if parsed is None:
        return None
    return [int(token.left) > int(token.right) for token in parsed]


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
              variant: str, *, allow_empty_headline: bool = False
              ) -> tuple[str, str, str, str]:
    values = tuple(value.strip() for value in (kicker, headline, detail, metric))
    kicker, headline, detail, metric = values
    if not kicker or not detail or not (headline or allow_empty_headline):
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
        if field == "metric" and score_number_colors(value) is not None:
            if len(value.split()) > 5:
                raise SystemExit("整场比分最多5盘")
            # Full scores are measured in pixels, not the prose character budget.
            continue
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
    """把 metric 切成 (片段, 是不是数字串)：数字串走 TL Score，其余走品牌标题字体。"""
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
    # 比分数字比同字号的标题字略矮，抬 20% 让数字成为这一截的主体。
    # 汉字标签走品牌标题那一支，数字走 TL Score。
    return _font(LABEL_FONT, size), _font(SCORE, round(size * 1.2))


def _metric_width(draw: ImageDraw.ImageDraw, metric: str, size: int,
                  *, stroke: int) -> int:
    cjk, score = _metric_fonts(size)
    parsed = score_number_colors(metric)
    if parsed is not None:
        # 整场比分按盘画，盘之间要真的留出间隔。量的是 advance 宽度：
        # 空格的墨迹框宽度是 0，拿墨迹框摞下去，三盘会挤成一串。
        total = 0
        for index, runs in enumerate(parsed):
            for chunk, _won in runs:
                total += round(draw.textlength(chunk, font=score))
            if index < len(parsed) - 1:
                total += _SET_GAP
        return total
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


def _draw_colored_score(draw: ImageDraw.ImageDraw, shadow: Image.Image,
                        xy: tuple[int, int], metric: str, size: int,
                        stroke: int, anchor: str) -> None:
    """整场比分按局数上色；不是整场比分时整行一个强调色。"""
    cjk, score = _metric_fonts(size)
    mx, y = xy
    parsed = score_number_colors(metric)
    if parsed is not None:
        for index, runs in enumerate(parsed):
            for chunk, won in runs:
                _draw_text(draw, (mx, y), chunk, font=score,
                           fill=BRAND_GREEN if won else WHITE,
                           stroke=stroke, anchor=anchor, shadow_layer=shadow)
                mx += round(draw.textlength(chunk, font=score))
            if index < len(parsed) - 1:
                mx += _SET_GAP
        return
    for chunk, is_score in metric_runs(metric):
        font = score if is_score else cjk
        _draw_text(draw, (mx, y), chunk, font=font, fill=BRAND_GREEN,
                   stroke=stroke, anchor=anchor, shadow_layer=shadow)
        mx = draw.textbbox((mx, y), chunk, font=font, stroke_width=stroke,
                           anchor=anchor)[2]


#: 日期和地点同一行时的分隔，和人物行里的「 · 」同一套。
META_SEP = " · "
#: 描边宽度：只保边，不当底板。
_STROKE_HEAD, _STROKE_SMALL = 2, 1
#: 软阴影的模糊半径（整层一次模糊）。
_SHADOW_BLUR = 7


@dataclass(frozen=True)
class CornerRun:
    text: str
    font: ImageFont.FreeTypeFont
    fill: tuple[int, ...]
    x: float = 0
    dy: float = 0
    stroke: int = CORNER_STROKE


def _corner_bounds(runs: Sequence[CornerRun]) -> tuple[float, float, float, float]:
    boxes = [r.font.getbbox(r.text, anchor="ls") for r in runs]
    return (min(r.x + b[0] for r, b in zip(runs, boxes)),
            min(r.dy + b[1] for r, b in zip(runs, boxes)),
            max(r.x + b[2] for r, b in zip(runs, boxes)),
            max(r.dy + b[3] for r, b in zip(runs, boxes)))


def _corner_score_runs(metric: str, size: int) -> list[CornerRun]:
    """One font family, won games bold/green, lost games light/white.

    Parentheses remain an input notation only. Tiebreak points sit above the
    losing game count, including when that 6 is on the left of the hyphen.
    Match deciders retain square brackets and both baseline point counts.
    The same runs are measured and drawn, so five sets include superscripts.
    """
    bold, light = _font(SCORE, size), _font(SCORE_LIGHT, size)
    small = _font(SCORE_LIGHT, round(size * 0.48))
    cursor = 0.0
    runs: list[CornerRun] = []

    def add(text, font, color, dy=0, stroke=CORNER_STROKE):
        nonlocal cursor
        runs.append(CornerRun(text, font, color, cursor, dy, stroke))
        cursor += font.getlength(text)

    parsed = _parse_score_tokens(metric)
    if parsed is None:
        for text, numeric in metric_runs(metric):
            add(text, bold if numeric else _font(LABEL_FONT, size), BRAND_GREEN)
        return runs
    raised = (bold.getbbox("6", anchor="ls")[1] - 5
              - small.getbbox("5", anchor="ls")[1])
    for index, token in enumerate(parsed):
        left, right, tie = token.left, token.right, token.tiebreak
        if index:
            cursor += max(30, size * 0.3)
        a, b = int(left), int(right)
        if token.match_decider:
            add("[", light, WHITE)
        add(left, bold if a > b else light, BRAND_GREEN if a > b else WHITE)
        if tie is not None and a < b:
            cursor += 2
            add(tie, small, WHITE, raised, 3)
            cursor += 3
        add("-", light, MUTED)
        add(right, bold if b > a else light, BRAND_GREEN if b > a else WHITE)
        if tie is not None and b < a:
            cursor += 2
            add(tie, small, WHITE, raised, 3)
            cursor += 3
        if token.match_decider:
            add("]", light, WHITE)
    return runs


def _corner_people_runs(detail: str, metric: str, size: int) -> list[CornerRun]:
    font = _font(LABEL_FONT, size)
    match = re.fullmatch(r"(.+?)(\s+[vV][sS]\s+)(.+)", detail)
    parsed = _parse_score_tokens(metric)
    if not match:
        return [CornerRun(detail, font, WHITE)]
    left, versus, right = match.groups()
    # A non-score event, or equal set count, provides no match winner.
    winner = None
    if parsed is not None:
        games = [(int(token.left), int(token.right)) for token in parsed]
        left_sets = sum(a > b for a, b in games)
        right_sets = sum(b > a for a, b in games)
        if left_sets != right_sets:
            winner = 0 if left_sets > right_sets else 1
    name_boxes = [font.getbbox(name, anchor="ls") for name in (left, right)]
    vs_box = font.getbbox(versus, anchor="ls")
    center = (min(b[1] for b in name_boxes) + max(b[3] for b in name_boxes)) / 2
    vs_dy = center - (vs_box[1] + vs_box[3]) / 2
    left_width, vs_width = font.getlength(left), font.getlength(versus)
    return [CornerRun(left, font, BRAND_GREEN if winner == 0 else WHITE),
            CornerRun(versus, font, MUTED, left_width, vs_dy),
            CornerRun(right, font, BRAND_GREEN if winner == 1 else WHITE,
                      left_width + vs_width)]


def _fit_corner_runs(builder, preferred: int) -> list[CornerRun]:
    for size in range(preferred, 27, -1):
        runs = builder(size)
        bounds = _corner_bounds(runs)
        if bounds[2] - bounds[0] <= CORNER_LANE:
            return runs
    raise SystemExit("角标文字过长，无法在右侧安全宽度内清晰显示；请缩短文字")


def _render_corner(kicker: str, headline: str, detail: str, out: Path, *,
                   metric: str, align: str, highlight: str) -> Path:
    """Confirmed V14 typography: transparent, original fonts, one shared baseline.

    Sizes are measured at the final 648px overlay width, rather than making
    a 1200px PNG look readable only before downscaling. Visible glyph bounds
    determine row spacing, including CJK, score superscripts and outlines.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, list[CornerRun]]] = []
    if headline:
        rows.append(("topic", _fit_corner_runs(
            lambda size: [CornerRun(headline, _font(LABEL_FONT, size), WHITE)],
            CORNER_TOPIC_SIZE)))

    def meta_runs(size):
        font = _font(LABEL_FONT, size)
        runs = [CornerRun(kicker, font, MUTED)]
        if highlight:
            runs.append(CornerRun(META_SEP + highlight, font, BRAND_GREEN,
                                  font.getlength(kicker)))
        return runs

    rows.append(("meta", _fit_corner_runs(meta_runs, CORNER_META_SIZE)))
    if metric:
        rows.append(("score", _fit_corner_runs(
            lambda size: _corner_score_runs(metric, size), CORNER_SCORE_SIZE)))
    rows.append(("people", _fit_corner_runs(
        lambda size: _corner_people_runs(detail, metric, size), CORNER_PEOPLE_SIZE)))
    bounds = [_corner_bounds(runs) for _kind, runs in rows]
    gaps = [CORNER_SCORE_GAP if "score" in (rows[i][0], rows[i + 1][0])
            else CORNER_GAP for i in range(len(rows) - 1)]
    content = sum(b[3] - b[1] for b in bounds) + sum(gaps)
    height = max(HEIGHT, int(content + 64 + 1) // 2 * 2)
    image = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rail = ((22, 34, 32, height - 34) if align == "left"
            else (WIDTH - 32, 34, WIDTH - 22, height - 34))
    draw.rounded_rectangle(rail, radius=5, fill=BRAND_GREEN)
    y = (height - content) / 2
    for index, ((_kind, runs), box) in enumerate(zip(rows, bounds)):
        offset = 66 - box[0] if align == "left" else WIDTH - 66 - box[2]
        baseline = y - box[1]
        # Paint all shadows first so a later run cannot cover an adjacent fill.
        for run in runs:
            draw.text((offset + run.x + CORNER_SHADOW_OFFSET,
                       baseline + run.dy + CORNER_SHADOW_OFFSET), run.text,
                      font=run.font, fill=(0, 0, 0, 255), anchor="ls",
                      stroke_width=run.stroke, stroke_fill=(0, 0, 0, 255))
        for run in runs:
            draw.text((offset + run.x, baseline + run.dy), run.text, font=run.font,
                      fill=run.fill, anchor="ls", stroke_width=run.stroke,
                      stroke_fill=CORNER_OUTLINE)
        y += box[3] - box[1] + (gaps[index] if index < len(gaps) else 0)
    image.save(out)
    return out


def render(kicker: str, headline: str, detail: str, out: Path, *,
           metric: str = "", variant: str = "timeline", align: str = "right",
           split_metric: bool = False, layout: str = "corner",
           highlight: str = "", sets: Sequence[SetScore] | None = None) -> Path:
    if sets is not None:
        formatted = score_line(sets)
        if metric.strip() and metric.strip() != formatted:
            raise SystemExit(
                f"metric「{metric.strip()}」和结构化盘分「{formatted}」不一致；"
                "颜色只从每个局数的大小算，不要另写一串或手写绿白")
        metric = formatted
    # split_metric 是旧四行合同的显式开关。默认 corner 不能把它的字号和行序换掉。
    effective = "classic" if split_metric else layout
    allow_empty = effective == "corner" and bool(highlight.strip())
    kicker, headline, detail, metric = _validate(
        kicker, headline, detail, metric, variant,
        allow_empty_headline=allow_empty)
    highlight = _validate_highlight(highlight)
    if align not in {"left", "right"}:
        raise SystemExit("align 只能是 left 或 right")
    if layout not in {"corner", "classic"}:
        raise SystemExit("layout 只能是 corner 或 classic")
    if split_metric and not metric:
        raise SystemExit("split_metric 必须填写 metric，比分才能独立成行")
    if effective == "corner" and not headline and not highlight:
        raise SystemExit("主标题和地点至少要有一个")
    if split_metric:
        layout = "classic"
    if layout == "corner":
        return _render_corner(kicker, headline, detail, out, metric=metric,
                              align=align, highlight=highlight)

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
    kicker_font = _fit_font(LABEL_FONT, 44, 36, kicker, WIDTH - x - 28,
                            stroke=_STROKE_SMALL)
    metric_width = metric_size = 0
    if metric:
        # 独立行按原60px上限绘制，不缩字去挤；默认同行继续沿用旧字号预算。
        metric_size = _fit_metric_size(draw, metric, 60, 60 if split_metric else 44,
                                      WIDTH - x - 28 if split_metric else 430,
                                      stroke=_STROKE_SMALL)
        metric_width = _metric_width(draw, metric, metric_size, stroke=_STROKE_SMALL)
        if split_metric and metric_width > WIDTH - x - 28:
            raise SystemExit("metric 独立行仍放不下；请缩短文字，不缩小比分字号")
    # 主标题和其余文字都是左上角品牌标题那一支；变体只改字号。
    headline_size = {"stat": 134, "chapter": 126}.get(variant, 122)
    headline_room = WIDTH - x - 28 - ((metric_width + 36) if metric and not split_metric else 0)
    headline_font = _fit_font(LABEL_FONT, headline_size, 92, headline, headline_room,
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
    detail_font = _fit_font(LABEL_FONT, 50, 40, detail, WIDTH - x - 28,
                            stroke=_STROKE_SMALL)

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
        # 整场比分按局数上色：更大的那个局数黄绿，更小的留白，连字符和抢七括号留白。
        # 不是整场比分（「决胜盘 1-5 赛点」）时整行一个强调色。不认手写的颜色标记。
        _draw_colored_score(metric_draw, metric_shadow, (mx, baseline), metric,
                            metric_size, _STROKE_SMALL, "ls")
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


_DATE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
_LEGACY_CORNER_LABEL = REPO / "data" / "legacy_corner_label.json"
_LEGACY_LABEL_FIELDS = REPO / "data" / "legacy_label_fields.json"


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


def legacy_label_fields_slugs() -> frozenset[str]:
    """已发、还没写齐 label 字段的片子。只许减不许加。"""
    if not _LEGACY_LABEL_FIELDS.is_file():
        return frozenset()
    data = json.loads(_LEGACY_LABEL_FIELDS.read_text(encoding="utf-8"))
    return frozenset(str(slug) for slug in (data.get("slugs") or []))


def label_fields_problem(label: object) -> str | None:
    """topic、date、place、people 都要有，另外还要有 score 或 event。

    date 写成 ``2026.10.11``。score 只能是整场比分（``6-4`` / ``7-6(5)``），
    说明性的字写进 event。event 和 topic 是同一句时不另起一行。
    对得上返回 None。
    """
    if not isinstance(label, dict):
        return "story_text 要写 label：topic、date、place、people，外加 score 或 event"
    missing = [key for key in ("topic", "date", "place", "people")
               if not str(label.get(key) or "").strip()]
    if missing:
        return f"label 缺 {', '.join(missing)}"
    topic = str(label["topic"]).strip()
    date = str(label["date"]).strip()
    place = str(label["place"]).strip()
    people = str(label["people"]).strip()
    score = str(label.get("score") or "").strip()
    event = str(label.get("event") or "").strip()
    if not score and not event:
        return "label 要有 score 或 event"
    if not _DATE.match(date):
        return "date 写成 2026.10.11"
    if score and score_number_colors(score) is None:
        return f"score「{score}」不是整场比分；说明写进 event"
    if score and len(score.split()) > 5:
        return "整场比分最多5盘"
    budgets = {"topic": 10.5, "place": 12.0, "people": 23.0, "score": 11.0}
    for field, value in (("topic", topic), ("place", place),
                         ("people", people), ("score", score)):
        if not value:
            continue
        if "\n" in value or "｜" in value or "|" in value:
            return f"{field} 只能一行，不要用竖线拼字段"
        if field == "score":
            continue  # Complete five-set scores fit by measured glyph width.
        if display_units(value) > budgets[field]:
            return (f"{field} 太长（{display_units(value):.1f}>{budgets[field]}）："
                    "一屏只留一个记忆点")
    drawn = event if event and event != topic and not score else ""
    if drawn and ("\n" in drawn or "｜" in drawn or "|" in drawn):
        return "event 只能一行，不要用竖线拼字段"
    if drawn and display_units(drawn) > 11.0:
        return (f"event 太长（{display_units(drawn):.1f}>11.0）："
                "和 topic 不同又没有比分时，event 自己占比分那一行")
    return None


def metric_from_label(label: dict) -> str:
    """比分占第三行。没有比分、且 event 不是把 topic 再说一遍时，event 占这一行。"""
    score = str(label.get("score") or "").strip()
    if score:
        return score
    event = str(label.get("event") or "").strip()
    topic = str(label.get("topic") or "").strip()
    if event and event != topic:
        return event
    return ""


def render_label(label: dict, out: Path, **kwargs) -> Path:
    """按 label 字段渲一张默认角标。字段不齐就停，不写出半张图。"""
    problem = label_fields_problem(label)
    if problem:
        raise SystemExit(problem)
    return render(
        str(label["date"]).strip(),
        str(label["topic"]).strip(),
        str(label["people"]).strip(),
        out,
        highlight=str(label["place"]).strip(),
        metric=metric_from_label(label),
        **kwargs,
    )


def story_label_field_problems(spec: dict, *, honor_legacy: bool = True) -> list[str]:
    """每张 story_text 都要写齐 label 字段。没有贴图的片子不报。

    已发、还没改字段的挂在 ``data/legacy_label_fields.json``。
    ``honor_legacy=False`` 用来证明那张表里的片子确实还缺字段。
    """
    slug = str(spec.get("slug") or "")
    if honor_legacy and slug in legacy_label_fields_slugs():
        return []
    problems: list[str] = []
    for index, raw in enumerate(spec.get("segments") or []):
        inset = (raw or {}).get("inset") or {}
        if str(inset.get("kind") or "") != "story_text":
            continue
        message = label_fields_problem(inset.get("label"))
        if message:
            problems.append(f"第 {index + 1} 段 {message}")
    return problems


def label_font_problem() -> str | None:
    """角标文字必须和左上角品牌标题同一支；比分数字仍是 TL Score。

    对得上返回 None。这道闸不看豁免表：字体漂了，已发的片子下次重渲也要红。
    """
    from tennislive.video.watermark import BRAND_FONT
    brand = (REPO / "assets" / "fonts" / BRAND_FONT).resolve()
    if LABEL_FONT.resolve() != brand:
        return (f"角标文字用了 {LABEL_FONT.name}，"
                f"左上角品牌标题是 {BRAND_FONT}")
    if SCORE.name != "TLScore-Bold.ttf":
        return "比分数字不是 TL Score Bold"
    return None


def story_corner_label_problems(spec: dict, *, honor_legacy: bool = True) -> list[str]:
    """每张 story_text 都要落在右上角，并且 PNG 是右轨右对齐。

    没有贴图的片子不报。已发左轨片挂在 ``data/legacy_corner_label.json``，
    ``honor_legacy=False`` 用来证明那张表里的片子确实还不合格式。
    字体闸在豁免之前：角标文字漂离品牌标题，已发的片子也红。
    """
    font = label_font_problem()
    if font:
        return [font]
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
                    help="地点或赛事，和日期同一行、写在日期后面，例如「ATP1000 上海」")
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
    with Image.open(out) as image:
        print(f"已渲 {out}（{image.width}×{image.height}，大字版 RGBA，无大底板）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
