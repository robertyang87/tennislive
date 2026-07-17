"""HTML/CSS + Chromium 截图渲染的整组晨报卡（大满贯节目册质感）.

Pillow 排印能力有限（无阴影/字距/字重控制），整组卡片用真正的
网页排版引擎渲染 1080x1440 竖版图：

- 深松绿渐变底 + 极淡球场线稿，暖象牙白内容卡 + 香槟金细节
- 标题用思源宋体 Black，正文思源黑体，比分用 Barlow Condensed
  转播体数字（全部子集化 base64 内嵌，本地与 CI 渲染一致）
- 球员中文名为主 + 小字英文原名；每盘一列严格对齐
- 一次浏览器会话渲染全组卡片；浏览器不可用时调用方回退 Pillow
"""

from __future__ import annotations

import base64
import html
import logging
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
from .rating import find_upset, is_upset, stay_up_stars, top_results, top_schedule

logger = logging.getLogger(__name__)

W, H = 1080, 1440
ASSETS = Path(__file__).resolve().parents[3] / "assets"

# ---------- 资源内嵌（自包含 HTML，避免 file:// 子资源限制） ----------


def _b64(path: Path) -> str | None:
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except OSError:
        return None


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
    return "\n".join(css)


def _flag_uri(country: str | None) -> str | None:
    iso2 = country_iso2(country)
    if not iso2:
        return None
    b = _b64(ASSETS / "flags" / f"{iso2.lower()}.png")
    return f"data:image/png;base64,{b}" if b else None


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
  --ground0:#07231B; --ground1:#0C3628;
  --ivory:#F7F3EA; --ink:#15261E; --fade:#8B968C;
  --gold:#C2A24E; --gold-soft:rgba(194,162,78,.38);
  --court:#0D5E3C; --winband:#E3EFDC; --flash:#C8502F;
  --neon:#CCFF00; --courtline:rgba(255,255,255,.05);
  --cardshadow:0 10px 30px rgba(0,0,0,.35);
  --pagetext:#F7F3EA;
}
html.light {
  --ground0:#F2EDE2; --ground1:#E9E2D2;
  --ivory:#FDFCF8; --fade:#95998F;
  --neon:#0B4D33; --courtline:rgba(20,60,40,.08);
  --cardshadow:0 10px 26px rgba(90,80,50,.16);
  --pagetext:#1E3328;
}
body {
  width:@W@px; height:@H@px; overflow:hidden; position:relative;
  background:linear-gradient(168deg, var(--ground0) 0%, var(--ground1) 100%);
  font-family:'TL Sans SC','Noto Sans CJK SC','Noto Sans SC','WenQuanYi Zen Hei',sans-serif;
  color:var(--pagetext);
}
.court { position:absolute; left:0; bottom:0; width:100%; height:1060px; }
.poster { position:relative; height:100%; padding:40px 64px 24px; display:flex; flex-direction:column; }

.masthead { display:flex; align-items:center; gap:16px; }
.ball { width:44px; height:44px; border-radius:50%; background:var(--neon); position:relative; overflow:hidden; flex:none; }
.ball::before, .ball::after { content:""; position:absolute; width:36px; height:36px; border:4px solid var(--ground0); border-radius:50%; }
.ball::before { left:-22px; top:4px; } .ball::after { right:-22px; top:4px; }
.brand { font-weight:700; font-size:34px; letter-spacing:2px; line-height:1.2; }
.date { margin-left:auto; font-family:'Barlow Condensed'; font-weight:600; font-size:30px; letter-spacing:2px; color:var(--fade); }

.titleband { margin:18px 0 14px; }
.kicker { font-family:'Barlow Condensed'; font-weight:600; font-size:26px; line-height:1.1;
  letter-spacing:.42em; text-transform:uppercase; color:var(--gold); }
h1 { font-family:'TL Serif SC','Noto Serif CJK SC',serif; font-size:76px; font-weight:900;
  letter-spacing:3px; line-height:1.15; color:var(--neon); margin-top:2px; }

.event { display:flex; align-items:center; gap:18px; margin:-6px 0 22px; }
.event i { flex:1; height:1px; background:var(--gold-soft); }
.event span { font-size:30px; font-weight:700; color:var(--pagetext); letter-spacing:2px; line-height:1.2; }

.card { background:var(--ivory); color:var(--ink); border-radius:14px;
  box-shadow:var(--cardshadow); padding:10px 30px 12px; margin-bottom:8px; }
.card.hero { border-top:3px solid var(--gold); padding:16px 34px 18px; }

.card header { display:flex; align-items:center; justify-content:space-between;
  height:42px; border-bottom:1px solid var(--gold-soft); }
.hero header { height:52px; }
.hl { display:flex; align-items:center; gap:14px; }
.round { font-size:24px; color:var(--fade); letter-spacing:1px; }
.tour { font-size:24px; color:var(--fade); letter-spacing:1px; }
.htime { font-family:'Barlow Condensed'; font-weight:600; font-size:30px; color:var(--gold); letter-spacing:1px; }
.stars { font-size:22px; color:var(--gold); letter-spacing:3px; }
.chip { font-size:24px; font-weight:700; color:#fff; padding:5px 16px 6px; border-radius:6px; }
.chip-green { background:var(--court); }
.chip-red { background:var(--flash); }
.chip-sm { font-size:20px; padding:3px 12px 4px; }

.set-index { display:grid; grid-template-columns:1fr repeat(var(--sets), 88px);
  height:28px; align-items:end; padding-bottom:3px; }
.set-index i { font-family:'Barlow Condensed'; font-weight:600; font-size:22px;
  font-style:normal; color:var(--gold); text-align:center; letter-spacing:1px; line-height:1; }

/* 行高固定，布局与字体度量脱钩（CI 的 Noto 行框远高于本地字体） */
.side { display:grid; grid-template-columns:1fr repeat(var(--sets), 72px);
  align-items:center; border-radius:10px; margin-top:4px; padding:0 14px; height:62px; }
.hero .side { grid-template-columns:1fr repeat(var(--sets), 88px); height:96px; margin-top:6px; }
.side.nosets { grid-template-columns:1fr; height:58px; }
.side.won { background:var(--winband); }
.who { display:flex; align-items:center; gap:12px; min-width:0; }
.names { display:flex; flex-direction:column; justify-content:center; min-width:0; }
.zh { display:flex; align-items:center; gap:8px; min-width:0; }
.flag { height:27px; border-radius:4px; box-shadow:0 0 0 1px rgba(0,0,0,.12); }
.hero .flag { height:36px; }
.seed { font-family:'Barlow Condensed'; font-weight:600; font-style:normal;
  font-size:22px; color:var(--gold); line-height:1; }
.hero .seed { font-size:27px; }
.name { font-style:normal; font-weight:700; font-size:30px; line-height:1.25;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hero .name { font-size:42px; letter-spacing:1px; }
.side.lost .name { color:var(--fade); font-weight:500; }
.rank { font-family:'Barlow Condensed'; font-weight:500; font-style:normal;
  font-size:22px; color:var(--fade); line-height:1; }
.hero .rank { font-size:26px; }
.en { font-family:'Barlow Condensed'; font-weight:500; font-size:19px; line-height:1.1;
  letter-spacing:1.2px; color:var(--fade); margin-top:2px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hero .en { font-size:23px; margin-top:4px; }
.note { font-style:normal; font-size:22px; color:var(--fade); }
/* 每盘独立强调：赢下该盘的一方数字深绿加粗，输的一方浅灰 */
.set { font-family:'Barlow Condensed'; font-size:42px;
  text-align:center; font-variant-numeric:tabular-nums; line-height:1; }
.hero .set { font-size:62px; }
.set.sw { color:var(--court); font-weight:700; }
.set.sl { color:var(--fade); font-weight:500; }
.set sup { font-size:.46em; font-weight:600; vertical-align:.62em; margin-left:1px; }

.footer { margin-top:auto; display:flex; align-items:center; }
.footer b { margin-left:auto; font-size:26px; font-weight:700; color:var(--fade); letter-spacing:2px; line-height:1.2; }

/* ---------- 封面 ---------- */
.cover-date { display:flex; align-items:baseline; gap:22px; margin-top:60px; }
.cover-date b { font-family:'Barlow Condensed'; font-weight:700; font-size:210px; line-height:.9; color:var(--pagetext); }
.cover-date i { font-style:normal; font-size:44px; color:var(--fade); }
.cover h1 { font-size:118px; margin-top:26px; letter-spacing:8px; }
.cover .slogan { font-size:32px; color:var(--fade); margin-top:16px; letter-spacing:2px; line-height:1.3; }
.cover .rule { height:1px; background:var(--gold-soft); margin:44px 0 30px; }
.cover .focus-label { font-family:'Barlow Condensed'; font-weight:600; font-size:24px;
  letter-spacing:.42em; color:var(--gold); text-transform:uppercase; }
.cover .focus { font-size:52px; font-weight:700; line-height:1.45; margin-top:14px;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.cover .chips { display:flex; gap:16px; margin-top:44px; }
.cover .chips span { background:var(--ivory); color:var(--ink); font-size:28px; font-weight:700;
  padding:14px 28px; border-radius:12px; box-shadow:var(--cardshadow); line-height:1.2; }
.cover .update { display:inline-flex; align-items:center; margin-top:40px; border:2px solid var(--gold);
  color:var(--gold); border-radius:999px; padding:10px 26px; font-size:26px; letter-spacing:3px; line-height:1.2; width:max-content; }

/* ---------- 栏目段落 ---------- */
.seclabel { display:flex; align-items:center; gap:16px; margin:10px 0 10px; }
.seclabel i { flex:1; height:1px; background:var(--gold-soft); }
.seclabel span { font-size:26px; color:var(--fade); letter-spacing:4px; line-height:1.2; }

/* ---------- 互动卡（爆冷/竞猜/收尾） ---------- */
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
  position:relative; overflow:hidden; margin:90px auto 0; }
.bigball::before, .bigball::after { content:""; position:absolute; width:124px; height:124px;
  border:12px solid var(--ground0); border-radius:50%; }
.bigball::before { left:-76px; top:13px; } .bigball::after { right:-76px; top:13px; }
.end-title { font-family:'TL Serif SC',serif; font-weight:900; font-size:84px; line-height:1.5;
  letter-spacing:6px; margin-top:48px; color:var(--pagetext); }
.end-sub { font-size:32px; color:var(--fade); margin-top:18px; letter-spacing:3px; }

/* ---------- 排名卡 ---------- */
.rank-card { padding:16px 30px 18px; }
.rank-card h3 { font-family:'Barlow Condensed'; font-weight:600; font-size:26px; letter-spacing:.32em;
  color:var(--gold); text-transform:uppercase; height:38px; border-bottom:1px solid var(--gold-soft); }
.rrow { display:flex; align-items:center; height:58px; gap:16px; }
.rrow .no { font-family:'Barlow Condensed'; font-weight:700; font-size:36px; color:var(--gold); width:52px; line-height:1; }
.rrow .rnames { display:flex; flex-direction:column; min-width:0; flex:1; }
.rrow .pts { font-family:'Barlow Condensed'; font-weight:500; font-size:24px; color:var(--fade); line-height:1; }
.rrow .mv { font-family:'Barlow Condensed'; font-weight:600; font-size:26px; width:72px; text-align:right; line-height:1; }
.mv.up { color:#1B7C4D; } .mv.down { color:var(--flash); } .mv.flat { color:var(--fade); }
"""


def _shell(body: str, theme: str) -> str:
    light = "true" if theme == "light" else "false"
    css = _CSS.replace("@W@", str(W)).replace("@H@", str(H))
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_font_css()}\n{css}'
        f"</style></head><body>{_COURT_SVG}{body}"
        f"<script>document.documentElement.classList.toggle('light', {light});</script>"
        "</body></html>"
    )


def _masthead(date_label: str) -> str:
    return (
        '<div class="masthead"><span class="ball"></span><span class="brand">网球时差</span>'
        f'<span class="date">{html.escape(date_label)}</span></div>'
    )


def _titleband(kicker: str, title: str) -> str:
    return (
        f'<div class="titleband"><div class="kicker">{kicker}</div>'
        f"<h1>{title}</h1></div>"
    )


_FOOTER = '<div class="footer"><b>@网球时差 · TENNIS JETLAG</b></div>'


# ---------- 比赛卡组件 ----------


def _names(players) -> tuple[str, str]:
    """(主行, 英文小字行)：有译名→中文为主+英文原名小字；无译名→缩写英文为主."""
    zh_parts, en_parts = [], []
    for p in players[:2]:
        zh = player_zh(p.name)
        if zh != p.name:
            zh_parts.append(zh)
            en_parts.append(p.name)
        elif p.name.isascii():
            zh_parts.append(_abbrev_en(p.name))
        else:
            zh_parts.append(p.name)
    return "/".join(zh_parts), " / ".join(en_parts)


def _side_html(m: Match, side: int, n_sets: int, with_sets: bool = True) -> str:
    players = m.home if side == 0 else m.away
    won = m.winner == side
    flags = []
    for p in players[:2]:
        uri = _flag_uri(p.country)
        if uri:
            flags.append(f'<img class="flag" src="{uri}" alt=""/>')
    seed = players[0].seed if players else None
    seed_html = f'<i class="seed">{seed}</i>' if seed else ""
    main, en = _names(players)
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
        f'<span class="who">{"".join(flags)}<span class="names">'
        f'<span class="zh">{seed_html}<em class="name">{html.escape(main)}</em>'
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
        tour_txt = html.escape(g.name_zh)
    chip_html = ""
    if hero:
        text, cls = _story_chip(m)
        chip_html = f'<b class="chip {cls}">{text}</b>'
    elif tag_upset:
        chip_html = '<b class="chip chip-red chip-sm">爆冷</b>'
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


def _sched_card(m: Match, *, with_stars: bool = False) -> str:
    """赛程卡：元信息条（轮次+赛事 | 时间/熬夜指数）+ 两行球员（无比分）."""
    g = group_by_tournament([m])[0]
    meta = html.escape(match_round_display(m) or "")
    tour_txt = html.escape(g.name_zh)
    t = fmt_time_beijing(m.start_utc)
    right = f'<span class="htime">{t}</span>'
    if with_stars:
        stars = "★" * stay_up_stars(m)
        right = f'<span class="stars">{stars}</span>' + right
    return (
        '<article class="card">'
        f'<header><span class="hl"><span class="round">{tour_txt} · {meta}</span></span>'
        f'<span class="hl">{right}</span></header>'
        f"{_side_html(m, 0, 0, with_sets=False)}{_side_html(m, 1, 0, with_sets=False)}"
        "</article>"
    )


def _seclabel(text: str) -> str:
    return f'<div class="seclabel"><i></i><span>{html.escape(text)}</span><i></i></div>'


# ---------- 各卡页面 ----------


def cover_body(digest: Digest, headline: str, date_label: str) -> str:
    d = digest.today
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()]
    chips = []
    if digest.results:
        chips.append(f"昨夜赛果 {len(digest.results)} 场")
    if digest.schedule:
        chips.append(f"今日赛程 {len(digest.schedule)} 场")
    chips_html = "".join(f"<span>{c}</span>" for c in chips)
    return (
        '<div class="poster cover">'
        + _masthead(date_label)
        + f'<div class="cover-date"><b>{d.month}.{d.day}</b><i>{weekday}</i></div>'
        + "<h1>网球晨报</h1>"
        + '<div class="slogan">替你熬夜看网球 · 昨夜赛果，今晨看懂</div>'
        + '<div class="rule"></div>'
        + '<div class="focus-label">Today\'s Focus · 今日焦点</div>'
        + f'<div class="focus">{html.escape(headline)}</div>'
        + f'<div class="chips">{chips_html}</div>'
        + '<div class="update">每天 7:30 更新</div>'
        + _FOOTER
        + "</div>"
    )


def scoreboard_body(matches: list[Match], date_label: str) -> str:
    names = {m.tournament.name for m in matches}
    single_event = len(names) == 1
    banner = ""
    if single_event:
        g = group_by_tournament(matches[:1])[0]
        title = g.title
        if len({m.tour for m in matches}) > 1 and title.startswith(("ATP ", "WTA ")):
            title = title[4:]
        banner = f'<div class="event"><i></i><span>{html.escape(title)}</span><i></i></div>'
    hero, rest = matches[0], matches[1:]
    rest = rest[: 3 if single_event else 4]
    top_upset = find_upset(rest)
    cards = [_result_card(hero, hero=True, show_tournament=not single_event, tag_upset=False)]
    for m in rest:
        cards.append(_result_card(
            m, hero=False, show_tournament=not single_event,
            tag_upset=(top_upset is not None and m.match_id == top_upset.match_id),
        ))
    return (
        '<div class="poster">'
        + _masthead(date_label)
        + _titleband("Overnight Results · 昨夜赛果", "赛果速递")
        + banner
        + "".join(cards)
        + _FOOTER
        + "</div>"
    )


def china_body(results: list[Match], today: list[Match], date_label: str) -> str:
    results = results[:3]
    today = today[: max(0, 5 - len(results))]
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
        '<div class="poster">'
        + _masthead(date_label)
        + _titleband("Team China · 中国军团", "中国军团")
        + "".join(parts)
        + _FOOTER
        + "</div>"
    )


def tonight_body(matches: list[Match], date_label: str) -> str:
    cards = [_sched_card(m, with_stars=True) for m in matches[:5]]
    return (
        '<div class="poster">'
        + _masthead(date_label)
        + _titleband("Tonight's Picks · 今晚看球", "今晚看球")
        + "".join(cards)
        + _FOOTER
        + "</div>"
    )


def upset_body(m: Match, date_label: str) -> str:
    winners = m.winner_players() or []
    w_name = player_zh(winners[0].name) if winners else "黑马"
    if w_name.isascii():
        w_name = w_name.split()[-1]
    return (
        '<div class="poster">'
        + _masthead(date_label)
        + _titleband("Upset Alert · 昨夜冷门", "昨夜冷门")
        + _result_card(m, hero=True, show_tournament=True, tag_upset=False)
        + '<div class="cta-wrap">'
        + f'<div class="cta-copy">{html.escape(w_name)}爆了个大冷</div>'
        + '<div class="cta-sub">你看好这匹黑马能走多远？</div>'
        + '<div class="cta-btn">评论区聊聊</div>'
        + "</div>"
        + _FOOTER
        + "</div>"
    )


def topic_body(m: Match, date_label: str) -> str:
    return (
        '<div class="poster">'
        + _masthead(date_label)
        + _titleband("Match Poll · 今日竞猜", "你猜谁赢？")
        + _sched_card(m, with_stars=True)
        + '<div class="cta-wrap">'
        + '<div class="cta-copy">猜中的今晚一起庆祝</div>'
        + '<div class="cta-sub">开赛前投下你的一票</div>'
        + '<div class="cta-btn">评论区扣 1 或 2</div>'
        + "</div>"
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
        '<div class="poster">'
        + _masthead(date_label)
        + _titleband("Weekly Rankings · 本周排名", "本周排名")
        + section("ATP Top 5", rankings.atp)
        + section("WTA Top 5", rankings.wta)
        + cn_html
        + _FOOTER
        + "</div>"
    )


def end_body(date_label: str) -> str:
    return (
        '<div class="poster cta-wrap">'
        + '<div class="bigball"></div>'
        + '<div class="end-title">今天的网球时差<br/>就倒到这里</div>'
        + '<div class="end-sub">明早 7:30 · 准时更新</div>'
        + '<div class="pills"><span>点赞</span><span>收藏</span><span>评论</span></div>'
        + '<div class="cta-btn" style="margin-top:70px">关注 @网球时差</div>'
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
    from .titles import pick_headline_auto

    pages: list[tuple[str, str]] = []
    headline = pick_headline_auto(digest)
    pages.append(("cover", cover_body(digest, headline, date_label)))

    singles = [m for m in digest.results if m.is_singles]
    if singles:
        board = top_results(singles, 8)
        pages.append(("scoreboard", scoreboard_body(board, date_label)))

    cn_results = [m for m in digest.results if is_chinese_involved(m)]
    cn_today = [m for m in digest.schedule + digest.live if is_chinese_involved(m)]
    if cn_results or cn_today:
        pages.append(("china", china_body(cn_results, cn_today, date_label)))

    tonight = top_schedule([m for m in digest.schedule if m.is_singles], 5)
    if tonight:
        pages.append(("tonight", tonight_body(tonight, date_label)))

    if digest.today.weekday() == 0 and digest.rankings is not None:
        try:
            pages.append(("rankings", rankings_body(digest.rankings, date_label)))
        except Exception as e:  # noqa: BLE001
            logger.warning("排名卡生成失败（跳过）: %s", e)

    upset = find_upset(digest.results)
    if upset:
        pages.append(("upset", upset_body(upset, date_label)))
    elif tonight:
        pages.append(("topic", topic_body(tonight[0], date_label)))

    pages.append(("end", end_body(date_label)))
    return _screenshot_pages(pages, theme)


def render_scoreboard(matches: list[Match], date_label: str, theme: str = "dark"):
    """单独渲染赛果速递卡（兼容旧调用），返回 PIL Image."""
    return _screenshot_pages(
        [("scoreboard", scoreboard_body(matches, date_label))], theme
    )[0][1]
