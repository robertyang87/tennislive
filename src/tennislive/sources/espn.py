"""ESPN 公开数据接口数据源（聚合备用）.

ESPN 提供无需鉴权的公开 JSON 接口（其官网前端同款），覆盖 ATP/WTA 巡回赛的
赛程、实时比分与赛果，且对数据中心 IP（如 GitHub Actions）友好（已实测）：

    https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard?dates=YYYYMMDD
    https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard?dates=YYYYMMDD

实测结构要点（2026-07）：
- events[] 是赛事（tournament），内含 groupings[]（男单/女单/男双/女双），
  分组内 competitions[] 才是一场场比赛；
- 一个赛事包含整个赛程周期的所有比赛（不只请求日期当天），必须按比赛
  start 时间的北京日期过滤；
- 合办赛事（如 Nordea Open）会同时出现在 atp 与 wta 两个接口里，且分组里
  同时有男子与女子项目 —— tour 必须从分组名推导，去重用 event+competition id；
- 双打 competitor.type == "team"，球员在 roster.athletes[]（dict 而非 list）；
- 比赛的 status.type: state=pre/in/post, description=Final/Walkover/Retired/Scheduled;
- round.displayName 如 "Round 1" / "Quarterfinal" / "Qualifying 1st Round"。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from ..models import Match, MatchStatus, Player, SetScore, Tour, Tournament
from ..timeutil import BEIJING
from ..zh.tournaments import tournament_level
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


def _country_of(athlete: dict[str, Any]) -> str | None:
    flag = athlete.get("flag") or {}
    if not isinstance(flag, dict):
        return None
    # 优先从旗帜图 URL 提取三字码（.../countries/500/ita.png → ITA），
    # 取不到再用 alt（国家英文全名）
    href = flag.get("href") or ""
    m = re.search(r"/countries/\d+/([a-zA-Z]{2,3})\.png", href)
    if m:
        return m.group(1).upper()
    return flag.get("alt") or None


def _athlete_id(athlete: dict[str, Any], fallback: str | None = None) -> str | None:
    """athlete 对象本身无 id：从 playercard 链接提取（/player/_/id/3042/...）."""
    aid = str(athlete.get("id") or "") or None
    if aid:
        return aid
    for link in athlete.get("links") or []:
        href = link.get("href") if isinstance(link, dict) else ""
        m = re.search(r"/id/(\d+)", href or "")
        if m:
            return m.group(1)
    return fallback


def _mk_player(athlete: dict[str, Any], aid: str | None = None) -> Player:
    aid = _athlete_id(athlete, fallback=aid)
    return Player(
        name=athlete.get("displayName") or athlete.get("shortName") or "?",
        country=_country_of(athlete),
        player_id=aid,
        headshot_url=HEADSHOT_URL.format(athlete_id=aid) if aid else None,
    )


def _players_of(competitor: dict[str, Any]) -> list[Player]:
    """从 competitor 提取球员：单打 athlete；双打 roster.athletes."""
    players: list[Player] = []
    comp_id = str(competitor.get("id") or "")  # 单打=athlete id；双打="id1-id2"

    roster = competitor.get("roster")
    if isinstance(roster, dict):
        team_ids = comp_id.split("-") if "-" in comp_id else []
        for i, ath in enumerate(roster.get("athletes") or []):
            if isinstance(ath, dict):
                fallback = team_ids[i] if i < len(team_ids) else None
                players.append(_mk_player(ath, aid=fallback))
    elif isinstance(roster, list):  # 兼容旧结构
        for entry in roster:
            ath = entry.get("athlete") if isinstance(entry, dict) else None
            if ath:
                players.append(_mk_player(ath))

    if not players:
        ath = competitor.get("athlete")
        if isinstance(ath, dict):
            players.append(_mk_player(ath, aid=comp_id or None))

    if not players:
        # 兜底：team.displayName 形如 "A. Krajicek / H. Patten"
        team = competitor.get("team")
        name = None
        if isinstance(team, dict):
            name = team.get("displayName") or team.get("name")
        if not name and isinstance(roster, dict):
            name = roster.get("displayName")
        if name:
            for part in str(name).split("/"):
                players.append(Player(name=part.strip()))

    # 种子号：seed 字段，或 curatedRank（实测为赛事种子而非世界排名，
    # 如 250 赛头号种子 curatedRank=1）。世界排名统一由 rankings 接口补全。
    for p in players:
        seed = competitor.get("seed")
        if seed is None:
            seed = (competitor.get("curatedRank") or {}).get("current")
        if seed is not None:
            try:
                s = int(seed)
                if 0 < s <= 40:  # 种子号最多 33（大满贯），再大视为脏数据
                    p.seed = s
            except (TypeError, ValueError):
                pass
    return players


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _sets_of(home: dict[str, Any], away: dict[str, Any]) -> list[SetScore]:
    hs = home.get("linescores") or []
    as_ = away.get("linescores") or []
    sets: list[SetScore] = []
    for i in range(max(len(hs), len(as_))):
        h = hs[i] if i < len(hs) else {}
        a = as_[i] if i < len(as_) else {}
        hg = _int_or_none(h.get("value"))
        ag = _int_or_none(a.get("value"))
        if hg is None and ag is None:
            continue
        sets.append(
            SetScore(
                home=hg if hg is not None else 0,
                away=ag if ag is not None else 0,
                home_tiebreak=_int_or_none(h.get("tiebreak")),
                away_tiebreak=_int_or_none(a.get("tiebreak")),
            )
        )
    return sets


def _tour_of(discipline: str | None, league_tour: Tour) -> Tour:
    """从项目名推导巡回赛：合办赛事在两个接口里都有男女项目.

    注意 "women's" 字符串里包含 "men's"，必须先判女子。
    """
    d = (discipline or "").lower()
    if "mixed" in d:
        return league_tour
    if d.startswith("wom") or "women" in d:
        return Tour.WTA
    if d.startswith("men") or "men's" in d:
        return Tour.ATP
    return league_tour


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
        league_tour: Tour,
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
        # 过滤对阵未定的占位比赛（后续轮次的 "TBD vs TBD"）
        placeholder = {"tbd", "?", ""}
        if any(p.name.strip().lower() in placeholder for p in home + away):
            return None

        # 项目名：competition.type.text 优先，其次分组名
        discipline = grouping
        ctype = comp.get("type")
        if isinstance(ctype, dict) and ctype.get("text"):
            discipline = ctype["text"]
        tour = _tour_of(discipline, league_tour)

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

        tournament = Tournament(
            name=event.get("name") or event.get("shortName") or "?",
            tour=tour,
            level=tournament_level(
                event.get("name") or event.get("shortName"), tour.value
            ),
            tournament_id=str(event.get("id") or "") or None,
        )

        court = None
        venue = comp.get("venue")
        if isinstance(venue, dict):
            court = venue.get("court") or None

        start_utc = None
        if comp.get("timeValid", True):
            start_utc = _parse_iso(comp.get("date"))

        event_id = str(event.get("id") or "")
        comp_id = str(comp.get("id") or "")
        # 不能用 uid 做去重键：合办赛事在 atp/wta 两个接口里 uid 的联赛段不同
        # （l:851 vs l:900），会导致同一场比赛重复
        return Match(
            match_id=f"{event_id}:{comp_id}",
            tour=tour,
            tournament=tournament,
            home=home,
            away=away,
            status=status,
            round_name=round_name,
            discipline=discipline,
            start_utc=start_utc,
            sets=_sets_of(c_home, c_away),
            winner=winner,
            note=note,
            court=court,
            status_detail=detail,
        )

    def fetch_day(self, d: date) -> list[Match]:
        """抓取北京时间 d 当天的比赛.

        北京的一天横跨 UTC 的 d-1 与 d，且 ESPN 返回赛事全周期比赛，
        因此拉取 d-1、d 两天并按比赛开始时间的北京日期过滤、按比赛 id 去重。
        """
        matches: dict[str, Match] = {}
        errors: list[str] = []
        fetched_any = False
        for league, league_tour in (("atp", Tour.ATP), ("wta", Tour.WTA)):
            for day in (d - timedelta(days=1), d):
                d8 = day.strftime("%Y%m%d")
                try:
                    data = self._fetch_scoreboard(league, d8)
                    fetched_any = True
                except SourceError as e:
                    errors.append(str(e))
                    logger.warning("ESPN %s %s 抓取失败: %s", league, d8, e)
                    continue
                for event, comp, grouping in self._iter_competitions(data):
                    m = self._parse_match(league_tour, event, comp, grouping)
                    if m is None:
                        continue
                    if m.start_utc is not None:
                        if m.start_utc.astimezone(BEIJING).date() != d:
                            continue
                    elif day != d:
                        # 无有效时间的比赛只在目标日期的请求中收录一次
                        continue
                    matches.setdefault(m.match_id, m)
        if not fetched_any:
            raise SourceError(f"ESPN 全部抓取失败: {'; '.join(errors[:4])}")
        return sorted(
            matches.values(),
            key=lambda m: (
                m.start_utc or datetime.max.replace(tzinfo=timezone.utc),
                m.tournament.name,
            ),
        )
