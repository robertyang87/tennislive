"""SofaScore 非官方接口数据源（备用）.

    https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{YYYY-MM-DD}

数据全面（含 ATP/WTA/挑战赛/ITF），但对数据中心 IP 有封锁风险（403），
因此仅作为 ESPN 之后的备用源。只保留 category 为 ATP/WTA 的巡回赛正赛。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from ..models import Match, MatchStatus, Player, SetScore, Tour, Tournament
from ..timeutil import BEIJING
from .base import SourceError, TennisSource, make_session

logger = logging.getLogger(__name__)

URL = "https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{d}"


def _status_of(ev: dict) -> tuple[MatchStatus, str | None, str | None]:
    st = ev.get("status") or {}
    typ = st.get("type") or ""
    desc = st.get("description") or ""
    low = desc.lower()
    if typ == "notstarted":
        return MatchStatus.SCHEDULED, desc or None, None
    if typ == "inprogress":
        return MatchStatus.LIVE, desc or None, None
    if typ in ("canceled", "cancelled"):
        return MatchStatus.CANCELLED, desc or None, None
    if typ == "postponed":
        return MatchStatus.POSTPONED, desc or None, None
    if typ == "finished" or typ == "":
        if "retired" in low or "retirement" in low:
            return MatchStatus.RETIRED, desc or None, "对手退赛"
        if "walkover" in low:
            return MatchStatus.WALKOVER, desc or None, "不战而胜"
        return MatchStatus.FINISHED, desc or None, None
    return MatchStatus.SCHEDULED, desc or None, None


def _players_of(team: dict) -> list[Player]:
    name = team.get("name") or "?"
    country = (team.get("country") or {}).get("alpha3") or (
        team.get("country") or {}
    ).get("alpha2")
    ranking = team.get("ranking")
    # 双打组合名形如 "Krajicek R. / Patten H."
    if "/" in name:
        return [Player(name=part.strip(), country=None) for part in name.split("/")]
    p = Player(name=name, country=country, player_id=str(team.get("id") or "") or None)
    if ranking:
        try:
            p.rank = int(ranking)
        except (TypeError, ValueError):
            pass
    return [p]


def _sets_of(home_score: dict, away_score: dict) -> list[SetScore]:
    sets: list[SetScore] = []
    for i in range(1, 6):
        h = home_score.get(f"period{i}")
        a = away_score.get(f"period{i}")
        if h is None and a is None:
            continue
        sets.append(
            SetScore(
                home=int(h or 0),
                away=int(a or 0),
                home_tiebreak=home_score.get(f"period{i}TieBreak"),
                away_tiebreak=away_score.get(f"period{i}TieBreak"),
            )
        )
    return sets


class SofaScoreSource(TennisSource):
    name = "sofascore"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = make_session(
            {
                "Referer": "https://www.sofascore.com/",
                "Origin": "https://www.sofascore.com",
            }
        )

    def _fetch(self, d: date) -> list[dict]:
        url = URL.format(d=d.isoformat())
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise SourceError(f"SofaScore HTTP {resp.status_code}（数据中心 IP 可能被封）")
        try:
            return resp.json().get("events") or []
        except ValueError as e:
            raise SourceError(f"SofaScore 返回的不是 JSON: {e}") from e

    def _parse(self, ev: dict) -> Match | None:
        tournament_info = ev.get("tournament") or {}
        category = ((tournament_info.get("category") or {}).get("name") or "").upper()
        if category not in ("ATP", "WTA"):
            return None  # 过滤挑战赛/ITF/青少年等
        tour = Tour.ATP if category == "ATP" else Tour.WTA

        home_team = ev.get("homeTeam") or {}
        away_team = ev.get("awayTeam") or {}
        home = _players_of(home_team)
        away = _players_of(away_team)
        if not home or not away:
            return None

        status, detail, note = _status_of(ev)
        winner_code = ev.get("winnerCode")
        winner = {1: 0, 2: 1}.get(winner_code)

        start_utc = None
        ts = ev.get("startTimestamp")
        if ts:
            start_utc = datetime.fromtimestamp(int(ts), tz=timezone.utc)

        unique = tournament_info.get("uniqueTournament") or {}
        tournament = Tournament(
            name=unique.get("name") or tournament_info.get("name") or "?",
            tour=tour,
            surface=ev.get("groundType") or None,
            tournament_id=str(unique.get("id") or "") or None,
        )

        round_info = ev.get("roundInfo") or {}
        round_name = round_info.get("name")
        if not round_name and round_info.get("round"):
            round_name = f"Round {round_info['round']}"

        return Match(
            match_id=str(ev.get("id") or ""),
            tour=tour,
            tournament=tournament,
            home=home,
            away=away,
            status=status,
            round_name=round_name,
            start_utc=start_utc,
            sets=_sets_of(ev.get("homeScore") or {}, ev.get("awayScore") or {}),
            winner=winner,
            note=note,
            status_detail=detail,
        )

    def fetch_day(self, d: date) -> list[Match]:
        """北京时间的一天对应 UTC 的 d-1 与 d 两个日期，各拉一次后按北京日期过滤."""
        matches: dict[str, Match] = {}
        fetched_any = False
        errors: list[str] = []
        for day in (d - timedelta(days=1), d):
            try:
                events = self._fetch(day)
                fetched_any = True
            except SourceError as e:
                errors.append(str(e))
                logger.warning("SofaScore %s 抓取失败: %s", day, e)
                continue
            for ev in events:
                m = self._parse(ev)
                if m is None:
                    continue
                if m.start_utc is not None:
                    if m.start_utc.astimezone(BEIJING).date() != d:
                        continue
                matches[m.match_id] = m
        if not fetched_any:
            raise SourceError(f"SofaScore 全部抓取失败: {'; '.join(errors)}")
        return sorted(
            matches.values(),
            key=lambda m: (
                m.start_utc or datetime.max.replace(tzinfo=timezone.utc),
                m.tournament.name,
            ),
        )
