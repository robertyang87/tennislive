"""标题全自动生成与选择：用可解释评分挑当天最值得点击的故事."""

from __future__ import annotations

from dataclasses import dataclass

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from .common import is_chinese_involved, match_round_display
from .rating import find_upset, is_upset, match_score, top_results, top_schedule
from .story import china_summary, chinese_side_won, is_chinese_player


@dataclass(frozen=True)
class _Candidate:
    text: str
    score: int
    kind: str


@dataclass(frozen=True)
class _HistoricalProfile:
    peak_rank: int
    legacy: str
    source_url: str


# Curated, source-backed context for cover hooks. Keep this list deliberately
# small: an absent profile falls back to match facts instead of invented lore.
_HISTORICAL_PROFILES = {
    "Stefanos Tsitsipas": _HistoricalProfile(
        peak_rank=3,
        legacy="两进大满贯决赛",
        source_url="https://www.atptour.com/en/players/tsitsipas-stefanos/te51/bio",
    ),
}


def _cn_side(players) -> bool:
    return any(is_chinese_player(p) for p in players)


def _flat_round(m) -> str:
    return (match_round_display(m) or "").replace("·", "")


def _cn_match_headline(m) -> str | None:
    w = m.winner_players()
    if not w:
        return None
    r = _flat_round(m)
    if chinese_side_won(m):
        cn_winner = next((p for p in w if is_chinese_player(p)), w[0])
        if r.endswith("决赛") and "半" not in r and "四" not in r:
            return f"{player_zh(cn_winner.name)}夺冠！"
        return f"{player_zh(cn_winner.name)}晋级{r or '下一轮'}"
    loser = next(
        (p for p in (m.loser_players() or []) if is_chinese_player(p)), None
    )
    if loser is not None:
        return f"{player_zh(loser.name)}止步{r or '本轮'}"
    return None


def _cn_candidates(digest: Digest) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for m in digest.results:
        if not is_chinese_involved(m):
            continue
        text = _cn_match_headline(m)
        if not text:
            continue
        positive = chinese_side_won(m)
        base = 300 if positive and m.is_singles else 215 if positive else 70
        candidates.append(_Candidate(text, base + match_score(m), "china"))

    for m in digest.schedule:
        if not (is_chinese_involved(m) and m.is_singles):
            continue
        p = next((p for p in m.home + m.away if is_chinese_player(p)), None)
        if p is None:
            continue
        t = fmt_time_beijing(m.start_utc)
        when = f"{t}出战" if t != "待定" else "今日出战"
        candidates.append(
            _Candidate(f"{player_zh(p.name)}{when}", 270 + match_score(m), "china")
        )

    summary = china_summary(digest)
    if summary:
        wins = sum(
            1 for m in digest.results if is_chinese_involved(m) and chinese_side_won(m)
        )
        candidates.append(_Candidate(summary, 230 + wins * 18, "china-summary"))
    return candidates


def cn_headline(digest: Digest) -> str | None:
    candidates = _cn_candidates(digest)
    return max(candidates, key=lambda c: c.score).text if candidates else None


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
    """去重后的候选列表，按故事价值评分排序."""
    candidates = _cn_candidates(digest)
    upset = upset_headline(digest)
    if upset:
        m = find_upset(digest.results)
        candidates.append(_Candidate(upset, 200 + (match_score(m) if m else 0), "upset"))
    star = star_headline(digest)
    if star:
        candidates.append(_Candidate(star, 150, "star"))

    seen: set[str] = set()
    out: list[str] = []
    for candidate in sorted(candidates, key=lambda c: c.score, reverse=True):
        h = candidate.text
        if h and h not in seen:
            seen.add(h)
            out.append(h)
    if not out:
        out.append("每日赛程赛果速览")
    return out


def cover_highlights(digest: Digest) -> tuple[str, str]:
    """Main cover hook plus a distinct secondary proof point."""
    candidates = title_candidates(digest)
    primary = candidates[0]
    secondary = next((h for h in candidates[1:] if h != primary), "")
    if not secondary:
        secondary = "昨夜赛果与今晚重点，一页看懂"
    return primary, secondary


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


def _whitelist_meaning(m) -> str | None:
    """V1 意义句白名单的机械模式：证据不足返回 None（调用方降级为结果句）.

    仅覆盖可从当日数据机械验证的四类：退赛、爆冷、先丢一盘逆转、
    决胜盘抢七/抢十。退赛不得推断原因；历史类表述走人工档案。
    """
    from ..models import MatchStatus

    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w or not l:
        return None
    wn, ln = player_zh(w.name), player_zh(l.name)
    r = _flat_round(m)

    if m.status is MatchStatus.RETIRED:
        return f"{ln}退赛，{wn}晋级{r or '下一轮'}"
    if is_upset(m):
        return f"爆冷：{wn}掀翻{ln}"
    sets = m.sets or []
    decided = [s for s in sets if s.home != s.away]
    if len(decided) >= 2:
        first, last = decided[0], decided[-1]
        winner_is_home = m.winner == 0
        lost_first = (first.home < first.away) if winner_is_home else (first.home > first.away)
        if lost_first:
            return f"{wn}先丢一盘，逆转晋级"
        super_tb = {last.home, last.away} == {1, 0}
        tb = last.home_tiebreak is not None and last.away_tiebreak is not None
        if len(decided) >= 3 and (super_tb or tb):
            how = "抢十" if super_tb else "抢七"
            return f"决胜盘{how}，{wn}惊险过关"
    return None


def cover_result_hook(m) -> tuple[str, str]:
    """Turn the lead result into a significance-first cover hook.

    Historical claims come only from reviewed profiles. Everyone else keeps the
    conservative, match-derived headline and insight path.
    """
    from .story import result_insight

    winner = (m.winner_players() or [None])[0]
    if winner is None:
        return flash_headline(m), result_insight(m)

    profile = _HISTORICAL_PROFILES.get(winner.name)
    if profile is None:
        mechanical = _whitelist_meaning(m)
        if mechanical:
            return mechanical, result_insight(m)
        return flash_headline(m), result_insight(m)

    name = player_zh(winner.name)
    rank = winner.rank
    round_name = _flat_round(m)
    is_final = round_name.endswith("决赛") and "半" not in round_name and "四" not in round_name
    if rank is not None and rank >= profile.peak_rank + 20:
        action = "终于捧杯" if is_final else "重新赢球"
        headline = f"跌至世界第{rank}，{name}{action}"
        result = "这座冠军" if is_final else "这场胜利"
        secondary = (
            f"曾高居世界第{profile.peak_rank}、{profile.legacy}；"
            f"{result}，是排名低谷里的反弹信号"
        )
        return headline, secondary

    if is_final:
        return (
            f"{profile.legacy}，{name}再迎冠军夜",
            "这不只是一场决赛胜利，更是生涯坐标上的新节点",
        )
    return flash_headline(m), f"{profile.legacy}再度过关，胜负之外更要看状态走向"
