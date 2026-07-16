"""晨报卡片图生成（Pillow）：小红书 3:4 竖版（1080x1440）.

固定 5 卡结构（内容不足时自动省略对应卡片）：
  1. 封面        —— 品牌 + 日期 + 今日焦点
  2. 昨夜焦点    —— 评分最高的 3 场赛果（rating.py 规则）
  3. 中国军团    —— 中国球员昨日赛果 + 今日出场
  4. 今晚看球    —— 推荐 3-5 场 + 熬夜指数
  5. 冷门/话题   —— 昨夜最大冷门；没有冷门则生成互动竞猜

需要中文字体：按 TENNISLIVE_FONT 环境变量 → 项目 fonts/ 目录 →
系统 Noto CJK 路径的顺序查找。CI 中 apt 安装 fonts-noto-cjk 即可。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..digest import Digest
from ..models import Match
from ..timeutil import fmt_time_beijing
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

BRAND = "网球早餐局"
COLUMN = "网球晨报"

# 配色：深绿底 + 网球荧光黄
BG = (11, 38, 31)
PANEL = (18, 54, 44)
PANEL_LINE = (28, 74, 61)
ACCENT = (204, 255, 0)
WHITE = (245, 248, 246)
GREY = (156, 175, 168)
RED = (255, 107, 87)

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

        self.title = load(bold, b_idx, 76)
        self.huge = load(bold, b_idx, 170)
        self.subtitle = load(regular, r_idx, 40)
        self.section = load(bold, b_idx, 46)
        self.label = load(regular, r_idx, 28)
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


def _draw_ball(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    draw.arc(
        [cx - int(r * 1.7), cy - r, cx - int(r * 0.1), cy + r],
        start=-60, end=60, fill=BG, width=max(3, r // 9),
    )
    draw.arc(
        [cx + int(r * 0.1), cy - r, cx + int(r * 1.7), cy + r],
        start=120, end=240, fill=BG, width=max(3, r // 9),
    )


def _page(fonts: _Fonts, date_label: str, column_title: str, accent=ACCENT):
    """新建一页并画页眉，返回 (img, draw, 内容起始 y)."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_ball(draw, MARGIN + 26, MARGIN + 30, 24)
    draw.text((MARGIN + 70, MARGIN), BRAND, font=fonts.section, fill=WHITE)
    tl = draw.textlength(date_label, font=fonts.small)
    draw.text((W - MARGIN - tl, MARGIN + 14), date_label, font=fonts.small, fill=GREY)
    y = MARGIN + 92
    draw.text((MARGIN, y), column_title, font=fonts.title, fill=accent)
    y += 108
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    return img, draw, y + 36


def _footer(draw: ImageDraw.ImageDraw, fonts: _Fonts, text: str = "") -> None:
    line = text or "数据来自公开比分接口 · 时间为北京时间"
    tl = draw.textlength(line, font=fonts.small)
    draw.text(((W - tl) / 2, H - MARGIN - 20), line, font=fonts.small, fill=GREY)


def _match_label(m: Match) -> str:
    g = group_by_tournament([m])[0]
    r = match_round_display(m)
    return f"{g.name_zh}{('·' + r) if r else ''}"


def _block(
    draw: ImageDraw.ImageDraw,
    fonts: _Fonts,
    y: int,
    label: str,
    main: str,
    sub: str = "",
    accent: bool = False,
    tag: str = "",
) -> int:
    """一场比赛的内容块：小标签 + 主行 + 副行；返回新的 y."""
    content_w = W - 2 * MARGIN
    x = MARGIN + 20
    top = y
    # 标签行
    draw.text((x, y), _fit(draw, label, fonts.label, content_w - 220), font=fonts.label, fill=GREY)
    if tag:
        tw = draw.textlength(tag, font=fonts.label)
        draw.rounded_rectangle(
            [W - MARGIN - tw - 36, y - 4, W - MARGIN - 8, y + 36],
            radius=8, fill=RED if tag == "冷门" else PANEL_LINE,
        )
        draw.text((W - MARGIN - tw - 22, y), tag, font=fonts.label, fill=WHITE)
    y += 44
    # 主行
    color = ACCENT if accent else WHITE
    draw.text((x, y), _fit(draw, _strip(main), fonts.main, content_w - 40), font=fonts.main, fill=color)
    y += 58
    # 副行（比分/看点）
    if sub:
        draw.text((x, y), _fit(draw, _strip(sub), fonts.score, content_w - 40), font=fonts.score, fill=GREY)
        y += 52
    # 左侧竖线装饰
    draw.rectangle([MARGIN, top + 4, MARGIN + 6, y - 10], fill=ACCENT if accent else PANEL_LINE)
    return y + 34


def _split_result(m: Match) -> tuple[str, str]:
    """赛果拆成 (对阵行, 比分行)."""
    line = result_line(m, short_en=True)
    if "（" in line:
        main, _, score = line.partition("（")
        return main.strip(), score.rstrip("）")
    return line, ""


def _cover(fonts: _Fonts, digest: Digest, headline: str) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_ball(draw, W - 180, 240, 96)
    d = digest.today
    draw.text((MARGIN, 180), BRAND, font=fonts.subtitle, fill=GREY)
    draw.text((MARGIN, 250), f"{d.month}.{d.day}", font=fonts.huge, fill=WHITE)
    draw.text((MARGIN, 460), COLUMN, font=fonts.title, fill=ACCENT)
    draw.text(
        (MARGIN, 570), "昨夜赛果，今晨看懂", font=fonts.subtitle, fill=GREY
    )

    y = 700
    draw.line([MARGIN, y, W - MARGIN, y], fill=PANEL_LINE, width=3)
    y += 48
    draw.text((MARGIN, y), "今日焦点", font=fonts.section, fill=WHITE)
    y += 82
    draw.text(
        (MARGIN, y),
        _fit(draw, _strip(headline), fonts.section, W - 2 * MARGIN),
        font=fonts.section,
        fill=ACCENT,
    )
    y += 110
    stats = []
    if digest.results:
        stats.append(f"昨夜赛果 {len(digest.results)} 场")
    if digest.schedule:
        stats.append(f"今日赛程 {len(digest.schedule)} 场")
    if stats:
        draw.text((MARGIN, y), " · ".join(stats), font=fonts.subtitle, fill=WHITE)
    _footer(draw, fonts)
    return img


def _spread(n_blocks: int, est_block: int = 190) -> tuple[int, int]:
    """按块数计算 (起始下移, 块间额外间距)，让少量内容垂直居中更饱满."""
    available = H - 330 - MARGIN - 60  # 页眉下方到页脚上方
    rest = available - n_blocks * est_block
    if rest <= 0:
        return 0, 0
    extra = min(70, rest // (n_blocks + 1))
    return extra, extra


def _card_focus(fonts: _Fonts, date_label: str, matches: list[Match]) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "昨夜焦点")
    lead, gap = _spread(len(matches))
    y += lead
    for m in matches:
        main, score = _split_result(m)
        tag = "冷门" if find_upset([m]) else ""
        y = _block(
            draw, fonts, y,
            label=_match_label(m),
            main=main,
            sub=score,
            accent=is_chinese_involved(m),
            tag=tag,
        ) + gap
    _footer(draw, fonts)
    return img


def _card_china(
    fonts: _Fonts, date_label: str, results: list[Match], today: list[Match]
) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "中国军团")
    results = results[:3]
    today = today[: max(0, 5 - len(results))]  # 总块数 ≤5，避免顶到页脚
    n = len(results) + len(today)
    lead, gap = _spread(n, est_block=190)
    y += lead
    if results:
        draw.text((MARGIN, y), "— 昨日战报 —", font=fonts.label, fill=GREY)
        y += 52
        for m in results:
            main, score = _split_result(m)
            y = _block(draw, fonts, y, _match_label(m), main, score, accent=True) + gap
    if today:
        draw.text((MARGIN, y), "— 今日出场（北京时间）—", font=fonts.label, fill=GREY)
        y += 52
        for m in today:
            main = (
                f"{fmt_time_beijing(m.start_utc)} "
                f"{side_display(m.home, short_en=True)} vs {side_display(m.away, short_en=True)}"
            )
            y = _block(draw, fonts, y, _match_label(m), main, accent=True) + gap
    _footer(draw, fonts)
    return img


def _card_tonight(fonts: _Fonts, date_label: str, matches: list[Match]) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "今晚看球")
    lead, gap = _spread(len(matches), est_block=150)
    y += lead
    for m in matches:
        stars = "★" * stay_up_stars(m) + "☆" * (5 - stay_up_stars(m))
        main = (
            f"{fmt_time_beijing(m.start_utc)}  "
            f"{side_display(m.home, short_en=True)} vs {side_display(m.away, short_en=True)}"
        )
        y = _block(
            draw, fonts, y,
            label=f"{_match_label(m)}　熬夜指数 {stars}",
            main=main,
            accent=is_chinese_involved(m),
        ) + gap
    _footer(draw, fonts)
    return img


def _card_upset(fonts: _Fonts, date_label: str, m: Match) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "昨夜冷门", accent=RED)
    main, score = _split_result(m)
    winners = m.winner_players() or []
    losers = m.loser_players() or []
    y += 10
    y = _block(draw, fonts, y, _match_label(m), main, score, tag="冷门")
    y += 20
    w_name = player_zh(winners[0].name) if winners else "胜者"
    l_name = player_zh(losers[0].name) if losers else "对手"
    lines = [
        f"{w_name} 掀翻 {l_name}",
        "你看好这匹黑马能走多远？",
        "评论区聊聊 👇",
    ]
    for text in lines:
        draw.text((MARGIN + 20, y), _strip(text), font=fonts.section, fill=WHITE)
        y += 84
    _footer(draw, fonts)
    return img


def _card_rankings(fonts: _Fonts, date_label: str, rankings) -> Image.Image:
    """周一排名卡：两巡回赛 Top5 + 中国球员动态."""
    from .common import CHINESE_PLAYER_NAMES

    img, draw, y = _page(fonts, date_label, "本周排名")

    def arrow(e) -> tuple[str, tuple]:
        if e.move > 0:
            return f"↑{e.move}", ACCENT
        if e.move < 0:
            return f"↓{-e.move}", RED
        return "—", GREY

    def section(title: str, entries, y: int) -> int:
        draw.text((MARGIN, y), title, font=fonts.label, fill=GREY)
        y += 46
        for e in entries:
            name = player_zh(e.name)
            mark, color = arrow(e)
            draw.text((MARGIN + 20, y), f"{e.rank}", font=fonts.score, fill=ACCENT)
            draw.text((MARGIN + 100, y), _fit(draw, name, fonts.score, 520), font=fonts.score, fill=WHITE)
            if e.points:
                pts = f"{int(e.points)}分"
                draw.text((MARGIN + 640, y), pts, font=fonts.label, fill=GREY)
            tw = draw.textlength(mark, font=fonts.score)
            draw.text((W - MARGIN - tw - 20, y), mark, font=fonts.score, fill=color)
            y += 56
        return y + 26

    y = section("— ATP Top5 —", rankings.atp[:5], y)
    y = section("— WTA Top5 —", rankings.wta[:5], y)
    cn = sorted(
        (
            e for e in rankings.atp + rankings.wta
            if player_zh(e.name) in CHINESE_PLAYER_NAMES
        ),
        key=lambda e: e.rank,
    )[:6]
    if cn:
        y = section("— 中国球员 —", cn, y)
    _footer(draw, fonts)
    return img


def _card_topic(fonts: _Fonts, date_label: str, m: Match) -> Image.Image:
    img, draw, y = _page(fonts, date_label, "今日竞猜")
    y += 20
    main = (
        f"{side_display(m.home, short_en=True, with_flag=False)} vs "
        f"{side_display(m.away, short_en=True, with_flag=False)}"
    )
    y = _block(
        draw, fonts, y,
        label=f"{_match_label(m)} · {fmt_time_beijing(m.start_utc)} 开打",
        main=main,
        accent=True,
    )
    y += 30
    for text in ("你猜谁赢？", "评论区扣 1 或 2", "猜中的今晚一起庆祝 🎉"):
        draw.text((MARGIN + 20, y), _strip(text), font=fonts.section, fill=WHITE)
        y += 84
    _footer(draw, fonts)
    return img


def generate_flash_card(m: Match, outpath: str | Path, headline: str) -> Path:
    """单场比赛的「赛后速报」卡（闪发模式用）."""
    outpath = Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fonts = _Fonts()
    img, draw, y = _page(fonts, "赛后速报", "刚刚结束", accent=RED)
    y += 60
    main, score = _split_result(m)
    y = _block(
        draw, fonts, y,
        label=_match_label(m),
        main=main,
        sub=score,
        accent=is_chinese_involved(m),
        tag="速报",
    )
    y += 40
    for chunk in _wrap_text(draw, _strip(headline), fonts.section, W - 2 * MARGIN - 20):
        draw.text((MARGIN + 20, y), chunk, font=fonts.section, fill=ACCENT)
        y += 76
    y += 30
    draw.text(
        (MARGIN + 20, y), "完整战报见明晨《网球晨报》", font=fonts.body, fill=GREY
    )
    _footer(draw, fonts)
    img.save(outpath, "PNG")
    return outpath


def _wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines[:3]


def generate_cards(digest: Digest, outdir: str | Path) -> list[Path]:
    """生成晨报 5 卡，返回文件路径列表（内容不足时自动省略）."""
    from .titles import pick_headline_auto

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("card_*.png"):
        old.unlink()

    fonts = _Fonts()
    d = digest.today
    date_label = f"{d.year}-{d.month:02d}-{d.day:02d}"

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
