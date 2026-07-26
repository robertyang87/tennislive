"""Select and summarize one singles match for a deeper daily review."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..digest import Digest
from ..models import Match
from ..zh import player_zh
from .common import is_chinese_involved
from .editorial_memory import recent_focus_ids
from .rating import is_tour_focus_match, is_upset, match_score
from .story import result_insight

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FocusComparison:
    match: Match
    left_name: str
    right_name: str
    left_won: bool
    rows: tuple[tuple[str, str, str], ...]
    verdict: str
    source_label: str | None = None
    source_url: str | None = None
    duration_label: str | None = None


def _tiebreak_wins(match: Match, side: int) -> int:
    wins = 0
    for s in match.sets:
        home_tb, away_tb = s.home_tiebreak, s.away_tiebreak
        if home_tb is None or away_tb is None:
            continue
        if (side == 0 and home_tb > away_tb) or (side == 1 and away_tb > home_tb):
            wins += 1
    return wins


def _sets_won(match: Match, side: int) -> int:
    wins = 0
    for s in match.sets:
        home, away = s.home, s.away
        if home == away and s.home_tiebreak is not None and s.away_tiebreak is not None:
            home, away = s.home_tiebreak, s.away_tiebreak
        if (side == 0 and home > away) or (side == 1 and away > home):
            wins += 1
    return wins


def _games_won(match: Match, side: int) -> int:
    total = 0
    for s in match.sets:
        # Match tiebreak is not a normal service game and is excluded here.
        if {s.home, s.away} == {0, 1} and (
            s.home_tiebreak is not None and s.away_tiebreak is not None
        ):
            continue
        total += s.home if side == 0 else s.away
    return total


def _set_value(match: Match, index: int, side: int) -> str:
    score = match.sets[index]
    games = score.home if side == 0 else score.away
    tiebreak = score.home_tiebreak if side == 0 else score.away_tiebreak
    return f"{games}({tiebreak})" if tiebreak is not None else str(games)


def _int(value: float) -> str:
    return str(int(round(value)))


def _pct(value: float) -> str:
    return f"{int(round(value))}%"


def _pair_rows(match: Match) -> list[tuple[str, str, str]]:
    """Build compact, publication-ready rows from official match statistics."""
    stats = match.stats
    if stats is None:
        return []

    rows: list[tuple[str, str, str]] = []

    def add(label: str, pair, formatter=_int) -> None:
        if pair is not None:
            rows.append((label, formatter(pair.home), formatter(pair.away)))

    add("总得分", stats.total_points_won)
    add("一发成功率", stats.first_serve_in_pct, _pct)
    add("一发得分率", stats.first_serve_won_pct, _pct)
    add("二发得分率", stats.second_serve_won_pct, _pct)

    if stats.aces is not None or stats.double_faults is not None:
        aces = stats.aces
        double_faults = stats.double_faults
        rows.append(
            (
                "ACE / 双误",
                f"{_int(aces.home) if aces else '—'} / "
                f"{_int(double_faults.home) if double_faults else '—'}",
                f"{_int(aces.away) if aces else '—'} / "
                f"{_int(double_faults.away) if double_faults else '—'}",
            )
        )

    if stats.break_points_won is not None:
        won, chances = stats.break_points_won, stats.break_points_chances
        rows.append(
            (
                "破发兑现",
                f"{_int(won.home)}/{_int(chances.home)}" if chances else _int(won.home),
                f"{_int(won.away)}/{_int(chances.away)}" if chances else _int(won.away),
            )
        )

    # Winners and unforced errors must be a complete pair from one provider.
    if stats.winners is not None and stats.unforced_errors is not None:
        winners, errors = stats.winners, stats.unforced_errors
        rows.append(
            (
                "制胜分 / 非受迫",
                f"{_int(winners.home)} / {_int(errors.home)}",
                f"{_int(winners.away)} / {_int(errors.away)}",
            )
        )
    return rows


def has_detailed_stats(match: Match | None) -> bool:
    """Whether a match has enough licensed statistics for a recap page."""
    return bool(match is not None and _pair_rows(match))


def _stats_verdict(match: Match) -> str | None:
    stats = match.stats
    if stats is None:
        return None
    winner = match.winner if match.winner in (0, 1) else 0
    winner_name = player_zh((match.home if winner == 0 else match.away)[0].name)
    fragments: list[str] = []

    if stats.total_points_won is not None:
        gap = abs(stats.total_points_won.home - stats.total_points_won.away)
        fragments.append(f"全场总得分只差{_int(gap)}分")
    if stats.unforced_errors is not None:
        win_errors = (
            stats.unforced_errors.home if winner == 0 else stats.unforced_errors.away
        )
        lose_errors = (
            stats.unforced_errors.away if winner == 0 else stats.unforced_errors.home
        )
        gap = lose_errors - win_errors
        if gap > 0:
            fragments.append(f"{winner_name}将非受迫失误少犯{_int(gap)}次")
    if stats.break_points_won is not None and stats.break_points_chances is not None:
        won = stats.break_points_won.home if winner == 0 else stats.break_points_won.away
        chances = (
            stats.break_points_chances.home
            if winner == 0
            else stats.break_points_chances.away
        )
        fragments.append(f"关键分上兑现{_int(won)}/{_int(chances)}个破发点")

    if not fragments:
        return result_insight(match)
    duration = (
        f"，最终熬过{stats.duration_minutes // 60}小时"
        f"{stats.duration_minutes % 60:02d}分"
        if stats.duration_minutes
        else ""
    )
    return "；".join(fragments[:3]) + duration + "。"


def headline_stats_targets(digest: Digest, budget: int = 4) -> list[Match]:
    """Matches whose official per-match stats the headline page may need.

    The lead card renders a technical comparison only when its match carries
    stats, and degrades to prose otherwise. Prose is meant to be the no-data
    fallback, not the default -- but stats used to be fetched solely for
    select_focus_match(), which picks by its own rules and is frequently a
    different match than the headline (on 2026-07-25 stats landed on a WTA
    match while the headline page was an ATP one, leaving that page with no
    comparison at all).

    Returns the current headline plus the fallback headline candidates the
    cover stage may reselect into, so whichever one is finally rendered has
    its data ready. The headline is included even when it carries no
    editorial heat -- lead_story_candidates() filters those out, and on a
    quiet day it can come back empty while a headline still exists, which is
    exactly why the cover stage keeps its own `or [lead]` fallback.
    """
    from .rating import lead_story_candidates
    from .titles import daily_lead_match

    ordered: list[Match] = []
    seen: set[str] = set()
    lead = daily_lead_match(digest)
    for match in [lead, *(item.match for item in lead_story_candidates(digest)[:budget])]:
        if match is None or match.match_id in seen:
            continue
        seen.add(match.match_id)
        # 只有已完赛单打才有逐场技术统计可取。
        if match.status.is_final and match.is_singles:
            ordered.append(match)
    return ordered


def _focus_score(match: Match) -> int:
    level = match.tournament.level or ""
    tour_level = level in {
        "GS", "M1000", "W1000", "ATP500", "WTA500", "ATP250", "WTA250"
    }
    return (
        match_score(match, cn_boost=False)
        + (85 if is_chinese_involved(match) else 0)
        + (45 if tour_level else 0)
        + (35 if is_upset(match) else 0)
        + sum(
            1
            for s in match.sets
            if s.home_tiebreak is not None or s.away_tiebreak is not None
        )
        * 8
    )


def select_focus_match(digest: Digest) -> Match | None:
    singles = [
        m for m in digest.results
        if m.is_singles and m.sets and is_tour_focus_match(m)
    ]
    if not singles:
        return None

    # 跨期去重：收尾晚的场次次日仍留在 digest.results 里，而这里只取分数
    # 最大值——昨天最高分的今天照样最高分。2026-07-24 与 07-25 就这样选出
    # 同一场，两期焦点复盘的技术统计逐字相同。editorial_memory 原本只记头条，
    # 焦点由 select_focus_match 自己挑、经常和头条不是同一场，没有任何地方
    # 拦得住它，所以那边补了一份焦点台账。
    used = recent_focus_ids(digest.today, days=1)
    fresh = [m for m in singles if m.match_id not in used]
    if not fresh:
        # 候选全被上一期用光时宁可重复，也不能让焦点页整页消失；但要留下
        # 痕迹，否则"去重没生效"和"本来就只有这一场"看起来一模一样。
        logger.info(
            "焦点复盘候选 %d 场全部在最近一期用过，本期只能重复", len(singles)
        )
        fresh = singles
    return max(fresh, key=_focus_score)


def focus_comparison(match: Match) -> FocusComparison:
    left, right = 0, 1
    left_name = player_zh(match.home[0].name)
    right_name = player_zh(match.away[0].name)
    rows = _pair_rows(match)
    if not rows:
        rows = [
            ("盘数", str(_sets_won(match, left)), str(_sets_won(match, right))),
            ("总局数", str(_games_won(match, left)), str(_games_won(match, right))),
            ("抢七胜", str(_tiebreak_wins(match, left)), str(_tiebreak_wins(match, right))),
        ]
        set_labels = ("首盘", "第二盘", "决胜盘", "第四盘", "第五盘")
        rows.extend(
            (set_labels[index], _set_value(match, index, left), _set_value(match, index, right))
            for index in range(min(len(match.sets), len(set_labels)))
        )
    stats = match.stats
    duration_label = None
    if stats and stats.duration_minutes:
        duration_label = (
            f"{stats.duration_minutes // 60}小时{stats.duration_minutes % 60:02d}分"
        )
    return FocusComparison(
        match=match,
        left_name=left_name,
        right_name=right_name,
        left_won=match.winner == 0,
        rows=tuple(rows),
        verdict=_stats_verdict(match) or result_insight(match),
        source_label=stats.source if stats else None,
        source_url=stats.source_url if stats else None,
        duration_label=duration_label,
    )
