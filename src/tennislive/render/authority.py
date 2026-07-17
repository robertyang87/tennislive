"""Turn verified prior-match facts into attributable schedule talking points."""

from __future__ import annotations

import json
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..digest import Digest
from ..models import Match, MatchStats, Player, StatPair
from ..zh import player_zh
from .common import CHINESE_PLAYER_NAMES

logger = logging.getLogger(__name__)
EDITORIAL_NOTES = Path(__file__).resolve().parents[3] / "data" / "editorial_notes.json"


@dataclass(frozen=True)
class EditorialEvidence:
    text: str
    source: str
    priority: int


def _timestamp(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _name_key(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in plain if ch.isalnum())


def apply_curated_editorial(
    digest: Digest, path: Path = EDITORIAL_NOTES
) -> int:
    """Apply manually reviewed media summaries for this edition.

    The file stores our own fact-based summaries plus the source URL. It is
    intentionally separate from automatic score evidence: media copy must be
    checked by an editor unless a licensed content API is configured.
    """
    try:
        editions = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 0
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("编辑台数据读取失败（继续使用数据看点）: %s", exc)
        return 0

    entries = editions.get(digest.today.isoformat(), [])
    applied = 0
    for match in digest.schedule:
        match_players = {
            _name_key(player.name) for player in match.home + match.away
        }
        tournament = match.tournament.name.casefold()
        for entry in entries:
            expected_players = {
                _name_key(str(name)) for name in entry.get("players", [])
            }
            aliases = [
                str(alias).casefold() for alias in entry.get("tournament_aliases", [])
            ]
            if entry.get("tour") and str(entry["tour"]) != match.tour.value:
                continue
            if expected_players != match_players:
                continue
            if aliases and not any(alias in tournament for alias in aliases):
                continue
            text = str(entry.get("text", "")).strip()
            source = str(entry.get("source_name", "")).strip()
            source_url = str(entry.get("source_url", "")).strip()
            if not (text and source and source_url.startswith("https://")):
                continue
            match.editorial_note = text
            match.editorial_source = source
            match.editorial_url = source_url
            applied += 1
            break
    return applied


def _same_player(left: Player, right: Player) -> bool:
    if left.player_id and right.player_id and left.player_id == right.player_id:
        return True
    return _name_key(left.name) == _name_key(right.name)


def _is_chinese(player: Player) -> bool:
    return (player.country or "").upper() in {"CHN", "CN"} or player_zh(
        player.name
    ) in CHINESE_PLAYER_NAMES


def _player_side(match: Match, player: Player) -> int | None:
    if any(_same_player(player, candidate) for candidate in match.home):
        return 0
    if any(_same_player(player, candidate) for candidate in match.away):
        return 1
    return None


def _pair_value(pair: StatPair | None, side: int) -> float | None:
    if pair is None:
        return None
    return pair.home if side == 0 else pair.away


def _number(value: float) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"


def _stats_source_label(stats: MatchStats) -> str:
    source = stats.source.casefold()
    if "sportradar" in source:
        return "Sportradar授权技术统计"
    return "授权技术统计"


def _stats_evidence(result: Match, player: Player) -> EditorialEvidence | None:
    stats = result.stats
    side = _player_side(result, player)
    if stats is None or side is None:
        return None

    facts: list[str] = []
    aces = _pair_value(stats.aces, side)
    first_won = _pair_value(stats.first_serve_won_pct, side)
    breaks = _pair_value(stats.break_points_won, side)
    break_chances = _pair_value(stats.break_points_chances, side)

    if aces is not None and aces > 0:
        facts.append(f"{_number(aces)}记Ace")
    if first_won is not None:
        facts.append(f"一发得分率{_number(first_won)}%")
    if breaks is not None and break_chances is not None:
        facts.append(f"破发点兑现{_number(breaks)}/{_number(break_chances)}")
    if not facts:
        total_points = _pair_value(stats.total_points_won, side)
        if total_points is not None:
            facts.append(f"拿到{_number(total_points)}个总得分")
    if not facts:
        return None

    name = player_zh(player.name)
    label = _stats_source_label(stats)
    return EditorialEvidence(
        text=f"{label}：{name}上一轮" + "、".join(facts[:2]),
        source=stats.source,
        priority=4,
    )


def _tiebreak_count(match: Match) -> int:
    return sum(
        1
        for score in match.sets
        if score.home_tiebreak is not None
        or score.away_tiebreak is not None
        or {score.home, score.away} == {6, 7}
    )


def _score_source(match: Match, digest_source: str) -> tuple[str, str]:
    if match.editorial_source:
        return match.editorial_source, match.editorial_source
    return "聚合赛果", digest_source or "aggregated results"


def _score_evidence(
    result: Match, player: Player, digest_source: str
) -> EditorialEvidence | None:
    side = _player_side(result, player)
    if side is None or result.winner != side or not result.sets:
        return None

    played_sets = [score for score in result.sets if score.home != score.away]
    if not played_sets:
        return None
    winner_lost_first = (
        played_sets[0].home < played_sets[0].away
        if side == 0
        else played_sets[0].away < played_sets[0].home
    )
    opponent_games = sum(
        score.away if side == 0 else score.home for score in played_sets
    )
    tiebreaks = _tiebreak_count(result)

    if len(played_sets) == 2:
        fact = "直落两盘过关"
        if opponent_games <= 5:
            fact += f"，仅丢{opponent_games}局"
        if tiebreaks == 2:
            fact = "两盘均经抢七后过关"
    elif winner_lost_first:
        fact = "先丢一盘后连扳两盘逆转"
    elif len(played_sets) >= 3:
        fact = "鏖战三盘过关"
    else:
        return None

    label, source = _score_source(result, digest_source)
    return EditorialEvidence(
        text=f"{label}：{player_zh(player.name)}上一轮{fact}",
        source=source,
        priority=3,
    )


def _latest_result(digest: Digest, scheduled: Match, player: Player) -> Match | None:
    candidates = []
    for result in digest.results:
        if result.tour != scheduled.tour or result.is_singles != scheduled.is_singles:
            continue
        if result.tournament.name != scheduled.tournament.name:
            continue
        if _player_side(result, player) is None:
            continue
        if (
            scheduled.start_utc
            and result.start_utc
            and _timestamp(result.start_utc) >= _timestamp(scheduled.start_utc)
        ):
            continue
        candidates.append(result)

    def when(match: Match) -> float:
        return _timestamp(match.start_utc) if match.start_utc else 0

    return max(candidates, key=when, default=None)


def collect_schedule_evidence(
    digest: Digest, scheduled: Match
) -> list[EditorialEvidence]:
    """Collect attributable prior-round evidence for both sides of a match."""
    evidence: list[tuple[bool, EditorialEvidence]] = []
    for player in scheduled.home + scheduled.away:
        result = _latest_result(digest, scheduled, player)
        if result is None:
            continue
        item = _stats_evidence(result, player) or _score_evidence(
            result, player, digest.source
        )
        if item:
            evidence.append((_is_chinese(player), item))

    evidence.sort(key=lambda item: (item[0], item[1].priority), reverse=True)
    return [item for _, item in evidence]


def build_schedule_evidence(digest: Digest, scheduled: Match) -> EditorialEvidence | None:
    """Build one concise, attributable preview from same-event prior results."""
    evidence = collect_schedule_evidence(digest, scheduled)
    return evidence[0] if evidence else None


def enrich_schedule_editorial(digest: Digest) -> None:
    """Attach verified preview evidence to scheduled matches in place."""
    for scheduled in digest.schedule:
        if scheduled.editorial_note:
            continue
        evidence = build_schedule_evidence(digest, scheduled)
        if evidence:
            scheduled.editorial_note = evidence.text
            scheduled.editorial_source = evidence.source
