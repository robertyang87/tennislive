"""标题全自动生成与选择：三个角度各出一个候选，按规则自动选用.

优先级：中国球员 > 冷门 > 球星战报 > 兜底。
所有候选都会写入 title_candidates.txt 留档，便于日后复盘哪类标题表现好。
"""

from __future__ import annotations

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from .common import is_chinese_involved, match_round_display
from .rating import find_upset, top_results, top_schedule


def _cn_side(players) -> bool:
    from .common import CHINESE_PLAYER_NAMES

    for p in players:
        if (p.country or "").upper() in ("CHN", "CN"):
            return True
        if player_zh(p.name) in CHINESE_PLAYER_NAMES:
            return True
    return False


def _flat_round(m) -> str:
    return (match_round_display(m) or "").replace("·", "")


def cn_headline(digest: Digest) -> str | None:
    """中国球员角度：赛果优先，其次今日出场."""
    finished = [m for m in digest.results if is_chinese_involved(m) and m.is_singles]
    finished = finished or [m for m in digest.results if is_chinese_involved(m)]
    if finished:
        m = finished[0]
        w = m.winner_players()
        if w:
            r = _flat_round(m)
            won = _cn_side(w)
            if won and r.endswith("决赛") and "半" not in r and "四" not in r:
                return f"{player_zh(w[0].name)}夺冠！"
            if won:
                return f"{player_zh(w[0].name)}晋级{r or '下一轮'}"
            loser = (m.loser_players() or [None])[0]
            if loser is not None:
                return f"{player_zh(loser.name)}止步{r or '本轮'}"
    upcoming = [m for m in digest.schedule if is_chinese_involved(m) and m.is_singles]
    if upcoming:
        m = upcoming[0]
        for p in m.home + m.away:
            if _cn_side([p]):
                t = fmt_time_beijing(m.start_utc)
                suffix = f"今晚{t}登场" if t != "待定" else "今日登场"
                return f"{player_zh(p.name)}{suffix}"
    return None


def upset_headline(digest: Digest) -> str | None:
    m = find_upset(digest.results)
    if m is None:
        return None
    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w or not l:
        return None
    return f"爆冷！{player_zh(w.name)}掀翻{player_zh(l.name)}"


def star_headline(digest: Digest) -> str | None:
    for m in top_results([x for x in digest.results if x.is_singles], 3):
        if is_chinese_involved(m):
            continue  # 中国角度另有候选
        w = m.winner_players()
        if w:
            from .common import group_by_tournament

            g = group_by_tournament([m])[0]
            r = _flat_round(m)
            if r == "决赛":
                return f"{player_zh(w[0].name)}问鼎{g.name_zh}"
            return f"{player_zh(w[0].name)}晋级{g.name_zh}{r or ''}"
    tonight = top_schedule([x for x in digest.schedule if x.is_singles], 1)
    if tonight:
        m = tonight[0]
        a = player_zh(m.home[0].name)
        b = player_zh(m.away[0].name)
        return f"今晚焦点：{a}对阵{b}"
    return None


def title_candidates(digest: Digest) -> list[str]:
    """去重后的候选列表，按优先级排序."""
    seen = set()
    out = []
    for h in (cn_headline(digest), upset_headline(digest), star_headline(digest)):
        if h and h not in seen:
            seen.add(h)
            out.append(h)
    if not out:
        out.append("每日赛程赛果速览")
    return out


def pick_headline_auto(digest: Digest) -> str:
    return title_candidates(digest)[0]


def flash_headline(m) -> str:
    """单场比赛的闪发标题，如 '郑钦文晋级！雅典公开赛八强'."""
    from .common import group_by_tournament

    g = group_by_tournament([m])[0]
    r = _flat_round(m)
    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w:
        return f"{g.name_zh}{r}战报"
    is_final = r.endswith("决赛") and "半" not in r and "四" not in r
    cn_won = _cn_side(m.winner_players() or [])
    cn_lost = _cn_side(m.loser_players() or [])
    if cn_won:
        # 双打时用中国球员的名字打头
        cn_w = next(
            (p for p in (m.winner_players() or []) if _cn_side([p])), w
        )
        if is_final:
            return f"{player_zh(cn_w.name)}夺冠！{g.name_zh}登顶"
        return f"{player_zh(cn_w.name)}晋级！赢下{g.name_zh}{r or '本轮'}"
    if cn_lost and l is not None:
        return f"{player_zh(l.name)}止步{g.name_zh}{r or '本轮'}"
    if is_final:
        return f"{player_zh(w.name)}问鼎{g.name_zh}"
    return f"{player_zh(w.name)}晋级{g.name_zh}{r or ''}"
