"""Select and summarize one singles match for a deeper daily review."""

from __future__ import annotations

from dataclasses import dataclass

from ..digest import Digest
from ..models import Match
from ..zh import player_zh
from .common import is_chinese_involved
from .rating import is_tour_focus_match, is_upset, match_score
from .story import result_insight


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


def select_focus_match(digest: Digest) -> Match | None:
    singles = [
        m for m in digest.results
        if m.is_singles and m.sets and is_tour_focus_match(m)
    ]
    if not singles:
        return None

    def score(match: Match) -> int:
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

    return max(singles, key=score)


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
