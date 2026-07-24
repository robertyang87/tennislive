"""HTML/CSS + Chromium 截图渲染的整组晨报卡（大满贯节目册质感）.

Pillow 排印能力有限（无阴影/字距/字重控制），整组卡片用真正的
网页排版引擎渲染 1080x1440 竖版图：

- 深松绿渐变底 + 极淡球场线稿，暖象牙白内容卡 + 香槟金细节
- 封面标题用得意黑，正文思源黑体，比分用 Barlow Condensed
  转播体数字（全部子集化 base64 内嵌，本地与 CI 渲染一致）
- 球员中文名为主 + 小字英文原名；每盘一列严格对齐
- 一次浏览器会话渲染全组卡片；浏览器不可用时调用方回退 Pillow
"""

from __future__ import annotations

import base64
import html
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from ..digest import Digest
from ..models import Match
from ..research.media import brief_for_match
from ..timeutil import fmt_schedule_time, fmt_time_beijing
from ..zh import player_zh, surface_zh
from ..zh.tournaments import tournament_surface
from ..zh.countries import country_iso2
from .common import (
    _abbrev_en,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
)
from .focus import focus_comparison, has_detailed_stats
from .narrative import editor_takeaway, preview_angle
from .rating import (
    editorial_tonight_focus,
    find_upset,
    is_tour_focus_match,
    is_upset,
    match_score,
    tonight_event_focus,
    top_results,
)
from .story import (
    chinese_side_won,
    is_chinese_player,
    recommendation_label,
    result_insight,
    sort_china_matches,
)
from .titles import daily_lead_match
from .tournament_story import (
    TournamentStory,
    direct_story_for_match,
)
from .venue_assets import venue_asset_for_match

logger = logging.getLogger(__name__)

W, H = 1080, 1440
ASSETS = Path(__file__).resolve().parents[3] / "assets"

_LOCAL_PLAYER_COVER_FRAMING = {
    # Per-photo editorial crop: keep the athlete large while preserving head,
    # racket/trophy, and enough court context for a 3:4 poster.
    "jannik-sinner.jpg": ("50% 78%", "auto 180%"),
    "carlos-alcaraz.jpg": ("36% 44%", "cover"),
    "zheng-qinwen.jpg": ("32% 52%", "auto 125%"),
    "aryna-sabalenka.jpg": ("50% 30%", "cover"),
    "iga-swiatek.jpg": ("50% 30%", "cover"),
    "coco-gauff.jpg": ("50% 30%", "cover"),
    "novak-djokovic.jpg": ("50% 26%", "cover"),
    "stefanos-tsitsipas.jpg": ("50% 28%", "cover"),
}

# ---------- 资源内嵌（自包含 HTML，避免 file:// 子资源限制） ----------


@lru_cache(maxsize=32)
def _b64(path: Path) -> str | None:
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except OSError:
        return None


def _asset_image_uri(path: Path) -> str | None:
    data = _b64(path)
    if not data:
        return None
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{data}"


@lru_cache(maxsize=1)
def _font_css() -> str:
    css = []
    faces = [
        ("Barlow Condensed", 500, "BarlowCondensed-Medium.ttf"),
        ("Barlow Condensed", 600, "BarlowCondensed-SemiBold.ttf"),
        ("Barlow Condensed", 700, "BarlowCondensed-Bold.ttf"),
        # 子集化的思源字体（tools/build_fonts.py 产出），本地与 CI 渲染一致
        ("TL Serif SC", 900, "NotoSerifSC-Black-sub.ttf"),
        ("TL Sans SC", 700, "NotoSansSC-Bold-sub.ttf"),
        ("TL Sans SC", 400, "NotoSansSC-Regular-sub.ttf"),
    ]
    for family, weight, fname in faces:
        b = _b64(ASSETS / "fonts" / fname)
        if b:
            css.append(
                f"@font-face{{font-family:'{family}';font-weight:{weight};"
                f"src:url(data:font/ttf;base64,{b}) format('truetype');}}"
            )
    display_font = _b64(ASSETS / "fonts" / "SmileySans-Oblique.woff2")
    if display_font:
        css.append(
            "@font-face{font-family:'TL Display SC';font-weight:400;"
            f"src:url(data:font/woff2;base64,{display_font}) format('woff2');}}"
        )
    return "\n".join(css)


def _flag_uri(country: str | None) -> str | None:
    iso2 = country_iso2(country)
    if not iso2:
        return None
    b = _b64(ASSETS / "flags" / f"{iso2.lower()}.png")
    return f"data:image/png;base64,{b}" if b else None


def _icon_uri(name: str) -> str | None:
    b = _b64(ASSETS / "icons" / f"{name}.svg")
    return f"data:image/svg+xml;base64,{b}" if b else None


def _icon_html(name: str, *, alt: str = "") -> str:
    uri = _icon_uri(name)
    if not uri:
        return ""
    return f'<img class="ui-icon" src="{uri}" alt="{html.escape(alt)}"/>'


_HEADLINE_BREAK_AFTER = frozenset("，；：！？｜")
_HEADLINE_CLOSING = frozenset("，。！？；：、）】》〉」』”’…")
_HEADLINE_OPENING = frozenset("（【《〈「『“‘")


def _headline_display_width(text: str) -> float:
    """Approximate display width well enough to choose a balanced punctuation break."""
    width = 0.0
    for char in text:
        if char.isspace():
            width += 0.3
        elif char.isascii() and (char.isalnum() or char in "-+/&"):
            width += 0.56
        elif char in _HEADLINE_BREAK_AFTER or char in _HEADLINE_CLOSING:
            width += 0.55
        else:
            width += 1.0
    return width


def _balanced_headline_lines(headline: str) -> list[str]:
    """Prefer a balanced break after Chinese punctuation on long cover titles."""
    explicit = [line.strip() for line in headline.splitlines() if line.strip()]
    if len(explicit) > 1:
        return explicit
    text = explicit[0] if explicit else ""
    total = _headline_display_width(text)
    if total < 12:
        return [text]
    candidates: list[tuple[float, int]] = []
    for index, char in enumerate(text[:-1], start=1):
        if char not in _HEADLINE_BREAK_AFTER:
            continue
        left = _headline_display_width(text[:index])
        right = _headline_display_width(text[index:])
        if min(left, right) < 4:
            continue
        candidates.append((abs(left - right), index))
    if not candidates:
        return [text]
    _, split_at = min(candidates)
    return [text[:split_at].strip(), text[split_at:].strip()]


def _headline_line_html(line: str) -> str:
    """Keep punctuation with its neighbor and keep the final two glyphs together."""
    units: list[str] = []
    index = 0
    while index < len(line):
        char = line[index]
        if char in _HEADLINE_CLOSING and units:
            units[-1] += char
        elif char in _HEADLINE_OPENING and index + 1 < len(line):
            units.append(char + line[index + 1])
            index += 1
        else:
            units.append(char)
        index += 1
    if not units:
        return ""
    tail_start = max(0, len(units) - 2)
    rendered: list[str] = []
    for unit in units[:tail_start]:
        escaped = html.escape(unit)
        if len(unit) > 1 or any(char in _HEADLINE_CLOSING for char in unit):
            rendered.append(f'<span class="headline-keep">{escaped}</span>')
        else:
            rendered.append(escaped)
    tail = html.escape("".join(units[tail_start:]))
    rendered.append(f'<span class="headline-keep headline-tail">{tail}</span>')
    return "".join(rendered)


def _cover_headline_html(headline: str) -> str:
    """Render a safe, punctuation-aware cover headline without orphan glyphs."""
    return "".join(
        f'<span class="headline-line">{_headline_line_html(line)}</span>'
        for line in _balanced_headline_lines(headline)
    )


def _cover_text_layout(focus: str) -> tuple[str, float, float]:
    """Place cover copy away from the detected athlete focus point.

    The visual QA stage emits a percentage focus derived from the largest face
    (or upper body when the face is turned away). This renderer only needs that
    stable, JSON-safe signal, so the same rule works in headless GitHub Actions.
    """
    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)%\s+([0-9]+(?:\.[0-9]+)?)%",
        focus,
    )
    if match:
        focus_x = max(0.0, min(100.0, float(match.group(1))))
        focus_y = max(0.0, min(100.0, float(match.group(2))))
    else:
        focus_x, focus_y = 50.0, 28.0

    # Put a compact copy column on the opposite side. The visual selector gives
    # clear match-time faces a strong preference, so the title can stay high
    # and concise instead of being pushed into the lower information area.
    text_side = "left" if focus_x >= 50.0 else "right"
    return text_side, focus_x, focus_y


# ---------- 页面骨架 ----------

_COURT_SVG = """<svg class="court" viewBox="0 0 1080 1060" preserveAspectRatio="none">
<g fill="none" stroke="var(--courtline)" stroke-width="3">
<polygon points="-56,1060 1136,1060 799,0 281,0"/>
<line x1="75" y1="1060" x2="338" y2="0"/><line x1="1005" y1="1060" x2="742" y2="0"/>
<line x1="176" y1="657" x2="904" y2="657"/><line x1="540" y1="657" x2="540" y2="0"/>
<line x1="281" y1="0" x2="799" y2="0" stroke-width="8"/>
</g></svg>"""

_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
:root {
  --ground0:#061D17; --ground1:#0B3B2C;
  --ivory:#F7F3E8; --fade:#9AA89F;
  --gold:#D5B44D; --gold-soft:rgba(213,180,77,.38);
  --flash:#F15A3A;
  --neon:#D6FF00; --sky:#76D7EA; --coral:#FF7657;
  --panel:rgba(3,24,19,.82); --panel-strong:rgba(4,30,23,.92);
  --panel-border:rgba(214,255,0,.18); --panel-text:#F6F7F2;
  --panel-muted:#A8B9B1; --panel-soft:rgba(214,255,0,.11);
  --divider:rgba(214,255,0,.17); --score-win:#D6FF00;
  --reason:#CDDBD4;
  --courtline:rgba(255,255,255,.055);
  --cardshadow:0 14px 34px rgba(0,0,0,.42);
  --pagetext:#F7F3EA;
  --section-accent:var(--neon);
}
html.light {
  --ground0:#F2EDE2; --ground1:#E9E2D2;
  --ivory:#FDFCF8; --fade:#95998F;
  --neon:#0B4D33; --courtline:rgba(20,60,40,.08);
  --panel:rgba(253,252,248,.94); --panel-strong:rgba(253,252,248,.98);
  --panel-border:rgba(213,180,77,.34); --panel-text:#142820;
  --panel-muted:#7D8C84; --panel-soft:#DDEED7;
  --divider:rgba(213,180,77,.35); --score-win:#0A7048;
  --reason:#4D6157;
  --cardshadow:0 10px 26px rgba(90,80,50,.16);
  --pagetext:#1E3328;
}
body {
  width:@W@px; height:@H@px; overflow:hidden; position:relative;
  background:linear-gradient(168deg, var(--ground0) 0%, var(--ground1) 100%);
  font-family:'TL Sans SC','Noto Sans CJK SC','Noto Sans SC','WenQuanYi Zen Hei',sans-serif;
  color:var(--pagetext);
}
body::before { content:""; position:absolute; left:0; top:0; width:100%; height:12px;
  background:linear-gradient(90deg,var(--neon) 0 42%,var(--coral) 42% 72%,var(--sky) 72%); }
.court { position:absolute; left:0; bottom:0; width:100%; height:1060px; }
.poster { position:relative; height:100%; padding:40px 64px 24px; display:flex; flex-direction:column; }
.results-page { --section-accent:var(--neon); }
.china-page { --section-accent:var(--coral); }
.tonight-page { --section-accent:var(--sky); }
.focus-page { --section-accent:var(--gold); }
.story-page { --section-accent:var(--coral); }
.rankings-page { --section-accent:var(--gold); }
.insight-page { --section-accent:var(--gold); }
.discussion-page { --section-accent:var(--coral); }
.media-page { --section-accent:var(--sky); }
.poster:not(.cover) { isolation:isolate; }
.poster:not(.cover)::before { content:""; position:absolute; inset:0;
  background:
    linear-gradient(180deg,rgba(1,13,11,.78) 0%,rgba(1,13,11,.5) 34%,rgba(1,13,11,.82) 100%),
    linear-gradient(90deg,rgba(1,13,11,.48) 0%,rgba(1,13,11,.08) 75%),
    var(--inner-bg) center 48%/cover no-repeat;
  opacity:.72; pointer-events:none; }
html.light .poster:not(.cover)::before { opacity:.16; }
.poster:not(.cover)>* { position:relative; z-index:1; }

.poster.tonight-page::before {
  background:
    linear-gradient(180deg,rgba(2,16,20,.16) 0%,rgba(2,16,20,.22) 30%,rgba(2,20,18,.42) 58%,rgba(2,20,18,.76) 100%),
    var(--page-bg,var(--inner-bg)) var(--page-bg-pos,center 42%)/cover no-repeat;
  opacity:1;
}
html.light .poster.tonight-page::before { opacity:.52; }

.masthead { display:flex; flex:none; align-items:center; gap:16px; }
.brand-icon { width:54px; height:54px; object-fit:contain; flex:none; }
.ball { width:44px; height:44px; border-radius:50%; background:var(--neon); position:relative; overflow:hidden; flex:none; }
.ball::before, .ball::after { content:""; position:absolute; width:36px; height:36px; border:4px solid var(--ground0); border-radius:50%; }
.ball::before { left:-22px; top:4px; } .ball::after { right:-22px; top:4px; }
.brand { font-weight:700; font-size:34px; letter-spacing:2px; line-height:1.2; }
.poster:not(.cover) .brand { font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:40px; font-weight:400; letter-spacing:0; }
.date { margin-left:auto; font-family:'Barlow Condensed','TL Sans SC',sans-serif; font-weight:600; font-size:30px; letter-spacing:2px; color:var(--fade); }

.titleband { flex:none; margin:20px 0 16px; padding-left:18px; border-left:6px solid var(--section-accent); }
.titleband.compact h1 { font-size:64px; line-height:1.1; }
.poster:not(.cover)>.save-badge { position:absolute; top:126px; right:64px; padding:7px 13px;
  border:1px solid var(--section-accent); border-radius:5px;
  color:var(--section-accent); font-size:19px; font-weight:700; line-height:1.2; }
.kicker { font-family:'Barlow Condensed'; font-weight:600; font-size:26px; line-height:1.1;
  letter-spacing:.36em; text-transform:uppercase; color:var(--section-accent); }
h1 { font-family:'TL Display SC','TL Sans SC',sans-serif; font-size:82px; font-weight:400;
  letter-spacing:0; line-height:1.08; color:var(--section-accent); margin-top:5px;
  text-shadow:0 6px 24px rgba(0,0,0,.28); }

.event { display:flex; align-items:center; gap:18px; margin:-6px 0 22px; }
.event i { flex:1; height:1px; background:var(--gold-soft); }
.event span { font-size:30px; font-weight:700; color:var(--pagetext); letter-spacing:2px; line-height:1.2; }

.card { background:var(--panel); color:var(--panel-text); border:1px solid var(--panel-border);
  border-radius:8px; box-shadow:var(--cardshadow); padding:10px 30px 12px;
  margin-bottom:12px; backdrop-filter:blur(14px); }
.card.hero { background:var(--panel-strong); border-top:3px solid var(--gold);
  padding:16px 34px 18px; }

.card header { display:flex; align-items:center; justify-content:space-between;
  height:42px; border-bottom:1px solid var(--divider); }
.hero header { height:52px; }
.hl { display:flex; align-items:center; gap:14px; }
.round { font-size:24px; color:var(--panel-muted); letter-spacing:1px; }
.tour { display:flex; align-items:center; justify-content:flex-end; gap:8px;
  min-width:0; max-width:54%; font-size:24px; color:var(--panel-muted); letter-spacing:1px; }
.tour-level { flex:none; padding:3px 8px 4px; border-radius:4px; background:var(--section-accent);
  color:#082018; font-family:'Barlow Condensed'; font-size:19px; font-weight:700;
  line-height:1; letter-spacing:.04em; }
html.light .tour-level { color:#fff; }
.tour-name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.htime { font-family:'Barlow Condensed'; font-weight:600; font-size:30px; color:var(--gold); letter-spacing:1px; }
.rating { font-size:20px; font-weight:700; color:#082018; background:var(--section-accent);
  padding:4px 11px; border-radius:5px; letter-spacing:1px; display:inline-flex;
  align-items:center; gap:6px; }
.ui-icon { width:20px; height:20px; flex:none; object-fit:contain; }
.rating .ui-icon { width:19px; height:19px; filter:brightness(0) saturate(100%); }
.chip { font-size:24px; font-weight:700; color:#fff; padding:5px 16px 6px; border-radius:6px; }
.chip-green { background:var(--neon); color:#0B2018; }
html.light .chip-green { color:#fff; }
.chip-red { background:var(--flash); }
.chip-gold { background:var(--gold); color:#241D0A; }
.chip-sm { font-size:20px; padding:3px 12px 4px; }

.set-index { display:grid; grid-template-columns:1fr repeat(var(--sets), 88px);
  height:28px; align-items:end; padding-bottom:3px; }
.set-index i { font-family:'Barlow Condensed'; font-weight:600; font-size:22px;
  font-style:normal; color:var(--gold); text-align:center; letter-spacing:1px; line-height:1; }

/* 行高固定，布局与字体度量脱钩（CI 的 Noto 行框远高于本地字体） */
.side { display:grid; grid-template-columns:1fr repeat(var(--sets), 72px);
  align-items:center; border-radius:6px; margin-top:4px; padding:0 14px; height:62px; }
.hero .side { grid-template-columns:1fr repeat(var(--sets), 88px); height:96px; margin-top:6px; }
.side.nosets { grid-template-columns:1fr; height:58px; }
.side.won { background:var(--panel-soft); }
.who { display:flex; align-items:center; gap:12px; min-width:0; }
.names { display:flex; flex-direction:column; justify-content:center; min-width:0; }
.zh { display:flex; align-items:center; gap:8px; min-width:0; }
/* 统一外框 4:3，超宽/方形旗居中裁切；直角矩形展示 */
.flag { width:36px; height:27px; object-fit:cover;
  box-shadow:0 0 0 1px rgba(0,0,0,.12); flex:none; }
.hero .flag { width:48px; height:36px; }
.slash { font-style:normal; font-weight:700; font-size:26px; color:var(--panel-muted); margin:0 2px; }
.seed { font-family:'Barlow Condensed'; font-weight:600; font-style:normal;
  font-size:22px; color:var(--gold); line-height:1;
  width:26px; text-align:right; flex:none; }
.hero .seed { font-size:27px; width:32px; }
.name { font-family:'TL Display SC','TL Sans SC',sans-serif; font-style:normal;
  font-weight:400; font-size:32px; line-height:1.2;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hero .name { font-size:44px; letter-spacing:0; }
.side.lost .name { color:var(--panel-muted); font-weight:400; }
.rank { font-family:'Barlow Condensed'; font-weight:500; font-style:normal;
  font-size:22px; color:var(--panel-muted); line-height:1; }
.hero .rank { font-size:26px; }
.en { font-family:'Barlow Condensed'; font-weight:500; font-size:19px; line-height:1.1;
  letter-spacing:1.2px; color:var(--panel-muted); margin-top:2px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  margin-left:78px; /* 种子槽26+间距8+国旗36+间距8：与中文名左对齐 */ }
.hero .en { font-size:23px; margin-top:4px; margin-left:96px; }
.note { font-style:normal; font-size:22px; color:var(--panel-muted); }
/* 每盘独立强调：赢下该盘的一方数字深绿加粗，输的一方浅灰 */
.set { font-family:'Barlow Condensed'; font-size:42px;
  text-align:center; font-variant-numeric:tabular-nums; line-height:1; }
.hero .set { font-size:62px; }
.set.sw { color:var(--score-win); font-weight:700; }
.set.sl { color:var(--panel-muted); font-weight:500; }
.set sup { font-size:.46em; font-weight:600; vertical-align:.62em; margin-left:1px; }

.footer { margin-top:auto; display:flex; align-items:center; }
.footer b { margin-left:auto; font-size:26px; font-weight:700; color:var(--fade); letter-spacing:2px; line-height:1.2; }
.poster:not(.cover) .footer { position:absolute; left:64px; right:64px; bottom:24px; }

/* ---------- 封面 ---------- */
.cover { overflow:hidden; color:#F7F3EA; }
.cover::before { content:""; position:absolute; inset:0; z-index:1; pointer-events:none;
  background:linear-gradient(180deg,rgba(1,13,11,.08) 0%,rgba(1,13,11,0) 50%,rgba(1,13,11,.04) 76%,rgba(1,13,11,.2) 100%),
    linear-gradient(90deg,rgba(1,13,11,.18) 0%,rgba(1,13,11,.06) 52%,rgba(1,13,11,0) 100%); }
.cover::after { content:""; position:absolute; left:0; right:0; top:0; height:12px; z-index:5;
  background:linear-gradient(90deg,var(--neon) 0 42%,var(--coral) 42% 72%,var(--sky) 72%); }
.cover-bg { position:absolute; inset:0; z-index:0;
  background-size:var(--cover-size,cover); background-position:var(--cover-focus,center);
  background-repeat:no-repeat; background-color:#061D17;
  filter:saturate(1.08) contrast(1.02) brightness(1.08); }
.cover .masthead,.cover .footer { position:relative; z-index:3; }
.cover .brand { font-family:'TL Display SC','TL Sans SC',sans-serif; font-size:42px; font-weight:400; letter-spacing:0; }
.cover .date { color:#D6E3DD; }
.cover-copy { position:relative; z-index:2; width:590px; margin-top:22px;
  padding:12px 18px 18px; border-radius:6px;
  background:linear-gradient(90deg,rgba(2,20,16,.15),rgba(2,20,16,.04) 72%,rgba(2,20,16,0)); }
.cover.cover-text-left .cover-copy { align-self:flex-start; }
.cover.cover-text-right .cover-copy { align-self:flex-end;
  background:linear-gradient(270deg,rgba(2,20,16,.15),rgba(2,20,16,.04) 72%,rgba(2,20,16,0)); }
.edition { display:inline-block; color:var(--neon); font-family:'Barlow Condensed';
  font-size:23px; font-weight:600; letter-spacing:4px; line-height:1.2;
  text-shadow:0 3px 14px rgba(0,0,0,.75); }
.cover .focus { font-family:'TL Display SC','TL Sans SC',sans-serif; font-size:68px; font-weight:400;
  line-height:1.06; letter-spacing:0; margin-top:10px; color:#fff; max-width:550px;
  text-shadow:0 7px 28px rgba(0,0,0,.7); line-break:strict; word-break:normal;
  overflow-wrap:normal; }
.cover .focus .headline-line { display:block; }
.cover .focus .headline-keep { white-space:nowrap; }
.cover.compact-headline .focus { font-size:58px; line-height:1.08; max-width:550px; }
.cover.extra-compact-headline .focus { font-size:51px; line-height:1.1; }
.cover-lower { position:relative; z-index:3; width:900px; margin-top:auto; margin-bottom:20px;
  padding:18px 20px; border-radius:8px; background:rgba(2,20,16,.22);
  backdrop-filter:blur(3px); }
.cover-secondary { margin-bottom:16px; padding-left:14px; border-left:5px solid var(--coral);
  color:#F0F4F1; font-size:25px; font-weight:700; line-height:1.35; max-width:850px;
  text-shadow:0 3px 14px rgba(0,0,0,.7); }
.cover-highlights { display:grid; grid-template-columns:1fr 1fr; gap:24px;
  padding:18px 0 20px; border-top:1px solid rgba(255,255,255,.42);
  border-bottom:1px solid rgba(255,255,255,.32); }
.cover-highlight { min-width:0; }
.cover-highlight + .cover-highlight { padding-left:24px; border-left:1px solid rgba(255,255,255,.24); }
.cover-highlight small { display:block; font-family:'Barlow Condensed'; font-size:20px;
  font-weight:600; letter-spacing:3px; color:var(--sky); text-transform:uppercase; line-height:1.2; }
.cover-highlight small { display:flex; align-items:center; gap:8px; }
.cover-highlight small .ui-icon { width:19px; height:19px; }
.cover-highlight:first-child small { color:var(--coral); }
.cover-highlight b { display:block; margin-top:9px; font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:37px; font-weight:400; color:#fff; line-height:1.12; }
.cover-highlight.compact b { font-size:30px; line-height:1.18; }
.cover-highlight span { display:block; margin-top:8px; color:#C6D2CC; font-size:20px;
  line-height:1.3; }
.cover .footer { margin-top:0; color:#C2CEC8; }
.cover-photo-credit { margin-top:10px; color:#AEBDB6; font-size:14px; line-height:1.3; }

/* ---------- 今晚焦点 ---------- */
.tonight-page h1 { font-size:62px; }
.tonight-page .titleband { margin:16px 0 4px; }
.event-meta { display:flex; align-items:center; gap:14px; min-height:40px; color:#fff; }
.event-meta b { padding:5px 10px; border-radius:4px; background:var(--section-accent);
  color:#09221B; font-family:'Barlow Condensed'; font-size:21px; letter-spacing:1px; }
.event-meta span { font-size:23px; font-weight:700; text-shadow:0 2px 10px rgba(0,0,0,.65); }
.event-meta i { margin-left:auto; font-size:19px; font-style:normal; color:#E4EBE7; }
.event-spacer { height:220px; flex:none; }
.tonight-page.count-1 .event-spacer { height:310px; }
.tonight-page.count-2 .event-spacer { height:230px; }
.tonight-page.count-3 .event-spacer { height:110px; }
.tonight-page.count-4 .event-spacer,
.tonight-page.count-5 .event-spacer { height:30px; }
.court-label { display:flex; align-items:center; gap:12px; height:35px; margin:0 0 7px;
  color:#F5F7F4; font-size:21px; font-weight:700; letter-spacing:1px; }
.court-label::before { content:""; width:24px; height:3px; background:var(--section-accent); }
.china-marker { display:inline-flex; align-items:center; margin-right:8px; padding:3px 8px;
  border:1px solid var(--gold); border-radius:4px; color:var(--gold); font-size:16px;
  line-height:1; vertical-align:2px; }
.venue-credit { position:absolute!important; left:64px; bottom:28px; max-width:500px;
  overflow:hidden; color:#AAB8B1; font-size:15px; line-height:1.2; white-space:nowrap;
  text-overflow:ellipsis; }
.pick { border-left:5px solid var(--sky); padding:7px 26px 8px; margin-bottom:8px; }
.tonight-page .pick {
  background:linear-gradient(90deg,rgba(2,29,23,.72),rgba(2,29,23,.52));
  border-top-color:rgba(118,215,234,.28);
  border-right-color:rgba(118,215,234,.28);
  border-bottom-color:rgba(118,215,234,.28);
  box-shadow:0 10px 24px rgba(0,0,0,.20);
  backdrop-filter:blur(3px) saturate(1.08);
}
.pick header { height:36px; }
.pick header > .hl:first-child { min-width:0; flex:1; }
.pick .round { font-size:22px; }
.pick header .round { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pick .htime { font-size:28px; }
.pick .rating { font-size:18px; padding:3px 9px; }
.pick .rating .ui-icon { width:17px; height:17px; }
.pick .side.nosets { height:55px; margin-top:2px; padding:2px 12px; }
.pick .name { font-size:28px; line-height:1.02; }
.pick .en { margin-top:4px; font-size:15px; line-height:1; letter-spacing:1px; }
.pick .reason { margin:4px 12px 0; padding-top:5px; border-top:1px solid var(--divider);
  font-size:20px; line-height:1.2; color:var(--reason); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pick .reason b { display:inline-flex; align-items:center; gap:6px; margin-right:9px;
  padding:2px 7px 3px; border-radius:4px; background:var(--coral); color:#fff;
  font-size:16px; line-height:1; vertical-align:2px; }
.pick .reason b .ui-icon { width:15px; height:15px; }
.tonight-page.count-3 .pick { padding:12px 26px 16px; margin-bottom:16px; }
.tonight-page.count-3 .pick header { height:44px; }
.tonight-page.count-3 .pick .side.nosets { height:68px; }
.tonight-page.count-3 .pick .name { font-size:30px; }
.tonight-page.count-3 .pick .reason { margin-top:8px; padding-top:9px; min-height:52px;
  font-size:22px; line-height:1.34; white-space:normal; display:-webkit-box;
  -webkit-line-clamp:2; -webkit-box-orient:vertical; }

/* ---------- 栏目段落 ---------- */
.seclabel { display:flex; align-items:center; gap:16px; margin:10px 0 10px; }
.seclabel i { flex:1; height:1px; background:var(--gold-soft); }
.seclabel span { font-size:26px; color:var(--fade); letter-spacing:4px; line-height:1.2; }

/* ---------- 复盘 / 赛事档案 / 收尾 ---------- */
.compare-head { display:grid; grid-template-columns:230px 1fr 1fr; align-items:center;
  margin-top:18px; color:var(--pagetext); font-size:27px; font-weight:700; text-align:center; }
.compare-head span:first-child { text-align:left; color:var(--fade); font-size:23px; }
.compare-grid { margin-top:8px; background:var(--panel); color:var(--panel-text);
  border:1px solid var(--panel-border); border-radius:8px;
  box-shadow:var(--cardshadow); overflow:hidden; backdrop-filter:blur(14px); }
.compare-row { display:grid; grid-template-columns:230px 1fr 1fr; height:59px;
  align-items:center; border-bottom:1px solid var(--divider); text-align:center; }
.compare-row:last-child { border-bottom:0; }
.compare-row b { font-size:21px; color:var(--panel-muted); text-align:left; padding-left:22px; }
.compare-row span { font-family:'Barlow Condensed'; font-size:36px; font-weight:700; }
.compare-row .winner { color:var(--score-win); background:var(--panel-soft); height:100%; display:flex;
  align-items:center; justify-content:center; }
.stats-source { margin-top:10px; color:#AEBBB4; font-size:18px; line-height:1.3;
  text-align:right; letter-spacing:1px; }
.verdict { margin-top:12px; padding:15px 22px; border-left:7px solid var(--gold);
  background:rgba(247,243,232,.1); font-size:25px; line-height:1.42; }
.verdict b { color:var(--gold); margin-right:12px; }
.verdict-quote { margin-top:16px; padding:30px 32px; border-left:none;
  border-radius:10px; background:linear-gradient(135deg, rgba(213,180,77,.2), rgba(213,180,77,.06));
  font-family:'TL Serif SC','TL Sans SC',serif; font-size:36px; line-height:1.52; }
.verdict-quote b { display:block; font-family:'Barlow Condensed'; font-size:22px;
  font-weight:600; letter-spacing:.3em; text-transform:uppercase; margin-bottom:14px; }

.insight-hero { margin-top:18px; padding:28px 30px 30px;
  background:var(--panel-strong); border:1px solid var(--panel-border);
  border-left:7px solid var(--section-accent); border-radius:8px;
  box-shadow:var(--cardshadow); }
.insight-hero .tag-row { display:flex; flex-wrap:wrap; gap:10px; }
.insight-hero strong { display:block; margin-top:14px; font-family:'TL Serif SC','TL Sans SC',serif;
  font-size:44px; line-height:1.48; color:var(--pagetext); }
.fact-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:18px; }
.fact { min-height:150px; padding:20px 18px; background:var(--panel);
  border:1px solid var(--panel-border); border-radius:8px; text-align:center;
  display:flex; flex-direction:column; justify-content:center; box-shadow:var(--cardshadow); }
.fact b { font-family:'Barlow Condensed'; font-size:34px; color:var(--section-accent); line-height:1.05; }
.fact span { margin-top:10px; color:var(--panel-muted); font-size:22px; line-height:1.3; }
.discussion-card { margin-top:74px; padding:42px 46px 48px; background:var(--panel-strong);
  border:1px solid var(--panel-border); border-top:6px solid var(--section-accent);
  border-radius:8px; box-shadow:var(--cardshadow); }
.discussion-card small { font-family:'Barlow Condensed'; font-size:25px; font-weight:600;
  letter-spacing:.3em; color:var(--section-accent); text-transform:uppercase; }
.discussion-card strong { display:block; margin-top:24px; font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:64px; font-weight:400; line-height:1.3; color:var(--pagetext); }
.discussion-card p { margin-top:28px; padding-top:24px; border-top:1px solid var(--divider);
  font-size:27px; line-height:1.5; color:var(--reason); }

.story-page .titleband { margin-bottom:12px; }
.story-page h1 { font-size:86px; }
.venue-photo { position:relative; height:365px; margin-top:0; background-size:cover;
  background-position:center; border:1px solid var(--panel-border); border-radius:8px;
  overflow:hidden; box-shadow:var(--cardshadow); }
.venue-photo::after { content:""; position:absolute; inset:0; background:linear-gradient(180deg,transparent 45%,rgba(4,22,16,.92)); }
/* 竖版人像：完整显示不裁脸，同图模糊铺满做底 */
.venue-photo .ph-back { position:absolute; inset:0; background-size:cover; background-position:center;
  filter:blur(24px) brightness(.68); transform:scale(1.15); }
.venue-photo .ph-main { position:absolute; inset:0; background-size:contain;
  background-repeat:no-repeat; background-position:center; }
.venue-caption { position:absolute; left:24px; right:24px; bottom:20px; z-index:1; }
.venue-caption b { display:block; font-size:34px; color:#fff; line-height:1.2; }
.venue-caption span { display:block; font-size:22px; color:#DDE8E1; margin-top:6px; }
.story-hero { margin-top:24px; font-family:'TL Serif SC',serif; font-size:40px; font-weight:900;
  line-height:1.42; color:var(--pagetext); }
.story-list { margin-top:24px; border-top:2px solid var(--coral); list-style:none; }
.story-list li { display:grid; grid-template-columns:96px 1fr; align-items:center; gap:24px;
  min-height:132px; padding:18px 0; border-bottom:1px solid var(--divider); }
.story-index { font-family:'Barlow Condensed'; font-size:54px; font-weight:700;
  font-style:normal; color:var(--neon); line-height:1; }
.story-copy { min-width:0; padding-left:22px; border-left:1px solid rgba(255,255,255,.42); }
.story-copy strong { display:block; font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:31px; font-weight:400; line-height:1.18; color:var(--pagetext); }
.story-copy p { margin-top:7px; font-size:20px; line-height:1.42; color:var(--reason); }
.photo-credit { font-size:15px; color:var(--fade); margin-top:10px; }

/* ---------- 网球有故事 · 多页知识卡 ---------- */
.knowledge-page { --section-accent:var(--coral); }
.knowledge-page .titleband { margin:18px 0 16px; }
.knowledge-page h1 { font-size:72px; line-height:1.08; }
.knowledge-page .knowledge-kicker { margin-top:22px; color:var(--coral);
  font-family:'Barlow Condensed','TL Sans SC'; font-size:24px; font-weight:600;
  letter-spacing:.26em; text-transform:uppercase; }
.knowledge-photo { position:relative; height:390px; margin-top:18px; overflow:hidden;
  flex:0 0 auto; border:1px solid var(--panel-border); border-radius:8px;
  background:var(--panel-strong); }
.knowledge-photo.compact { height:480px; margin-top:14px; }
.knowledge-photo .kn-back { position:absolute; inset:0; background-size:cover;
  background-position:center; filter:blur(22px) brightness(.58); transform:scale(1.12); }
.knowledge-photo img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain;
  object-position:center; }
.knowledge-photo.portrait img { object-fit:contain; }
.knowledge-photo.wide-cover img { object-fit:cover; }
.knowledge-photo::after { content:""; position:absolute; inset:0;
  background:linear-gradient(180deg,transparent 38%,rgba(2,21,16,.94)); }
.knowledge-photo-copy { position:absolute; z-index:2; left:28px; right:28px; bottom:24px; }
.knowledge-photo-copy small { display:block; color:#D4E0D9; font-size:19px; }
.knowledge-photo-copy strong { display:block; margin-top:7px; color:#fff;
  font-family:'TL Display SC','TL Sans SC'; font-size:36px; font-weight:400; line-height:1.25; }
.knowledge-photo.compact .knowledge-photo-copy { bottom:20px; }
.knowledge-photo.compact .knowledge-photo-copy small { font-size:20px; }
.knowledge-photo.compact .knowledge-photo-copy strong { max-width:820px; font-size:38px; }
.knowledge-cover .knowledge-photo { height:560px; }
.knowledge-cover { isolation:isolate; --cover-focus:50% 28%; }
.knowledge-cover::before {
  background:linear-gradient(180deg,rgba(1,13,11,.08) 0%,rgba(1,13,11,0) 50%,rgba(1,13,11,.04) 76%,rgba(1,13,11,.2) 100%),
    linear-gradient(90deg,rgba(1,13,11,.18) 0%,rgba(1,13,11,.06) 64%,rgba(1,13,11,0) 100%);
}
.knowledge-cover>.knowledge-cover-bg { position:absolute; inset:0; z-index:0;
  background-size:cover; background-position:var(--knowledge-cover-focus,50% 28%);
  filter:saturate(1.08) contrast(1.02) brightness(1.08); }
.knowledge-cover .masthead,.knowledge-cover .knowledge-cover-copy,
.knowledge-cover .knowledge-hook,.knowledge-cover .photo-credit,.knowledge-cover .footer {
  position:relative; z-index:3;
}
.knowledge-cover .knowledge-cover-copy { width:950px; margin-top:54px; padding:4px 18px 18px 0;
  background:linear-gradient(90deg,rgba(2,20,16,.2),rgba(2,20,16,0) 74%); }
.knowledge-cover .knowledge-kicker { margin-top:0; color:var(--neon); text-shadow:0 3px 14px rgba(0,0,0,.7); }
.knowledge-cover h1 { margin-top:16px; max-width:950px; color:#fff; font-size:86px;
  line-height:1.03; text-shadow:0 8px 30px rgba(0,0,0,.78); }
.knowledge-cover .knowledge-hook { margin-top:36px; padding:30px 30px;
  border:1px solid rgba(120,211,220,.26); border-left:7px solid var(--coral);
  border-radius:8px; background:rgba(10,55,44,.88);
  display:grid; grid-template-columns:145px 1fr; gap:32px; align-items:center; }
.knowledge-cover .knowledge-hook { margin-top:auto; margin-bottom:14px;
  background:rgba(3,28,22,.32); backdrop-filter:blur(5px); }
.knowledge-hook b { font-family:'Barlow Condensed'; font-size:65px; color:var(--neon); line-height:1; }
.knowledge-hook p { color:var(--pagetext); font-family:'TL Serif SC','TL Sans SC';
  font-size:31px; font-weight:900; line-height:1.62; }
.knowledge-scene { display:grid; grid-template-columns:180px 1fr; gap:34px; margin-top:38px;
  padding:34px 0 38px; border-top:2px solid var(--coral); border-bottom:1px solid var(--divider); }
.knowledge-scene time { color:var(--neon); font-family:'Barlow Condensed'; font-size:82px;
  font-weight:700; line-height:1; }
.knowledge-scene small { display:block; margin-top:12px; color:var(--coral); font-size:16px;
  font-weight:700; letter-spacing:.16em; }
.knowledge-scene b { display:block; font-family:'TL Display SC','TL Sans SC';
  font-size:34px; font-weight:400; line-height:1.28; }
.knowledge-scene p { margin-top:16px; color:var(--reason); font-size:22px; line-height:1.58; }
.knowledge-story-visual { height:205px; margin-top:38px; overflow:hidden;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider); }
.knowledge-story-visual svg { width:100%; height:100%; }
.knowledge-story-visual .path { fill:none; stroke:var(--sky); stroke-width:6; }
.knowledge-story-visual .node { fill:var(--neon); stroke:#073126; stroke-width:5; }
.knowledge-story-visual .year { fill:var(--ivory); font:700 35px 'Barlow Condensed'; }
.knowledge-story-visual .label { fill:var(--reason); font:18px 'TL Sans SC'; }
.knowledge-timeline { margin-top:34px; border-top:2px solid var(--coral); }
.knowledge-moment { display:grid; grid-template-columns:96px 1fr; gap:24px;
  min-height:174px; padding:28px 0; align-items:center; border-bottom:1px solid var(--divider); }
.knowledge-moment i { font-family:'Barlow Condensed'; font-size:52px; font-weight:700;
  font-style:normal; color:var(--neon); }
.knowledge-moment div { padding-left:28px; border-left:1px solid rgba(255,255,255,.35); }
.knowledge-moment b { display:block; font-family:'TL Display SC','TL Sans SC';
  font-size:38px; font-weight:400; line-height:1.2; }
.knowledge-moment p { margin-top:12px; color:var(--reason); font-size:28px; line-height:1.44; }
.knowledge-verdict { margin-top:31px; padding:25px 27px;
  border:1px solid rgba(120,211,220,.26); border-left:7px solid var(--coral);
  border-radius:8px; background:rgba(10,55,44,.88);
  font-family:'TL Serif SC','TL Sans SC'; color:var(--ivory);
  font-size:36px; font-weight:900; line-height:1.44; }
.has-page-photo .knowledge-timeline { margin-top:16px; }
.has-page-photo .knowledge-moment { min-height:120px; padding:10px 0; }
.has-page-photo .knowledge-moment b { font-size:35px; }
.has-page-photo .knowledge-moment p { margin-top:6px; font-size:27px; line-height:1.38; }
.has-page-photo .knowledge-verdict { margin-top:14px; padding:16px 22px; font-size:33px; line-height:1.36; }
.semantic-marker { min-width:84px; display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:7px; color:var(--neon); }
.semantic-marker svg { width:46px; height:46px; fill:none; stroke:currentColor;
  stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
.semantic-marker small { color:var(--reason); font-family:'TL Sans SC'; font-size:18px;
  font-weight:700; line-height:1; white-space:nowrap; letter-spacing:0; }
.semantic-marker.mini { min-width:auto; flex-direction:row; gap:6px; }
.semantic-marker.mini svg { width:27px; height:27px; }
.semantic-marker.mini small { color:var(--neon); font-size:15px; }
.official-flow { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:24px; }
.official-step { height:292px; padding:19px 21px; overflow:hidden; border-radius:8px;
  border:1px solid var(--panel-border); background:rgba(255,255,255,.035); }
.official-step header { display:flex; align-items:center; gap:11px; }
.official-step header i { color:var(--neon); font-family:'Barlow Condensed';
  font-size:34px; font-weight:700; font-style:normal; }
.official-step header b { font-family:'TL Display SC','TL Sans SC'; font-size:28px;
  font-weight:400; line-height:1.15; }
.official-step header > .official-code { margin-left:auto; color:var(--fade); font-size:14px; }
.official-visual { position:relative; height:198px; margin-top:12px;
  border-top:1px solid var(--divider); }
.official-visual svg { width:100%; height:172px; }
.official-visual p { position:absolute; left:0; right:0; bottom:0; text-align:center;
  color:var(--reason); font-size:17px; line-height:1.3; }
.official-facts { display:grid; grid-template-columns:repeat(3,1fr); margin-top:18px;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider); }
.official-facts div { min-height:104px; padding:16px 18px; border-right:1px solid var(--divider); }
.official-facts div:last-child { border-right:0; }
.official-facts b { display:block; color:var(--coral); font-family:'Barlow Condensed';
  font-size:31px; line-height:1; }
.official-facts span { display:block; margin-top:7px; color:var(--reason); font-size:17px; }
.official-summary { margin-top:17px; padding:17px 20px;
  border:1px solid rgba(120,211,220,.26); border-left:7px solid var(--coral);
  border-radius:8px; background:rgba(10,55,44,.88); color:var(--ivory);
  font-size:20px; line-height:1.42; }
.official-summary b { color:#E85545; }
.marathon-story-visual { margin-top:16px; padding:19px 28px 20px;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider);
  background:rgba(5,42,33,.56); }
.marathon-story-head { display:grid; grid-template-columns:1fr auto; align-items:end;
  gap:24px; }
.marathon-story-head span { display:block; color:var(--sky); font-size:21px;
  font-weight:700; }
.marathon-story-head strong { display:block; margin-top:5px; color:var(--ivory);
  font-family:'Barlow Condensed'; font-size:70px; line-height:.95; }
.marathon-story-head b { color:var(--neon); font-family:'TL Display SC','TL Sans SC';
  font-size:33px; font-weight:400; }
.marathon-days { display:grid; grid-template-columns:repeat(3,1fr); gap:12px;
  margin-top:17px; }
.marathon-day { position:relative; min-height:112px; padding:15px 18px 13px;
  border:1px solid var(--panel-border); border-top:5px solid var(--sky);
  border-radius:7px; background:rgba(255,255,255,.035); }
.marathon-day:nth-child(2) { border-top-color:var(--coral); }
.marathon-day:nth-child(3) { border-top-color:var(--neon); }
.marathon-day time { display:block; color:var(--reason); font-family:'Barlow Condensed';
  font-size:22px; }
.marathon-day strong { display:block; margin-top:9px; color:var(--pagetext);
  font-family:'TL Display SC','TL Sans SC'; font-size:29px; font-weight:400;
  line-height:1.18; }
.marathon-day small { display:block; margin-top:7px; color:var(--reason);
  font-size:17px; line-height:1.25; }
.marathon-rule { margin-top:20px; display:grid; grid-template-columns:1fr 90px 1fr;
  align-items:center; gap:18px; }
.marathon-rule-block { min-height:150px; padding:24px 26px; border-radius:8px;
  border:1px solid var(--panel-border); background:rgba(255,255,255,.035); }
.marathon-rule-block small { display:block; color:var(--sky); font-size:18px;
  font-weight:700; }
.marathon-rule-block strong { display:block; margin-top:12px; color:var(--ivory);
  font-family:'Barlow Condensed'; font-size:52px; line-height:1; }
.marathon-rule-block p { margin-top:10px; color:var(--reason); font-size:22px;
  line-height:1.35; }
.marathon-rule-arrow { color:var(--neon); font-size:55px; text-align:center; }
.marathon-scoreline { margin-top:25px; padding:24px 26px 27px;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider);
  background:rgba(5,42,33,.52); }
.marathon-scoreline header { display:flex; align-items:baseline; justify-content:space-between; }
.marathon-scoreline header span { color:var(--sky); font-size:20px; font-weight:700; }
.marathon-scoreline header b { color:var(--reason); font-size:20px; }
.marathon-sets { display:grid; grid-template-columns:repeat(5,1fr); margin-top:17px; }
.marathon-set { min-height:104px; padding:15px 10px; text-align:center;
  border-right:1px solid var(--divider); }
.marathon-set:last-child { border-right:0; background:rgba(211,255,18,.06); }
.marathon-set small { display:block; color:var(--reason); font-size:16px; }
.marathon-set strong { display:block; margin-top:9px; color:var(--ivory);
  font-family:'Barlow Condensed'; font-size:43px; line-height:1; }
.marathon-set:last-child strong { color:var(--neon); font-size:49px; }
.marathon-records { display:grid; grid-template-columns:repeat(3,1fr); margin-top:25px;
  border-top:1px solid var(--divider); border-bottom:1px solid var(--divider); }
.marathon-record { min-height:180px; padding:27px 22px; text-align:center;
  border-right:1px solid var(--divider); }
.marathon-record:last-child { border-right:0; }
.marathon-record strong { display:block; color:var(--neon);
  font-family:'Barlow Condensed'; font-size:61px; line-height:1; }
.marathon-record b { display:block; margin-top:11px; color:var(--pagetext);
  font-size:24px; }
.marathon-record span { display:block; margin-top:7px; color:var(--reason);
  font-size:18px; line-height:1.3; }
.marathon-summary { margin-top:26px; padding:23px 25px;
  border-left:7px solid var(--coral); border-radius:8px;
  background:rgba(10,55,44,.88); color:var(--ivory);
  font-family:'TL Serif SC','TL Sans SC'; font-size:30px; font-weight:900;
  line-height:1.42; }
.marathon-event-photo { position:relative; height:480px; margin-top:14px;
  overflow:hidden; border:1px solid var(--panel-border); border-radius:8px;
  background-size:cover; background-position:var(--marathon-focus,50% 42%); }
.marathon-event-photo::after { content:""; position:absolute; inset:0;
  background:linear-gradient(180deg,transparent 34%,rgba(2,21,16,.9)); }
.marathon-event-photo div { position:absolute; z-index:1; left:28px; right:28px;
  bottom:22px; }
.marathon-event-photo small { display:block; color:var(--sky); font-size:19px;
  font-weight:700; }
.marathon-event-photo strong { display:block; margin-top:7px; color:#fff;
  font-family:'TL Display SC','TL Sans SC'; font-size:37px; font-weight:400; }
.marathon-event-photo + .marathon-scoreline { margin-top:14px; padding-top:18px; padding-bottom:18px; }
.marathon-event-photo + .marathon-scoreline .marathon-set { min-height:90px; padding-top:11px; padding-bottom:11px; }
.marathon-event-photo ~ .marathon-records { margin-top:18px; }
.marathon-event-photo ~ .marathon-records .marathon-record { min-height:150px; padding-top:20px; padding-bottom:18px; }
.marathon-event-photo ~ .marathon-summary { margin-top:18px; padding-top:18px; padding-bottom:18px; }
.marathon-today-visual { margin-top:38px; padding:34px 32px;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider);
  background:rgba(5,42,33,.5); }
.marathon-era { display:grid; grid-template-columns:150px 1fr; gap:26px;
  align-items:center; min-height:172px; }
.marathon-era + .marathon-era { margin-top:16px; padding-top:20px;
  border-top:1px solid var(--divider); }
.marathon-era time { color:var(--neon); font-family:'Barlow Condensed';
  font-size:57px; font-weight:700; line-height:1; }
.marathon-era b { display:block; color:var(--pagetext);
  font-family:'TL Display SC','TL Sans SC'; font-size:32px; font-weight:400; }
.marathon-era p { margin-top:8px; color:var(--reason); font-size:23px;
  line-height:1.4; }
.knowledge-fact-grid { display:grid; grid-template-columns:1fr; gap:0; margin-top:40px;
  border-top:2px solid var(--coral); }
.knowledge-fact-card { min-height:238px; padding:34px 28px; display:grid;
  grid-template-columns:118px 1fr; gap:32px; align-items:center;
  border-bottom:1px solid var(--divider); background:transparent; }
.knowledge-fact-card i { color:var(--sky); font-family:'Barlow Condensed';
  font-size:72px; font-weight:700; font-style:normal; }
.knowledge-fact-card p { margin:0; color:var(--pagetext); font-size:32px; line-height:1.5; }
.has-page-photo .knowledge-fact-grid { margin-top:14px; }
.has-page-photo .knowledge-fact-card { min-height:154px; padding:16px 24px;
  grid-template-columns:120px 1fr; gap:22px; }
.knowledge-fact-card .semantic-marker { color:var(--sky); }
.has-page-photo .knowledge-fact-card p { font-size:29px; line-height:1.4; }
.player-pillars { display:grid; grid-template-columns:repeat(3,1fr); margin-top:42px;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider); }
.player-pillar { min-height:550px; padding:50px 28px 38px; border-right:1px solid var(--divider); }
.player-pillar:last-child { border-right:0; }
.player-pillar em { display:block; color:var(--neon); font-family:'Barlow Condensed';
  font-size:112px; font-weight:700; font-style:normal; line-height:1; }
.player-pillar small { display:block; margin-top:7px; color:var(--coral); font-size:15px;
  font-weight:700; letter-spacing:.15em; }
.player-pillar p { margin-top:30px; color:var(--pagetext); font-size:29px; line-height:1.5; }
.has-page-photo .player-pillars { margin-top:18px; }
.has-page-photo .player-pillar { min-height:315px; padding:26px 25px 24px; }
.has-page-photo .player-pillar em { font-size:82px; }
.has-page-photo .player-pillar p { margin-top:16px; font-size:27px; line-height:1.42; }
.event-profile { display:grid; grid-template-columns:repeat(3,1fr); margin-top:42px;
  border-top:2px solid var(--coral); border-bottom:1px solid var(--divider); }
.event-profile article { min-height:230px; padding:35px 28px; border-right:1px solid var(--divider); }
.event-profile article:last-child { border-right:0; }
.event-profile em { display:block; color:var(--neon); font-family:'Barlow Condensed';
  font-size:54px; font-weight:700; font-style:normal; line-height:1.05; }
.event-profile span { display:block; margin-top:18px; color:var(--reason); font-size:19px; }
.event-notes { margin-top:34px; border-top:1px solid var(--divider); }
.event-note { display:grid; grid-template-columns:96px 1fr; gap:24px; min-height:170px;
  padding:27px 0; align-items:center; border-bottom:1px solid var(--divider); }
.event-note i { color:var(--sky); font-family:'Barlow Condensed'; font-size:48px;
  font-weight:700; font-style:normal; }
.event-note p { color:var(--pagetext); font-size:28px; line-height:1.46; }
.has-page-photo .event-profile { margin-top:24px; }
.has-page-photo .event-profile article { min-height:170px; padding:26px 24px; }
.has-page-photo .event-profile em { font-size:43px; }
.has-page-photo .event-notes { margin-top:20px; display:grid;
  grid-template-columns:repeat(3,1fr); }
.has-page-photo .event-note { min-height:238px; padding:20px 18px; display:flex;
  flex-direction:column; align-items:flex-start; gap:13px; border-right:1px solid var(--divider); }
.has-page-photo .event-note:last-child { border-right:0; }
.has-page-photo .event-note .semantic-marker { min-width:0; flex-direction:row; }
.has-page-photo .event-note .semantic-marker svg { width:38px; height:38px; }
.has-page-photo .event-note p { font-size:27px; line-height:1.4; }
.explainer-mark { height:115px; margin-top:34px; border-top:2px solid var(--coral);
  border-bottom:1px solid var(--divider); }
.explainer-mark svg { width:100%; height:100%; }
.explainer-mark path { fill:none; stroke:var(--sky); stroke-width:5; }
.explainer-mark circle { fill:var(--neon); stroke:#073126; stroke-width:4; }
.knowledge-years { margin-top:38px; padding-left:50px; position:relative; }
.knowledge-years::before { content:""; position:absolute; left:17px; top:12px; bottom:12px;
  width:3px; background:linear-gradient(var(--coral),var(--sky),var(--neon)); }
.knowledge-year { position:relative; display:grid; grid-template-columns:150px 1fr; gap:18px;
  min-height:182px; padding:13px 0 30px; }
.knowledge-year::before { content:""; position:absolute; left:-41px; top:16px; width:16px;
  height:16px; border-radius:50%; background:var(--neon);
  box-shadow:0 0 0 7px rgba(211,255,18,.13); }
.knowledge-year time { font-family:'Barlow Condensed'; font-size:56px; color:var(--neon); line-height:1; }
.knowledge-year b { display:block; font-family:'TL Display SC','TL Sans SC';
  font-size:38px; font-weight:400; }
.knowledge-year p { margin-top:10px; color:var(--reason); font-size:28px; line-height:1.44; }
.knowledge-years.count-2 .knowledge-year { min-height:245px; padding-top:22px; }
.today-visual { height:155px; margin-top:36px; border-top:2px solid var(--coral);
  border-bottom:1px solid var(--divider); }
.today-visual svg { width:100%; height:100%; }
.today-visual line { stroke:var(--sky); stroke-width:5; }
.today-visual circle { fill:var(--neon); stroke:#073126; stroke-width:5; }
.today-visual text { fill:var(--ivory); font:700 31px 'Barlow Condensed'; }
.knowledge-question { margin-top:30px; padding:28px 29px; border:1px solid rgba(120,211,220,.26);
  border-left:7px solid var(--coral); border-radius:8px;
  background:rgba(10,55,44,.88); color:var(--pagetext); }
.knowledge-question small { color:#E85545; font-size:16px; font-weight:700; letter-spacing:.18em; }
.knowledge-question strong { display:block; margin-top:14px; color:var(--ivory);
  font-family:'TL Serif SC','TL Sans SC'; font-size:38px; line-height:1.42; }
.has-page-photo .knowledge-years { margin-top:16px; }
.has-page-photo .knowledge-year,
.has-page-photo .knowledge-years.count-2 .knowledge-year {
  min-height:116px; padding:6px 0 12px;
}
.has-page-photo .knowledge-year b { font-size:36px; }
.has-page-photo .knowledge-year p { margin-top:5px; font-size:27px; line-height:1.38; }
.has-page-photo .knowledge-question { margin-top:12px; padding:18px 24px; }
.has-page-photo .knowledge-question strong { margin-top:9px; font-size:36px; line-height:1.34; }

/* ---------- 外媒赛后室 ---------- */
.media-page h1 { font-size:72px; }
.media-visual { position:relative; height:310px; margin-top:16px; overflow:hidden;
  border-radius:8px; background:var(--panel-strong); box-shadow:var(--cardshadow); }
.media-visual img { width:100%; height:100%; object-fit:cover; object-position:50% 24%;
  filter:saturate(.84) contrast(1.06); }
.media-visual::after { content:""; position:absolute; inset:0;
  background:linear-gradient(90deg,rgba(0,25,20,.96) 0%,rgba(0,25,20,.78) 47%,rgba(0,25,20,.12) 100%); }
.media-visual-copy { position:absolute; z-index:2; left:30px; top:34px; width:64%; }
.media-visual small { font-family:'TL Sans SC'; color:var(--sky); font-size:20px;
  font-weight:700; }
.media-visual strong { display:block; margin-top:14px; font-family:'TL Serif SC',serif;
  color:#fff; font-size:44px; line-height:1.34; }
.media-visual-credit { position:absolute; z-index:2; right:16px; bottom:12px;
  color:rgba(255,255,255,.7); font-size:13px; }
.media-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:16px; }
.media-stat { min-height:118px; padding:18px 20px; border-top:4px solid var(--neon);
  background:var(--panel); box-shadow:var(--cardshadow); }
.media-stat strong { display:block; color:var(--neon); font-family:'Barlow Condensed';
  font-size:44px; line-height:1; }
.media-stat span { display:block; margin-top:9px; color:var(--reason); font-size:18px; }
.media-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:16px; }
.media-card { min-height:148px; padding:20px 22px; border-radius:8px;
  border:1px solid var(--panel-border); background:var(--panel); box-shadow:var(--cardshadow); }
.media-card b { display:block; color:var(--section-accent); font-size:22px; line-height:1.2; }
.media-card p { margin-top:10px; color:var(--reason); font-size:25px; line-height:1.38; }
.media-verdict { margin-top:16px; padding:18px 24px; border-left:6px solid var(--coral);
  background:rgba(255,119,93,.09); color:var(--pagetext); font-size:25px; line-height:1.42; }
.media-verdict b { color:var(--coral); margin-right:12px; }
.media-sources { margin-top:14px; color:var(--fade); font-size:16px; line-height:1.4; }

.cta-wrap { display:flex; flex-direction:column; align-items:center; text-align:center; }
.cta-copy { font-family:'TL Serif SC',serif; font-weight:900; font-size:58px; line-height:1.5;
  color:var(--pagetext); margin-top:54px; letter-spacing:3px; }
.cta-sub { font-size:32px; color:var(--fade); margin-top:22px; letter-spacing:2px; line-height:1.4; }
.cta-btn { margin-top:56px; background:var(--neon); color:#0B2018; font-size:38px; font-weight:700;
  padding:24px 72px; border-radius:999px; line-height:1.2; box-shadow:var(--cardshadow); }
html.light .cta-btn { color:#F2F7EF; }
.pills { display:flex; gap:26px; margin-top:60px; }
.pills span { border:2px solid var(--gold-soft); color:var(--pagetext); border-radius:999px;
  padding:16px 46px; font-size:30px; letter-spacing:4px; line-height:1.2; }
.bigball { width:150px; height:150px; border-radius:50%; background:var(--neon);
  position:relative; overflow:hidden; margin:64px auto 0; }
.bigball::before, .bigball::after { content:""; position:absolute; width:124px; height:124px;
  border:12px solid var(--ground0); border-radius:50%; }
.bigball::before { left:-76px; top:13px; } .bigball::after { right:-76px; top:13px; }
.end-title { font-family:'TL Serif SC',serif; font-weight:900; font-size:84px; line-height:1.5;
  letter-spacing:4px; margin-top:40px; color:var(--pagetext); }
.end-sub { font-size:32px; color:var(--fade); margin-top:12px; letter-spacing:2px; }
.end-value { margin-top:40px; padding:22px 30px; border-top:1px solid var(--gold-soft);
  border-bottom:1px solid var(--gold-soft); color:var(--ivory); font-size:28px; line-height:1.6; }

/* ---------- 排名卡 ---------- */
.rank-card { padding:16px 30px 18px; }
.rank-card h3 { font-family:'Barlow Condensed'; font-weight:600; font-size:26px; letter-spacing:.32em;
  color:var(--gold); text-transform:uppercase; height:38px; border-bottom:1px solid var(--divider); }
.rrow { display:flex; align-items:center; height:58px; gap:16px; }
.rrow .no { font-family:'Barlow Condensed'; font-weight:700; font-size:36px; color:var(--gold); width:52px; line-height:1; }
.rrow .rnames { display:flex; flex-direction:column; min-width:0; flex:1; }
.rrow .pts { font-family:'Barlow Condensed'; font-weight:500; font-size:24px; color:var(--panel-muted); line-height:1; }
.rrow .mv { font-family:'Barlow Condensed'; font-weight:600; font-size:26px; width:72px; text-align:right; line-height:1; }
.mv.up { color:var(--score-win); } .mv.down { color:var(--flash); } .mv.flat { color:var(--panel-muted); }
"""


def _shell(body: str, theme: str) -> str:
    light = "true" if theme == "light" else "false"
    css = _CSS.replace("@W@", str(W)).replace("@H@", str(H))
    inner_bg = _asset_image_uri(ASSETS / "covers" / "tennis-night-court.png") or ""
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_font_css()}\n{css}'
        f"</style></head><body style=\"--inner-bg:url('{inner_bg}')\">{_COURT_SVG}{body}"
        f"<script>document.documentElement.classList.toggle('light', {light});</script>"
        "</body></html>"
    )


def _masthead(date_label: str) -> str:
    icon_uri = _asset_image_uri(ASSETS / "logo" / "tennis-clock-icon.png")
    icon = (
        f'<img class="brand-icon" src="{icon_uri}" alt="">'
        if icon_uri
        else '<span class="ball"></span>'
    )
    # The bundled condensed Latin font is deterministic across local Chromium
    # and GitHub Actions; keep the masthead date numeric and let the cover carry
    # the Chinese weekday separately.
    compact_date = date_label.split("·", 1)[0].strip()
    return (
        f'<div class="masthead">{icon}<span class="brand">网球时差</span>'
        f'<span class="date">{html.escape(compact_date)}</span></div>'
    )


def _titleband(kicker: str, title: str) -> str:
    compact = " compact" if len(title) >= 16 else ""
    return (
        f'<div class="titleband{compact}"><div class="kicker">{kicker}</div>'
        f"<h1>{title}</h1></div>"
    )


_FOOTER = '<div class="footer"><b>@网球时差 · TENNIS JETLAG</b></div>'


# ---------- 比赛卡组件 ----------


def _names_html(players) -> tuple[str, str]:
    """(主行 HTML, 英文小字行)：中文名为主（各自国旗紧贴人名前），英文原名小字.

    双打时国旗放在对应球员名前：🇫🇷卡斯基诺/🇨🇳冯朔。
    """
    zh_parts, en_parts = [], []
    for p in players[:2]:
        zh = player_zh(p.name)
        if zh != p.name:
            shown = zh
            en_parts.append(p.name)
        elif p.name.isascii():
            shown = _abbrev_en(p.name)
        else:
            shown = p.name
        uri = _flag_uri(p.country)
        flag = f'<img class="flag" src="{uri}" alt=""/>' if uri else ""
        zh_parts.append(f'{flag}<em class="name">{html.escape(shown)}</em>')
    return '<i class="slash">/</i>'.join(zh_parts), " / ".join(en_parts)


def _side_html(m: Match, side: int, n_sets: int, with_sets: bool = True) -> str:
    players = m.home if side == 0 else m.away
    won = m.winner == side
    # 种子槽位固定宽度：无种子留空，保证上下两行国旗对齐
    seed = players[0].seed if players else None
    seed_html = f'<i class="seed">{seed if seed else ""}</i>'
    main_html, en = _names_html(players)
    rank = players[0].rank if len(players) == 1 else None
    rank_html = f'<i class="rank">({rank})</i>' if rank else ""
    en_html = f'<span class="en">{html.escape(en)}</span>' if en else ""
    cells = []
    if with_sets:
        for s in m.sets:
            games = s.home if side == 0 else s.away
            opp = s.away if side == 0 else s.home
            tb = s.home_tiebreak if side == 0 else s.away_tiebreak
            opp_tb = s.away_tiebreak if side == 0 else s.home_tiebreak
            # 超级抢十：数据源记为 1-0 + 抢十小分，直接显示小分（10/8）
            if {s.home, s.away} == {1, 0} and tb is not None and opp_tb is not None:
                games, opp, tb, opp_tb = tb, opp_tb, None, None
            # 粗体按"这一盘谁赢"标注，而不是按比赛胜者整行加粗
            if games != opp:
                set_won = games > opp
            elif tb is not None and opp_tb is not None:
                set_won = tb > opp_tb
            else:
                set_won = False
            sup = f"<sup>{tb}</sup>" if tb is not None else ""
            cells.append(f'<b class="set {"sw" if set_won else "sl"}">{games}{sup}</b>')
    note = ""
    if with_sets and not m.sets and side == (m.winner or 0) and m.note:
        note = f'<i class="note">{html.escape(str(m.note)[:12])}</i>'
    cls = "side"
    cls += " won" if (won and with_sets) else (" lost" if (with_sets and m.winner is not None) else "")
    if not with_sets or not n_sets:
        cls += " nosets"
    return (
        f'<div class="{cls}" style="--sets:{max(n_sets, 1)}">'
        f'<span class="who"><span class="names">'
        f'<span class="zh">{seed_html}{main_html}'
        f'{rank_html}{note}</span>{en_html}</span></span>'
        f'{"".join(cells)}</div>'
    )


def _story_chip(m: Match) -> tuple[str, str]:
    from ..zh.terms import round_zh

    if is_chinese_involved(m):
        return "中国军团", "chip-green"
    if (round_zh(m.round_name) or "") == "决赛":
        return "夺冠时刻", "chip-green"
    if is_upset(m):
        return "爆冷", "chip-red"
    return "今日头条", "chip-green"


def _result_card(m: Match, *, hero: bool, show_tournament: bool, tag_upset: bool) -> str:
    """赛果卡：元信息条 + 两行球员 + 每盘一列比分."""
    n = len(m.sets)
    round_txt = html.escape(match_round_display(m) or "")
    tour_txt = ""
    if show_tournament:
        g = group_by_tournament([m])[0]
        tour_txt = (
            f'<b class="tour-level">{html.escape(g.compact_level)}</b>'
            f'<span class="tour-name">{html.escape(g.name_zh)}</span>'
        )
    chip_html = ""
    if hero:
        text, cls = _story_chip(m)
        chip_html = f'<b class="chip {cls}">{text}</b>'
    else:
        chips = []
        if is_chinese_involved(m):
            chips.append('<b class="chip chip-green chip-sm">中国军团</b>')
        if tag_upset:
            chips.append('<b class="chip chip-red chip-sm">爆冷</b>')
        chip_html = "".join(chips)
    set_index = ""
    if hero and n:
        idx = "".join(f"<i>{i + 1}</i>" for i in range(n))
        set_index = f'<div class="set-index" style="--sets:{n}"><span></span>{idx}</div>'
    order = (0, 1) if m.winner in (None, 0) else (1, 0)
    sides = "".join(_side_html(m, s, n) for s in order)
    return (
        f'<article class="card {"hero" if hero else ""}">'
        f'<header><span class="hl">{chip_html}<span class="round">{round_txt}</span></span>'
        f'<span class="tour">{tour_txt}</span></header>'
        f"{set_index}{sides}</article>"
    )


def _sched_card(
    m: Match,
    *,
    with_reason: bool = False,
    show_tournament: bool = True,
) -> str:
    """赛程卡：时间、对阵，以及可核验的推荐理由."""
    g = group_by_tournament([m])[0]
    meta = html.escape(match_round_display(m) or "")
    tour_txt = html.escape(g.name_zh) if show_tournament else ""
    level_badge = html.escape(g.compact_level)
    level_html = (
        f'<b class="tour-level">{level_badge}</b>' if show_tournament else ""
    )
    t = fmt_schedule_time(m)
    right = f'<span class="htime">{t}</span>'
    reason = ""
    card_class = "card"
    if with_reason:
        label = recommendation_label(m)
        label_icon = {
            "必看": "flame",
            "重点": "star",
            "悬念": "eye",
            "有看头": "circle",
        }[label]
        right = (
            f'<span class="rating">{_icon_html(label_icon)}'
            f'<span>{html.escape(label)}</span></span>' + right
        )
        reason = (
            f'<div class="reason"><b>{_icon_html("eye")}<span>看点</span></b>'
            f'{html.escape(preview_angle(m))}</div>'
        )
        card_class += " pick"
    chinese = (
        '<b class="china-marker">中国选手</b>' if is_chinese_involved(m) else ""
    )
    event_meta = f"{tour_txt} · " if tour_txt else ""
    return (
        f'<article class="{card_class}">'
        f'<header><span class="hl">{level_html}'
        f'<span class="round">{chinese}{event_meta}{meta}</span></span>'
        f'<span class="hl">{right}</span></header>'
        f"{_side_html(m, 0, 0, with_sets=False)}{_side_html(m, 1, 0, with_sets=False)}"
        f"{reason}"
        "</article>"
    )


def _seclabel(text: str) -> str:
    return f'<div class="seclabel"><i></i><span>{html.escape(text)}</span><i></i></div>'


# ---------- 各卡页面 ----------


def cover_body(
    digest: Digest,
    headline: str,
    secondary: str,
    date_label: str,
    cover_visual: object | None = None,
) -> str:
    overnight = top_results(
        [match for match in digest.results if match.is_singles],
        2,
        cn_boost=True,
    )
    lead = daily_lead_match(digest)
    # The cover may tease a lone confirmed fixture; event pages stay stricter
    # and require 2-5 matches so they remain useful schedule boards.
    focus_matches = editorial_tonight_focus(digest.schedule)
    subject = direct_story_for_match(lead, prefer_player=True) if lead else None
    cover_path = Path(_visual_value(cover_visual, "path", "")) if cover_visual else None
    cover_focus = str(_visual_value(cover_visual, "focus", "50% 24%"))
    cover_size = "cover"
    if cover_path is None or not cover_path.is_file():
        if subject is not None and subject.kind == "player" and subject.image.exists():
            cover_path = subject.image
            cover_focus, cover_size = _LOCAL_PLAYER_COVER_FRAMING.get(
                subject.image.name, ("50% 24%", "cover")
            )
        else:
            cover_path = ASSETS / "covers" / "tennis-night-court.png"
            cover_focus = "center"
    text_side, focus_x, focus_y = _cover_text_layout(cover_focus)
    background_uri = _asset_image_uri(cover_path)
    background = (
        f'<div class="cover-bg" style="background-image:url(\'{background_uri}\');'
        f'--cover-focus:{html.escape(cover_focus, quote=True)};'
        f'--cover-size:{html.escape(cover_size, quote=True)}"></div>'
        if background_uri else ""
    )
    secondary_html = (
        f'<div class="cover-secondary">{html.escape(secondary)}</div>'
        if secondary else ""
    )
    def cover_highlight(label: str, match: Match) -> str:
        group = group_by_tournament([match])[0]
        round_name = match_round_display(match).replace("·", "") or "本轮"
        if match.status.is_final:
            if "中国焦点" in label and is_chinese_involved(match):
                chinese = [
                    player
                    for player in match.home + match.away
                    if is_chinese_player(player)
                ]
                name = " / ".join(player_zh(player.name) for player in chinese)
                if chinese_side_won(match):
                    action = "捧杯" if round_name.endswith("决赛") and "半" not in round_name else "过关"
                else:
                    action = f"止步{round_name}"
                value = f"{name} {action}"
            else:
                winners = match.winner_players() or match.home
                name = " / ".join(player_zh(player.name) for player in winners)
                action = "捧杯" if round_name.endswith("决赛") and "半" not in round_name else "过关"
                value = f"{name} {action}"
        else:
            if "中国焦点" in label and is_chinese_involved(match):
                chinese = [
                    player
                    for player in match.home + match.away
                    if is_chinese_player(player)
                ]
                name = " / ".join(player_zh(player.name) for player in chinese)
                value = f"{name} 今日出战"
            else:
                left = " / ".join(player_zh(player.name) for player in match.home)
                right = " / ".join(player_zh(player.name) for player in match.away)
                value = f"{left} vs {right}"
        meta = " · ".join(
            part for part in (
                fmt_time_beijing(match.start_utc) if not match.status.is_final else "",
                group.compact_level,
                match_round_display(match),
            ) if part
        )
        icon = "flame" if "必看" in label else "star" if "亮点" in label else "eye"
        compact = " compact" if len(value) > 20 else ""
        return (
            f'<article class="cover-highlight{compact}">'
            f'<small>{_icon_html(icon)}{html.escape(label)}</small><b>{html.escape(value)}</b>'
            f'<span>{html.escape(meta)}</span></article>'
        )

    support: list[tuple[str, Match]] = []
    lead_id = lead.match_id if lead else None
    chinese = [
        match for match in digest.results + digest.schedule
        if is_chinese_involved(match)
        and match.match_id != lead_id
        and is_tour_focus_match(match)
    ]
    if chinese:
        support.append(("China Focus · 中国焦点", max(chinese, key=match_score)))
    elif lead is not None and is_chinese_involved(lead):
        # 中国场次成为总头条时，底部仍保留固定的“中国焦点”信息位。
        support.append(("China Focus · 中国焦点", lead))
    elif len(overnight) > 1:
        support.append(("More Result · 昨夜亮点", overnight[1]))
    for focus_match in focus_matches:
        if (
            focus_match.match_id != lead_id
            and all(match.match_id != focus_match.match_id for _, match in support)
        ):
            support.append(("Tonight · 今晚必看", focus_match))
            break
    if len(support) < 2:
        for result in overnight[1:]:
            if all(match.match_id != result.match_id for _, match in support):
                support.append(("More Result · 昨夜亮点", result))
                break
    highlights_html = "".join(
        cover_highlight(label, match) for label, match in support[:2]
    )
    highlights_html = (
        f'<div class="cover-highlights">{highlights_html}</div>'
        if highlights_html else ""
    )
    headline_width = _headline_display_width(headline)
    headline_class = (
        " extra-compact-headline"
        if headline_width > 22
        else " compact-headline"
        if headline_width > 16
        else ""
    )
    return (
        f'<div class="poster cover cover-text-{text_side}{headline_class}" '
        f'data-cover-text-side="{text_side}" '
        f'data-cover-focus-x="{focus_x:.1f}" data-cover-focus-y="{focus_y:.1f}">'
        + background
        + _masthead(date_label)
        + '<div class="cover-copy">'
        + '<div class="edition">MATCH POINT · 今日头条</div>'
        + f'<div class="focus">{_cover_headline_html(headline)}</div>'
        + '</div><div class="cover-lower">'
        + secondary_html
        + highlights_html
        + '</div>'
        + _FOOTER
        + "</div>"
    )


def scoreboard_body(
    matches: list[Match], date_label: str, *,
    with_hero: bool = True, page: int = 1, total: int = 1,
) -> str:
    """赛果页：首页头条 + 3 场；续页 4 场，保证手机端可读性."""
    names = {m.tournament.name for m in matches}
    single_event = len(names) == 1
    banner = ""
    if single_event:
        g = group_by_tournament(matches[:1])[0]
        level = g.compact_level
        if len({m.tour for m in matches}) > 1 and level.startswith(("ATP", "WTA")):
            level = level[3:]
        title = f"{level}·{g.name_zh}"
        banner = f'<div class="event"><i></i><span>{html.escape(title)}</span><i></i></div>'
    cards = []
    if with_hero:
        hero, rest = matches[0], matches[1:]
        rest = rest[:3]
        cards.append(_result_card(hero, hero=True, show_tournament=not single_event, tag_upset=False))
    else:
        rest = matches[:4]
    top_upset = find_upset(rest)
    for m in rest:
        cards.append(_result_card(
            m, hero=False, show_tournament=not single_event,
            tag_upset=(top_upset is not None and m.match_id == top_upset.match_id),
        ))
    kicker = "Overnight Results · 昨夜赛果"
    if total > 1:
        kicker += f" · {page}/{total}"
    return (
        '<div class="poster results-page">'
        + _masthead(date_label)
        + _titleband(kicker, "赛果速递")
        + banner
        + "".join(cards)
        + _FOOTER
        + "</div>"
    )


def china_body(results: list[Match], today: list[Match], date_label: str) -> str:
    results = sort_china_matches(results)[:3]
    today = sorted(today, key=lambda m: (0 if m.is_singles else 1))[
        : max(0, 5 - len(results))
    ]
    parts = []
    if results:
        parts.append(_seclabel("昨 日 战 报"))
        for m in results:
            parts.append(_result_card(m, hero=False, show_tournament=True, tag_upset=False))
    if today:
        parts.append(_seclabel("今 日 出 场 · 北 京 时 间"))
        for m in today:
            parts.append(_sched_card(m))
    return (
        '<div class="poster china-page">'
        + _masthead(date_label)
        + _titleband("Team China · 中国军团", "中国军团")
        + "".join(parts)
        + _FOOTER
        + "</div>"
    )


def _tonight_event_groups(matches: list[Match]):
    """Merge ATP/WTA draws that belong to the same named tournament."""
    buckets: dict[str, list] = {}
    order: list[str] = []
    for group in group_by_tournament(matches):
        key = " ".join(group.name_en.casefold().split())
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(group)
    return [buckets[key] for key in order]


def tonight_body(matches: list[Match], date_label: str) -> str:
    # A schedule page belongs to one event. Mixed input is intentionally narrowed
    # to its highest-priority event; generate_deck emits the remaining groups as
    # separate pages.
    event_groups = _tonight_event_groups(matches)[0]
    group = event_groups[0]
    matches = [
        match for event_group in event_groups for match in event_group.matches
    ][:5]
    has_estimates = any(
        fmt_schedule_time(match).startswith("预计") for match in matches
    )
    cards: list[str] = []
    courts = {m.court.strip() for m in matches if m.court and m.court.strip()}
    # Five-match pages need the vertical space for the fixtures themselves;
    # court group headings are useful metadata but must never collide with the
    # venue credit or footer.
    show_courts = len(courts) > 1 and len(matches) <= 4
    last_court = None
    for match in sorted(
        matches,
        key=lambda m: (
            m.court or "",
            m.start_utc.timestamp() if m.start_utc else float("inf"),
        ),
    ):
        court = (match.court or "").strip()
        if show_courts and court != last_court:
            cards.append(
                f'<div class="court-label">{html.escape(court or "场地待定")}</div>'
            )
            last_court = court
        cards.append(
            _sched_card(
                match,
                with_reason=True,
                show_tournament=False,
            )
        )

    venue = venue_asset_for_match(matches[0])
    page_style = ""
    location = ""
    if venue is not None:
        uri = _asset_image_uri(venue.image)
        if uri:
            page_style = (
                f"--page-bg:url('{uri}');"
                f"--page-bg-pos:{html.escape(venue.focal_point)}"
            )
            location = venue.location
    first = matches[0].tournament
    location = location or " · ".join(filter(None, (first.city, first.country)))
    levels = list(dict.fromkeys(event_group.compact_level for event_group in event_groups))
    level_label = " / ".join(levels)
    surface = first.surface or tournament_surface(first.name)
    surface_label = surface_zh(surface) or "场地待核"
    meta = "".join(
        (
            f'<b class="event-level">{html.escape(level_label)}</b>',
            f'<b class="event-surface">{html.escape(surface_label)}</b>',
            f'<span>{html.escape(location)}</span>' if location else "",
            '<i>北京时间 · *为预计时间</i>' if has_estimates else '<i>北京时间</i>',
        )
    )
    return (
        f'<div class="poster tonight-page count-{len(matches)}" style="{page_style}">'
        + _masthead(date_label)
        + _titleband("Tonight's Focus · 今晚焦点", group.name_zh)
        + f'<div class="event-meta">{meta}</div><div class="event-spacer"></div>'
        + "".join(cards)
        + _FOOTER
        + "</div>"
    )


def media_body(m: Match, date_label: str, today) -> str:
    brief = brief_for_match(m, today)
    if brief is None:
        raise ValueError("match has no reviewed media brief")
    highlights = brief.highlights or (("多源", "交叉核验"), ("1场", "继续追踪"), ("原创", "中文摘要"))
    stats = "".join(
        f'<article class="media-stat"><strong>{html.escape(value)}</strong>'
        f'<span>{html.escape(label)}</span></article>'
        for value, label in highlights
    )
    cards = "".join(
        '<article class="media-card">'
        f'<b>{html.escape(source.name)}</b><p>{html.escape(source.lens)}</p></article>'
        for source in brief.sources[:2]
    )
    story = direct_story_for_match(m, prefer_player=True)
    photo = ""
    if story is not None:
        uri = _asset_image_uri(story.image)
        if uri:
            photo = f'<img src="{uri}" alt="">'
    return (
        '<div class="poster media-page">'
        + _masthead(date_label)
        + _titleband("POST-MATCH LENS · 赛后观察", "赛后显微镜")
        + '<article class="media-visual">'
        + photo
        + '<div class="media-visual-copy"><small>先别急着说“回来了”</small>'
        + f'<strong>{html.escape(brief.headline)}</strong></div></article>'
        + f'<div class="media-stats">{stats}</div>'
        + f'<div class="media-grid">{cards}</div>'
        + f'<div class="media-verdict"><b>我的判断</b>{html.escape(brief.takeaway)}</div>'
        + _FOOTER
        + "</div>"
    )


def focus_body(m: Match, date_label: str) -> str:
    comparison = focus_comparison(m)
    rows = []
    for label, left, right in comparison.rows:
        left_cls = "winner" if comparison.left_won else ""
        right_cls = "" if comparison.left_won else "winner"
        rows.append(
            f'<div class="compare-row"><b>{html.escape(label)}</b>'
            f'<span class="{left_cls}">{html.escape(left)}</span>'
            f'<span class="{right_cls}">{html.escape(right)}</span></div>'
        )
    return (
        '<div class="poster focus-page">'
        + _masthead(date_label)
        + _titleband("Match Breakdown · 单场复盘", "焦点复盘")
        + '<div class="save-badge">建议收藏 · 技术对比</div>'
        + _result_card(m, hero=True, show_tournament=True, tag_upset=False)
        + '<div class="compare-head"><span>'
        + ("专业技术统计" if comparison.source_label else "比赛结构")
        + "</span>"
        + f'<span>{html.escape(comparison.left_name)}</span>'
        + f'<span>{html.escape(comparison.right_name)}</span></div>'
        + f'<div class="compare-grid">{"".join(rows)}</div>'
        + f'<div class="verdict"><b>一句判断</b>{html.escape(comparison.verdict)}</div>'
        + _FOOTER
        + "</div>"
    )


def _tag_chip_class(tag: str) -> str:
    if tag == "中国球员":
        return "chip-green"
    if tag == "爆冷":
        return "chip-red"
    return "chip-gold"


def insight_body(m: Match, date_label: str, kind: str, today=None) -> str:
    """单场内容解释页：只使用可验证的比分和赛程事实。"""
    from .focus import focus_comparison, has_detailed_stats
    from .hotspot import hotspot_reasons
    from .story import result_insight, trajectory_arc
    from .context import historical_context

    group = group_by_tournament([m])[0]
    context = historical_context(m, today)
    extra_html = ""
    if kind == "result":
        if context is not None:
            kicker = "Career Context · 人物背景"
            title = "把今天放回生涯里"
            insight = context.summary
        else:
            kicker = "Why It Matters · 一句看懂"
            title = "这场意味着什么"
            insight = result_insight(m)
        match_card = _result_card(
            m, hero=True, show_tournament=False, tag_upset=False
        )
        verdict = editor_takeaway(m, today)
        facts = []

        arc = trajectory_arc(m)
        arc_html = (
            f'<div class="verdict"><b>比赛走势</b>{html.escape(arc)}</div>'
            if arc
            else ""
        )
        extra_html = arc_html
        if has_detailed_stats(m):
            comparison = focus_comparison(m)
            rows_html = "".join(
                f'<div class="compare-row"><b>{html.escape(label)}</b>'
                f'<span class="{"winner" if comparison.left_won else ""}">'
                f'{html.escape(left)}</span>'
                f'<span class="{"" if comparison.left_won else "winner"}">'
                f'{html.escape(right)}</span></div>'
                for label, left, right in comparison.rows
            )
            extra_html += (
                f'<div class="compare-head"><span>专业技术统计</span>'
                + f'<span>{html.escape(comparison.left_name)}</span>'
                + f'<span>{html.escape(comparison.right_name)}</span></div>'
                + f'<div class="compare-grid">{rows_html}</div>'
            )
        surface = surface_zh(m.tournament.surface or tournament_surface(m.tournament.name))
        event_suffix = f"·{surface}" if surface else ""
    else:
        verdict = ""
        event_suffix = ""
        if context is not None:
            kicker = "Player Context · 人物背景"
            title = "今晚看这条故事"
            insight = context.summary
            facts = list(context.facts) or [
                (fmt_time_beijing(m.start_utc), "北京时间"),
                (group.compact_level, "赛事级别"),
                (match_round_display(m) or "待定", "比赛轮次"),
            ]
        else:
            kicker = "Match Preview · 赛前看点"
            title = "为什么值得看"
            insight = preview_angle(m, today)
            facts = [
                (fmt_time_beijing(m.start_utc), "北京时间"),
                (group.compact_level, "赛事级别"),
                (match_round_display(m) or "待定", "比赛轮次"),
            ]
        match_card = _sched_card(m, with_reason=False)
    tags_html = "".join(
        f'<b class="chip chip-sm {_tag_chip_class(tag)}">{html.escape(tag)}</b>'
        for tag in hotspot_reasons(m)[:3]
    )
    facts_html = "".join(
        f'<article class="fact"><b>{html.escape(value)}</b>'
        f'<span>{html.escape(label)}</span></article>'
        for value, label in facts
    )
    if facts_html:
        facts_html = f'<div class="fact-grid">{facts_html}</div>'
    verdict_html = (
        f'<div class="verdict verdict-quote"><b>编辑锐评</b>{html.escape(verdict)}</div>'
        if verdict
        else ""
    )
    return (
        '<div class="poster insight-page">'
        + _masthead(date_label)
        + _titleband(kicker, title)
        + f'<div class="event"><i></i><span>{html.escape(group.compact_title)}{html.escape(event_suffix)}</span><i></i></div>'
        + match_card
        + '<article class="insight-hero">'
        + f'<div class="tag-row">{tags_html}</div><strong>{html.escape(insight)}</strong></article>'
        + facts_html
        + extra_html
        + verdict_html
        + _FOOTER
        + "</div>"
    )


def discussion_body(m: Match, date_label: str, kind: str) -> str:
    """开放式讨论页，避免低质的固定答案诱导。"""
    from ..zh.terms import round_zh
    from .common import is_chinese_involved
    from .rating import is_upset

    if kind == "preview":
        question = "如果只观察一个胜负变量，你会盯发球还是接发？"
        helper = "开赛前留下你的判断，赛后回来对照比赛走势。"
    elif round_zh(m.round_name) == "决赛":
        question = "回看这场决赛，冠军最关键的胜负手是什么？"
        helper = "从发球、接发、相持或关键分里，留下你的具体判断。"
    elif is_upset(m):
        question = "这场冷门的真正转折，你会选哪一盘？为什么？"
        helper = "欢迎写下你看到的比赛细节，而不只是最终比分。"
    elif is_chinese_involved(m):
        question = "下一场继续往前走，最需要守住哪个环节？"
        helper = "发球、接发、相持或关键分，留下你的具体判断。"
    else:
        question = "这场结果，改变了你对哪位球员的判断？"
        helper = "评论区聊比赛本身：过程、转折和下一场。"
    return (
        '<div class="poster discussion-page">'
        + _masthead(date_label)
        + _titleband("Your Take · 继续聊这场", "你的判断")
        + '<article class="discussion-card"><small>OPEN QUESTION · 开放讨论</small>'
        + f'<strong>{html.escape(question)}</strong><p>{html.escape(helper)}</p></article>'
        + _FOOTER
        + "</div>"
    )


def tournament_story_body(story: TournamentStory, date_label: str) -> str:
    uri = _asset_image_uri(story.image)
    if not uri:
        raise FileNotFoundError(story.image)
    # 竖版人像在宽幅横幅位里裁切会切掉人脸——完整显示 + 同图模糊铺底
    portrait = False
    try:
        from PIL import Image as _Image

        with _Image.open(story.image) as im:
            portrait = im.height > im.width
    except OSError:
        pass
    def moment_item(moment) -> tuple[str, str]:
        year = moment.date.split("-", 1)[0]
        title = " · ".join((year, moment.player, moment.headline))
        return title, moment.detail

    moment_items = [moment_item(moment) for moment in story.moments[:2]]
    fact_item = (
        ("为什么会改变" if story.kind == "trivia" else "关键事实", story.facts[0])
        if story.facts
        else None
    )
    if story.kind == "trivia" and len(moment_items) == 2 and fact_item:
        story_items = [moment_items[0], fact_item, moment_items[1]]
    else:
        story_items = moment_items + ([fact_item] if fact_item else [])
    rows = "".join(
        '<li>'
        + _semantic_marker_for_text(
            f"{title} {detail}", index, story_kind=story.kind
        )
        + f'<div class="story-copy"><strong>{html.escape(title)}</strong>'
        f'<p>{html.escape(detail)}</p></div></li>'
        for index, (title, detail) in enumerate(story_items[:3])
    )
    kicker = {
        "player": "Player Spotlight · 球员特写",
        "trivia": "Tennis Story · 网球有故事",
    }.get(story.kind, "Tournament Archive · 赛事档案")
    location = (
        story.location.replace("网球冷知识", "网球有故事")
        if story.kind == "trivia"
        else story.location
    )
    return (
        '<div class="poster story-page">'
        + _masthead(date_label)
        + _titleband(kicker, story.title)
        + (
            f'<div class="venue-photo">'
            f'<i class="ph-back" style="background-image:url(\'{uri}\')"></i>'
            f'<i class="ph-main" style="background-image:url(\'{uri}\')"></i>'
            if portrait
            else f'<div class="venue-photo" style="background-image:url(\'{uri}\')">'
        )
        + '<div class="venue-caption">'
        + f'<b>{html.escape(story.venue)}</b><span>{html.escape(location)}</span>'
        + "</div></div>"
        + f'<div class="story-hero">{html.escape(story.hero_fact)}</div>'
        + f'<ol class="story-list">{rows}</ol>'
        + _FOOTER
        + "</div>"
    )


def _card_excerpt(text: str, limit: int) -> str:
    """Keep card copy spacious without cutting a fact mid-clause when possible."""
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    window = clean[: limit + 1]
    stops = [window.rfind(mark) for mark in ("。", "！", "？", "；", "：", "，")]
    cut = max(stops)
    if cut >= max(16, limit // 2):
        result = window[: cut + 1].rstrip("，；：、 ")
    else:
        result = clean[:limit].rstrip("，；：、 ")
    return result if result.endswith(("。", "！", "？")) else result + "。"


def _card_excerpt_html(text: str, limit: int) -> str:
    escaped = html.escape(_card_excerpt(text, limit))
    return re.sub(r"(?<=\d)-(?=\d)", "&#8209;", escaped)


def _timeline_visual(years: list[str], *, css_class: str) -> str:
    clean = [re.sub(r"[^0-9]", "", year)[:4] or "NOW" for year in years[:3]]
    while len(clean) < 3:
        clean.append("NOW")
    xs = (120, 475, 830)
    nodes = "".join(
        f'<circle class="node" cx="{x}" cy="92" r="17"/>'
        f'<text class="year" x="{x}" y="55" text-anchor="middle">{html.escape(year)}</text>'
        for x, year in zip(xs, clean)
    )
    if css_class == "knowledge-story-visual":
        path = '<path class="path" d="M120 92 Q300 18 475 92 T830 92"/>'
        labels = (
            '<text class="label" x="120" y="145" text-anchor="middle">起点</text>'
            '<text class="label" x="475" y="145" text-anchor="middle">转折</text>'
            '<text class="label" x="830" y="145" text-anchor="middle">回响</text>'
        )
    else:
        path = '<line x1="120" y1="92" x2="830" y2="92"/>'
        labels = ""
    return (
        f'<div class="{css_class}" aria-label="故事时间节点图">'
        f'<svg viewBox="0 0 950 180">{path}{nodes}{labels}</svg></div>'
    )


def _hawkeye_story_visual() -> str:
    return (
        '<div class="knowledge-story-visual" aria-label="挑战回放改变判罚流程示意图">'
        '<svg viewBox="0 0 950 180">'
        '<rect x="36" y="34" width="190" height="112" rx="8" fill="#0F4B3D" stroke="#78D3DC" stroke-width="3"/>'
        '<circle cx="131" cy="90" r="23" fill="#D3FF12"/>'
        '<text x="131" y="169" text-anchor="middle" fill="#A9B9B0" font-size="18">争议落点</text>'
        '<path d="M250 90 H405" stroke="#FF765F" stroke-width="6"/>'
        '<polygon points="405,90 380,76 380,104" fill="#FF765F"/>'
        '<rect x="430" y="23" width="210" height="134" rx="8" fill="#082C22" stroke="#78D3DC" stroke-width="3"/>'
        '<path d="M470 120 Q535 40 603 119" fill="none" stroke="#78D3DC" stroke-width="5"/>'
        '<ellipse cx="568" cy="111" rx="25" ry="14" fill="#D3FF12"/>'
        '<text x="535" y="169" text-anchor="middle" fill="#A9B9B0" font-size="18">多机位重建</text>'
        '<path d="M662 90 H775" stroke="#FF765F" stroke-width="6"/>'
        '<polygon points="775,90 750,76 750,104" fill="#FF765F"/>'
        '<rect x="797" y="43" width="120" height="95" rx="8" fill="#D3FF12"/>'
        '<text x="857" y="101" text-anchor="middle" fill="#073126" font-size="35" font-weight="800">IN</text>'
        '<text x="857" y="169" text-anchor="middle" fill="#A9B9B0" font-size="18">现场复核</text>'
        '</svg></div>'
    )


def _longest_match_story_visual() -> str:
    return (
        '<div class="marathon-story-visual" aria-label="2010年温网最长比赛三日进程图">'
        '<div class="marathon-story-head"><div><span>比赛总时长</span>'
        '<strong>11:05</strong></div><b>一场首轮，跨过三个比赛日</b></div>'
        '<div class="marathon-days">'
        '<article class="marathon-day"><time>6月22日</time>'
        '<strong>两盘战平</strong><small>决胜盘 4-4，因天黑暂停</small></article>'
        '<article class="marathon-day"><time>6月23日</time>'
        '<strong>整日没有胜负</strong><small>决胜盘一路打到 59-59</small></article>'
        '<article class="marathon-day"><time>6月24日</time>'
        '<strong>第138局才破发</strong><small>伊斯内尔以 70-68 结束比赛</small></article>'
        '</div></div>'
    )


def _longest_match_today_visual() -> str:
    return (
        '<div class="marathon-today-visual" aria-label="大满贯决胜盘规则变化图">'
        '<div class="marathon-era"><time>2010</time><div>'
        '<b>6-6之后继续打，直到领先两局</b>'
        '<p>没有抢七，决胜盘最终被推到 70-68。</p></div></div>'
        '<div class="marathon-era"><time>2022</time><div>'
        '<b>四大满贯统一为10分抢十</b>'
        '<p>决胜盘到 6-6，先得10分且领先两分者获胜。</p></div></div>'
        '</div>'
    )


def _hawkeye_today_visual() -> str:
    return (
        '<div class="today-visual" aria-label="司线判罚到实时电子司线演进图">'
        '<svg viewBox="0 0 950 180">'
        '<line x1="100" y1="88" x2="850" y2="88"/>'
        '<circle cx="120" cy="88" r="18"/><circle cx="475" cy="88" r="18"/>'
        '<circle cx="830" cy="88" r="18"/>'
        '<text x="120" y="48" text-anchor="middle">人眼判线</text>'
        '<text x="475" y="48" text-anchor="middle">球员挑战</text>'
        '<text x="830" y="48" text-anchor="middle">实时电子司线</text>'
        '<text x="120" y="145" text-anchor="middle" fill="#A9B9B0" font-size="20">LINE JUDGE</text>'
        '<text x="475" y="145" text-anchor="middle" fill="#A9B9B0" font-size="20">REVIEW</text>'
        '<text x="830" y="145" text-anchor="middle" fill="#A9B9B0" font-size="20">LIVE ELC</text>'
        '</svg></div>'
    )


def _explainer_mark() -> str:
    return (
        '<div class="explainer-mark" aria-label="三节点视觉导览"><svg viewBox="0 0 950 110">'
        '<path d="M95 57 C250 7 330 99 475 57 S700 7 855 57"/>'
        '<circle cx="95" cy="57" r="15"/><circle cx="475" cy="57" r="15"/>'
        '<circle cx="855" cy="57" r="15"/></svg></div>'
    )


def _visual_value(visual: object | None, key: str, default: Any) -> Any:
    if visual is None:
        return default
    if isinstance(visual, Mapping):
        return visual.get(key, default)
    return getattr(visual, key, default)


_SEMANTIC_ICON_PATHS: dict[str, str] = {
    "activity": '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
    "calendar": (
        '<path d="M8 2v4M16 2v4M3 10h18"/>'
        '<path d="M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2Z"/>'
    ),
    "camera": (
        '<path d="M14.5 4 16 7h4a2 2 0 0 1 2 2v10H2V9a2 2 0 0 1 2-2h4l1.5-3h5Z"/>'
        '<circle cx="12" cy="13" r="3"/>'
    ),
    "circle-check": (
        '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>'
        '<path d="M3 3v5h5M12 7v5l3 2"/>'
    ),
    "landmark": (
        '<path d="m3 10 9-6 9 6M5 10v8M9 10v8M15 10v8M19 10v8M3 21h18"/>'
    ),
    "layers": (
        '<path d="m12 2 9 5-9 5-9-5 9-5Z"/>'
        '<path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>'
    ),
    "medal": (
        '<circle cx="12" cy="15" r="5"/><path d="m9 10-3-8h4l2 4 2-4h4l-3 8"/>'
    ),
    "route": (
        '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/>'
        '<path d="M8 19h3a3 3 0 0 0 3-3V8a3 3 0 0 1 3-3"/>'
    ),
    "scan": (
        '<path d="M3 7V3h4M17 3h4v4M21 17v4h-4M7 21H3v-4"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "timer": (
        '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2h6"/>'
    ),
    "trophy": (
        '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/>'
        '<path d="M5 6H3v2a4 4 0 0 0 4 4M19 6h2v2a4 4 0 0 1-4 4"/>'
    ),
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
}


def _semantic_marker(
    icon: str,
    label: str,
    *,
    marker_kind: str = "concept",
    mini: bool = False,
) -> str:
    """Render an offline semantic marker; year labels must stay four digits."""
    if marker_kind == "year" and not re.fullmatch(r"(?:18|19|20)\d{2}", label):
        raise ValueError(f"年份标记必须使用四位年份：{label}")
    try:
        paths = _SEMANTIC_ICON_PATHS[icon]
    except KeyError as exc:
        raise ValueError(f"未知的故事语义图标：{icon}") from exc
    classes = "semantic-marker mini" if mini else "semantic-marker"
    return (
        f'<span class="{classes}" data-marker-kind="{html.escape(marker_kind, quote=True)}">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>'
        f'<small>{html.escape(label)}</small></span>'
    )


def _semantic_marker_for_text(
    text: str,
    index: int,
    *,
    story_kind: str = "trivia",
    role: str = "",
) -> str:
    """Choose a future-proof marker from the meaning of each story beat."""
    year = re.search(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)", text)
    role_markers = {
        "origin": ("history", "缘起"),
        "history": ("history", "历史"),
        "person": ("user", "人物"),
        "venue": ("landmark", "现场"),
        "turning_point": ("route", "转折"),
        "trophy": ("trophy", "冠军"),
        "medal": ("medal", "金牌"),
        "surface": ("layers", "场地"),
        "cycle": ("timer", "周期"),
        "rule": ("circle-check", "规则"),
        "technology": ("scan", "科技"),
        "legacy": ("circle-check", "影响"),
        "record": ("trophy", "纪录"),
        "today": ("circle-check", "今天"),
    }
    if role:
        try:
            icon, label = role_markers[role]
        except KeyError as exc:
            raise ValueError(f"未知的故事事实角色：{role}") from exc
        return _semantic_marker(
            icon,
            year.group(0) if year else label,
            marker_kind="year" if year else "concept",
        )
    rules = (
        (("相机", "影像", "轨迹", "电子", "系统", "技术"), "scan", "科技"),
        (("规则", "判罚", "司线", "界内", "界外"), "circle-check", "判定"),
        (("奥运",), "medal", "奥运"),
        (("金牌",), "medal", "金牌"),
        (("红土", "草地", "硬地", "场地", "材质"), "layers", "场地"),
        (("四年", "小时", "分钟", "三天", "赛历", "周期"), "timer", "时间"),
        (("冠军", "夺冠", "捧杯", "满贯"), "trophy", "冠军"),
        (("球场", "城市", "现场", "中心球场"), "landmark", "现场"),
        (("决赛", "比赛", "对手", "赛点", "回合"), "activity", "赛场"),
        (("出生", "起源", "开始", "创办", "首次"), "history", "起点"),
        (("球员", "人物", "少年", "少女"), "user", "人物"),
    )
    for keywords, icon, label in rules:
        if any(keyword in text for keyword in keywords):
            return _semantic_marker(
                icon,
                year.group(0) if year else label,
                marker_kind="year" if year else "concept",
            )
    if year:
        return _semantic_marker("calendar", year.group(0), marker_kind="year")
    kind_defaults = {
        "player": (("user", "起点"), ("route", "转折"), ("trophy", "高光")),
        "tournament": (("landmark", "起源"), ("history", "传统"), ("trophy", "冠军")),
        "trivia": (("history", "缘起"), ("route", "转折"), ("circle-check", "今天")),
    }
    defaults = kind_defaults.get(story_kind, kind_defaults["trivia"])
    icon, label = defaults[min(index, len(defaults) - 1)]
    return _semantic_marker(icon, label)


def _knowledge_photo(
    story: TournamentStory,
    caption: str,
    subline: str = "",
    *,
    visual: object | None = None,
    compact: bool = False,
    extra_class: str = "",
) -> str:
    image_path = Path(_visual_value(visual, "path", story.image))
    image_source = str(
        _visual_value(visual, "source_url", story.image_source_url)
    ).strip()
    uri = _asset_image_uri(image_path)
    if not uri:
        raise FileNotFoundError(image_path)
    portrait = False
    wide_cover = False
    try:
        from PIL import Image as _Image

        with _Image.open(image_path) as image:
            portrait = image.height > image.width
            wide_cover = image.width / max(1, image.height) >= 1.95
    except OSError:
        pass
    portrait_class = " portrait" if portrait else ""
    wide_class = " wide-cover" if wide_cover else ""
    compact_class = " compact" if compact else ""
    extra = f" {html.escape(extra_class, quote=True)}" if extra_class else ""
    layout_attr = ' data-photo-layout="inner-hero"' if compact else ""
    sub = f"<small>{html.escape(subline)}</small>" if subline else ""
    # Keep player faces above the caption gradient. Do not zoom portraits: the
    # old scale transform was the reason heads were clipped in exported cards.
    person_led = story.kind == "player" or story.slug in {
        "golden-slam", "big-three", "china-tennis",
    }
    default_focus = "50% 24%" if person_led else "50% 42%"
    focus = str(_visual_value(visual, "focus", default_focus))
    photo_source = (
        f' data-photo-source="{html.escape(image_source, quote=True)}"'
        if image_source
        else ""
    )
    return (
        f'<div class="knowledge-photo{portrait_class}{wide_class}{compact_class}{extra}"'
        f'{layout_attr}{photo_source}>'
        f'<i class="kn-back" style="background-image:url(\'{uri}\');'
        f'background-position:{html.escape(focus, quote=True)}"></i>'
        f'<img src="{uri}" alt="" style="object-position:{html.escape(focus, quote=True)}">'
        '<div class="knowledge-photo-copy">'
        f'{sub}<strong>{html.escape(caption)}</strong></div></div>'
    )


def _knowledge_cover_body(
    story: TournamentStory,
    date_label: str,
    visual: object | None = None,
) -> str:
    hooks = {
        "hawkeye": "一场误判，逼网球把判罚交给机器",
        "scoring-history": "网球最奇怪的数字，已经用了几百年",
        "yellow-ball": "网球从白色变黄，不只是为了好看",
        "longest-match": "一场比赛，打了整整三天",
        "golden-slam": "一年拿齐五座最高荣誉，到底有多难",
        "surfaces": "换一块场地，像换了一项运动",
        "big-three": "三个人，重新画出了网球时代",
        "china-tennis": "中国网球的二十年，从哪一冠开始",
    }
    hook = hooks.get(story.slug, story.title)
    if story.hero_marker:
        if story.hero_marker.isdigit() and not re.fullmatch(
            r"(?:18|19|20)\d{2}", story.hero_marker
        ):
            raise ValueError(f"封面年份必须使用四位年份：{story.hero_marker}")
        year = story.hero_marker
    elif story.kind == "player":
        born = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", story.founded)
        year = born.group(0) if born else "PLAYER"
    else:
        # The cover year belongs to the headline claim.  A supporting timeline
        # may begin earlier (for example Laver 1969 before Graf 1988), so using
        # its first row can put the wrong year beside the cover subject.
        hero_year = re.search(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)", story.hero_fact)
        year = (
            hero_year.group(0)
            if hero_year
            else story.moments[0].date[:4] if story.moments else "STORY"
        )
    promise = (
        "那一夜之后，人的眼睛不再拥有最后一句话。"
        if story.slug == "hawkeye"
        else story.hero_fact
    )
    image_path = Path(_visual_value(visual, "path", story.image))
    image_source = str(_visual_value(visual, "source_url", story.image_source_url)).strip()
    uri = _asset_image_uri(image_path)
    if not uri:
        raise FileNotFoundError(image_path)
    person_led = story.kind == "player" or story.slug in {
        "golden-slam", "big-three", "china-tennis",
        "longest-match",
    }
    default_focus = (
        "82% 24%"
        if story.slug == "longest-match"
        else "50% 22%" if person_led else "50% 38%"
    )
    focus = str(_visual_value(visual, "focus", default_focus))
    hook_html = html.escape(hook).replace("，", "，<br>", 1)
    return (
        '<div class="poster cover knowledge-page knowledge-cover" data-visual="verified-photo">'
        + f'<div class="knowledge-cover-bg" data-photo-source="{html.escape(image_source, quote=True)}" '
        + f'style="background-image:url(\'{uri}\');--knowledge-cover-focus:{focus}"></div>'
        + _masthead(date_label)
        + '<div class="knowledge-cover-copy">'
        + '<div class="knowledge-kicker">Tennis Story · 网球有故事</div>'
        + f'<h1>{hook_html}</h1></div>'
        + '<div class="knowledge-hook">'
        + f'<b>{html.escape(year)}</b><p>{html.escape(_card_excerpt(promise, 62))}</p></div>'
        + _FOOTER
        + "</div>"
    )


def _knowledge_timeline_body(
    story: TournamentStory,
    date_label: str,
    visual: object | None = None,
) -> str:
    title_overrides = {
        "hawkeye": "那一夜，发生了什么？",
        "golden-slam": "从1969到1988，格拉芙多拿了哪一冠",
        "surfaces": "场地一换，比赛就变了",
        "big-three": "三个人，怎样接管一个时代",
        "china-tennis": "从李娜到郑钦文，二十年三次破门",
        "scoring-history": "15、30、40，是怎么留下来的",
        "yellow-ball": "一场电视实验，改变了球的颜色",
        "longest-match": "三天十一小时，比赛怎么撑下来的",
    }
    if story.kind == "player":
        default_title = f"{story.title}，从哪一场被记住"
    elif story.kind == "tournament":
        default_title = f"{story.title}的冠军谱系"
    else:
        default_title = f"{story.title}，来路比结论更有意思"
    title = title_overrides.get(story.slug, default_title)
    items: list[tuple[str, str]] = []
    if story.slug == "golden-slam":
        items = [
            (
                "1969：拉沃尔同年拿齐四大满贯",
                "同一年赢下四大满贯；这是公开赛时代男子至今唯一一次。",
            ),
            (
                "四大满贯之外，还要等奥运会",
                "奥运网球四年一次，巅峰赛季必须恰好与奥运年重合。",
            ),
            (
                "1988：格拉芙把金牌也带走",
                "四大满贯之后，她在汉城击败萨巴蒂尼，把奥运金牌也装进同一年。",
            ),
        ]
    else:
        if story.moments:
            items.append((story.moments[0].headline, story.moments[0].detail))
        if len(story.facts) > 1:
            trivia_middle_labels = {
                "big-three": "18 年，没人能挤进来",
            }
            middle_labels = {
                "player": "技术标签不是一天长成的",
                "tournament": "赛事传统在这里定型",
                "trivia": "这个变化为什么留到了今天",
            }
            label = trivia_middle_labels.get(story.slug) or middle_labels.get(
                story.kind, "历史继续往前"
            )
            items.append((label, story.facts[1]))
        if len(story.moments) > 1:
            items.append((story.moments[1].headline, story.moments[1].detail))
    if not items:
        items = [("关键事实", fact) for fact in story.facts[:3]]
    rows = "".join(
        '<div class="knowledge-moment">'
        + _semantic_marker_for_text(
            f"{headline} {detail}", index, story_kind=story.kind
        )
        + f'<div><b>{html.escape(headline)}</b>'
        f'<p>{html.escape(_card_excerpt(detail, 50))}</p></div></div>'
        for index, (headline, detail) in enumerate(items[:3])
    )
    verdict = (
        "问题不只是一个球看错，而是关键分曾经无处申诉。"
        if story.slug == "hawkeye"
        else (
            "拉沃尔同年拿齐四大满贯；格拉芙在1988年又把奥运金牌放进同一个赛季。"
            if story.slug == "golden-slam"
            else story.hero_fact
        )
    )
    visual_years = [moment.date[:4] for moment in story.moments[:3]]
    if story.founded:
        visual_years.insert(0, story.founded)
    has_photo = visual is not None
    if has_photo:
        first = story.moments[0] if story.moments else None
        photo_caption = (
            "同一年拿齐四大满贯"
            if story.slug == "golden-slam"
            else first.headline if first else story.venue
        )
        media = _knowledge_photo(
            story,
            photo_caption,
            (
                f"{first.date[:4]} · {first.age} · {first.player}"
                if first and story.slug == "big-three"
                else f"{first.date[:4]} · {first.player}" if first else story.location
            ),
            visual=visual,
            compact=True,
        )
    else:
        media = (
            _hawkeye_story_visual()
            if story.slug == "hawkeye"
            else (
                _longest_match_story_visual()
                if story.slug == "longest-match"
                else _timeline_visual(
                    visual_years, css_class="knowledge-story-visual"
                )
            )
        )
    page_class = " has-page-photo" if has_photo else ""
    return (
        f'<div class="poster knowledge-page{page_class}" data-visual="narrative-timeline">'
        + _masthead(date_label)
        + _titleband("The Story · 故事现场", title)
        + media
        + f'<div class="knowledge-timeline">{rows}</div>'
        + f'<div class="knowledge-verdict">{html.escape(_card_excerpt(verdict, 60))}</div>'
        + _FOOTER
        + "</div>"
    )


def _hawkeye_official_flow_body(date_label: str) -> str:
    return (
        '<div class="poster knowledge-page" data-visual="rule-diagram">'
        + _masthead(date_label)
        + _titleband("Sony / Hawk-Eye Official Workflow", "鹰眼不看回放，它重建轨迹")
        + '<div class="official-flow">'
        + '<article class="official-step"><header>'
        + _semantic_marker("camera", "取像", mini=True)
        + '<b>每台相机先找球心</b><span class="official-code">2D VISION</span></header>'
        + '<div class="official-visual"><svg viewBox="0 0 420 172">'
        + '<rect x="16" y="17" width="168" height="112" fill="#0F4B3D" stroke="#78D3DC" stroke-width="2"/>'
        + '<rect x="236" y="17" width="168" height="112" fill="#0F4B3D" stroke="#78D3DC" stroke-width="2"/>'
        + '<circle cx="122" cy="55" r="12" fill="#D3FF12"/><circle cx="284" cy="91" r="12" fill="#D3FF12"/>'
        + '<text x="61" y="154" fill="#A9B9B0" font-size="17">CAMERA A</text>'
        + '<text x="281" y="154" fill="#A9B9B0" font-size="17">CAMERA B</text></svg>'
        + '<p>同一颗球，在不同画面里的位置不同</p></div></article>'
        + '<article class="official-step"><header>'
        + _semantic_marker("scan", "定位", mini=True)
        + '<b>视线交会，算出空间位置</b><span class="official-code">3D</span></header>'
        + '<div class="official-visual"><svg viewBox="0 0 420 172">'
        + '<circle cx="42" cy="39" r="12" fill="#FF765F"/><circle cx="42" cy="137" r="12" fill="#FF765F"/>'
        + '<line x1="54" y1="39" x2="292" y2="88" stroke="#78D3DC" stroke-width="3"/>'
        + '<line x1="54" y1="137" x2="292" y2="88" stroke="#78D3DC" stroke-width="3"/>'
        + '<circle cx="292" cy="88" r="15" fill="#D3FF12"/><text x="320" y="96" fill="#78D3DC" font-size="20">X / Y / Z</text></svg>'
        + '<p>两台以上相机交叉定位</p></div></article>'
        + '<article class="official-step"><header>'
        + _semantic_marker("route", "轨迹", mini=True)
        + '<b>连续帧连成3D轨迹</b><span class="official-code">TIME</span></header>'
        + '<div class="official-visual"><svg viewBox="0 0 420 172">'
        + '<path d="M35 135 Q190 8 382 138" fill="none" stroke="#78D3DC" stroke-width="4"/>'
        + '<g fill="#D3FF12"><circle cx="43" cy="129" r="9"/><circle cx="112" cy="70" r="9"/>'
        + '<circle cx="193" cy="43" r="9"/><circle cx="282" cy="65" r="9"/><circle cx="372" cy="130" r="9"/></g></svg>'
        + '<p>球心位置随时间连接，得到完整路径</p></div></article>'
        + '<article class="official-step"><header>'
        + _semantic_marker("circle-check", "判定", mini=True)
        + '<b>计算弹跳点，再与边线比对</b><span class="official-code">CALL</span></header>'
        + '<div class="official-visual"><svg viewBox="0 0 420 172">'
        + '<rect x="62" y="73" width="298" height="22" fill="#F7F3E8"/>'
        + '<ellipse cx="257" cy="68" rx="42" ry="28" fill="#D3FF12" stroke="#0C362B" stroke-width="4"/>'
        + '<text x="274" y="135" fill="#D3FF12" font-size="30" font-weight="700">IN · 界内</text></svg>'
        + '<p>最终画面是CG可视化，不是慢动作录像</p></div></article></div>'
        + '<div class="official-facts"><div><b>8–12台</b><span>多机位光学摄像机</span></div>'
        + '<div><b>最高340fps</b><span>同步捕捉高速网球</span></div>'
        + '<div><b>&lt;2mm</b><span>Sony公布的系统误差</span></div></div>'
        + '<div class="official-summary"><b>一句看懂：</b>先在每幅画面找到球，'
        + '再用多个角度算出它在三维空间的位置。</div>'
        + _FOOTER
        + "</div>"
    )


def _longest_match_record_body(
    date_label: str,
    story: TournamentStory | None = None,
    visual: object | None = None,
) -> str:
    photo = ""
    if story is not None and visual is not None:
        photo = _knowledge_photo(
            story,
            "决胜盘138局，记分牌最终定格70-68",
            "2010 · 温网18号球场",
            visual=visual,
            compact=True,
            extra_class="marathon-event-photo",
        )
    return (
        '<div class="poster knowledge-page" data-visual="rule-diagram">'
        + _masthead(date_label)
        + _titleband("Match Anatomy · 比赛解剖", "为什么这场球能打到70-68")
        + photo
        + (
            ""
            if photo
            else '<div class="marathon-rule"><article class="marathon-rule-block">'
            '<small>2010年温网决胜盘</small><strong>6-6 → 继续</strong>'
            '<p>当时没有抢七，必须领先两局才能结束。</p></article>'
            '<div class="marathon-rule-arrow">→</div>'
            '<article class="marathon-rule-block"><small>比分被不断推高</small>'
            '<strong>70-68</strong><p>第五盘单独打了138局。</p></article></div>'
        )
        + '<div class="marathon-scoreline"><header><span>五盘完整比分</span>'
        + '<b>伊斯内尔 3-2 马胡</b></header><div class="marathon-sets">'
        + '<div class="marathon-set"><small>第一盘</small><strong>6-4</strong></div>'
        + '<div class="marathon-set"><small>第二盘</small><strong>3-6</strong></div>'
        + '<div class="marathon-set"><small>第三盘</small><strong>6-7</strong></div>'
        + '<div class="marathon-set"><small>第四盘</small><strong>7-6</strong></div>'
        + '<div class="marathon-set"><small>决胜盘</small><strong>70-68</strong></div>'
        + '</div></div>'
        + '<div class="marathon-records">'
        + '<article class="marathon-record"><strong>11:05</strong><b>总时长</b>'
        + '<span>跨越三个比赛日</span></article>'
        + '<article class="marathon-record"><strong>183</strong><b>总局数</b>'
        + '<span>其中决胜盘138局</span></article>'
        + '<article class="marathon-record"><strong>216</strong><b>ACE总数</b>'
        + '<span>伊斯内尔113，马胡103</span></article></div>'
        + '<div class="marathon-summary">不是双方不肯结束，而是旧规则没有给决胜盘设置出口。</div>'
        + _FOOTER
        + "</div>"
    )


def _knowledge_fact_body(
    story: TournamentStory,
    date_label: str,
    visual: object | None = None,
) -> str:
    facts = story.facts[:3]
    if story.slug == "golden-slam":
        facts = (
            "四大满贯横跨硬地、红土和草地，整季状态不能掉线。",
            "奥运网球四年一次，巅峰期还必须恰好撞上奥运年。",
            "五项冠军必须全部发生在同一个自然年，1988年的格拉芙至今唯一。",
        )
    lead = "" if visual is not None else _explainer_mark()
    if story.kind == "player":
        cards = []
        for index, fact in enumerate(facts):
            age = re.search(r"(\d{1,2})\s*岁", fact)
            role = story.fact_roles[index] if index < len(story.fact_roles) else ""
            marker = (
                f'<span class="meaningful-stat"><em>{html.escape(age.group(1))}</em>'
                '<small>岁</small></span>'
                if age
                else _semantic_marker_for_text(
                    fact, index, story_kind=story.kind, role=role
                )
            )
            cards.append(
                '<article class="player-pillar">'
                f'{marker}'
                f'<p>{html.escape(_card_excerpt(fact, 38))}</p></article>'
            )
        content = lead + '<div class="player-pillars">' + "".join(cards) + "</div>"
        title = f"{story.title}，从起点到被看见"
    elif story.kind == "tournament":
        profile = (
            '<div class="event-profile">'
            f'<article><em>{html.escape(story.founded.replace("始于 ", ""))}</em><span>赛事起点</span></article>'
            f'<article><em>{html.escape(story.level)}</em><span>巡回赛级别</span></article>'
            f'<article><em>{html.escape(story.surface)}</em><span>场地类型</span></article></div>'
        )
        notes = "".join(
            '<div class="event-note">'
            + _semantic_marker_for_text(
                fact,
                index,
                story_kind=story.kind,
                role=story.fact_roles[index] if index < len(story.fact_roles) else "",
            )
            + f'<p>{_card_excerpt_html(fact, 42)}</p></div>'
            for index, fact in enumerate(facts)
        )
        content = lead + profile + f'<div class="event-notes">{notes}</div>'
        title = f"{story.title}，冠军与传统如何写成"
    else:
        cards = "".join(
            '<article class="knowledge-fact-card">'
            + _semantic_marker_for_text(
                fact,
                index,
                story_kind=story.kind,
                role=story.fact_roles[index] if index < len(story.fact_roles) else "",
            )
            + f'<p>{html.escape(_card_excerpt(fact, 40))}</p></article>'
            for index, fact in enumerate(facts)
        )
        content = lead + f'<div class="knowledge-fact-grid">{cards}</div>'
        trivia_titles = {
            "scoring-history": "四个数字，藏着几百年争论",
            "yellow-ball": "从白到黄，电视改变了网球",
            "longest-match": "比分之外，身体经历了什么",
            "golden-slam": "金满贯难在哪？五项冠军必须挤进同一年",
            "surfaces": "材质一变，弹跳与战术全变",
            "big-three": "三个名字，三条统治曲线",
            "china-tennis": "二十年，中国网球三次破门",
        }
        title = trivia_titles.get(story.slug, f"{story.title}，真正难在哪里")
    has_photo = visual is not None
    page_class = " has-page-photo" if has_photo else ""
    if story.slug == "big-three" and len(story.moments) > 1:
        mid = story.moments[1]
        caption = mid.headline
        subline = f"{mid.date[:4]} · {mid.age} · {mid.player}"
    else:
        caption, subline = story.venue, story.location
    media = (
        _knowledge_photo(
            story,
            caption,
            subline,
            visual=visual,
            compact=True,
        )
        if visual is not None
        else ""
    )
    return (
        f'<div class="poster knowledge-page{page_class}" data-visual="{html.escape(story.kind)}-explainer">'
        + _masthead(date_label)
        + _titleband("Visual Explainer · 图解", title)
        + media
        + content
        + _FOOTER
        + "</div>"
    )


def _knowledge_today_body(
    story: TournamentStory,
    date_label: str,
    question: str,
    year: int,
    visual: object | None = None,
) -> str:
    if story.slug == "hawkeye":
        title = "从举手挑战，到实时电子司线"
        rows = (
            ("2006", "鹰眼挑战制进入美网", "球员可以主动挑战判罚，现场大屏给出结果。"),
            ("2021", "澳网、美网采用实时电子司线", "从“球员申请复核”，走向系统主动完成判定。"),
            ("2025", "温网告别人工司线", "延续近150年的传统，也最终让位于电子判罚。"),
        )
        eyebrow = f"{year} · 最后的例外"
        question = "四大满贯中，只剩法网仍保留人工司线。红土球印，足够可靠吗？"
    else:
        today_titles = {
            "golden-slam": "1988之后，为什么没人复制这条夺冠路线",
            "surfaces": "今天看球，先看脚下这块地",
            "big-three": "时代散场，纪录仍在追人",
            "china-tennis": "从第一冠到下一代，故事没停",
            "scoring-history": "数字没变，比赛已经变了",
            "yellow-ball": "今天每颗黄球，都来自那次选择",
            "longest-match": "规则改了，那样的比赛不会重演",
        }
        if story.kind == "player":
            default_today_title = f"今天再看{story.title}，该看什么"
        elif story.kind == "tournament":
            default_today_title = f"这项赛事，怎样走到今天"
        else:
            default_today_title = f"{story.title}，今天留下了什么"
        title = today_titles.get(story.slug, default_today_title)
        if story.slug == "golden-slam":
            rows = (
                (
                    "1969",
                    "拉沃尔同年拿齐四大满贯",
                    "美网决赛击败罗切，成为公开赛时代至今唯一同年拿齐四大满贯的男子球员。",
                ),
                (
                    "1988",
                    "格拉芙再加一枚奥运金牌",
                    "四大满贯之后，她又赢下汉城奥运会，五座冠军全部装进同一年。",
                ),
            )
        else:
            rows = tuple(
                (
                    moment.date[:4],
                    moment.headline,
                    moment.detail,
                )
                for moment in story.moments[:3]
            )
        eyebrow_labels = {
            "player": "这一代球迷的记忆",
            "tournament": "下一站仍在继续",
            "trivia": "把问题留到今天",
        }
        eyebrow = f"{year} · {eyebrow_labels.get(story.kind, '今天的回响')}"
    years = "".join(
        '<div class="knowledge-year">'
        f'<time>{html.escape(row_year)}</time><div><b>{html.escape(headline)}</b>'
        f'<p>{html.escape(_card_excerpt(detail, 48))}</p></div></div>'
        for row_year, headline, detail in rows
    )
    has_photo = visual is not None
    if has_photo:
        last = story.moments[-1] if story.moments else None
        photo_caption = (
            "四大满贯之后，又拿奥运金牌"
            if story.slug == "golden-slam"
            else (
                "18号球场留下了这块纪念牌"
                if story.slug == "longest-match"
                else last.headline if last else story.hero_fact
            )
        )
        photo_meta = (
            "2010 · 温网18号球场"
            if story.slug == "longest-match"
            else (
                f"{last.date[:4]} · {last.age} · {last.player}"
                if last and story.slug == "big-three"
                else f"{last.date[:4]} · {last.player}" if last else story.location
            )
        )
        media = _knowledge_photo(
            story,
            photo_caption,
            photo_meta,
            visual=visual,
            compact=True,
        )
    else:
        media = (
            _hawkeye_today_visual()
            if story.slug == "hawkeye"
            else (
                _longest_match_today_visual()
                if story.slug == "longest-match"
                else _timeline_visual(
                    [row[0] for row in rows], css_class="today-visual"
                )
            )
        )
    page_class = " has-page-photo" if has_photo else ""
    if story.slug == "longest-match" and not has_photo:
        return (
            '<div class="poster knowledge-page" data-visual="history-timeline">'
            + _masthead(date_label)
            + _titleband("Then & Now · 从过去到今天", title)
            + media
            + '<div class="knowledge-question">'
            + f'<small>{html.escape(eyebrow)}</small>'
            + f'<strong>{html.escape(question)}</strong></div>'
            + _FOOTER
            + "</div>"
        )
    return (
        f'<div class="poster knowledge-page{page_class}" data-visual="history-timeline">'
        + _masthead(date_label)
        + _titleband("Then & Now · 从过去到今天", title)
        + media
        + f'<div class="knowledge-years count-{len(rows)}">{years}</div>'
        + '<div class="knowledge-question">'
        + f'<small>{html.escape(eyebrow)}</small><strong>{html.escape(question)}</strong></div>'
        + _FOOTER
        + "</div>"
    )


def knowledge_deck_bodies(
    story: TournamentStory,
    date_label: str,
    *,
    question: str,
    year: int,
    page_visuals: Mapping[str, object] | None = None,
) -> list[tuple[str, str]]:
    """Return a four-page, evidence-backed story deck for social publishing."""
    page_visuals = page_visuals or {}
    diagram_builders = {
        "trajectory": _hawkeye_official_flow_body,
        "marathon": _longest_match_record_body,
    }
    if story.diagram_type:
        try:
            if story.diagram_type == "marathon":
                explainer = _longest_match_record_body(
                    date_label,
                    story,
                    page_visuals.get("explainer"),
                )
            else:
                explainer = diagram_builders[story.diagram_type](date_label)
        except KeyError as exc:
            raise ValueError(f"未实现的规则示意图类型：{story.diagram_type}") from exc
    else:
        explainer = _knowledge_fact_body(
            story,
            date_label,
            page_visuals.get("explainer"),
        )
    return [
        ("knowledge", _knowledge_cover_body(story, date_label, page_visuals.get("cover"))),
        (
            "story",
            _knowledge_timeline_body(story, date_label, page_visuals.get("story")),
        ),
        ("explainer", explainer),
        (
            "today",
            _knowledge_today_body(
                story,
                date_label,
                question,
                year,
                page_visuals.get("today"),
            ),
        ),
    ]


def rankings_body(rankings, date_label: str) -> str:
    from .common import CHINESE_PLAYER_NAMES

    def rrow(e) -> str:
        zh = player_zh(e.name)
        en = e.name if zh != e.name else ""
        mv, cls = "—", "flat"
        if e.move > 0:
            mv, cls = f"↑{e.move}", "up"
        elif e.move < 0:
            mv, cls = f"↓{-e.move}", "down"
        pts = f'<span class="pts">{int(e.points)}分</span>' if e.points else ""
        en_html = f'<span class="en">{html.escape(en)}</span>' if en else ""
        return (
            f'<div class="rrow"><span class="no">{e.rank}</span>'
            f'<span class="rnames"><em class="name" style="font-style:normal">{html.escape(zh)}</em>{en_html}</span>'
            f'{pts}<span class="mv {cls}">{mv}</span></div>'
        )

    def section(title: str, entries) -> str:
        rows = "".join(rrow(e) for e in entries[:5])
        return f'<article class="card rank-card"><h3>{title}</h3>{rows}</article>'

    cn = [
        e for e in (rankings.atp + rankings.wta)
        if player_zh(e.name) in CHINESE_PLAYER_NAMES
    ][:4]
    cn_html = ""
    if cn:
        cn_html = _seclabel("中 国 球 员 动 态") + section("Team China", cn)
    return (
        '<div class="poster rankings-page">'
        + _masthead(date_label)
        + _titleband("Weekly Rankings · 本周排名", "本周排名")
        + section("ATP Top 5", rankings.atp)
        + section("WTA Top 5", rankings.wta)
        + cn_html
        + _FOOTER
        + "</div>"
    )


# ---------- 截图 ----------


def _chromium_executable() -> str | None:
    import glob
    import os

    for base in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), "/opt/pw-browsers"):
        if not base:
            continue
        hits = sorted(glob.glob(f"{base}/chromium-*/chrome-linux/chrome"))
        if hits:
            return hits[-1]
    return None


def _screenshot_pages(pages: list[tuple[str, str]], theme: str):
    """一次浏览器会话渲染多页，返回 [(kind, PIL.Image)]（2x 超采样）."""
    import io

    from PIL import Image
    from playwright.sync_api import sync_playwright

    out = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            exe = _chromium_executable()
            if not exe:
                raise
            browser = p.chromium.launch(executable_path=exe)
        try:
            for kind, body in pages:
                # A fresh page per card prevents Chromium from carrying scroll
                # restoration state from a taller preceding document.
                page = browser.new_page(
                    viewport={"width": W, "height": H}, device_scale_factor=2
                )
                try:
                    page.set_content(_shell(body, theme))
                    page.wait_for_function(
                        "document.fonts.status === 'loaded'", timeout=15000
                    )
                    page.wait_for_function(
                        "Array.from(document.images).every(img => img.complete)",
                        timeout=15000,
                    )
                    page.evaluate("window.scrollTo(0, 0)")
                    layout = page.evaluate(
                        """() => {
                          const poster = document.querySelector('.poster.knowledge-page:not(.cover)');
                          if (!poster) return null;
                          const footer = poster.querySelector(':scope > .footer');
                          const footerTop = footer ? footer.getBoundingClientRect().top : 1440;
                          const flow = Array.from(poster.children).filter((node) => {
                            if (node === footer) return false;
                            const style = getComputedStyle(node);
                            return style.position !== 'absolute' && style.display !== 'none';
                          });
                          const maxBottom = Math.max(
                            poster.getBoundingClientRect().top,
                            ...flow.map((node) => node.getBoundingClientRect().bottom),
                          );
                          const photo = poster.querySelector('[data-photo-layout="inner-hero"]');
                          const overflow = Array.from(poster.querySelectorAll(
                            '.official-step,.knowledge-moment,.knowledge-fact-card,' +
                            '.event-note,.knowledge-question'
                          )).filter((node) => node.scrollHeight > node.clientHeight + 2)
                            .map((node) => node.className);
                          return {
                            photoHeight: photo ? photo.getBoundingClientRect().height : 0,
                            footerTop,
                            maxBottom,
                            posterScrollHeight: poster.scrollHeight,
                            documentScrollHeight: document.documentElement.scrollHeight,
                            overflow,
                          };
                        }"""
                    )
                    if layout:
                        if layout["photoHeight"] and layout["photoHeight"] < 475:
                            raise RuntimeError(
                                f"{kind} 页内图实际高度仅 {layout['photoHeight']:.0f}px"
                            )
                        if layout["maxBottom"] > layout["footerTop"] - 12:
                            raise RuntimeError(
                                f"{kind} 页正文与页脚重叠："
                                f"content={layout['maxBottom']:.0f}, footer={layout['footerTop']:.0f}"
                            )
                        if layout["posterScrollHeight"] > H + 2 or layout["documentScrollHeight"] > H + 2:
                            raise RuntimeError(f"{kind} 页内容超出 {H}px 画布")
                        if layout["overflow"]:
                            raise RuntimeError(
                                f"{kind} 页文本块溢出：{', '.join(layout['overflow'])}"
                            )
                    # Full-page capture always starts at document coordinates 0,0.
                    # Fixed clips have shown intermittent viewport offsets on CI.
                    shot = page.screenshot(type="png", full_page=True)
                    img = Image.open(io.BytesIO(shot)).convert("RGB")
                    if img.height > img.width * H / W:
                        img = img.crop((0, 0, img.width, round(img.width * H / W)))
                    if img.size != (W, H):
                        img = img.resize((W, H), Image.LANCZOS)
                    out.append((kind, img))
                finally:
                    page.close()
        finally:
            browser.close()
    return out


def generate_deck(
    digest: Digest,
    date_label: str,
    theme: str = "dark",
    *,
    cover_visual: object | None = None,
):
    """整组晨报卡（与 cards.generate_cards 的选卡逻辑一致），返回 [(kind, Image)]."""
    from .titles import cover_highlights

    pages: list[tuple[str, str]] = []
    # V1 唯一封面：不再输出"钩子页 + 设计封面"双封面
    headline, secondary = cover_highlights(digest)
    pages.append(("cover", cover_body(
        digest, headline, secondary, date_label, cover_visual=cover_visual,
    )))

    lead = daily_lead_match(digest)
    lead_id = lead.match_id if lead is not None else None
    if lead is not None:
        lead_kind = "result" if lead.status.is_final else "preview"
        pages.append(("lead", insight_body(lead, date_label, lead_kind, digest.today)))

    if lead is not None and brief_for_match(lead, digest.today) is not None:
        pages.append(("media", media_body(lead, date_label, digest.today)))

    if lead is not None and lead.status.is_final and has_detailed_stats(lead):
        pages.append(("focus", focus_body(lead, date_label)))

    singles = [
        m for m in digest.results
        if m.is_singles and m.match_id != lead_id
    ]
    if singles:
        # 速递页按比赛本身分量排序（中国场次不加权放大，出现时打标签即可）
        board = top_results(singles, 8, cn_boost=False)
        page2 = board[4:8]
        total = 2 if page2 else 1
        pages.append(("scoreboard", scoreboard_body(
            board[:4], date_label, with_hero=True, page=1, total=total,
        )))
        if page2:
            pages.append(("results2", scoreboard_body(
                page2, date_label, with_hero=False, page=2, total=total,
            )))

    tonight_events = tonight_event_focus(digest.schedule)
    if tonight_events:
        for index, event_matches in enumerate(tonight_events, start=1):
            kind = "tonight" if index == 1 else f"tonight{index}"
            pages.append((kind, tonight_body(event_matches, date_label)))

    if digest.today.weekday() == 0 and digest.rankings is not None:
        try:
            pages.append(("rankings", rankings_body(digest.rankings, date_label)))
        except Exception as e:  # noqa: BLE001
            logger.warning("排名卡生成失败（跳过）: %s", e)

    # Cover, result recap, and every eligible event page are core editorial
    # content. Only weekly rankings may be
    # dropped when the deck grows; yesterday's scoreboards must never disappear
    # merely because several tour events share the same day.
    protected = sum(
        kind in {
            "cover",
            "lead",
            "media",
            "focus",
            "scoreboard",
            "results2",
        }
        or kind.startswith("tonight")
        for kind, _body in pages
    )
    target_pages = max(10, protected)
    if len(pages) > target_pages:
        pages = [page for page in pages if page[0] != "rankings"]

    return _screenshot_pages(pages, theme)


def generate_match_deck(
    match: Match,
    *,
    headline: str,
    today,
    date_label: str,
    kind: str,
    theme: str = "dark",
    cover_visual: object | None = None,
):
    """单场热点/赛前统一卡组，复用晨报同一套HTML视觉组件。"""
    from .story import result_insight

    is_result = kind == "result"
    digest = Digest(
        today=today,
        results=[match] if is_result else [],
        schedule=[] if is_result else [match],
    )
    secondary = result_insight(match) if is_result else preview_angle(match, today)
    pages: list[tuple[str, str]] = [
        ("cover", cover_body(
            digest, headline, secondary, date_label, cover_visual=cover_visual,
        )),
    ]
    if is_result:
        pages.extend(
            [
                ("score", scoreboard_body([match], date_label)),
                ("breakdown", focus_body(match, date_label)),
            ]
        )
    else:
        pages.append(("match", tonight_body([match], date_label)))
    pages.extend(
        [
            ("insight", insight_body(match, date_label, kind, today)),
            ("discussion", discussion_body(match, date_label, kind)),
        ]
    )
    return _screenshot_pages(pages, theme)


def render_scoreboard(matches: list[Match], date_label: str, theme: str = "dark"):
    """单独渲染赛果速递卡（兼容旧调用），返回 PIL Image."""
    return _screenshot_pages(
        [("scoreboard", scoreboard_body(matches, date_label))], theme
    )[0][1]
