"""WTA 官方前端接口数据源（第三备用，只覆盖 WTA，不覆盖 ATP）.

2026-08-07：ESPN 与 SofaScore 两个源同时对 GitHub Actions 机房 IP 返回
403（`source-health` 连续多次全红），才补上这一条。ATP 那半边没有接——
`atptour.com` 全站 403、`api.protennislive.com` 要 token（实测 401）、
Hawkeye 在 Cloudflare 人机校验后面，`docs/match-momentum-sources.md` 已经
反复验证过没有免费可达的候选。**两个主源同时失效时，ATP 覆盖仍然会丢**，
这个源只能保住 WTA 那一半。

接口不是查文档拼出来的，是用 Chromium 打开 wtatennis.com/scores 抓包
实测出来的（`tools/probe_tnns.py --url https://www.wtatennis.com/scores`，
那个脚本本来是给 TNNS 写的，指哪打哪，这次指向了 WTA 官网）：

    发现这一天在打哪些赛事：
    GET api.wtatennis.com/tennis/tournaments/
        ?page=0&pageSize=100&excludeLevels=ITF&from=<YYYY-MM-DD>&to=<YYYY-MM-DD>
    ⚠️ from/to 必须是 `YYYY-MM-DD` 且要带 `excludeLevels`，两者缺一，这两个
    参数会被服务端整个忽略，回退成从 1960 年开始的全量列表（18738 条，
    实测过），看起来像"查到了"其实什么都没过滤。

    这一站这一天的比赛：
    GET api.wtatennis.com/tennis/tournaments/<id>/<year>/matches
        ?from=<YYYY-MM-DD>&to=<YYYY-MM-DD>

MatchState 实测四种：`F`=已结束、`C`=已登场（进行中）、`U`=未开始（配
`NotBefore`/`NotBeforeText`，和 `official_schedule.py` 里"确切/不早于"
是同一件事）、`W`=不战而胜（Warsaw 女双决赛实测直接给的这个码，不用再从
`ResultString` 里猜关键词）。

⚠️ **`RoundID` 不可靠，别猜数字轮次对应哪一轮。** 只有明确签表（Warsaw
32 签）实测出干净的规律：最后三轮给文字码 `Q`=1/4决赛、`S`=半决赛、
`F`=决赛（这里的 `Q` 不是 Qualifying——资格赛是另一个 `DrawLevelType`，
不会跟主赛的 `M` 混在一起）；96 签的联合赛事（这次的 Montreal/Toronto）
数字轮次和公开轮次名对不上——同一天 `RoundID='3'` 只有 8 场，不是常规
96 签该有的 16 场，说明这套编号不是纯粹的"离决赛还有几轮"，具体规则没有
可靠样本能验证。**所以这里只认三个文字码，纯数字 RoundID 一律留空**，
不去猜"第几轮"——空比错的轮次名安全，这个源本来就是末级备用。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..models import Match, MatchStatus, Player, SetScore, Tour, Tournament
from ..timeutil import BEIJING
from ..zh.tournaments import tournament_level
from .base import SourceError, TennisSource, make_session

logger = logging.getLogger(__name__)

TOURNAMENTS_URL = "https://api.wtatennis.com/tennis/tournaments/"
MATCHES_URL = "https://api.wtatennis.com/tennis/tournaments/{tid}/{year}/matches"

# 只认实测过的文字码；纯数字 RoundID 见模块 docstring 里的理由，一律留空。
_ROUND_TEXT = {"q": "Quarterfinal", "s": "Semifinal", "f": "Final"}

# WTA 接口自己给的 level 字符串（"WTA 1000" 这类），仅在按赛事名查不到时
# 兜底——两条路径都要落到和 ESPN 源同一套代码，否则跨源合并会被判成不同赛事。
_RAW_LEVEL_MAP = {
    "grand slam": "GS",
    "wta 1000": "W1000",
    "wta 500": "WTA500",
    "wta 250": "WTA250",
    "wta 125": "WTA125",
    "wta finals": "Finals",
}


def _resolve_level(name: str, raw_level: str | None) -> str | None:
    level = tournament_level(name, "WTA")
    if level is not None:
        return level
    return _RAW_LEVEL_MAP.get((raw_level or "").strip().lower())


def _round_name(round_id: Any) -> str | None:
    if round_id is None:
        return None
    return _ROUND_TEXT.get(str(round_id).strip().lower())


def _status_of(m: dict[str, Any]) -> tuple[MatchStatus, str | None, str | None]:
    state = m.get("MatchState")
    if state == "U":
        return MatchStatus.SCHEDULED, m.get("NotBeforeText") or None, None
    if state == "C":
        return MatchStatus.LIVE, None, None
    if state == "W":
        return MatchStatus.WALKOVER, None, "不战而胜"
    if state == "F":
        result = (m.get("ResultString") or "").lower()
        # 实测 WTA 的 ResultString 写的是 "Ret'd"（带撇号），不是常见的 "Ret."
        # ——已经在真实数据里核过一遍（"6-0,3-0 Ret'd" 这类），不是猜的
        if "ret'd" in result or "retired" in result:
            return MatchStatus.RETIRED, None, "对手退赛"
        if "w/o" in result or "walkover" in result:
            return MatchStatus.WALKOVER, None, "不战而胜"
        return MatchStatus.FINISHED, None, None
    if state == "X":
        return MatchStatus.CANCELLED, None, None
    if state == "P":
        return MatchStatus.POSTPONED, None, None
    logger.warning("WTA 未知 MatchState %r，按未开始处理", state)
    return MatchStatus.SCHEDULED, None, None


def _winner_of(m: dict[str, Any]) -> int | None:
    """从 `ResultString` 的文字判断谁赢了，不信 `Winner` 那个数字码。

    `Winner` 字段实测不是干净的 1/2：拿真实数据里"` d `前面是谁"反查过，
    正常结束是 2=A胜/3=B胜，退赛胜是 4=A胜（对手退），不战而胜见过 7=B胜
    （对手不战而胜）——5/6 没有样本，说明这套编码还有没见过的取值。
    与其继续往下猜，不如直接读 `ResultString` 自己说的"谁在 ` d ` 前面"，
    跟哪个名字对上算谁赢；两边都没对上或者 `ResultString` 是空的（`W`
    这个 MatchState 就是空的，见模块 docstring）就留 `None`——不确定的
    赢家比猜错的赢家安全得多。
    """
    result = m.get("ResultString") or ""
    if " d " not in result:
        return None
    winner_text = result.split(" d ", 1)[0]
    last_a = m.get("PlayerNameLastA") or ""
    last_b = m.get("PlayerNameLastB") or ""
    a_hit = bool(last_a) and last_a in winner_text
    b_hit = bool(last_b) and last_b in winner_text
    if a_hit and not b_hit:
        return 0
    if b_hit and not a_hit:
        return 1
    return None


def _int_or_none(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _players_of(m: dict[str, Any], side: str) -> list[Player]:
    """side='A' 或 'B'；单打只有 <side>，双打还有 <side>2（搭档）."""
    seed = _int_or_none(m.get(f"Seed{side}"))
    players: list[Player] = []
    for suffix in ("", "2"):
        first = m.get(f"PlayerNameFirst{side}{suffix}")
        last = m.get(f"PlayerNameLast{side}{suffix}")
        if not first and not last:
            continue
        pid = m.get(f"PlayerID{side}{suffix}")
        players.append(
            Player(
                name=f"{first or ''} {last or ''}".strip(),
                country=m.get(f"PlayerCountry{side}{suffix}") or None,
                seed=seed,
                player_id=str(pid) if pid else None,
            )
        )
    return players


def _sets_of(m: dict[str, Any]) -> list[SetScore]:
    """WTA 只给单个 `ScoreTbSet{i}`（输方小分，见 `SetScore.display()` 同一惯例）."""
    sets: list[SetScore] = []
    for i in range(1, 6):
        ga = _int_or_none(m.get(f"ScoreSet{i}A"))
        gb = _int_or_none(m.get(f"ScoreSet{i}B"))
        if ga is None and gb is None:
            continue
        tb = _int_or_none(m.get(f"ScoreTbSet{i}")) if i <= 4 else None
        home_tb = away_tb = None
        if tb is not None:
            if (ga or 0) <= (gb or 0):
                home_tb = tb
            else:
                away_tb = tb
        sets.append(
            SetScore(
                home=ga or 0,
                away=gb or 0,
                home_tiebreak=home_tb,
                away_tiebreak=away_tb,
            )
        )
    return sets


def _start_utc(m: dict[str, Any]) -> datetime | None:
    ts = m.get("MatchTimeStamp")
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class WtaLiveSource(TennisSource):
    """WTA 官网前端同款接口：只发现 WTA 赛事，ATP 不在这条线上."""

    name = "wta-live"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = make_session()

    def _active_tournaments(self, d8: str, d8b: str) -> list[dict[str, Any]]:
        resp = self.session.get(
            TOURNAMENTS_URL,
            params={
                "page": 0,
                "pageSize": 100,
                "excludeLevels": "ITF",
                "from": d8,
                "to": d8b,
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise SourceError(f"WTA tournaments HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            raise SourceError(f"WTA tournaments 返回的不是 JSON: {e}") from e
        return data.get("content") or []

    def _matches_of(self, tid: int, year: int, d8: str, d8b: str) -> list[dict[str, Any]]:
        url = MATCHES_URL.format(tid=tid, year=year)
        resp = self.session.get(url, params={"from": d8, "to": d8b}, timeout=self.timeout)
        if resp.status_code != 200:
            raise SourceError(f"WTA matches({tid}) HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            raise SourceError(f"WTA matches({tid}) 返回的不是 JSON: {e}") from e
        return data.get("matches") or []

    def _parse_match(self, tour_name: str, level: str | None, m: dict[str, Any]) -> Match | None:
        home = _players_of(m, "A")
        away = _players_of(m, "B")
        if not home or not away:
            return None
        status, detail, note = _status_of(m)
        winner = _winner_of(m)
        is_doubles = m.get("DrawMatchType") == "D"
        tournament = Tournament(
            name=tour_name,
            tour=Tour.WTA,
            level=level,
        )
        event_id = str(m.get("EventID") or "")
        year = str(m.get("EventYear") or "")
        match_id = f"{event_id}-{year}:{m.get('MatchID')}"
        return Match(
            match_id=match_id,
            tour=Tour.WTA,
            tournament=tournament,
            home=home,
            away=away,
            status=status,
            round_name=_round_name(m.get("RoundID")),
            discipline="Women's Doubles" if is_doubles else "Women's Singles",
            start_utc=_start_utc(m),
            sets=_sets_of(m),
            winner=winner,
            note=note,
            court=m.get("CourtName") or None,
            status_detail=detail,
        )

    def fetch_day(self, d: date) -> list[Match]:
        """抓取北京时间 d 当天的 WTA 比赛（ATP 这条线上没有）.

        和 espn.py 同一个理由：北京的一天横跨 UTC 的 d-1 与 d，所以查询窗口
        按 (d-1, d) 取，再按比赛开始时间的北京日期精确过滤。
        """
        d8, d8b = (d - timedelta(days=1)).isoformat(), d.isoformat()
        try:
            tournaments = self._active_tournaments(d8, d8b)
        except SourceError as e:
            raise SourceError(f"WTA 赛事发现失败: {e}") from e

        # 没有赛事在打是真实情况（休赛期），不是失败——空结果先自证是真空：
        # 赛事发现那一步已经成功返回了（否则前面已经抛错），tournaments 为空
        # 说明这一天确实没有 WTA 赛事，不是接口挂了。单个赛事的比赛拉取失败
        # 只记警告不中断整体——ESPN/SofaScore 同时倒时，部分 WTA 数据也比
        # 完全没有数据强。
        matches: dict[str, Match] = {}
        for t in tournaments:
            group = t.get("tournamentGroup") or {}
            tid = group.get("id")
            year = t.get("year")
            if tid is None or year is None:
                continue
            name = group.get("name") or t.get("title") or "?"
            level = _resolve_level(name, group.get("level"))
            try:
                raw_matches = self._matches_of(tid, year, d8, d8b)
            except SourceError as e:
                logger.warning("WTA 赛事 %s(%s) 抓取失败: %s", name, tid, e)
                continue
            for raw in raw_matches:
                match = self._parse_match(name, level, raw)
                if match is None:
                    continue
                if (
                    match.start_utc is not None
                    and match.start_utc.astimezone(BEIJING).date() != d
                ):
                    continue
                matches.setdefault(match.match_id, match)

        return sorted(
            matches.values(),
            key=lambda m: (
                m.start_utc or datetime.max.replace(tzinfo=timezone.utc),
                m.tournament.name,
            ),
        )
