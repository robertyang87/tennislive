"""赛果卡片图生成（Pillow）：小红书 3:4 竖版（1080x1440）.

需要中文字体：按 TENNISLIVE_FONT 环境变量 → 项目 fonts/ 目录 →
系统 Noto CJK 路径的顺序查找。CI 中 apt 安装 fonts-noto-cjk 即可。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..digest import Digest
from ..models import Match
from ..timeutil import fmt_time_beijing
from .common import group_by_tournament, match_round_display, result_line, side_display
from .wechat import pick_headline

logger = logging.getLogger(__name__)

W, H = 1080, 1440
MARGIN = 64

# 配色：深绿底 + 网球荧光黄
BG = (11, 38, 31)
PANEL = (18, 54, 44)
PANEL_LINE = (28, 74, 61)
ACCENT = (204, 255, 0)
WHITE = (245, 248, 246)
GREY = (156, 175, 168)

_FONT_CANDIDATES = [
    # (路径, ttc 内的字体索引)
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
        return _find_font(bold=False)  # 找不到粗体时退回常规体
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

        self.title = load(bold, b_idx, 76)
        self.huge = load(bold, b_idx, 170)
        self.subtitle = load(regular, r_idx, 40)
        self.section = load(bold, b_idx, 46)
        self.tournament = load(bold, b_idx, 38)
        self.body = load(regular, r_idx, 34)
        self.body_bold = load(bold, b_idx, 34)
        self.small = load(regular, r_idx, 28)
        self.badge = load(bold, b_idx, 28)


def _fit(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _draw_ball(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    """画一个简化的网球（圆 + 弧线）."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    draw.arc(
        [cx - int(r * 1.7), cy - r, cx - int(r * 0.1), cy + r],
        start=-60, end=60, fill=BG, width=max(3, r // 9),
    )
    draw.arc(
        [cx + int(r * 0.1), cy - r, cx + int(r * 1.7), cy + r],
        start=120, end=240, fill=BG, width=max(3, r // 9),
    )


@dataclass
class CardLine:
    left: str      # 左侧标签：时间或轮次
    main: str      # 主文本：对阵或赛果
    accent: bool = False  # 是否高亮（如中国球员）


@dataclass
class CardSection:
    title: str          # 赛事名
    lines: list[CardLine]


def _header(draw: ImageDraw.ImageDraw, fonts: _Fonts, date_label: str, page_title: str) -> int:
    """画页眉，返回内容起始 y."""
    _draw_ball(draw, MARGIN + 30, MARGIN + 34, 26)
    draw.text((MARGIN + 78, MARGIN), "网球每日速报", font=fonts.section, fill=WHITE)
    tl = draw.textlength(date_label, font=fonts.small)
    draw.text((W - MARGIN - tl, MARGIN + 12), date_label, font=fonts.small, fill=GREY)
    y = MARGIN + 92
    draw.text((MARGIN, y), page_title, font=fonts.title, fill=ACCENT)
    y += 110
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    return y + 28


def _footer(draw: ImageDraw.ImageDraw, fonts: _Fonts, page: int, pages: int) -> None:
    text = f"数据来自公开比分接口 · 时间为北京时间 · {page}/{pages}"
    tl = draw.textlength(text, font=fonts.small)
    draw.text(((W - tl) / 2, H - MARGIN - 20), text, font=fonts.small, fill=GREY)


def _paginate(sections: list[CardSection], per_page: int = 12) -> list[list[CardSection]]:
    """按行数分页；一场赛事的行可以跨页（重复赛事标题）."""
    pages: list[list[CardSection]] = []
    cur: list[CardSection] = []
    used = 0
    for sec in sections:
        remaining = sec.lines[:]
        while remaining:
            cap = per_page - used - 1  # 赛事标题占 1 行
            if cap <= 0:
                pages.append(cur)
                cur, used = [], 0
                continue
            take = remaining[:cap]
            remaining = remaining[cap:]
            cur.append(CardSection(title=sec.title, lines=take))
            used += 1 + len(take)
    if cur:
        pages.append(cur)
    return pages


def _render_page(
    fonts: _Fonts,
    date_label: str,
    page_title: str,
    sections: list[CardSection],
    page: int,
    pages: int,
) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    y = _header(draw, fonts, date_label, page_title)

    line_h = 62
    sec_title_h = 74
    content_w = W - 2 * MARGIN

    for sec in sections:
        # 赛事标题条
        draw.rounded_rectangle(
            [MARGIN, y, W - MARGIN, y + sec_title_h - 16],
            radius=10,
            fill=PANEL,
        )
        draw.rectangle([MARGIN, y, MARGIN + 8, y + sec_title_h - 16], fill=ACCENT)
        draw.text(
            (MARGIN + 28, y + 8),
            _fit(draw, sec.title, fonts.tournament, content_w - 56),
            font=fonts.tournament,
            fill=ACCENT,
        )
        y += sec_title_h
        for line in sec.lines:
            left_w = 150
            if line.left:
                draw.text((MARGIN + 16, y + 8), line.left, font=fonts.badge, fill=GREY)
            main_font = fonts.body_bold if line.accent else fonts.body
            color = ACCENT if line.accent else WHITE
            draw.text(
                (MARGIN + left_w + 14, y + 4),
                _fit(draw, line.main, main_font, content_w - left_w - 40),
                font=main_font,
                fill=color,
            )
            y += line_h
        y += 20

    _footer(draw, fonts, page, pages)
    return img


def _cover(fonts: _Fonts, digest: Digest) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    _draw_ball(draw, W - 180, 240, 96)
    d = digest.today
    draw.text((MARGIN, 200), f"{d.year}", font=fonts.subtitle, fill=GREY)
    draw.text((MARGIN, 260), f"{d.month}.{d.day}", font=fonts.huge, fill=WHITE)
    draw.text((MARGIN, 470), "网球每日速报", font=fonts.title, fill=ACCENT)
    draw.text(
        (MARGIN, 580),
        "WTA / ATP 巡回赛 · 赛果与赛程",
        font=fonts.subtitle,
        fill=GREY,
    )

    y = 720
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    y += 48
    headline = pick_headline(digest)
    draw.text((MARGIN, y), "今日焦点", font=fonts.section, fill=WHITE)
    y += 80
    draw.text(
        (MARGIN, y),
        _fit(draw, headline, fonts.section, W - 2 * MARGIN),
        font=fonts.section,
        fill=ACCENT,
    )
    y += 110

    stats = []
    if digest.results:
        stats.append(f"昨日赛果 {len(digest.results)} 场")
    if digest.schedule:
        stats.append(f"今日赛程 {len(digest.schedule)} 场")
    if stats:
        draw.text((MARGIN, y), " · ".join(stats), font=fonts.subtitle, fill=WHITE)

    _footer(draw, fonts, 1, 1)
    return img


def _result_sections(matches: list[Match]) -> list[CardSection]:
    sections = []
    for group in group_by_tournament(matches):
        lines = []
        for m in group.matches:
            r = match_round_display(m)
            lines.append(
                CardLine(
                    left=(r or "")[:6],
                    main=result_line(m).replace("（", " (").replace("）", ")"),
                    accent=_has_chinese(m),
                )
            )
        sections.append(CardSection(title=group.title, lines=lines))
    return sections


def _schedule_sections(matches: list[Match]) -> list[CardSection]:
    sections = []
    for group in group_by_tournament(matches):
        lines = []
        for m in group.matches:
            lines.append(
                CardLine(
                    left=fmt_time_beijing(m.start_utc),
                    main=f"{side_display(m.home)} vs {side_display(m.away)}",
                    accent=_has_chinese(m),
                )
            )
        sections.append(CardSection(title=group.title, lines=lines))
    return sections


def _has_chinese(m: Match) -> bool:
    from .wechat import _is_chinese_involved

    return _is_chinese_involved(m)


def generate_cards(digest: Digest, outdir: str | Path) -> list[Path]:
    """生成封面 + 赛果页 + 赛程页，返回文件路径列表."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fonts = _Fonts()
    d = digest.today
    date_label = f"{d.year}-{d.month:02d}-{d.day:02d} 北京时间"

    images: list[tuple[str, Image.Image]] = [("card_00_cover.png", _cover(fonts, digest))]

    result_pages = _paginate(_result_sections(digest.results)) if digest.results else []
    for i, page_secs in enumerate(result_pages):
        img = _render_page(
            fonts, date_label, "昨日赛果", page_secs, i + 1, len(result_pages)
        )
        images.append((f"card_1{i}_results.png", img))

    schedule_pages = (
        _paginate(_schedule_sections(digest.schedule)) if digest.schedule else []
    )
    for i, page_secs in enumerate(schedule_pages):
        img = _render_page(
            fonts, date_label, "今日赛程", page_secs, i + 1, len(schedule_pages)
        )
        images.append((f"card_2{i}_schedule.png", img))

    paths: list[Path] = []
    for name, img in images:
        p = outdir / name
        img.save(p, "PNG")
        paths.append(p)
    logger.info("生成 %d 张卡片图到 %s", len(paths), outdir)
    return paths
