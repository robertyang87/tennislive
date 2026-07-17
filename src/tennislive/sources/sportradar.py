"""Licensed post-match statistics from Sportradar Tennis v3."""

from __future__ import annotations

import os
import unicodedata
from datetime import timezone

from ..models import Match, MatchStats, StatPair
from ..timeutil import BEIJING
from .base import SourceError, make_session

API = "https://api.sportradar.com/tennis"


def _name_tokens(value: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", value.casefold()).replace(",", " ")
    return {
        "".join(ch for ch in token if ch.isalnum())
        for token in plain.replace("-", " ").split()
        if token
    }


def _same_name(left: str, right: str) -> bool:
    left_tokens, right_tokens = _name_tokens(left), _name_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return left_tokens == right_tokens or (
        len(left_tokens & right_tokens) >= 2
        and min(len(left_tokens), len(right_tokens)) <= len(left_tokens & right_tokens) + 1
    )


def _pair(home: dict, away: dict, key: str) -> StatPair | None:
    if key not in home and key not in away:
        return None
    return StatPair(float(home.get(key) or 0), float(away.get(key) or 0))


def _pct(numerator: float, denominator: float) -> float:
    return round(numerator * 100 / denominator) if denominator else 0


def _pct_pair(home: dict, away: dict, numerator: str, denominator: str) -> StatPair | None:
    if numerator not in home and numerator not in away:
        return None
    return StatPair(
        _pct(float(home.get(numerator) or 0), float(home.get(denominator) or 0)),
        _pct(float(away.get(numerator) or 0), float(away.get(denominator) or 0)),
    )


def _serve_in_pair(home: dict, away: dict) -> StatPair | None:
    if "first_serve_successful" not in home and "first_serve_successful" not in away:
        return None

    def value(row: dict) -> float:
        first = float(row.get("first_serve_successful") or 0)
        second = float(row.get("second_serve_successful") or 0)
        faults = float(row.get("double_faults") or 0)
        return _pct(first, first + second + faults)

    return StatPair(value(home), value(away))


def _second_serve_pair(home: dict, away: dict) -> StatPair | None:
    if "second_serve_points_won" not in home and "second_serve_points_won" not in away:
        return None

    def value(row: dict) -> float:
        won = float(row.get("second_serve_points_won") or 0)
        played = float(row.get("second_serve_successful") or 0) + float(
            row.get("double_faults") or 0
        )
        return _pct(won, played)

    return StatPair(value(home), value(away))


def _shot_total(row: dict, suffix: str) -> float | None:
    keys = (
        f"forehand_{suffix}",
        f"backhand_{suffix}",
        f"volley_{suffix}",
        f"overhead_stroke_{suffix}",
        f"drop_shot_{suffix}",
        f"lob_{suffix}",
        f"return_{suffix}",
    )
    values = [float(row[key]) for key in keys if row.get(key) is not None]
    return sum(values) if values else None


def _shot_pair(home: dict, away: dict, suffix: str) -> StatPair | None:
    left, right = _shot_total(home, suffix), _shot_total(away, suffix)
    if left is None and right is None:
        return None
    return StatPair(left or 0, right or 0)


def _statistics_rows(summary: dict) -> list[dict]:
    statistics = summary.get("statistics") or {}
    totals = statistics.get("totals") or {}
    return totals.get("competitors") or statistics.get("competitors") or []


def _parse_stats(summary: dict, match: Match, source_url: str) -> MatchStats:
    event_competitors = (summary.get("sport_event") or {}).get("competitors") or []
    rows = _statistics_rows(summary)
    if not rows:
        raise SourceError("Sportradar summary has no match statistics")

    by_id = {row.get("id"): row.get("statistics") or {} for row in rows}
    home_stats: dict = {}
    away_stats: dict = {}
    for competitor in event_competitors:
        stats = by_id.get(competitor.get("id"), {})
        name = competitor.get("name") or ""
        if _same_name(name, match.home[0].name):
            home_stats = stats
        elif _same_name(name, match.away[0].name):
            away_stats = stats
    if not home_stats and not away_stats and len(rows) >= 2:
        home_stats = rows[0].get("statistics") or {}
        away_stats = rows[1].get("statistics") or {}
    if not home_stats and not away_stats:
        raise SourceError("Sportradar competitor statistics are empty")

    return MatchStats(
        source="Sportradar 授权网球数据",
        source_url=source_url,
        total_points_won=_pair(home_stats, away_stats, "points_won"),
        service_points_won=_pair(home_stats, away_stats, "service_points_won"),
        first_serve_in_pct=_serve_in_pair(home_stats, away_stats),
        first_serve_won_pct=_pct_pair(
            home_stats,
            away_stats,
            "first_serve_points_won",
            "first_serve_successful",
        ),
        second_serve_won_pct=_second_serve_pair(home_stats, away_stats),
        aces=_pair(home_stats, away_stats, "aces"),
        double_faults=_pair(home_stats, away_stats, "double_faults"),
        break_points_won=_pair(home_stats, away_stats, "breakpoints_won"),
        break_points_chances=_pair(home_stats, away_stats, "total_breakpoints"),
        winners=_shot_pair(home_stats, away_stats, "winners"),
        unforced_errors=_shot_pair(home_stats, away_stats, "unforced_errors"),
    )


class SportradarOfficialStats:
    """Fetch one licensed match summary when an API key is configured."""

    def __init__(self, api_key: str, access_level: str = "trial", timeout: int = 30):
        self.api_key = api_key
        self.access_level = access_level
        self.timeout = timeout
        self.session = make_session()

    @classmethod
    def from_env(cls) -> "SportradarOfficialStats | None":
        key = os.environ.get("SPORTRADAR_API_KEY", "").strip()
        if not key:
            return None
        access = os.environ.get("SPORTRADAR_ACCESS_LEVEL", "trial").strip()
        return cls(key, access_level=access or "trial")

    def _summaries(self, date_value: str) -> list[dict]:
        url = (
            f"{API}/{self.access_level}/v3/en/schedules/"
            f"{date_value}/summaries.json"
        )
        return self._get_json(url).get("summaries") or []

    def _get_json(self, url: str) -> dict:
        response = self.session.get(
            url,
            params={"api_key": self.api_key},
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise SourceError(f"Sportradar HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError("Sportradar returned non-JSON data") from exc
        return data

    def _event_summary(self, event_id: str) -> tuple[dict, str]:
        url = (
            f"{API}/{self.access_level}/v3/en/sport_events/"
            f"{event_id}/summary.json"
        )
        return self._get_json(url), url

    @staticmethod
    def _is_match(summary: dict, match: Match) -> bool:
        competitors = (summary.get("sport_event") or {}).get("competitors") or []
        if len(competitors) != 2 or match.is_doubles:
            return False
        names = {row.get("qualifier"): row.get("name") or "" for row in competitors}
        direct = _same_name(names.get("home", ""), match.home[0].name) and _same_name(
            names.get("away", ""), match.away[0].name
        )
        reverse = _same_name(names.get("home", ""), match.away[0].name) and _same_name(
            names.get("away", ""), match.home[0].name
        )
        return direct or reverse

    def fetch_match_stats(self, match: Match) -> MatchStats:
        if match.start_utc is None:
            raise SourceError("Match start time is unavailable for Sportradar lookup")
        dates = {
            match.start_utc.astimezone(timezone.utc).date().isoformat(),
            match.start_utc.astimezone(BEIJING).date().isoformat(),
        }
        for date_value in dates:
            for summary in self._summaries(date_value):
                if not self._is_match(summary, match):
                    continue
                event_id = (summary.get("sport_event") or {}).get("id", "")
                if not event_id:
                    continue
                detail, source_url = self._event_summary(event_id)
                return _parse_stats(detail, match, source_url)
        raise SourceError("Sportradar match summary was not found")
