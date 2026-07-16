"""ESPN 公开数据接口数据源.

ESPN 提供无需鉴权的公开 JSON 接口（其官网前端同款），覆盖 ATP/WTA 巡回赛的
赛程、实时比分与赛果，且对数据中心 IP（如 GitHub Actions）友好：

    https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard?dates=YYYYMMDD
    https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard?dates=YYYYMMDD

网球的返回结构中 events[] 是"赛事（tournament）"，每个赛事内含
groupings[]（按单打/双打分组），分组内 competitions[] 才是一场场比赛。
部分历史结构没有 groupings 而是直接 events[].competitions[]，两者都兼容。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from ..models import Match, MatchStatus, Player, SetScore, Tour, Tournament
from ..timeutil import BEIJING
from .base import SourceError, TennisSource, make_session

logger = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{league}/scoreboard"
HEADSHOT_URL = "https://a.espncdn.com/i/headshots/tennis/players/full/{athlete_id}.png"


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # ESPN 格式如 "2026-07-15T11:00Z"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _status_of(comp: dict[str, Any]) -> tuple[MatchStatus, str | None, str | None]:
    """返回 (状态, 状态详情, 备注)."""
    st = comp.get("status") or {}
    st_type = st.get("type") or {}
    state = st_type.get("state") or ""
    desc = (st_type.get("description") or "").lower()
    detail = st_type.get("detail") or st_type.get("shortDetail") or None

    if state == "pre":
        return MatchStatus.SCHEDULED, detail, None
    if state == "in":
        return MatchStatus.LIVE, detail, None
    # state == "post"
    if "retired" in desc:
        return MatchStatus.RETIRED, detail, "对手退赛"
    if "walkover" in desc:
        return MatchStatus.WALKOVER, detail, "不战而胜"
    if "cancel" in desc:
        return MatchStatus.CANCELLED, detail, None
    if "postpone" in desc:
        return MatchStatus.POSTPONED, detail, None
    return MatchStatus.FINISHED, detail, None


def _players_of(competitor: dict[str, Any]) -> list[Player]:
    """从 competitor 结构提取球员（单打 athlete / 双打 roster 或 team）."""
    players: list[Player] = []

    def mk(athlete: dict[str, Any]) -> Player:
        aid = str(athlete.get("id") or "") or None
        country = None
        flag = athlete.get("flag") or {}
        if isinstance(flag, dict):
            # 优先从旗帜图 URL 提取三字码（.../countries/500/ita.png → ITA），
            # 取不到再用 alt（国家英文全名）
            href = flag.get("href") or ""
            m = re.search(r"/countries/\d+/([a-zA-Z]{2,3})\.png", href)
            if m:
                country = m.group(1).upper()
            else:
                country = flag.get("alt") or None
        headshot = HEADSHOT_URL.format(athlete_id=aid) if aid else None
        return Player(
            name=athlete.get("displayName") or athlete.get("shortName") or "?",
            country=country,
            player_id=aid,
            headshot_url=headshot,
        )

    roster = competitor.get("roster")
    if isinstance(roster, list) and roster:
        for entry in roster:
            ath = entry.get("athlete") if isinstance(entry, dict) else None
            if ath:
                players.append(mk(ath))
    if not players:
        ath = competitor.get("athlete")
        if isinstance(ath, dict):
            players.append(mk(ath))
    if not players:
        team = competitor.get("team")
        if isinstance(team, dict):
            name = team.get("displayName") or team.get("name") or "?"
            # 双打组合名形如 "A. Krajicek / H. Patten"
            for part in str(name).split("/"):
                players.append(Player(name=part.strip()))

    # 种子/排名
    for p in players:
        seed = competitor.get("seed")
        if seed is not None:
            try:
                p.seed = int(seed)
            except (TypeError, ValueError):
                pass
        rank = (competitor.get("curatedRank") or {}).get("current")
        if rank is not None and p.rank is None:
            try:
                r = int(rank)
                if 0 < r < 9999:
                    p.rank = r
            except (TypeError, ValueError):
                pass
    return players


def _sets_of(home: dict[str, Any], away: dict[str, Any]) -> list[SetScore]:
    hs = home.get("linescores") or []
    as_ = away.get("linescores") or []
    sets: list[SetScore] = []
    for i in range(max(len(hs), len(as_))):
        h = hs[i] if i < len(hs) else {}
        a = as_[i] if i < len(as_) else {}

        def games(d: dict[str, Any]) -> int | None:
            v = d.get("value")
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        def tb(d: dict[str, Any]) -> int | None:
            v = d.get("tiebreak")
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        hg, ag = games(h), games(a)
        if hg is None and ag is None:
            continue
        sets.append(
            SetScore(
                home=hg if hg is not None else 0,
                away=ag if ag is not None else 0,
                home_tiebreak=tb(h),
                away_tiebreak=tb(a),
            )
        )
    return sets


class EspnSource(TennisSource):
    name = "espn"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = make_session()

    def _fetch_scoreboard(self, league: str, d8: str) -> dict[str, Any]:
        url = SCOREBOARD_URL.format(league=league)
        resp = self.session.get(url, params={"dates": d8}, timeout=self.timeout)
        if resp.status_code != 200:
            raise SourceError(f"ESPN {league} scoreboard HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as e:
            raise SourceError(f"ESPN {league} 返回的不是 JSON: {e}") from e

    def _iter_competitions(
        self, data: dict[str, Any]
    ) -> Iterable[tuple[dict[str, Any], dict[str, Any], str | None]]:
        """产出 (event赛事, competition比赛, 分组名)."""
        for event in data.get("events") or []:
            groupings = event.get("groupings")
            if isinstance(groupings, list) and groupings:
                for g in groupings:
                    gname = (g.get("grouping") or {}).get("displayName")
                    for comp in g.get("competitions") or []:
                        yield event, comp, gname
            else:
                for comp in event.get("competitions") or []:
                    yield event, comp, None

    def _parse_match(
        self,
        tour: Tour,
        event: dict[str, Any],
        comp: dict[str, Any],
        grouping: str | None,
    ) -> Match | None:
        competitors = comp.get("competitors") or []
        if len(competitors) != 2:
            return None
        # order=1 在前
        competitors = sorted(competitors, key=lambda c: c.get("order") or 0)
        c_home, c_away = competitors[0], competitors[1]
        home = _players_of(c_home)
        away = _players_of(c_away)
        if not home or not away:
            return None

        status, detail, note = _status_of(comp)
        winner: int | None = None
        if c_home.get("winner"):
            winner = 0
        elif c_away.get("winner"):
            winner = 1

        round_name = None
        rnd = comp.get("round")
        if isinstance(rnd, dict):
            round_name = rnd.get("displayName") or rnd.get("shortName")
        if not round_name:
            for n in comp.get("notes") or []:
                headline = n.get("headline") if isinstance(n, dict) else None
                if headline:
                    round_name = headline
                    break

        tournament = Tournament(
            name=event.get("name") or event.get("shortName") or "?",
            tour=tour,
            tournament_id=str(event.get("id") or "") or None,
        )

        court = None
        venue = comp.get("venue")
        if isinstance(venue, dict):
            court = venue.get("fullName") or None

        return Match(
            match_id=str(comp.get("id") or "") or f"{tournament.name}-{home[0].name}-{away[0].name}",
            tour=tour,
            tournament=tournament,
            home=home,
            away=away,
            status=status,
            round_name=round_name,
            discipline=grouping,
            start_utc=_parse_iso(comp.get("date") or event.get("date")),
            sets=_sets_of(c_home, c_away),
            winner=winner,
            note=note,
            court=court,
            status_detail=detail,
        )

    def fetch_day(self, d: date) -> list[Match]:
        """抓取北京时间 d 当天的比赛.

        北京的一天横跨两个 UTC 日期，而 ESPN 的 dates 参数按美东日期组织，
        因此拉取 d-1、d、d+1 三天并按比赛开始时间的北京日期过滤去重。
        """
        matches: dict[str, Match] = {}
        errors: list[str] = []
        for tour, league in ((Tour.ATP, "atp"), (Tour.WTA, "wta")):
            got_any = False
            for delta in (-1, 0, 1):
                day = d + timedelta(days=delta)
                d8 = day.strftime("%Y%m%d")
                try:
                    data = self._fetch_scoreboard(league, d8)
                    got_any = True
                except SourceError as e:
                    errors.append(str(e))
                    logger.warning("ESPN %s %s 抓取失败: %s", league, d8, e)
                    continue
                for event, comp, grouping in self._iter_competitions(data):
                    m = self._parse_match(tour, event, comp, grouping)
                    if m is None:
                        continue
                    if m.start_utc is not None:
                        beijing_day = m.start_utc.astimezone(BEIJING).date()
                        if beijing_day != d:
                            continue
                    elif delta != 0:
                        continue
                    key = f"{tour.value}:{m.match_id}"
                    matches[key] = m
            if not got_any:
                raise SourceError(
                    f"ESPN {league} 三天全部抓取失败: {'; '.join(errors[-3:])}"
                )
        return sorted(
            matches.values(),
            key=lambda m: (
                m.start_utc or datetime.max.replace(tzinfo=timezone.utc),
                m.tournament.name,
            ),
        )
