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
from functools import lru_cache
from pathlib import Path

from ..digest import Digest
from ..models import Match
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from ..zh.countries import country_iso2
from .common import (
    _abbrev_en,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
)
from .focus import focus_comparison, has_detailed_stats, select_focus_match
from .rating import find_upset, is_upset, match_score, tonight_focus, top_results
from .story import (
    chinese_side_won,
    is_chinese_player,
    recommendation_label,
    result_insight,
    schedule_insight,
    sort_china_matches,
)
from .titles import daily_lead_match
from .tournament_story import TournamentStory, pick_tournament_story

logger = logging.getLogger(__name__)

W, H = 1080, 1440
ASSETS = Path(__file__).resolve().parents[3] / "assets"

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
.poster:not(.cover) { isolation:isolate; }
.poster:not(.cover)::before { content:""; position:absolute; inset:0;
  background:
    linear-gradient(180deg,rgba(1,13,11,.78) 0%,rgba(1,13,11,.5) 34%,rgba(1,13,11,.82) 100%),
    linear-gradient(90deg,rgba(1,13,11,.48) 0%,rgba(1,13,11,.08) 75%),
    var(--inner-bg) center 48%/cover no-repeat;
  opacity:.72; pointer-events:none; }
html.light .poster:not(.cover)::before { opacity:.16; }
.poster:not(.cover)>* { position:relative; z-index:1; }

.masthead { display:flex; align-items:center; gap:16px; }
.brand-icon { width:54px; height:54px; object-fit:contain; flex:none; }
.ball { width:44px; height:44px; border-radius:50%; background:var(--neon); position:relative; overflow:hidden; flex:none; }
.ball::before, .ball::after { content:""; position:absolute; width:36px; height:36px; border:4px solid var(--ground0); border-radius:50%; }
.ball::before { left:-22px; top:4px; } .ball::after { right:-22px; top:4px; }
.brand { font-weight:700; font-size:34px; letter-spacing:2px; line-height:1.2; }
.poster:not(.cover) .brand { font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:40px; font-weight:400; letter-spacing:0; }
.date { margin-left:auto; font-family:'Barlow Condensed'; font-weight:600; font-size:30px; letter-spacing:2px; color:var(--fade); }

.titleband { margin:20px 0 16px; padding-left:18px; border-left:6px solid var(--section-accent); }
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
  background:linear-gradient(180deg,rgba(1,13,11,.5) 0%,rgba(1,13,11,.08) 31%,rgba(1,13,11,.38) 58%,rgba(1,13,11,.96) 100%),
    linear-gradient(90deg,rgba(1,13,11,.9) 0%,rgba(1,13,11,.7) 54%,rgba(1,13,11,.08) 100%); }
.cover::after { content:""; position:absolute; left:0; right:0; top:0; height:12px; z-index:5;
  background:linear-gradient(90deg,var(--neon) 0 42%,var(--coral) 42% 72%,var(--sky) 72%); }
.cover-bg { position:absolute; inset:0; z-index:0; background-size:cover; background-position:center; }
.cover .masthead,.cover .footer { position:relative; z-index:3; }
.cover .brand { font-family:'TL Display SC','TL Sans SC',sans-serif; font-size:42px; font-weight:400; letter-spacing:0; }
.cover .date { color:#D6E3DD; }
.cover-copy { position:relative; z-index:2; width:850px; }
.cover-date { display:flex; align-items:flex-end; gap:22px; margin-top:50px; }
.cover-date b { font-family:'Barlow Condensed'; font-weight:700; font-size:130px; line-height:.82; color:var(--neon); }
.cover-date span { display:flex; flex-direction:column; gap:8px; padding-bottom:4px; }
.cover-date i { font-style:normal; font-size:40px; font-weight:700; color:#fff; line-height:1; }
.cover-date small { font-family:'Barlow Condensed'; font-size:22px; color:#B9C8C1; letter-spacing:3px; line-height:1; }
.edition { display:inline-block; margin-top:34px; padding:8px 14px; border:1px solid rgba(214,255,0,.7);
  color:var(--neon); font-family:'Barlow Condensed'; font-size:24px; font-weight:600; letter-spacing:4px; line-height:1.2; }
.cover .focus-label { font-family:'Barlow Condensed'; font-weight:600; font-size:23px;
  letter-spacing:.34em; color:#E4C96E; text-transform:uppercase; margin-top:24px; }
.cover .focus { font-family:'TL Display SC','TL Sans SC',sans-serif; font-size:66px; font-weight:400;
  line-height:1.1; letter-spacing:0; margin-top:12px; color:#fff; max-width:900px;
  text-shadow:0 6px 24px rgba(0,0,0,.55); display:-webkit-box; -webkit-line-clamp:2;
  -webkit-box-orient:vertical; overflow:hidden; }
.cover .secondary { margin-top:22px; padding-left:18px; border-left:6px solid var(--coral);
  color:#E6EEEA; font-size:28px; font-weight:700; line-height:1.45; max-width:820px;
  text-shadow:0 3px 14px rgba(0,0,0,.7); }
.cover-lower { position:relative; z-index:3; width:900px; margin-top:auto; margin-bottom:20px; }
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
  font-size:37px; font-weight:400; color:#fff; line-height:1.12;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cover-highlight span { display:block; margin-top:8px; color:#C6D2CC; font-size:20px;
  line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cover .chips { display:flex; flex-wrap:wrap; gap:10px; margin-top:17px; }
.cover .chips span { background:rgba(4,26,21,.72); border:1px solid rgba(255,255,255,.32);
  color:#F6F7F2; font-size:21px; font-weight:700; padding:9px 14px; border-radius:5px;
  box-shadow:0 5px 18px rgba(0,0,0,.24); line-height:1.2; }
.cover .footer { margin-top:0; color:#C2CEC8; }

/* ---------- 今晚焦点 ---------- */
.tonight-page h1 { font-size:62px; }
.tonight-page .titleband { margin:16px 0 10px; }
.pick { border-left:5px solid var(--sky); padding:7px 26px 8px; margin-bottom:8px; }
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
.pick .reason i { display:inline-block; margin-right:9px; padding:2px 7px; border-radius:4px;
  background:rgba(118,215,234,.14); color:var(--sky); font-family:'Barlow Condensed'; font-size:18px;
  font-weight:700; font-style:normal; letter-spacing:1px; vertical-align:2px; }

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

.insight-hero { margin-top:18px; padding:28px 30px 30px;
  background:var(--panel-strong); border:1px solid var(--panel-border);
  border-left:7px solid var(--section-accent); border-radius:8px;
  box-shadow:var(--cardshadow); }
.insight-hero small { display:block; font-family:'Barlow Condensed'; font-size:24px;
  font-weight:600; letter-spacing:.28em; color:var(--section-accent); text-transform:uppercase; }
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
    return (
        f'<div class="masthead">{icon}<span class="brand">网球时差</span>'
        f'<span class="date">{html.escape(date_label)}</span></div>'
    )


def _titleband(kicker: str, title: str) -> str:
    return (
        f'<div class="titleband"><div class="kicker">{kicker}</div>'
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


def _sched_card(m: Match, *, with_reason: bool = False) -> str:
    """赛程卡：时间、对阵，以及可核验的推荐理由."""
    g = group_by_tournament([m])[0]
    meta = html.escape(match_round_display(m) or "")
    tour_txt = html.escape(g.name_zh)
    level_badge = html.escape(g.compact_level)
    t = fmt_time_beijing(m.start_utc)
    right = f'<span class="htime">{t}</span>'
    reason = ""
    card_class = "card"
    if with_reason:
        label = recommendation_label(m)
        label_icon = {"必看": "flame", "推荐": "star", "关注": "eye", "可选": "circle"}[label]
        right = (
            f'<span class="rating">{_icon_html(label_icon)}'
            f'<span>{html.escape(label)}</span></span>' + right
        )
        source = ""
        reason_label = "看点"
        if m.editorial_url and m.editorial_source:
            reason_label = "媒体"
            source = f'<i>{html.escape(m.editorial_source.upper())}</i>'
        reason = (
            f'<div class="reason"><b>{_icon_html("eye")}<span>{reason_label}</span></b>{source}'
            f'{html.escape(schedule_insight(m))}</div>'
        )
        card_class += " pick"
    return (
        f'<article class="{card_class}">'
        f'<header><span class="hl"><b class="tour-level">{level_badge}</b>'
        f'<span class="round">{tour_txt} · {meta}</span></span>'
        f'<span class="hl">{right}</span></header>'
        f"{_side_html(m, 0, 0, with_sets=False)}{_side_html(m, 1, 0, with_sets=False)}"
        f"{reason}"
        "</article>"
    )


def _seclabel(text: str) -> str:
    return f'<div class="seclabel"><i></i><span>{html.escape(text)}</span><i></i></div>'


# ---------- 各卡页面 ----------


def cover_body(
    digest: Digest, headline: str, secondary: str, date_label: str
) -> str:
    d = digest.today
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()]
    weekday_en = [
        "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY",
        "FRIDAY", "SATURDAY", "SUNDAY",
    ][d.weekday()]
    chips = []
    if digest.results:
        chips.append(f"赛果复盘 {len(digest.results)} 场")
    if digest.schedule:
        chips.append(f"后续赛程 {len(digest.schedule)} 场")
    overnight = top_results(
        [match for match in digest.results if match.is_singles],
        2,
        cn_boost=True,
    )
    lead = daily_lead_match(digest)
    focus_matches = tonight_focus(digest.schedule)
    focus_count = len(focus_matches)
    if focus_count:
        chips.append(f"今晚焦点 {focus_count} 场")
    chips_html = "".join(f"<span>{c}</span>" for c in chips)
    background_uri = _asset_image_uri(ASSETS / "covers" / "tennis-night-court.png")
    background = (
        f'<div class="cover-bg" style="background-image:url(\'{background_uri}\')"></div>'
        if background_uri else ""
    )
    secondary_html = (
        f'<div class="secondary">{html.escape(secondary)}</div>' if secondary else ""
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
        return (
            '<article class="cover-highlight">'
            f'<small>{_icon_html(icon)}{html.escape(label)}</small><b>{html.escape(value)}</b>'
            f'<span>{html.escape(meta)}</span></article>'
        )

    support: list[tuple[str, Match]] = []
    lead_id = lead.match_id if lead else None
    chinese = [
        match for match in digest.results + digest.schedule
        if is_chinese_involved(match) and match.match_id != lead_id
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
    lead_label = "Overnight Lead · 昨夜头条" if lead else "Today's Lead · 今日头条"
    return (
        '<div class="poster cover">'
        + background
        + _masthead(date_label)
        + '<div class="cover-copy">'
        + f'<div class="cover-date"><b>{d.month:02d}.{d.day:02d}</b><span>'
        + f'<i>{weekday}</i><small>{weekday_en} · BEIJING TIME</small></span></div>'
        + '<div class="edition">DAILY MATCH BRIEF · 每日网球速递</div>'
        + f'<div class="focus-label">{lead_label}</div>'
        + f'<div class="focus">{html.escape(headline)}</div>'
        + secondary_html
        + '</div><div class="cover-lower">'
        + highlights_html
        + f'<div class="chips">{chips_html}</div></div>'
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


def tonight_body(matches: list[Match], date_label: str) -> str:
    # Keep the page curated, but allow five matches without spilling past 9:16.
    cards = [_sched_card(m, with_reason=True) for m in matches[:5]]
    return (
        '<div class="poster tonight-page">'
        + _masthead(date_label)
        + _titleband("Tonight's Focus · 今晚焦点", "今晚焦点")
        + "".join(cards)
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
    source_html = ""
    if comparison.source_label:
        source = comparison.source_label
        duration = f" · {comparison.duration_label}" if comparison.duration_label else ""
        source_html = (
            f'<div class="stats-source">数据来源：{html.escape(source + duration)}</div>'
        )
    return (
        '<div class="poster focus-page">'
        + _masthead(date_label)
        + _titleband("Match Breakdown · 单场复盘", "焦点复盘")
        + _result_card(m, hero=True, show_tournament=True, tag_upset=False)
        + '<div class="compare-head"><span>'
        + ("专业技术统计" if comparison.source_label else "比赛结构")
        + "</span>"
        + f'<span>{html.escape(comparison.left_name)}</span>'
        + f'<span>{html.escape(comparison.right_name)}</span></div>'
        + f'<div class="compare-grid">{"".join(rows)}</div>'
        + source_html
        + f'<div class="verdict"><b>一句判断</b>{html.escape(comparison.verdict)}</div>'
        + _FOOTER
        + "</div>"
    )


def insight_body(m: Match, date_label: str, kind: str) -> str:
    """单场内容解释页：只使用可验证的比分和赛程事实。"""
    from .hotspot import hotspot_reasons
    from .story import result_insight, schedule_insight

    group = group_by_tournament([m])[0]
    if kind == "result":
        kicker = "Why It Matters · 一句看懂"
        title = "这场意味着什么"
        insight = result_insight(m)
        facts = [
            (group.compact_level, "赛事级别"),
            (match_round_display(m) or "完赛", "比赛轮次"),
            (m.score_display(from_winner=True) or "已完赛", "完整盘分"),
        ]
    else:
        kicker = "Match Preview · 赛前看点"
        title = "为什么值得看"
        insight = schedule_insight(m)
        facts = [
            (fmt_time_beijing(m.start_utc), "北京时间"),
            (group.compact_level, "赛事级别"),
            (match_round_display(m) or "待定", "比赛轮次"),
        ]
    reason = " · ".join(hotspot_reasons(m)[:3])
    facts_html = "".join(
        f'<article class="fact"><b>{html.escape(value)}</b>'
        f'<span>{html.escape(label)}</span></article>'
        for value, label in facts
    )
    return (
        '<div class="poster insight-page">'
        + _masthead(date_label)
        + _titleband(kicker, title)
        + f'<div class="event"><i></i><span>{html.escape(group.compact_title)}</span><i></i></div>'
        + '<article class="insight-hero">'
        + f'<small>{html.escape(reason)}</small><strong>{html.escape(insight)}</strong></article>'
        + f'<div class="fact-grid">{facts_html}</div>'
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
        f'<i class="story-index">{index:02d}</i>'
        f'<div class="story-copy"><strong>{html.escape(title)}</strong>'
        f'<p>{html.escape(detail)}</p></div></li>'
        for index, (title, detail) in enumerate(story_items[:3], 1)
    )
    kicker = {
        "player": "Player Spotlight · 球员特写",
        "trivia": "Tennis Story · 网球冷知识",
    }.get(story.kind, "Tournament Archive · 赛事档案")
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
        + f'<b>{html.escape(story.venue)}</b><span>{html.escape(story.location)}</span>'
        + "</div></div>"
        + f'<div class="story-hero">{html.escape(story.hero_fact)}</div>'
        + f'<ol class="story-list">{rows}</ol>'
        + f'<div class="photo-credit">资料：{html.escape(story.source_label)} · '
        + f'图源：{html.escape(story.image_credit)}</div>'
        + _FOOTER
        + "</div>"
    )


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
            page = browser.new_page(
                viewport={"width": W, "height": H}, device_scale_factor=2
            )
            for kind, body in pages:
                page.set_content(_shell(body, theme))
                page.wait_for_function(
                    "document.fonts.status === 'loaded'", timeout=15000
                )
                shot = page.screenshot(type="png")
                img = Image.open(io.BytesIO(shot)).convert("RGB")
                if img.size != (W, H):
                    img = img.resize((W, H), Image.LANCZOS)
                out.append((kind, img))
        finally:
            browser.close()
    return out


def generate_deck(digest: Digest, date_label: str, theme: str = "dark"):
    """整组晨报卡（与 cards.generate_cards 的选卡逻辑一致），返回 [(kind, Image)]."""
    from .titles import cover_highlights

    pages: list[tuple[str, str]] = []
    # V1 唯一封面：不再输出"钩子页 + 设计封面"双封面
    headline, secondary = cover_highlights(digest)
    pages.append(("cover", cover_body(digest, headline, secondary, date_label)))

    singles = [m for m in digest.results if m.is_singles]
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

    cn_results = [m for m in digest.results if is_chinese_involved(m)]
    cn_today = [m for m in digest.schedule + digest.live if is_chinese_involved(m)]
    if cn_results or cn_today:
        pages.append(("china", china_body(cn_results, cn_today, date_label)))

    tonight = tonight_focus(digest.schedule)
    if tonight:
        pages.append(("tonight", tonight_body(tonight, date_label)))

    focus = select_focus_match(digest)
    if has_detailed_stats(focus):
        pages.append(("focus", focus_body(focus, date_label)))

    story = pick_tournament_story(digest)
    if story:
        pages.append(("story", tournament_story_body(story, date_label)))

    if digest.today.weekday() == 0 and digest.rankings is not None:
        try:
            pages.append(("rankings", rankings_body(digest.rankings, date_label)))
        except Exception as e:  # noqa: BLE001
            logger.warning("排名卡生成失败（跳过）: %s", e)

    # V1 每日包最多 7 张。内容同时触发时先舍弃额外技术复盘，再舍弃
    # 周榜和第二赛果页；封面、首张赛果、中国、今晚与故事主链不动。
    for optional_kind in ("focus", "rankings", "results2"):
        if len(pages) <= 7:
            break
        pages = [page for page in pages if page[0] != optional_kind]

    return _screenshot_pages(pages, theme)


def generate_match_deck(
    match: Match,
    *,
    headline: str,
    today,
    date_label: str,
    kind: str,
    theme: str = "dark",
):
    """单场热点/赛前统一卡组，复用晨报同一套HTML视觉组件。"""
    from .story import result_insight, schedule_insight

    is_result = kind == "result"
    digest = Digest(
        today=today,
        results=[match] if is_result else [],
        schedule=[] if is_result else [match],
    )
    secondary = result_insight(match) if is_result else schedule_insight(match)
    pages: list[tuple[str, str]] = [
        ("cover", cover_body(digest, headline, secondary, date_label)),
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
            ("insight", insight_body(match, date_label, kind)),
            ("discussion", discussion_body(match, date_label, kind)),
        ]
    )
    return _screenshot_pages(pages, theme)


def render_scoreboard(matches: list[Match], date_label: str, theme: str = "dark"):
    """单独渲染赛果速递卡（兼容旧调用），返回 PIL Image."""
    return _screenshot_pages(
        [("scoreboard", scoreboard_body(matches, date_label))], theme
    )[0][1]
