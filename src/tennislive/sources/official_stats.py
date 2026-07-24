"""Official per-match statistics with deterministic provider fallbacks."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Protocol

from ..models import Match, MatchStats, StatPair, Tour
from .base import SourceError, make_session
from .official_schedule import _event_for_match, _load_registry
from .sportradar import SportradarOfficialStats

WTA_API = "https://api.wtatennis.com/tennis"
ATP_API = "https://api.protennislive.com/feeds"


def _norm(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold()).replace(",", " ")
    return " ".join(
        "".join(ch for ch in token if ch.isalnum())
        for token in re.split(r"[\s.-]+", plain)
        if token
    )


def _name_tokens(value: str) -> set[str]:
    return {token for token in _norm(value).split() if len(token) >= 2}


def _same_name(left: str, right: str) -> bool:
    left_tokens, right_tokens = _name_tokens(left), _name_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    overlap = left_tokens & right_tokens
    return bool(
        overlap
        and (
            len(overlap) >= 2
            or (
                len(overlap) == 1
                and max(map(len, overlap)) >= 5
                and min(len(left_tokens), len(right_tokens)) == 1
            )
        )
    )


def _field(row: dict, name: str, default=None):
    if name in row:
        return row[name]
    folded = name.casefold()
    for key, value in row.items():
        if str(key).casefold() == folded:
            return value
    return default


def _number(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator * 100 / denominator)


def _duration_minutes(value: object) -> int | None:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) not in {2, 3} or not all(part.isdigit() for part in parts):
        return None
    if len(parts) == 2:
        hours, minutes = map(int, parts)
        seconds = 0
    else:
        hours, minutes, seconds = map(int, parts)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return round(total_seconds / 60)


def _pair(left: float | None, right: float | None, *, reverse: bool) -> StatPair | None:
    if left is None or right is None:
        return None
    if reverse:
        left, right = right, left
    return StatPair(left, right)


def _stats_are_useful(stats: MatchStats) -> bool:
    core = (
        stats.total_points_won,
        stats.first_serve_in_pct,
        stats.first_serve_won_pct,
        stats.second_serve_won_pct,
        stats.aces,
        stats.break_points_won,
    )
    return sum(value is not None for value in core) >= 3


def _wta_player_name(row: dict, side: str) -> str:
    first = str(_field(row, f"PlayerNameFirst{side}", "") or "").strip()
    last = str(_field(row, f"PlayerNameLast{side}", "") or "").strip()
    return f"{first} {last}".strip()


def _wta_shot_value(row: dict, side: str, names: tuple[str, ...]) -> float | None:
    suffix = side.casefold()
    for name in names:
        value = _number(_field(row, f"{name}{suffix}"))
        if value is not None:
            return value
    return None


def _parse_wta_stats(
    rows: list[dict],
    *,
    reverse: bool,
    source_url: str,
    duration: object = None,
) -> MatchStats:
    total = next(
        (
            row
            for row in rows
            if _number(_field(row, "setnum")) is not None
            and int(_number(_field(row, "setnum"))) == 0
        ),
        None,
    )
    if total is None:
        raise SourceError("WTA official response has no full-match statistics")

    def values(stem: str) -> tuple[float | None, float | None]:
        return (
            _number(_field(total, f"{stem}a")),
            _number(_field(total, f"{stem}b")),
        )

    first_won_a, first_won_b = values("ptswon1stserv")
    first_played_a, first_played_b = values("ptsplayed1stserv")
    service_won_a, service_won_b = values("ptstotwonserv")
    service_played_a, service_played_b = values("totservplayed")

    second_won_a = (
        service_won_a - first_won_a
        if service_won_a is not None and first_won_a is not None
        else None
    )
    second_won_b = (
        service_won_b - first_won_b
        if service_won_b is not None and first_won_b is not None
        else None
    )
    second_played_a = (
        service_played_a - first_played_a
        if service_played_a is not None and first_played_a is not None
        else None
    )
    second_played_b = (
        service_played_b - first_played_b
        if service_played_b is not None and first_played_b is not None
        else None
    )

    winners_a = _wta_shot_value(total, "A", ("winners", "winner"))
    winners_b = _wta_shot_value(total, "B", ("winners", "winner"))
    errors_a = _wta_shot_value(
        total, "A", ("unforcederrors", "unforcederrs", "unforcederror")
    )
    errors_b = _wta_shot_value(
        total, "B", ("unforcederrors", "unforcederrs", "unforcederror")
    )

    stats = MatchStats(
        source="WTA 官方逐场技术统计",
        source_url=source_url,
        total_points_won=_pair(*values("totptswon"), reverse=reverse),
        service_points_won=_pair(service_won_a, service_won_b, reverse=reverse),
        first_serve_in_pct=_pair(
            _pct(first_played_a, service_played_a),
            _pct(first_played_b, service_played_b),
            reverse=reverse,
        ),
        first_serve_won_pct=_pair(
            _pct(first_won_a, first_played_a),
            _pct(first_won_b, first_played_b),
            reverse=reverse,
        ),
        second_serve_won_pct=_pair(
            _pct(second_won_a, second_played_a),
            _pct(second_won_b, second_played_b),
            reverse=reverse,
        ),
        aces=_pair(*values("aces"), reverse=reverse),
        double_faults=_pair(*values("dblflt"), reverse=reverse),
        break_points_won=_pair(*values("breakptsconv"), reverse=reverse),
        break_points_chances=_pair(*values("breakptsplayed"), reverse=reverse),
        winners=_pair(winners_a, winners_b, reverse=reverse),
        unforced_errors=_pair(errors_a, errors_b, reverse=reverse),
        duration_minutes=_duration_minutes(duration),
    )
    if not _stats_are_useful(stats):
        raise SourceError("WTA official response has too few usable statistics")
    return stats


class WtaOfficialStats:
    """Public JSON used by WTA's own tournament score pages."""

    def __init__(self, timeout: int = 30, session=None):
        self.timeout = timeout
        self.session = session or make_session(
            {
                "Accept": "application/json",
                "Origin": "https://www.wtatennis.com",
                "Referer": "https://www.wtatennis.com/",
            }
        )

    def _get_json(self, path: str, *, params: dict | None = None):
        url = f"{WTA_API}/{path.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code != 200:
            raise SourceError(f"WTA official API HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError("WTA official API returned non-JSON data") from exc

    @staticmethod
    def _event_score(event: dict, match: Match) -> int:
        group = _field(event, "tournamentGroup") or {}
        haystack = " ".join(
            str(value or "")
            for value in (
                _field(group, "name"),
                _field(event, "title"),
                _field(event, "city"),
            )
        )
        wanted = _name_tokens(
            f"{match.tournament.name} {match.tournament.city or ''}"
        )
        available = _name_tokens(haystack)
        return len(wanted & available)

    @staticmethod
    def _match_order(row: dict, match: Match) -> bool | None:
        if str(_field(row, "DrawMatchType", "")).upper() != "S":
            return None
        player_a = _wta_player_name(row, "A")
        player_b = _wta_player_name(row, "B")
        direct = _same_name(player_a, match.home[0].name) and _same_name(
            player_b, match.away[0].name
        )
        reverse = _same_name(player_a, match.away[0].name) and _same_name(
            player_b, match.home[0].name
        )
        if direct:
            return False
        if reverse:
            return True
        return None

    def fetch_match_stats(self, match: Match) -> MatchStats:
        if match.tour != Tour.WTA or match.is_doubles:
            raise SourceError("WTA official stats only support WTA singles here")
        if match.start_utc is None:
            raise SourceError("Match start time is unavailable for WTA lookup")

        match_date = match.start_utc.astimezone(timezone.utc).date()
        events_payload = self._get_json(
            "tournaments",
            params={
                "page": 0,
                "pageSize": 100,
                "excludeLevels": "ITF",
                "from": (match_date - timedelta(days=7)).isoformat(),
                "to": (match_date + timedelta(days=7)).isoformat(),
            },
        )
        events = list(_field(events_payload, "content") or [])
        events.sort(key=lambda event: self._event_score(event, match), reverse=True)

        for event in events:
            group = _field(event, "tournamentGroup") or {}
            event_id = _field(group, "id") or _field(event, "liveScoringId")
            year = _field(event, "year")
            if not event_id or not year:
                continue
            match_payload = self._get_json(
                f"tournaments/{event_id}/{year}/matches",
                params={
                    "from": (match_date - timedelta(days=1)).isoformat(),
                    "to": (match_date + timedelta(days=1)).isoformat(),
                },
            )
            for official_match in _field(match_payload, "matches") or []:
                reverse = self._match_order(official_match, match)
                if reverse is None:
                    continue
                match_id = _field(official_match, "MatchID")
                if not match_id:
                    continue
                source_url = (
                    f"{WTA_API}/tournaments/{event_id}/{year}/matches/"
                    f"{match_id}/stats"
                )
                rows = self._get_json(
                    f"tournaments/{event_id}/{year}/matches/{match_id}/stats"
                )
                return _parse_wta_stats(
                    list(rows or []),
                    reverse=reverse,
                    source_url=source_url,
                    duration=_field(official_match, "MatchTimeTotal"),
                )
        raise SourceError("WTA official match statistics were not found")


def _atp_team_name(row: dict, team_key: str) -> str:
    team = _field(row, team_key) or {}
    first = _field(team, "PlayerFirstNameFull") or _field(team, "PlayerFirstName") or ""
    last = _field(team, "PlayerLastName") or ""
    return f"{first} {last}".strip()


def _atp_multiple(row: dict, *path: str, value: str) -> float | None:
    current = row
    for key in path:
        current = _field(current or {}, key) or {}
    return _number(_field(current or {}, value))


def _atp_summary(team: dict) -> dict:
    sets = _field(team, "Sets") or []
    summary = next(
        (
            row
            for row in sets
            if _number(_field(row, "SetNumber")) is not None
            and int(_number(_field(row, "SetNumber"))) == 0
        ),
        None,
    )
    if not summary:
        raise SourceError("ATP official response has no full-match statistics")
    return _field(summary, "Stats") or {}


def _parse_atp_stats(
    payload: dict,
    *,
    reverse: bool,
    source_url: str,
    duration: object = None,
) -> MatchStats:
    team1 = _atp_summary(_field(payload, "PlayerTeam1") or {})
    team2 = _atp_summary(_field(payload, "PlayerTeam2") or {})

    def number_pair(section: str, field_name: str) -> StatPair | None:
        left = _atp_multiple(team1, section, field_name, value="Number")
        right = _atp_multiple(team2, section, field_name, value="Number")
        return _pair(left, right, reverse=reverse)

    def multiple_pair(
        section: str, field_name: str, value: str = "Percent"
    ) -> StatPair | None:
        left = _atp_multiple(team1, section, field_name, value=value)
        right = _atp_multiple(team2, section, field_name, value=value)
        return _pair(left, right, reverse=reverse)

    stats = MatchStats(
        source="ATP ProTennisLive 官方技术统计",
        source_url=source_url,
        total_points_won=multiple_pair("PointStats", "TotalPointsWon", "Dividend"),
        service_points_won=multiple_pair(
            "PointStats", "TotalServicePointsWon", "Dividend"
        ),
        first_serve_in_pct=multiple_pair("ServiceStats", "FirstServe"),
        first_serve_won_pct=multiple_pair(
            "ServiceStats", "FirstServePointsWon"
        ),
        second_serve_won_pct=multiple_pair(
            "ServiceStats", "SecondServePointsWon"
        ),
        aces=number_pair("ServiceStats", "Aces"),
        double_faults=number_pair("ServiceStats", "DoubleFaults"),
        break_points_won=multiple_pair(
            "ReturnStats", "BreakPointsConverted", "Dividend"
        ),
        break_points_chances=multiple_pair(
            "ReturnStats", "BreakPointsConverted", "Divisor"
        ),
        duration_minutes=_duration_minutes(duration),
    )
    if not _stats_are_useful(stats):
        raise SourceError("ATP official response has too few usable statistics")
    return stats


class AtpOfficialStats:
    """ATP ProTennisLive organisation API using an authorised Bearer token."""

    def __init__(self, token: str, timeout: int = 30, session=None):
        self.token = token
        self.timeout = timeout
        self.session = session or make_session(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }
        )

    @classmethod
    def from_env(cls) -> "AtpOfficialStats | None":
        token = (
            os.environ.get("ATP_PROTENNISLIVE_TOKEN", "").strip()
            or os.environ.get("PROTENNISLIVE_JWT", "").strip()
        )
        return cls(token) if token else None

    def _get_json(self, path: str):
        url = f"{ATP_API}/{path.lstrip('/')}"
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code in {401, 403}:
            raise SourceError(
                "ATP ProTennisLive token is invalid or lacks Tournament Claims"
            )
        if response.status_code != 200:
            raise SourceError(f"ATP ProTennisLive HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError("ATP ProTennisLive returned non-JSON data") from exc

    @staticmethod
    def _registry_event_id(match: Match) -> int | None:
        event = _event_for_match(match, _load_registry())
        if event is None:
            return None
        found = re.search(r"/(\d+)/(?:op|OP)\.pdf", event.url)
        return int(found.group(1)) if found else None

    def _event_candidates(self, match: Match) -> list[tuple[int, int]]:
        year = match.start_utc.year if match.start_utc else date.today().year
        candidates: list[tuple[int, int]] = []
        registry_id = self._registry_event_id(match)
        if registry_id:
            candidates.append((year, registry_id))

        calendar = self._get_json("Tournaments/calendar")
        wanted = _name_tokens(
            f"{match.tournament.name} {match.tournament.city or ''}"
        )
        ranked: list[tuple[int, int, int]] = []
        for event in _field(calendar, "TournamentInfos") or []:
            event_year = int(_number(_field(event, "TournamentYear")) or 0)
            event_id = int(_number(_field(event, "TournamentId")) or 0)
            if not event_year or not event_id:
                continue
            text = " ".join(
                str(_field(event, key, "") or "")
                for key in (
                    "TournamentName",
                    "TournamentTitle",
                    "TournamentCity",
                    "TournamentLocation",
                )
            )
            score = len(wanted & _name_tokens(text))
            if score:
                ranked.append((score, event_year, event_id))
        ranked.sort(reverse=True)
        for _score, event_year, event_id in ranked:
            candidate = (event_year, event_id)
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    @staticmethod
    def _match_order(row: dict, match: Match) -> bool | None:
        team1 = _atp_team_name(row, "PlayerTeam1")
        team2 = _atp_team_name(row, "PlayerTeam2")
        if _same_name(team1, match.home[0].name) and _same_name(
            team2, match.away[0].name
        ):
            return False
        if _same_name(team1, match.away[0].name) and _same_name(
            team2, match.home[0].name
        ):
            return True
        return None

    def fetch_match_stats(self, match: Match) -> MatchStats:
        if match.tour != Tour.ATP or match.is_doubles:
            raise SourceError("ATP official stats only support ATP singles here")
        for year, event_id in self._event_candidates(match):
            results = self._get_json(f"Results/{year}/{event_id}")
            for official_match in _field(results, "Matches") or []:
                reverse = self._match_order(official_match, match)
                if reverse is None:
                    continue
                match_id = str(_field(official_match, "MatchId", "") or "").strip()
                if not match_id:
                    continue
                source_url = (
                    f"{ATP_API}/MatchStats/{year}/{event_id}/{match_id}"
                )
                payload = self._get_json(
                    f"MatchStats/{year}/{event_id}/{match_id}"
                )
                return _parse_atp_stats(
                    payload,
                    reverse=reverse,
                    source_url=source_url,
                    duration=_field(official_match, "MatchTime"),
                )
        raise SourceError("ATP official match statistics were not found")


class StatsProvider(Protocol):
    def fetch_match_stats(self, match: Match) -> MatchStats: ...


@dataclass(frozen=True)
class StatsFetchResult:
    stats: MatchStats | None
    source_status: dict[str, str]


def fetch_match_stats_with_fallback(
    match: Match,
    *,
    providers: Iterable[tuple[str, StatsProvider]] | None = None,
) -> StatsFetchResult:
    """Try every configured provider; narrative fallback happens after this."""
    status: dict[str, str] = {}
    if providers is None:
        configured: list[tuple[str, StatsProvider]] = []
        if match.tour == Tour.WTA:
            configured.append(("WTA 官方技术统计", WtaOfficialStats()))
        else:
            atp = AtpOfficialStats.from_env()
            if atp is not None:
                configured.append(("ATP 官方技术统计", atp))
            else:
                status["ATP 官方技术统计"] = (
                    "未配置 · 缺少 ATP_PROTENNISLIVE_TOKEN"
                )
        sportradar = SportradarOfficialStats.from_env()
        if sportradar is not None:
            configured.append(("Sportradar 技术统计", sportradar))
        else:
            status["Sportradar 技术统计"] = (
                "未配置 · 缺少 SPORTRADAR_API_KEY"
            )
        providers = configured

    for label, provider in providers:
        try:
            stats = provider.fetch_match_stats(match)
        except (SourceError, OSError, ValueError, TypeError) as exc:
            status[label] = f"降级 · {exc}"
            continue
        if not _stats_are_useful(stats):
            status[label] = "降级 · 返回字段不足"
            continue
        status[label] = "正常 · 已命中焦点比赛逐场统计"
        return StatsFetchResult(stats, status)
    return StatsFetchResult(None, status)
