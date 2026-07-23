"""晨报卡片图生成（Pillow）：小红书 3:4 竖版（1080x1440）.

视觉体系（小红书审美）：
- 深绿渐变背景 + 右上装饰弧线，品牌网球荧光黄做强调色
- 每场比赛一个圆角面板（中国球员场次用荧光黄描边高亮）
- 栏目头中英混排（大黄字 + 英文小字），日期用 "7.16 · 周四"
- 内容少时自动垂直居中，不留大面积空白

赛程按赛事拆页；中国球员在所属赛事中高亮，不再重复生成独立页面。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..digest import Digest
from ..models import Match
from ..timeutil import WEEKDAY_ZH, fmt_time_beijing
from ..zh import player_zh, surface_zh
from ..zh.tournaments import tournament_surface
from .common import (
    _abbrev_en,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .rating import (
    find_upset,
    is_upset,
    stay_up_stars,
    tonight_event_focus,
    top_results,
)

logger = logging.getLogger(__name__)

W, H = 1080, 1440
MARGIN = 64
ASSETS = Path(__file__).resolve().parents[3] / "assets"

BRAND = "网球时差"
COLUMN = "网球晨报"

# 主题：dark=品牌深绿（默认），light=小红书奶油风
# BTN_TEXT 固定深色（荧光按钮上的字两种主题都要深）
_THEMES = {
    "dark": dict(
        BG_TOP=(14, 44, 36),
        BG_BOTTOM=(7, 23, 18),
        PANEL=(20, 58, 47),
        PANEL_HI=(26, 70, 56),
        PANEL_LINE=(34, 84, 68),
        DECO=(22, 62, 50),
        ACCENT=(204, 255, 0),        # 标题/高亮文字
        BALL=(204, 255, 0),          # 网球图形
        OUTLINE=(204, 255, 0),       # 高亮面板描边
        WHITE=(245, 248, 246),       # 主文字
        GREY=(168, 186, 179),
        SCORE_GREY=(190, 205, 198),
        RED=(255, 107, 87),
        FOOT=(110, 128, 120),
        STAR_PILL=(38, 92, 74),
        STAR_PILL_HOT=(176, 122, 20),
    ),
    "light": dict(
        BG_TOP=(250, 247, 239),
        BG_BOTTOM=(241, 235, 222),
        PANEL=(255, 255, 255),
        PANEL_HI=(250, 252, 235),
        PANEL_LINE=(224, 216, 198),
        DECO=(235, 228, 210),
        ACCENT=(13, 96, 60),         # 浅底上用深绿做强调字
        BALL=(198, 246, 0),
        OUTLINE=(168, 208, 40),
        WHITE=(30, 42, 37),          # 主文字改为深色
        GREY=(122, 134, 126),
        SCORE_GREY=(96, 110, 103),
        RED=(224, 112, 92),
        FOOT=(160, 168, 160),
        STAR_PILL=(120, 158, 60),
        STAR_PILL_HOT=(214, 154, 26),
    ),
}
BTN_TEXT = (10, 26, 20)


def set_theme(name: str) -> None:
    """切换配色主题（dark/light），直接更新模块级颜色常量."""
    globals().update(_THEMES.get(name, _THEMES["dark"]))


set_theme("dark")

_FONT_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", 0),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("C:/Windows/Fonts/msyh.ttc", 0),
]
_BOLD_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf", 0),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 2),
]


class FontNotFoundError(RuntimeError):
    pass


def _find_font(bold: bool = False) -> tuple[str, int]:
    env = os.environ.get("TENNISLIVE_FONT_BOLD" if bold else "TENNISLIVE_FONT")
    if env and Path(env).exists():
        return env, 0
    project_fonts = Path(__file__).resolve().parents[3] / "assets" / "fonts"
    if project_fonts.is_dir():
        pattern = "*Bold*" if bold else "*"
        for f in sorted(project_fonts.glob(pattern)):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                return str(f), 0
    for path, idx in (_BOLD_CANDIDATES if bold else _FONT_CANDIDATES):
        if Path(path).exists():
            return path, idx
    if bold:
        return _find_font(bold=False)
    raise FontNotFoundError(
        "找不到中文字体。请安装 fonts-noto-cjk（Ubuntu: sudo apt install fonts-noto-cjk）"
        "或设置 TENNISLIVE_FONT 环境变量指向一个 .ttf/.otf/.ttc 字体文件。"
    )


class _Fonts:
    def __init__(self) -> None:
        regular, r_idx = _find_font(False)
        bold, b_idx = _find_font(True)
        asset_dir = Path(__file__).resolve().parents[3] / "assets" / "fonts"

        def optional_font(env_name: str, asset_name: str, fallback: str) -> str:
            configured = os.environ.get(env_name)
            if configured and Path(configured).exists():
                return configured
            bundled = asset_dir / asset_name
            return str(bundled) if bundled.exists() else fallback

        display = optional_font(
            "TENNISLIVE_FONT_DISPLAY",
            "SmileySans-Oblique.woff2",
            bold,
        )
        latin = optional_font(
            "TENNISLIVE_FONT_LATIN",
            "BarlowCondensed-SemiBold.ttf",
            bold,
        )

        def load(path: str, idx: int, size: int) -> ImageFont.FreeTypeFont:
            return ImageFont.truetype(path, size=size, index=idx)

        self.title = load(bold, b_idx, 84)
        self.display_title = load(display, 0, 84)
        self.huge = load(bold, b_idx, 176)
        self.subtitle = load(regular, r_idx, 42)
        self.section = load(bold, b_idx, 52)
        self.label = load(regular, r_idx, 31)
        self.en = load(bold, b_idx, 26)
        self.latin = load(latin, 0, 28)
        self.main = load(bold, b_idx, 46)
        self.score = load(bold, b_idx, 38)
        self.body = load(regular, r_idx, 36)
        self.small = load(regular, r_idx, 27)
        # 赛果速递卡专用：列表行
        self.cell_meta = load(regular, r_idx, 25)
        self.cell_name = load(bold, b_idx, 34)
        self.cell_name_sm = load(bold, b_idx, 30)
        self.cell_name_xs = load(bold, b_idx, 26)
        self.cell_seed = load(regular, r_idx, 21)
        self.cell_score = load(bold, b_idx, 38)
        self.cell_sup = load(bold, b_idx, 20)
        # 赛果速递卡专用：头条区（字号大、对比强）
        self.hero_name = load(bold, b_idx, 52)
        self.hero_name_sm = load(bold, b_idx, 44)
        self.hero_name_xs = load(bold, b_idx, 36)
        self.hero_score = load(bold, b_idx, 84)
        self.hero_sup = load(bold, b_idx, 30)


def _fit(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


# CJK 字体没有 emoji 字形（会画成方框），卡片文本统一剥离 emoji（含国旗）
_EMOJI_RE = re.compile("[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF☀-➿️‍]+")


def _strip(s: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", s)).strip()


def _wrap_text(draw, text: str, font, max_w: int, max_lines: int = 3) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def _flash_headline_lines(draw, text: str, font, max_w: int) -> list[str]:
    """把长标题均衡分成两行，避免末行只剩一两个字。"""
    text = _strip(text)
    if draw.textlength(text, font=font) <= max_w:
        return [text]

    candidates: list[tuple[float, float, int]] = []
    for split_at in range(3, len(text) - 2):
        left, right = text[:split_at], text[split_at:]
        left_w = draw.textlength(left, font=font)
        right_w = draw.textlength(right, font=font)
        if left_w <= max_w and right_w <= max_w:
            candidates.append((abs(left_w - right_w), max(left_w, right_w), split_at))
    if candidates:
        _, _, split_at = min(candidates)
        return [text[:split_at], text[split_at:]]
    return _wrap_text(draw, text, font, max_w, 2)


def _draw_ball(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color=None, width_ratio=9) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color or BALL)
    draw.arc(
        [cx - int(r * 1.7), cy - r, cx - int(r * 0.1), cy + r],
        start=-60, end=60, fill=BG_TOP, width=max(3, r // width_ratio),
    )
    draw.arc(
        [cx + int(r * 0.1), cy - r, cx + int(r * 1.7), cy + r],
        start=120, end=240, fill=BG_TOP, width=max(3, r // width_ratio),
    )


@lru_cache(maxsize=8)
def _brand_icon(size: int) -> Image.Image | None:
    """Load the transparent brand mark used in every page masthead."""
    path = ASSETS / "logo" / "tennis-clock-icon.png"
    try:
        icon = Image.open(path).convert("RGBA")
    except OSError:
        return None
    return icon.resize((size, size), Image.Resampling.LANCZOS)


def _draw_court(draw: ImageDraw.ImageDraw, y_top: int, y_bottom: int, color) -> None:
    """透视网球场线稿（原创插画，替代版权球场照片做背景）."""
    base_l, base_r = MARGIN - 120, W - MARGIN + 120
    net_l, net_r = int(W * 0.26), int(W * 0.74)

    def edge(t: float) -> tuple[float, float, float]:
        """t=0 底线，t=1 球网；返回 (左x, 右x, y)."""
        return (
            base_l + (net_l - base_l) * t,
            base_r + (net_r - base_r) * t,
            y_bottom + (y_top - y_bottom) * t,
        )

    lw = 4
    # 外框（双打场）
    l0, r0, yb = edge(0.0)
    l1, r1, yn = edge(1.0)
    draw.polygon([(l0, yb), (r0, yb), (r1, yn), (l1, yn)], outline=color, width=lw)
    # 单打边线（内缩 11%）
    for side in (0.11, 0.89):
        pts = []
        for t in (0.0, 1.0):
            l, r, yy = edge(t)
            pts.append((l + (r - l) * side, yy))
        draw.line(pts, fill=color, width=lw)
    # 发球线 + 中线
    ls, rs, ys = edge(0.62)
    draw.line([(ls + (rs - ls) * 0.11, ys), (ls + (rs - ls) * 0.89, ys)], fill=color, width=lw)
    lm0, rm0, ym0 = edge(0.62)
    lm1, rm1, ym1 = edge(1.0)
    draw.line(
        [((lm0 + rm0) / 2, ym0), ((lm1 + rm1) / 2, ym1)], fill=color, width=lw
    )
    # 球网（顶边加厚 + 网柱）
    draw.line([(l1 - 14, yn), (r1 + 14, yn)], fill=color, width=10)
    draw.line([(l1 - 14, yn), (l1 - 14, yn + 26)], fill=color, width=6)
    draw.line([(r1 + 14, yn), (r1 + 14, yn + 26)], fill=color, width=6)


def _canvas(deco: str = "arcs") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """渐变背景 + 装饰（arcs=右上弧线 / court=透视球场线稿 / none）."""
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line([(0, y), (W, y)], fill=c)
    if deco == "arcs":
        draw.arc([W - 460, -300, W + 320, 480], start=60, end=250, fill=DECO, width=56)
        draw.arc([W - 320, -220, W + 220, 320], start=60, end=260, fill=DECO, width=30)
    elif deco == "court":
        _draw_court(draw, y_top=380, y_bottom=H + 80, color=DECO)
    elif deco == "court-faint":
        # 更淡的球场线稿：正文密集的卡片用，避免线条干扰文字
        faint = tuple((d + 2 * b) // 3 for d, b in zip(DECO, BG_BOTTOM))
        _draw_court(draw, y_top=380, y_bottom=H + 80, color=faint)
    return img, draw


# 赛事级别徽章配色
LEVEL_BADGE_COLOR = {
    "GS": (122, 84, 168),
    "M1000": (188, 152, 50),
    "W1000": (188, 152, 50),
    "Finals": (188, 152, 50),
    "ATP500": (74, 128, 176),
    "WTA500": (74, 128, 176),
    "ATP250": (40, 138, 84),
    "WTA250": (40, 138, 84),
}


def _tournament_badge(draw, fonts, cx: int, cy: int, r: int, level: str | None) -> None:
    """生成式赛事徽章：级别配色圆环 + 网球图形（原创，替代官方 logo）."""
    ring = LEVEL_BADGE_COLOR.get(level or "", (110, 128, 120))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ring, width=6)
    _draw_ball(draw, cx, cy, int(r * 0.55))


def _date_label(d) -> str:
    return f"{d.month}.{d.day} · {WEEKDAY_ZH[d.weekday()]}"


def _page(
    fonts: _Fonts,
    date_label: str,
    column_title: str,
    en_sub: str,
    accent=None,
    deco: str = "arcs",
    title_font=None,
):
    """新建一页并画页眉，返回 (img, draw, 内容起始 y)."""
    img, draw = _canvas(deco)
    icon = _brand_icon(56)
    if icon is not None:
        img.paste(icon, (MARGIN - 2, MARGIN + 2), icon)
    else:
        _draw_ball(draw, MARGIN + 26, MARGIN + 30, 24)
    draw.text((MARGIN + 70, MARGIN), BRAND, font=fonts.section, fill=WHITE)
    tl = draw.textlength(date_label, font=fonts.small)
    draw.text((W - MARGIN - tl, MARGIN + 16), date_label, font=fonts.small, fill=GREY)
    y = MARGIN + 96
    draw.text((MARGIN, y), en_sub, font=fonts.latin, fill=GREY)
    y += 42
    draw.text(
        (MARGIN, y),
        column_title,
        font=title_font or fonts.title,
        fill=accent or ACCENT,
    )
    y += 120
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    return img, draw, y + 40


def _footer(draw: ImageDraw.ImageDraw, fonts: _Fonts, text: str = "") -> None:
    if text:
        draw.text((MARGIN, H - MARGIN - 20), text, font=fonts.small, fill=FOOT)
    mark = f"@{BRAND}"
    tw = draw.textlength(mark, font=fonts.small)
    draw.text((W - MARGIN - tw, H - MARGIN - 20), mark, font=fonts.small, fill=GREY)


def _match_label(m: Match) -> str:
    g = group_by_tournament([m])[0]
    r = match_round_display(m)
    return f"{g.name_zh}{('·' + r) if r else ''}"


_PAD = 28  # 面板内边距


def _panel_block(
    draw: ImageDraw.ImageDraw,
    fonts: _Fonts,
    y: int,
    label: str,
    main: str,
    sub: str = "",
    accent: bool = False,
    tag: str = "",
    tag_color=RED,
) -> int:
    """一场比赛的圆角面板：小标签 + 主行 + 副行；返回新的 y."""
    inner_h = 48 + 64 + (54 if sub else 0) + 2 * _PAD - 20
    x0, x1 = MARGIN, W - MARGIN
    fill = PANEL_HI if accent else PANEL
    draw.rounded_rectangle([x0, y, x1, y + inner_h], radius=22, fill=fill)
    if accent:
        draw.rounded_rectangle(
            [x0, y, x1, y + inner_h], radius=22, outline=OUTLINE, width=3
        )

    tx = x0 + _PAD
    ty = y + _PAD - 6
    max_label_w = x1 - tx - _PAD - (draw.textlength(tag, font=fonts.label) + 70 if tag else 0)
    draw.text(
        (tx, ty), _fit(draw, label, fonts.label, int(max_label_w)),
        font=fonts.label, fill=GREY,
    )
    if tag:
        tw = draw.textlength(tag, font=fonts.label)
        bx1 = x1 - _PAD
        bx0 = bx1 - tw - 32
        draw.rounded_rectangle([bx0, ty - 4, bx1, ty + 38], radius=10, fill=tag_color)
        draw.text((bx0 + 16, ty), tag, font=fonts.label, fill=(255, 255, 255))
    ty += 50
    color = ACCENT if accent else WHITE
    draw.text(
        (tx, ty), _fit(draw, _strip(main), fonts.main, x1 - tx - _PAD),
        font=fonts.main, fill=color,
    )
    ty += 66
    if sub:
        draw.text(
            (tx, ty), _fit(draw, _strip(sub), fonts.score, x1 - tx - _PAD),
            font=fonts.score, fill=SCORE_GREY,
        )
    return y + inner_h + 24


_BLOCK_H = 48 + 64 + 54 + 2 * _PAD - 20 + 24   # 带副行的面板总高
_BLOCK_H_NOSUB = _BLOCK_H - 54


def _spread(n_blocks: int, block_h: int = _BLOCK_H) -> tuple[int, int]:
    """按块数计算 (起始下移, 块间额外间距)，让少量内容垂直居中更饱满."""
    available = H - 350 - MARGIN - 60
    rest = available - n_blocks * block_h
    if rest <= 0:
        return 0, 0
    extra = min(64, rest // (n_blocks + 1))
    return extra, extra


def _split_result(m: Match) -> tuple[str, str]:
    """赛果拆成 (对阵行, 比分行)."""
    line = result_line(m, short_en=True)
    if "（" in line:
        main, _, score = line.partition("（")
        return main.strip(), score.rstrip("）")
    return line, ""


# ---------- 各卡片 ----------

def _cover(fonts: _Fonts, digest: Digest, headline: str) -> Image.Image:
    img, draw = _canvas("court")
    _draw_ball(draw, W - 190, 250, 100)
    d = digest.today
    draw.text((MARGIN, 170), f"{BRAND} · TENNIS JETLAG", font=fonts.en, fill=GREY)
    draw.text((MARGIN, 220), f"{d.month}.{d.day}", font=fonts.huge, fill=WHITE)
    wd = WEEKDAY_ZH[d.weekday()]
    tl = draw.textlength(f"{d.month}.{d.day}", font=fonts.huge)
    draw.text((MARGIN + tl + 24, 340), wd, font=fonts.subtitle, fill=GREY)
    draw.text((MARGIN, 440), COLUMN, font=fonts.title, fill=ACCENT)
    draw.text(
        (MARGIN, 560), "替你熬夜看网球 · 昨夜赛果，今晨看懂",
        font=fonts.subtitle, fill=GREY,
    )
    # 吸睛标签（card-xiaohongshu 规范：封面带 engaging tag）
    tag = "每天早间更新"
    tw = draw.textlength(tag, font=fonts.label)
    draw.rounded_rectangle(
        [MARGIN, 626, MARGIN + tw + 44, 626 + 56], radius=28,
        outline=OUTLINE, width=3,
    )
    draw.text((MARGIN + 22, 626 + 11), tag, font=fonts.label, fill=ACCENT)

    y = 726
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    y += 42
    draw.text((MARGIN, y), "今日焦点", font=fonts.label, fill=GREY)
    y += 52
    for chunk in _wrap_text(draw, _strip(headline), fonts.section, W - 2 * MARGIN, 2):
        draw.text((MARGIN, y), chunk, font=fonts.section, fill=ACCENT)
        y += 72
    y += 40

    # 数据 chips
    chips = []
    if digest.results:
        chips.append(f"昨夜赛果 {len(digest.results)} 场")
    if digest.schedule:
        chips.append(f"今日赛程 {len(digest.schedule)} 场")
    cx = MARGIN
    for chip in chips:
        tw = draw.textlength(chip, font=fonts.body)
        draw.rounded_rectangle([cx, y, cx + tw + 48, y + 62], radius=31, fill=PANEL)
        draw.text((cx + 24, y + 11), chip, font=fonts.body, fill=WHITE)
        cx += tw + 48 + 20
    _footer(draw, fonts)
    return img


def _card_focus(fonts: _Fonts, date_label: str, matches: list[Match]) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "昨夜焦点", "OVERNIGHT RESULTS")
    lead, gap = _spread(len(matches))
    y += lead
    for m in matches:
        main, score = _split_result(m)
        y = _panel_block(
            draw, fonts, y,
            label=_match_label(m),
            main=main,
            sub=score,
            accent=is_chinese_involved(m),
            tag="冷门" if find_upset([m]) else "",
        ) + gap
    _footer(draw, fonts)
    return img


# ---------- 赛果速递：官方比分板风格（ATP/温网版式语言） ----------
# 参考 ATP/WTA/四大满贯官网记分卡的共同设计语言：
# 白色卡片承载比分；每盘比分独占固定宽度的列，两行严格纵向对齐；
# 胜者以色带+加粗强调；卡内三层结构（元信息条 / 球员行 / 比分列）。
# 叠加 card-xiaohongshu 的层级要求：当日最重磅一场放大为头条卡。

# 白卡配色（主题无关，深浅背景下都保持官方板的对比度）
CARD_BG = (250, 251, 249)
CARD_TEXT = (18, 32, 25)
CARD_GREY = (128, 139, 132)
CARD_LINE = (227, 232, 228)
WIN_BAND = (216, 238, 210)
WIN_GREEN = (13, 96, 53)
CHIP_GREEN = (11, 77, 47)


def _short_name(p) -> str:
    """有译名用中文；无译名的英文名缩写化（'V. Valdmannova'）."""
    n = player_zh(p.name)
    if n == p.name and n.isascii():
        n = _abbrev_en(n)
    return n


def _side_pairs(m: Match, side: int) -> list[tuple[int, int | None]]:
    if side == 0:
        return [(s.home, s.home_tiebreak) for s in m.sets]
    return [(s.away, s.away_tiebreak) for s in m.sets]


def _set_columns(
    draw, right: int, cy: int, pairs, font, sup_font, color, col_w: int
) -> None:
    """官方板式比分列：每盘居中于固定宽度列，两行天然对齐；抢七小分上标."""
    n = len(pairs)
    for i, (games, tb) in enumerate(pairs):
        cx = right - (n - i) * col_w + col_w // 2
        g = str(games)
        gw = draw.textlength(g, font=font)
        gy = cy - font.size // 2 - 4
        draw.text((cx - gw / 2, gy), g, font=font, fill=color)
        if tb is not None:
            draw.text((cx + gw / 2 + 2, gy - sup_font.size // 3), str(tb),
                      font=sup_font, fill=color)


def _name_line(
    img, draw, fonts, x: int, cy: int, max_right: int,
    players, color, name_fonts, flag_h: int, meta_font,
) -> None:
    """一方的姓名行：国旗 + 种子号 + 姓名 +（世界排名），字号自动降档放全名."""
    from .flags import flag_image

    for p in players[:2]:
        flag = flag_image(p.country, height=flag_h)
        if flag is not None:
            img.paste(flag, (int(x), cy - flag_h // 2), flag)
            x += flag.width + 10
    seed = players[0].seed if players else None
    if seed:
        draw.text((x, cy - meta_font.size // 2), str(seed), font=meta_font, fill=CARD_GREY)
        x += draw.textlength(str(seed), font=meta_font) + 7
    name = "/".join(_short_name(p) for p in players)
    rank = players[0].rank if len(players) == 1 else None
    rank_txt = f"({rank})" if rank else ""
    rank_w = draw.textlength(rank_txt, font=meta_font) + 8 if rank_txt else 0
    max_name_w = max_right - x - rank_w
    font = name_fonts[0]
    for smaller in name_fonts[1:]:
        if draw.textlength(name, font=font) <= max_name_w:
            break
        font = smaller
    if len(players) == 1 and name.isascii() and draw.textlength(name, font=font) > max_name_w:
        name = players[0].name.split()[-1]
    name = _fit(draw, name, font, int(max_name_w))
    draw.text((x, cy - font.size // 2 - 3), name, font=font, fill=color)
    if rank_txt:
        nw = draw.textlength(name, font=font)
        draw.text((x + nw + 8, cy - meta_font.size // 2), rank_txt,
                  font=meta_font, fill=CARD_GREY)


def _hero_story(m: Match) -> str:
    """头条故事标签：给这场比赛一个一眼能懂的看点."""
    from ..zh.terms import round_zh

    if is_chinese_involved(m):
        return "中国军团"
    if (round_zh(m.round_name) or "") == "决赛":
        return "夺冠时刻"
    if is_upset(m):
        return "爆冷"
    return "今日头条"


def _match_card(
    img, draw, fonts, y: int, m: Match, *,
    h: int, name_fonts, score_font, sup_font, meta_font,
    flag_h: int, col_w: int, chip: str | None = None,
    tag_upset: bool = False, show_tournament: bool = True,
) -> int:
    """官方板式比赛卡：元信息条 + 两行球员 + 每盘一列的比分网格. 返回底部 y."""
    x0, x1 = MARGIN, W - MARGIN
    draw.rounded_rectangle([x0, y, x1, y + h], radius=20, fill=CARD_BG)
    pad = 28
    top_h = 56 if chip is None else 72

    # 元信息条（官方板式两端分布）：故事标签/项目·轮次靠左，赛事靠右
    lx = x0 + pad
    ty = y + (26 if chip else 16)
    if chip:
        fill = RED if chip == "爆冷" else CHIP_GREEN
        tw = draw.textlength(chip, font=fonts.label)
        draw.rounded_rectangle([lx, y + 18, lx + tw + 36, y + 18 + 44], radius=22, fill=fill)
        draw.text((lx + 18, y + 18 + 6), chip, font=fonts.label, fill=(255, 255, 255))
        lx += tw + 36 + 16
    left = match_round_display(m) or ""
    if left:
        draw.text((lx, ty), left, font=meta_font, fill=CARD_GREY)
        lx += draw.textlength(left, font=meta_font) + 16
    if tag_upset and not chip:
        tw = draw.textlength("爆冷", font=fonts.cell_seed)
        draw.rounded_rectangle([lx, y + 10, lx + tw + 22, y + 44], radius=8, fill=RED)
        draw.text((lx + 11, y + 13), "爆冷", font=fonts.cell_seed, fill=(255, 255, 255))
    if show_tournament:
        g = group_by_tournament([m])[0]
        right = _fit(draw, g.compact_title, meta_font, int((x1 - x0) * 0.42))
        rw = draw.textlength(right, font=meta_font)
        draw.text((x1 - pad - rw, ty), right, font=meta_font, fill=CARD_GREY)
    draw.line([x0 + pad, y + top_h, x1 - pad, y + top_h], fill=CARD_LINE, width=2)

    # 球员两行（胜者在上）+ 比分列
    order = (0, 1) if m.winner in (None, 0) else (1, 0)
    row_h = (h - top_h - 12) // 2
    score_right = x1 - pad + col_w // 4  # 列有内边距，比分区右缘略进
    for row_i, side in enumerate(order):
        players = m.home if side == 0 else m.away
        won = m.winner == side
        ry = y + top_h + 6 + row_i * row_h
        cy = ry + row_h // 2
        if won:
            draw.rounded_rectangle(
                [x0 + 12, ry + 3, x1 - 12, ry + row_h - 3], radius=12, fill=WIN_BAND
            )
        pairs = _side_pairs(m, side)
        _set_columns(
            draw, score_right, cy, pairs, score_font, sup_font,
            WIN_GREEN if won else CARD_GREY, col_w,
        )
        _name_line(
            img, draw, fonts, x0 + pad, cy, score_right - len(pairs) * col_w - 14,
            players, CARD_TEXT if won else CARD_GREY,
            name_fonts, flag_h, meta_font,
        )
    if not m.sets and m.note:
        draw.text((x1 - pad - 220, y + top_h + 24), _strip(m.note)[:12],
                  font=fonts.body, fill=CARD_GREY)
    return y + h


def _card_scoreboard(fonts: _Fonts, date_label: str, matches: list[Match]) -> Image.Image:
    """赛果速递卡：头条大卡 + 官方板式比赛卡列表.

    背景为透视球场线稿；全部比赛同属一个赛事时显示赛事横幅（徽章+名称）。
    """
    img, draw, y = _page(fonts, date_label, "赛果速递", "SCOREBOARD", deco="court-faint")

    # 全部比赛同属一个赛事（如大满贯日）→ 顶部赛事横幅，卡内不再重复赛事名
    names = {m.tournament.name for m in matches}
    single_event = len(names) == 1
    if single_event:
        g = group_by_tournament(matches[:1])[0]
        title = g.title
        # 合办赛事（ATP+WTA 同名，如大满贯）不带单一巡回赛前缀
        if len({m.tour for m in matches}) > 1 and title.startswith(("ATP ", "WTA ")):
            title = title[4:]
        _tournament_badge(draw, fonts, MARGIN + 40, y + 34, 38, g.level)
        draw.text(
            (MARGIN + 100, y + 4),
            _fit(draw, title, fonts.section, W - 2 * MARGIN - 110),
            font=fonts.section,
            fill=WHITE,
        )
        y += 100

    hero, rest = matches[0], matches[1:]
    y = _match_card(
        img, draw, fonts, y + 6, hero,
        h=300, name_fonts=(fonts.hero_name, fonts.hero_name_sm, fonts.hero_name_xs),
        score_font=fonts.hero_score, sup_font=fonts.hero_sup,
        meta_font=fonts.cell_meta, flag_h=36, col_w=96,
        chip=_hero_story(hero), show_tournament=not single_event,
    )
    y += 18

    card_h, gap = 150, 14
    avail = H - y - MARGIN - 10
    n = max(0, min(len(rest), (avail + gap) // (card_h + gap)))
    rest = rest[:n]
    top_upset = find_upset(rest)
    for m in rest:
        y = _match_card(
            img, draw, fonts, y, m,
            h=card_h, name_fonts=(fonts.cell_name, fonts.cell_name_sm, fonts.cell_name_xs),
            score_font=fonts.cell_score, sup_font=fonts.cell_sup,
            meta_font=fonts.cell_meta, flag_h=27, col_w=60,
            tag_upset=(top_upset is not None and m.match_id == top_upset.match_id),
            show_tournament=not single_event,
        ) + gap
    _footer(draw, fonts)
    return img


def _card_china(
    fonts: _Fonts, date_label: str, results: list[Match], today: list[Match]
) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "中国军团", "TEAM CHINA")
    results = results[:3]
    today = today[: max(0, 5 - len(results))]  # 总块数 ≤5
    n = len(results) + len(today)
    lead, gap = _spread(n, block_h=_BLOCK_H - 20)
    y += lead
    if results:
        draw.text((MARGIN + 4, y), "— 昨日战报 —", font=fonts.label, fill=GREY)
        y += 52
        for m in results:
            main, score = _split_result(m)
            y = _panel_block(draw, fonts, y, _match_label(m), main, score, accent=True) + gap
    if today:
        draw.text((MARGIN + 4, y), "— 今日出场（北京时间）—", font=fonts.label, fill=GREY)
        y += 52
        for m in today:
            main = (
                f"{fmt_time_beijing(m.start_utc)} "
                f"{side_display(m.home, short_en=True)} vs {side_display(m.away, short_en=True)}"
            )
            y = _panel_block(draw, fonts, y, _match_label(m), main, accent=True) + gap
    _footer(draw, fonts)
    return img


def _card_tonight(fonts: _Fonts, date_label: str, matches: list[Match]) -> Image.Image:
    group = group_by_tournament(matches)[0]
    matches = group.matches
    img, draw, y = _page(fonts, date_label, group.name_zh, "TONIGHT'S FOCUS")
    first = matches[0].tournament
    surface = surface_zh(first.surface or tournament_surface(first.name)) or "场地待核"
    draw.text(
        (MARGIN + 4, y),
        f"{group.compact_level} · {surface}",
        font=fonts.label,
        fill=ACCENT,
    )
    y += 48
    lead, gap = _spread(len(matches), block_h=_BLOCK_H_NOSUB)
    y += lead
    for m in matches:
        stars = stay_up_stars(m)
        y = _panel_block(
            draw, fonts, y,
            label=f"{_match_label(m)} · {fmt_time_beijing(m.start_utc)}",
            main=(
                f"{side_display(m.home, short_en=True)} vs "
                f"{side_display(m.away, short_en=True)}"
            ),
            accent=is_chinese_involved(m),
            tag="★" * stars,
            tag_color=STAR_PILL if stars < 4 else STAR_PILL_HOT,
        ) + gap
    _footer(draw, fonts)
    return img


def _hero_cta(draw, fonts, y: int, lines: list[str], cta: str) -> int:
    """互动区：大字问题 + 居中仿按钮."""
    for text in lines:
        for chunk in _wrap_text(draw, _strip(text), fonts.section, W - 2 * MARGIN - 20, 2):
            draw.text((MARGIN + 10, y), chunk, font=fonts.section, fill=WHITE)
            y += 74
        y += 8
    y += 30
    tw = draw.textlength(cta, font=fonts.main)
    bx0 = (W - tw - 96) / 2
    draw.rounded_rectangle([bx0, y, bx0 + tw + 96, y + 92], radius=46, fill=BALL)
    draw.text((bx0 + 48, y + 20), cta, font=fonts.main, fill=BTN_TEXT)
    return y + 92


def _card_upset(fonts: _Fonts, date_label: str, m: Match) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "昨夜冷门", "UPSET ALERT", accent=RED)
    y += 60
    main, score = _split_result(m)
    y = _panel_block(draw, fonts, y, _match_label(m), main, score, tag="冷门")
    y += 70
    winners = m.winner_players() or []
    w_name = player_zh(winners[0].name) if winners else "黑马"
    if w_name.isascii():
        w_name = w_name.split()[-1]  # 未翻译的英文名只留姓氏
    _hero_cta(
        draw, fonts, y,
        [f"{w_name}爆了个大冷", "你看好这匹黑马能走多远？"],
        "评论区聊聊",
    )
    _footer(draw, fonts)
    return img


def _card_topic(fonts: _Fonts, date_label: str, m: Match) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "今日竞猜", "MATCH POLL")
    y += 60
    y = _panel_block(
        draw, fonts, y,
        label=f"{_match_label(m)} · {fmt_time_beijing(m.start_utc)} 开打",
        main=(
            f"{side_display(m.home, short_en=True, with_flag=False)} vs "
            f"{side_display(m.away, short_en=True, with_flag=False)}"
        ),
        accent=True,
    )
    y += 70
    _hero_cta(
        draw, fonts, y,
        ["你猜谁赢？", "猜中的今晚一起庆祝"],
        "评论区扣 1 或 2",
    )
    _footer(draw, fonts)
    return img


def _card_end(fonts: _Fonts, date_label: str) -> Image.Image:
    """收尾 CTA 卡（card-xiaohongshu 规范：总结 + 关注/收藏/评论引导）."""
    img, draw = _canvas()
    _draw_ball(draw, W // 2, 360, 120)
    y = 560
    for text, font, color in (
        ("今天的网球时差", fonts.title, WHITE),
        ("就倒到这里", fonts.title, WHITE),
    ):
        tw = draw.textlength(text, font=font)
        draw.text(((W - tw) / 2, y), text, font=font, fill=color)
        y += 110
    y += 16
    sub = "每天早间更新 · 发布前人工确认"
    tw = draw.textlength(sub, font=fonts.subtitle)
    draw.text(((W - tw) / 2, y), sub, font=fonts.subtitle, fill=GREY)
    y += 110

    # 三个引导药丸
    pills = ["点赞", "收藏", "评论"]
    pill_w, pill_h, gap = 200, 76, 28
    total = len(pills) * pill_w + (len(pills) - 1) * gap
    px = (W - total) / 2
    for label in pills:
        draw.rounded_rectangle(
            [px, y, px + pill_w, y + pill_h], radius=38,
            outline=OUTLINE, width=3,
        )
        tw = draw.textlength(label, font=fonts.body)
        draw.text((px + (pill_w - tw) / 2, y + 16), label, font=fonts.body, fill=WHITE)
        px += pill_w + gap
    y += pill_h + 70

    cta = f"关注 @{BRAND}"
    tw = draw.textlength(cta, font=fonts.main)
    bx0 = (W - tw - 120) / 2
    draw.rounded_rectangle([bx0, y, bx0 + tw + 120, y + 100], radius=50, fill=BALL)
    draw.text((bx0 + 60, y + 24), cta, font=fonts.main, fill=BTN_TEXT)
    _footer(draw, fonts)
    return img


def _card_rankings(fonts: _Fonts, date_label: str, rankings) -> Image.Image:
    """周一排名卡：两巡回赛 Top5 + 中国球员动态."""
    from .common import CHINESE_PLAYER_NAMES

    img, draw, y = _page(fonts, date_label, "本周排名", "WEEKLY RANKINGS")

    def arrow(e) -> tuple[str, tuple]:
        if e.move > 0:
            return f"↑{e.move}", ACCENT
        if e.move < 0:
            return f"↓{-e.move}", RED
        return "—", GREY

    def section(title: str, entries, y: int) -> int:
        draw.text((MARGIN + 4, y), title, font=fonts.label, fill=GREY)
        y += 46
        x0, x1 = MARGIN, W - MARGIN
        panel_h = len(entries) * 56 + 24
        draw.rounded_rectangle([x0, y, x1, y + panel_h], radius=18, fill=PANEL)
        ry = y + 12
        for e in entries:
            name = player_zh(e.name)
            mark, color = arrow(e)
            draw.text((x0 + 28, ry), f"{e.rank}", font=fonts.score, fill=ACCENT)
            draw.text(
                (x0 + 116, ry), _fit(draw, name, fonts.score, 470),
                font=fonts.score, fill=WHITE,
            )
            if e.points:
                draw.text((x0 + 620, ry + 6), f"{int(e.points)}分", font=fonts.label, fill=GREY)
            tw = draw.textlength(mark, font=fonts.score)
            draw.text((x1 - tw - 28, ry), mark, font=fonts.score, fill=color)
            ry += 56
        return y + panel_h + 30

    y = section("— ATP Top5 —", rankings.atp[:5], y)
    y = section("— WTA Top5 —", rankings.wta[:5], y)
    cn = sorted(
        (
            e for e in rankings.atp + rankings.wta
            if player_zh(e.name) in CHINESE_PLAYER_NAMES
        ),
        key=lambda e: e.rank,
    )[:5]
    if cn:
        y = section("— 中国球员 —", cn, y)
    _footer(draw, fonts)
    return img


def generate_flash_card(m: Match, outpath: str | Path, headline: str) -> Path:
    """单场热点首图：强钩子、比分证据和一句判断。"""
    from .hotspot import hotspot_reasons
    from .story import result_insight

    set_theme(os.environ.get("TENNISLIVE_THEME", "dark"))
    outpath = Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fonts = _Fonts()
    img, draw, y = _page(
        fonts,
        "刚刚结束",
        "热点闪报",
        "BREAK POINT · JUST IN",
        accent=RED,
        deco="court",
        title_font=fonts.display_title,
    )

    group = group_by_tournament([m])[0]
    badge = group.compact_level
    badge_font = fonts.latin if badge.isascii() else fonts.en
    badge_w = draw.textlength(badge, font=badge_font)
    draw.rounded_rectangle(
        [MARGIN, y, MARGIN + badge_w + 36, y + 48],
        radius=10,
        fill=ACCENT,
    )
    draw.text((MARGIN + 18, y + 6), badge, font=badge_font, fill=BTN_TEXT)
    reason = " · ".join(hotspot_reasons(m)[:3])
    reason_w = draw.textlength(reason, font=fonts.small)
    draw.text((W - MARGIN - reason_w, y + 8), reason, font=fonts.small, fill=GREY)
    y += 72

    for chunk in _flash_headline_lines(
        draw,
        headline,
        fonts.display_title,
        W - 2 * MARGIN,
    ):
        draw.text((MARGIN, y), chunk, font=fonts.display_title, fill=ACCENT)
        y += 102
    y += 18

    main, score = _split_result(m)
    y = _panel_block(
        draw,
        fonts,
        y,
        label=f"{group.compact_title}·{match_round_display(m)}".rstrip("·"),
        main=main,
        sub=score,
        accent=is_chinese_involved(m),
        tag="刚刚",
    )

    y += 24
    draw.text((MARGIN, y), "一句看懂 · WHY IT MATTERS", font=fonts.en, fill=RED)
    y += 52
    insight = _strip(result_insight(m))
    for chunk in _wrap_text(draw, insight, fonts.body, W - 2 * MARGIN, 3):
        draw.text((MARGIN, y), chunk, font=fonts.body, fill=WHITE)
        y += 52

    cta = "这场结果符合你的预期吗？"
    cta_w = draw.textlength(cta, font=fonts.label)
    cta_y = min(y + 34, H - MARGIN - 120)
    draw.rounded_rectangle(
        [MARGIN, cta_y, MARGIN + cta_w + 44, cta_y + 58],
        radius=29,
        outline=OUTLINE,
        width=3,
    )
    draw.text((MARGIN + 22, cta_y + 11), cta, font=fonts.label, fill=ACCENT)
    _footer(draw, fonts, "完赛后快速看懂，不堆数据")
    from .image_output import save_social_image

    return save_social_image(img, outpath)


def generate_cards(digest: Digest, outdir: str | Path) -> list[Path]:
    """生成晨报 5 卡，返回文件路径列表（内容不足时自动省略）."""
    from .titles import pick_headline_auto

    set_theme(os.environ.get("TENNISLIVE_THEME", "dark"))
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("card_*.*"):
        if old.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            old.unlink()

    from .image_output import save_social_image

    fonts = _Fonts()
    date_label = _date_label(digest.today)

    # 优先整组 HTML/Chromium 精细排版。生产环境启用严格封面后，封面
    # 选择和最终卡片是一项原子操作：任一步失败都不能退回到另一张图。
    cover_fetch_enabled = os.environ.get(
        "TENNISLIVE_COVER_VISUAL_FETCH", "off"
    ).lower() in {"1", "on", "true"}
    strict_cover = os.environ.get(
        "TENNISLIVE_COVER_VISUAL_STRICT", "off"
    ).lower() in {"1", "on", "true"}
    cover_report_path = outdir.parent / "cover_visual.json"
    cover_report: dict | None = None
    cover_visual = None
    cover_fallback_reason: str | None = None
    try:
        from .webcards import generate_deck

        theme = os.environ.get("TENNISLIVE_THEME", "dark")
        visual_cache = outdir.parent / ".cover-visual-cache"
        if strict_cover and not cover_fetch_enabled:
            raise RuntimeError("严格封面模式要求启用头条比赛图片核验")
        if cover_fetch_enabled:
            from ..research.visual_sources import resolve_match_cover_visual
            from .titles import daily_lead_match

            lead = daily_lead_match(digest)
            if lead is None and strict_cover:
                cover_fallback_reason = "no-bindable-headline-match"
            if lead is not None:
                cover_visual, cover_report = resolve_match_cover_visual(lead, visual_cache)
                cover_report_path.write_text(
                    json.dumps(cover_report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                if strict_cover and cover_visual is None:
                    cover_fallback_reason = ";".join(
                        str(item) for item in (cover_report or {}).get("errors", [])
                    ) or "no-qualified-headline-match-photo"
        images = generate_deck(
            digest, date_label, theme, cover_visual=cover_visual,
        )
        paths: list[Path] = []
        cover_path: Path | None = None
        for i, (kind, img) in enumerate(images):
            p = save_social_image(img, outdir / f"card_{i:02d}_{kind}")
            paths.append(p)
            if kind == "cover":
                cover_path = p

        if strict_cover:
            if cover_report is None:
                cover_report = {
                    "schema_version": 2,
                    "status": "fallback",
                    "match_id": "",
                    "match_players": [],
                    "fallback_reason": cover_fallback_reason or "no-cover-report",
                    "quality_score": 0,
                    "quality": {"status": "fallback", "hard_failures": []},
                }
            if cover_visual is None:
                cover_report.update(
                    status="fallback",
                    fallback_reason=cover_fallback_reason or "no-qualified-headline-match-photo",
                    quality_score=0,
                    quality={"status": "fallback", "hard_failures": []},
                )
            if cover_path is None or cover_path.name != "card_00_cover.jpg":
                raise RuntimeError("严格封面模式未生成唯一的 card_00_cover.jpg")
            source_path = Path(
                cover_visual.path
                if cover_visual is not None
                else ASSETS / "covers" / "tennis-night-court.png"
            )
            if not source_path.is_file():
                raise RuntimeError("严格封面模式的已核验原图在渲染后不可用")
            source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
            card_sha256 = hashlib.sha256(cover_path.read_bytes()).hexdigest()
            cover_report["selected_asset_sha256"] = source_sha256
            cover_report["render_binding"] = {
                "status": "bound",
                "renderer": "html-chromium",
                "match_id": cover_report.get("match_id", ""),
                "selected_asset_sha256": source_sha256,
                "card_file": f"cards/{cover_path.name}",
                "card_sha256": card_sha256,
            }
            cover_report_path.write_text(
                json.dumps(cover_report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if visual_cache.exists():
            import shutil

            shutil.rmtree(visual_cache, ignore_errors=True)
        logger.info("生成 %d 张晨报卡片（HTML 渲染）到 %s", len(paths), outdir)
        return paths
    except Exception as e:  # noqa: BLE001
        if strict_cover:
            if cover_report is not None:
                cover_report["render_binding"] = {
                    "status": "render_failed",
                    "renderer": "html-chromium",
                    "match_id": cover_report.get("match_id", ""),
                    "error": str(e),
                }
                cover_report_path.write_text(
                    json.dumps(cover_report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            raise RuntimeError(
                f"严格封面模式下 HTML 卡片渲染失败: {e}"
            ) from e
        logger.warning("HTML 渲染不可用，回退 Pillow 版卡片: %s", e)

    images: list[tuple[str, Image.Image]] = []
    headline = pick_headline_auto(digest)
    images.append(("cover", _cover(fonts, digest, headline)))

    singles_results = [m for m in digest.results if m.is_singles]
    if len(singles_results) >= 4:
        board = top_results(singles_results, 8)
        images.append(("scoreboard", _card_scoreboard(fonts, date_label, board)))
    elif singles_results:
        # 赛果少：大块 hero 版式（仍是赛果页，不叫 focus——焦点页已从卡组移除）
        board = top_results(singles_results, 3)
        images.append(("results", _card_focus(fonts, date_label, board)))

    tonight_events = tonight_event_focus(digest.schedule)
    if tonight_events:
        for index, event_matches in enumerate(tonight_events, start=1):
            kind = "tonight" if index == 1 else f"tonight{index}"
            images.append((kind, _card_tonight(fonts, date_label, event_matches)))

    # 周一排名日：排名每周一更新
    if digest.today.weekday() == 0 and digest.rankings is not None:
        try:
            images.append(
                ("rankings", _card_rankings(fonts, date_label, digest.rankings))
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("排名卡生成失败（跳过）: %s", e)

    paths: list[Path] = []
    for i, (kind, img) in enumerate(images):
        p = save_social_image(img, outdir / f"card_{i:02d}_{kind}")
        paths.append(p)
    logger.info("生成 %d 张晨报卡片到 %s", len(paths), outdir)
    return paths
