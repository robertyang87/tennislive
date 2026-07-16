"""晨报卡片图生成（Pillow）：小红书 3:4 竖版（1080x1440）.

视觉体系（小红书审美）：
- 深绿渐变背景 + 右上装饰弧线，品牌网球荧光黄做强调色
- 每场比赛一个圆角面板（中国球员场次用荧光黄描边高亮）
- 栏目头中英混排（大黄字 + 英文小字），日期用 "7.16 · 周四"
- 内容少时自动垂直居中，不留大面积空白

固定 5 卡结构（内容不足时自动省略对应卡片）：
  封面 / 昨夜焦点 / 中国军团 / 今晚看球 / 冷门或竞猜（周一附排名卡）
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..digest import Digest
from ..models import Match
from ..timeutil import WEEKDAY_ZH, fmt_time_beijing
from ..zh import player_zh
from .common import (
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .rating import find_upset, stay_up_stars, top_results, top_schedule

logger = logging.getLogger(__name__)

W, H = 1080, 1440
MARGIN = 64

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
        RED=(233, 84, 62),
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
    project_fonts = Path(__file__).resolve().parents[3] / "fonts"
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

        def load(path: str, idx: int, size: int) -> ImageFont.FreeTypeFont:
            return ImageFont.truetype(path, size=size, index=idx)

        self.title = load(bold, b_idx, 78)
        self.huge = load(bold, b_idx, 170)
        self.subtitle = load(regular, r_idx, 40)
        self.section = load(bold, b_idx, 48)
        self.label = load(regular, r_idx, 28)
        self.en = load(bold, b_idx, 24)
        self.main = load(bold, b_idx, 42)
        self.score = load(bold, b_idx, 36)
        self.body = load(regular, r_idx, 34)
        self.small = load(regular, r_idx, 26)


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


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """渐变背景 + 右上装饰弧线."""
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line([(0, y), (W, y)], fill=c)
    # 装饰：右上角大圆弧（比背景略亮的绿，低调纹理感）
    deco = DECO
    draw.arc([W - 460, -300, W + 320, 480], start=60, end=250, fill=deco, width=56)
    draw.arc([W - 320, -220, W + 220, 320], start=60, end=260, fill=deco, width=30)
    return img, draw


def _date_label(d) -> str:
    return f"{d.month}.{d.day} · {WEEKDAY_ZH[d.weekday()]}"


def _page(fonts: _Fonts, date_label: str, column_title: str, en_sub: str, accent=None):
    """新建一页并画页眉，返回 (img, draw, 内容起始 y)."""
    img, draw = _canvas()
    _draw_ball(draw, MARGIN + 26, MARGIN + 30, 24)
    draw.text((MARGIN + 70, MARGIN), BRAND, font=fonts.section, fill=WHITE)
    tl = draw.textlength(date_label, font=fonts.small)
    draw.text((W - MARGIN - tl, MARGIN + 16), date_label, font=fonts.small, fill=GREY)
    y = MARGIN + 96
    draw.text((MARGIN, y), en_sub, font=fonts.en, fill=GREY)
    y += 40
    draw.text((MARGIN, y), column_title, font=fonts.title, fill=accent or ACCENT)
    y += 112
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    return img, draw, y + 40


def _footer(draw: ImageDraw.ImageDraw, fonts: _Fonts, text: str = "") -> None:
    line = text or "数据来自公开比分接口 · 时间为北京时间"
    tl = draw.textlength(line, font=fonts.small)
    draw.text(((W - tl) / 2, H - MARGIN - 20), line, font=fonts.small, fill=FOOT)


def _match_label(m: Match) -> str:
    g = group_by_tournament([m])[0]
    r = match_round_display(m)
    return f"{g.name_zh}{('·' + r) if r else ''}"


_PAD = 26  # 面板内边距


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
    inner_h = 44 + 58 + (50 if sub else 0) + 2 * _PAD - 20
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
    ty += 46
    color = ACCENT if accent else WHITE
    draw.text(
        (tx, ty), _fit(draw, _strip(main), fonts.main, x1 - tx - _PAD),
        font=fonts.main, fill=color,
    )
    ty += 60
    if sub:
        draw.text(
            (tx, ty), _fit(draw, _strip(sub), fonts.score, x1 - tx - _PAD),
            font=fonts.score, fill=SCORE_GREY,
        )
    return y + inner_h + 24


_BLOCK_H = 44 + 58 + 50 + 2 * _PAD - 20 + 24   # 带副行的面板总高
_BLOCK_H_NOSUB = _BLOCK_H - 50


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
    img, draw = _canvas()
    _draw_ball(draw, W - 190, 250, 100)
    d = digest.today
    draw.text((MARGIN, 170), f"{BRAND} · TENNIS JETLAG", font=fonts.en, fill=GREY)
    draw.text((MARGIN, 220), f"{d.month}.{d.day}", font=fonts.huge, fill=WHITE)
    wd = WEEKDAY_ZH[d.weekday()]
    tl = draw.textlength(f"{d.month}.{d.day}", font=fonts.huge)
    draw.text((MARGIN + tl + 24, 340), wd, font=fonts.subtitle, fill=GREY)
    draw.text((MARGIN, 440), COLUMN, font=fonts.title, fill=ACCENT)
    draw.text(
        (MARGIN, 556), "替你熬夜看网球 · 昨夜赛果，今晨看懂",
        font=fonts.subtitle, fill=GREY,
    )

    y = 690
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    y += 44
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
    img, draw, y = _page(fonts, date_label, "今晚看球", "TONIGHT'S PICKS")
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
    """单场比赛的「赛后速报」卡（闪发模式用）."""
    set_theme(os.environ.get("TENNISLIVE_THEME", "dark"))
    outpath = Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fonts = _Fonts()
    img, draw, y = _page(fonts, "刚刚结束", "赛后速报", "FLASH REPORT", accent=RED)
    y += 80
    main, score = _split_result(m)
    y = _panel_block(
        draw, fonts, y,
        label=_match_label(m),
        main=main,
        sub=score,
        accent=is_chinese_involved(m),
        tag="速报",
    )
    y += 70
    for chunk in _wrap_text(draw, _strip(headline), fonts.section, W - 2 * MARGIN - 20, 3):
        draw.text((MARGIN + 10, y), chunk, font=fonts.section, fill=ACCENT)
        y += 74
    y += 40
    draw.text(
        (MARGIN + 10, y), "完整战报见明晨《网球晨报》", font=fonts.body, fill=GREY
    )
    _footer(draw, fonts)
    img.save(outpath, "PNG")
    return outpath


def generate_cards(digest: Digest, outdir: str | Path) -> list[Path]:
    """生成晨报 5 卡，返回文件路径列表（内容不足时自动省略）."""
    from .titles import pick_headline_auto

    set_theme(os.environ.get("TENNISLIVE_THEME", "dark"))
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("card_*.png"):
        old.unlink()

    fonts = _Fonts()
    date_label = _date_label(digest.today)

    images: list[tuple[str, Image.Image]] = []
    headline = pick_headline_auto(digest)
    images.append(("cover", _cover(fonts, digest, headline)))

    focus = top_results([m for m in digest.results if m.is_singles], 3)
    if focus:
        images.append(("focus", _card_focus(fonts, date_label, focus)))

    cn_results = [m for m in digest.results if is_chinese_involved(m)]
    cn_today = [
        m for m in digest.schedule + digest.live if is_chinese_involved(m)
    ]
    if cn_results or cn_today:
        images.append(
            ("china", _card_china(fonts, date_label, cn_results, cn_today))
        )

    tonight = top_schedule([m for m in digest.schedule if m.is_singles], 5)
    if tonight:
        images.append(("tonight", _card_tonight(fonts, date_label, tonight)))

    # 周一排名日：排名每周一更新
    if digest.today.weekday() == 0 and digest.rankings is not None:
        try:
            images.append(
                ("rankings", _card_rankings(fonts, date_label, digest.rankings))
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("排名卡生成失败（跳过）: %s", e)

    upset = find_upset(digest.results)
    if upset:
        images.append(("upset", _card_upset(fonts, date_label, upset)))
    elif tonight:
        images.append(("topic", _card_topic(fonts, date_label, tonight[0])))

    paths: list[Path] = []
    for i, (kind, img) in enumerate(images):
        p = outdir / f"card_{i:02d}_{kind}.png"
        img.save(p, "PNG")
        paths.append(p)
    logger.info("生成 %d 张晨报卡片到 %s", len(paths), outdir)
    return paths
