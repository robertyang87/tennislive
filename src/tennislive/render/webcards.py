"""HTML/CSS + Chromium 截图渲染的精美赛果卡（大满贯官网板式质感）.

Pillow 排印能力有限（无阴影/字距/字重控制），这里用真正的网页排版引擎
渲染 1080x1440 竖版卡片：

- 深松绿渐变底 + 极淡球场线稿（品牌一致）
- 暖象牙白比赛卡，香槟金发丝线/盘序号/种子号（大满贯节目册气质）
- 比分用 Barlow Condensed（转播比分牌式高窄数字，OFL 已内嵌 base64）
- 每盘一列严格对齐，头条卡带盘序号列头；胜者浅绿带 + 深绿比分

浏览器不可用时由调用方回退到 Pillow 版本。
"""

from __future__ import annotations

import base64
import html
import logging
from pathlib import Path

from ..models import Match
from ..zh import player_zh
from ..zh.countries import country_iso2
from .common import _abbrev_en, group_by_tournament, is_chinese_involved, match_round_display
from .rating import is_upset

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
    for weight, fname in ((500, "BarlowCondensed-Medium.ttf"),
                          (600, "BarlowCondensed-SemiBold.ttf"),
                          (700, "BarlowCondensed-Bold.ttf")):
        b = _b64(ASSETS / "fonts" / fname)
        if b:
            css.append(
                f"@font-face{{font-family:'Barlow Condensed';font-weight:{weight};"
                f"src:url(data:font/ttf;base64,{b}) format('truetype');}}"
            )
    return "\n".join(css)


def _flag_uri(country: str | None) -> str | None:
    iso2 = country_iso2(country)
    if not iso2:
        return None
    b = _b64(ASSETS / "flags" / f"{iso2.lower()}.png")
    return f"data:image/png;base64,{b}" if b else None


# ---------- 内容组装 ----------


def _short_name(p) -> str:
    n = player_zh(p.name)
    if n == p.name and n.isascii():
        n = _abbrev_en(n)
    return n


def _story_chip(m: Match) -> tuple[str, str] | None:
    from ..zh.terms import round_zh

    if is_chinese_involved(m):
        return "中国军团", "chip-green"
    if (round_zh(m.round_name) or "") == "决赛":
        return "夺冠时刻", "chip-green"
    if is_upset(m):
        return "爆冷", "chip-red"
    return "今日头条", "chip-green"


def _side_html(m: Match, side: int, n_sets: int) -> str:
    players = m.home if side == 0 else m.away
    won = m.winner == side
    flags = []
    for p in players[:2]:
        uri = _flag_uri(p.country)
        if uri:
            flags.append(f'<img class="flag" src="{uri}" alt=""/>')
    seed = players[0].seed if players else None
    seed_html = f'<i class="seed">{seed}</i>' if seed else ""
    name = html.escape("/".join(_short_name(p) for p in players))
    rank = players[0].rank if len(players) == 1 else None
    rank_html = f'<i class="rank">({rank})</i>' if rank else ""
    cells = []
    for s in m.sets:
        games = s.home if side == 0 else s.away
        tb = s.home_tiebreak if side == 0 else s.away_tiebreak
        sup = f"<sup>{tb}</sup>" if tb is not None else ""
        cells.append(f'<b class="set">{games}{sup}</b>')
    note = ""
    if not m.sets and side == (m.winner or 0) and m.note:
        note = f'<i class="note">{html.escape(str(m.note)[:12])}</i>'
    return (
        f'<div class="side {"won" if won else "lost"}" '
        f'style="--sets:{n_sets}">'
        f'<span class="who">{"".join(flags)}{seed_html}'
        f'<em class="name">{name}</em>{rank_html}{note}</span>'
        f'{"".join(cells)}</div>'
    )


def _card_html(m: Match, *, hero: bool, show_tournament: bool, tag_upset: bool) -> str:
    n = len(m.sets)
    round_txt = html.escape(match_round_display(m) or "")
    tour_txt = ""
    if show_tournament:
        g = group_by_tournament([m])[0]
        tour_txt = html.escape(g.name_zh)
    chip_html = ""
    if hero:
        chip = _story_chip(m)
        if chip:
            chip_html = f'<b class="chip {chip[1]}">{chip[0]}</b>'
    elif tag_upset:
        chip_html = '<b class="chip chip-red chip-sm">爆冷</b>'
    # 大满贯板式细节：头条卡带金色盘序号列头
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
        f'{set_index}{sides}</article>'
    )


_COURT_SVG = """<svg class="court" viewBox="0 0 1080 1060" preserveAspectRatio="none">
<g fill="none" stroke="var(--courtline)" stroke-width="3">
<polygon points="-56,1060 1136,1060 799,0 281,0"/>
<line x1="75" y1="1060" x2="338" y2="0"/><line x1="1005" y1="1060" x2="742" y2="0"/>
<line x1="176" y1="657" x2="904" y2="657"/><line x1="540" y1="657" x2="540" y2="0"/>
<line x1="281" y1="0" x2="799" y2="0" stroke-width="8"/>
</g></svg>"""


def scoreboard_html(
    matches: list[Match], date_label: str, theme: str = "dark"
) -> str:
    """整页 HTML：报头 + 标题带 + 头条卡 + 紧凑卡列表."""
    from .rating import find_upset

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
    cards = [_card_html(hero, hero=True, show_tournament=not single_event, tag_upset=False)]
    for m in rest:
        cards.append(_card_html(
            m, hero=False, show_tournament=not single_event,
            tag_upset=(top_upset is not None and m.match_id == top_upset.match_id),
        ))

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{_font_css()}
* {{ margin:0; padding:0; box-sizing:border-box; }}
:root {{
  --ground0:#07231B; --ground1:#0C3628;
  --ivory:#F7F3EA; --ink:#15261E; --fade:#8B968C;
  --gold:#C2A24E; --gold-soft:rgba(194,162,78,.38);
  --court:#0D5E3C; --winband:#E3EFDC; --flash:#C8502F;
  --neon:#CCFF00; --courtline:rgba(255,255,255,.05);
  --cardshadow:0 10px 30px rgba(0,0,0,.35);
  --pagetext:#F7F3EA;
}}
html.light {{
  --ground0:#F2EDE2; --ground1:#E9E2D2;
  --ivory:#FDFCF8; --fade:#95998F;
  --neon:#0B4D33; --courtline:rgba(20,60,40,.08);
  --cardshadow:0 10px 26px rgba(90,80,50,.16);
  --pagetext:#1E3328;
}}
body {{
  width:{W}px; height:{H}px; overflow:hidden; position:relative;
  background:linear-gradient(168deg, var(--ground0) 0%, var(--ground1) 100%);
  font-family:'Noto Sans CJK SC','Noto Sans SC','WenQuanYi Zen Hei',sans-serif;
  color:var(--pagetext);
}}
.court {{ position:absolute; left:0; bottom:0; width:100%; height:1060px; }}
.poster {{ position:relative; height:100%; padding:50px 64px 30px; display:flex; flex-direction:column; }}

.masthead {{ display:flex; align-items:center; gap:16px; }}
.ball {{ width:44px; height:44px; border-radius:50%; background:var(--neon); position:relative; overflow:hidden; }}
.ball::before, .ball::after {{ content:""; position:absolute; width:36px; height:36px; border:4px solid var(--ground0); border-radius:50%; }}
.ball::before {{ left:-22px; top:4px; }} .ball::after {{ right:-22px; top:4px; }}
.brand {{ font-weight:700; font-size:34px; letter-spacing:2px; line-height:1.2; }}
.date {{ margin-left:auto; font-family:'Barlow Condensed'; font-weight:600; font-size:30px; letter-spacing:2px; color:var(--fade); }}

.titleband {{ margin:26px 0 20px; }}
.kicker {{ font-family:'Barlow Condensed'; font-weight:600; font-size:26px; line-height:1.1;
  letter-spacing:.42em; text-transform:uppercase; color:var(--gold); }}
h1 {{ font-size:84px; font-weight:900; letter-spacing:6px; line-height:1.12; color:var(--neon); }}

.event {{ display:flex; align-items:center; gap:18px; margin:-6px 0 22px; }}
.event i {{ flex:1; height:1px; background:var(--gold-soft); }}
.event span {{ font-size:30px; font-weight:700; color:var(--pagetext); letter-spacing:2px; line-height:1.2; }}

.card {{ background:var(--ivory); color:var(--ink); border-radius:14px;
  box-shadow:var(--cardshadow); padding:13px 30px 14px; margin-bottom:10px; }}
.card.hero {{ border-top:3px solid var(--gold); padding:20px 34px 22px; }}

.card header {{ display:flex; align-items:center; justify-content:space-between;
  height:44px; border-bottom:1px solid var(--gold-soft); }}
.hero header {{ height:56px; }}
.hl {{ display:flex; align-items:center; gap:14px; }}
.round {{ font-size:24px; color:var(--fade); letter-spacing:1px; }}
.tour {{ font-size:24px; color:var(--fade); letter-spacing:1px; }}
.chip {{ font-size:24px; font-weight:700; color:#fff; padding:5px 16px 6px; border-radius:6px; }}
.chip-green {{ background:var(--court); }}
.chip-red {{ background:var(--flash); }}
.chip-sm {{ font-size:20px; padding:3px 12px 4px; }}

.set-index {{ display:grid; grid-template-columns:1fr repeat(var(--sets), 88px);
  height:32px; align-items:end; padding-bottom:4px; }}
.set-index i {{ font-family:'Barlow Condensed'; font-weight:600; font-size:22px;
  font-style:normal; color:var(--gold); text-align:center; letter-spacing:1px; line-height:1; }}

/* 行高固定，布局与字体度量脱钩（CI 的 Noto 行框远高于本地字体） */
.side {{ display:grid; grid-template-columns:1fr repeat(var(--sets), 72px);
  align-items:center; border-radius:10px; margin-top:4px; padding:0 14px; height:54px; }}
.hero .side {{ grid-template-columns:1fr repeat(var(--sets), 88px); height:88px; margin-top:6px; }}
.side.won {{ background:var(--winband); }}
.who {{ display:flex; align-items:center; gap:12px; min-width:0; }}
.flag {{ height:27px; border-radius:4px; box-shadow:0 0 0 1px rgba(0,0,0,.12); }}
.hero .flag {{ height:36px; }}
.seed {{ font-family:'Barlow Condensed'; font-weight:600; font-style:normal;
  font-size:22px; color:var(--gold); }}
.hero .seed {{ font-size:27px; }}
.name {{ font-style:normal; font-weight:700; font-size:30px; line-height:1.2;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.hero .name {{ font-size:44px; letter-spacing:1px; }}
.side.lost .name {{ color:var(--fade); font-weight:500; }}
.rank {{ font-family:'Barlow Condensed'; font-weight:500; font-style:normal;
  font-size:22px; color:var(--fade); }}
.hero .rank {{ font-size:26px; }}
.note {{ font-style:normal; font-size:22px; color:var(--fade); }}
.set {{ font-family:'Barlow Condensed'; font-weight:700; font-size:42px;
  text-align:center; color:var(--court); font-variant-numeric:tabular-nums; line-height:1; }}
.hero .set {{ font-size:62px; font-weight:700; }}
.side.lost .set {{ color:var(--fade); font-weight:600; }}
.set sup {{ font-size:.46em; font-weight:600; vertical-align:.62em; margin-left:1px; }}

.footer {{ margin-top:auto; display:flex; align-items:center; }}
.footer b {{ margin-left:auto; font-size:26px; font-weight:700; color:var(--fade); letter-spacing:2px; line-height:1.2; }}
</style></head>
<body>
{_COURT_SVG}
<div class="poster">
  <div class="masthead"><span class="ball"></span><span class="brand">网球时差</span>
    <span class="date">{html.escape(date_label)}</span></div>
  <div class="titleband"><div class="kicker">Overnight Results · 昨夜赛果</div>
    <h1>赛果速递</h1></div>
  {banner}
  {"".join(cards)}
  <div class="footer"><b>@网球时差 · TENNIS JETLAG</b></div>
</div>
<script>document.documentElement.classList.toggle('light', {str(theme == 'light').lower()});</script>
</body></html>"""


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


def render_scoreboard(matches: list[Match], date_label: str, theme: str = "dark"):
    """渲染赛果速递卡，返回 PIL Image（1080x1440，2x 超采样抗锯齿）."""
    import io

    from PIL import Image
    from playwright.sync_api import sync_playwright

    page_html = scoreboard_html(matches, date_label, theme)
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
            page.set_content(page_html)
            page.wait_for_function("document.fonts.status === 'loaded'", timeout=15000)
            shot = page.screenshot(type="png")
        finally:
            browser.close()
    img = Image.open(io.BytesIO(shot)).convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    return img
