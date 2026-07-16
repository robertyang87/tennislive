"""PushPlus 手机推送专用模板：窄屏友好 + 深色模式安全.

要点：
- 显式设置背景色和文字色（微信深色模式不会反转显式配色的卡片）
- 每条信息一行、行内容短，避免窄屏换行错乱
- 只放决策所需信息（焦点/中国军团/今晚看点），完整内容看仓库或公众号
"""

from __future__ import annotations

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from .common import (
    curate_for_social,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    side_display,
)
from .rating import stay_up_stars, top_results, top_schedule
from .titles import pick_headline_auto

# 深色模式安全：卡片自带浅色底，文字用深色，全部显式声明
_CARD = (
    "background-color:#f4f7f5;color:#1c2b26;border-radius:12px;"
    "padding:14px 16px;font-size:15px;line-height:1.9;"
)
_TITLE = "font-size:17px;font-weight:bold;color:#0b3d2e;"
_HEAD = "color:#0a7d43;font-weight:bold;font-size:16px;"
_SEC = "font-weight:bold;color:#0b3d2e;margin-top:6px;"
_DIM = "color:#5f6f68;font-size:13px;"
_HR = '<div style="border-top:1px solid #d8e2dc;margin:10px 0;"></div>'


def _short_side(players) -> str:
    return side_display(players, with_flag=True, with_seed=False, short_en=True)


def _score_of(m) -> str:
    return m.score_display(from_winner=True)


import os

# 卡片图 CDN：jsDelivr 镜像 GitHub 内容，国内可访问
_REPO = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
_CDN = f"https://cdn.jsdelivr.net/gh/{_REPO}@main"


def to_push_html(digest: Digest, cards: list[str] | None = None) -> str:
    d = digest.today
    parts: list[str] = [f'<div style="{_CARD}">']
    parts.append(f'<div style="{_TITLE}">🎾 网球晨报 · {d.month}月{d.day}日</div>')
    parts.append(f'<div style="{_HEAD}">{pick_headline_auto(digest)}</div>')
    parts.append(_HR)

    cn_results = [m for m in digest.results if is_chinese_involved(m)][:4]
    cn_today = [
        m for m in digest.schedule + digest.live if is_chinese_involved(m)
    ][:3]
    if cn_results or cn_today:
        parts.append(f'<div style="{_SEC}">🇨🇳 中国军团</div>')
        for m in cn_results:
            w = m.winner_players() or []
            mark = "✅" if any(is_chinese_involved_side([p]) for p in w) else "❌"
            parts.append(
                f"{mark} {_short_side(m.home if m.winner == 0 else m.away)} "
                f"胜 {_short_side(m.away if m.winner == 0 else m.home)}<br/>"
                f'<span style="{_DIM}">{_score_of(m)} · {_label(m)}</span>'
            )
        for m in cn_today:
            parts.append(
                f"⏰ {fmt_time_beijing(m.start_utc)} {_short_side(m.home)} vs "
                f"{_short_side(m.away)}<br/>"
                f'<span style="{_DIM}">{_label(m)}</span>'
            )
        parts.append(_HR)

    focus = top_results([m for m in digest.results if m.is_singles], 3)
    focus = [m for m in focus if not is_chinese_involved(m)]
    if focus:
        parts.append(f'<div style="{_SEC}">🏆 昨夜焦点</div>')
        for m in focus:
            w, l = m.winner_players() or [], m.loser_players() or []
            if not w or not l:
                continue
            parts.append(
                f"{_short_side(w)} 胜 {_short_side(l)}<br/>"
                f'<span style="{_DIM}">{_score_of(m)} · {_label(m)}</span>'
            )
        parts.append(_HR)

    tonight = top_schedule([m for m in digest.schedule if m.is_singles], 3)
    if tonight:
        parts.append(f'<div style="{_SEC}">🌙 今晚看点</div>')
        for m in tonight:
            stars = "★" * stay_up_stars(m)
            parts.append(
                f"{fmt_time_beijing(m.start_utc)} {_short_side(m.home)} vs "
                f"{_short_side(m.away)}<br/>"
                f'<span style="{_DIM}">{_label(m)} · 熬夜指数 {stars}</span>'
            )
        parts.append(_HR)

    if cards:
        parts.append(
            f'<div style="{_SEC}">📸 今日卡片（长按保存 → 订阅号助手/小红书发图）</div>'
        )
        for name in cards:
            url = f"{_CDN}/output/{d.isoformat()}/cards/{name}"
            parts.append(
                f'<img src="{url}" style="width:100%;border-radius:8px;'
                f'margin:6px 0;display:block;" />'
            )
        parts.append(_HR)
    parts.append(
        f'<div style="{_DIM}">📦 文案在仓库 output/{d.isoformat()}/xiaohongshu.txt'
        f"（可从推送标题直接复制标题）</div>"
    )
    parts.append("</div>")
    return "\n".join(parts)


def _label(m) -> str:
    g = group_by_tournament([m])[0]
    r = match_round_display(m)
    return f"{g.name_zh}{('·' + r) if r else ''}"


def is_chinese_involved_side(players) -> bool:
    from .common import CHINESE_PLAYER_NAMES
    from ..zh import player_zh

    for p in players:
        if (p.country or "").upper() in ("CHN", "CN"):
            return True
        if player_zh(p.name) in CHINESE_PLAYER_NAMES:
            return True
    return False
