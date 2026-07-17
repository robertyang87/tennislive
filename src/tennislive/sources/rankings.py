"""ATP/WTA 世界排名.

- WTA：官方 API（api.wtatennis.com，已实测）分页取全量 Top500，每周实时；
  失败时回退 ESPN。
- ATP：ESPN 接口（封顶 Top150）+ live-tennis.eu 实时榜补充 150 名开外。

用途：比赛数据的排名补全（冷门检测）、周一排名卡、中国球员雷达。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .base import SourceError, make_session

logger = logging.getLogger(__name__)

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{league}/rankings"


@dataclass
class RankEntry:
    rank: int
    name: str
    previous: int | None = None
    points: float | None = None
    trend: str | None = None       # "+2" / "-1" / "-"
    player_id: str | None = None

    @property
    def move(self) -> int:
        """排名变化：正数为上升."""
        if self.previous is None or self.previous <= 0:
            return 0
        return self.previous - self.rank


@dataclass
class Rankings:
    atp: list[RankEntry] = field(default_factory=list)
    wta: list[RankEntry] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.atp or self.wta)


def _parse(data: dict) -> list[RankEntry]:
    out: list[RankEntry] = []
    for ranking in data.get("rankings") or []:
        for r in ranking.get("ranks") or []:
            ath = r.get("athlete") or {}
            name = ath.get("displayName") or ath.get("shortname")
            cur = r.get("current")
            if not name or not cur:
                continue
            out.append(
                RankEntry(
                    rank=int(cur),
                    name=name,
                    previous=int(r["previous"]) if r.get("previous") else None,
                    points=r.get("points"),
                    trend=r.get("trend"),
                    player_id=str(ath.get("id") or "") or None,
                )
            )
        if out:
            break  # 只取第一个榜单（单打世界排名）
    return out


# WTA 官方 API（实测：pageSize 上限 100，翻页到 500 名）
WTA_URL = (
    "https://api.wtatennis.com/tennis/players/ranked"
    "?page={page}&pageSize=100&type=rankSingles&sort=asc&name=&metric=SINGLES&at="
)
WTA_HEADERS = {
    "account": "wta",
    "Origin": "https://www.wtatennis.com",
    "Referer": "https://www.wtatennis.com/rankings/singles",
}


def _fetch_wta_official(session, timeout: int, pages: int = 5) -> list[RankEntry]:
    """WTA 官方全量排名（Top 500，实时每周更新）."""
    out: list[RankEntry] = []
    for page in range(pages):
        resp = session.get(
            WTA_URL.format(page=page), headers=WTA_HEADERS, timeout=timeout
        )
        if resp.status_code != 200:
            raise SourceError(f"HTTP {resp.status_code}")
        data = resp.json()
        rows = data if isinstance(data, list) else data.get("content") or []
        if not rows:
            break
        for r in rows:
            pl = r.get("player") or {}
            name = (
                pl.get("fullName")
                or f"{pl.get('firstName', '')} {pl.get('lastName', '')}".strip()
            )
            rank = int(r.get("ranking") or 0)
            if not name or not rank:
                continue
            move = int(r.get("movement") or 0)  # 正数=上升
            out.append(
                RankEntry(
                    rank=rank,
                    name=name,
                    previous=rank + move if move else rank,
                    points=r.get("points"),
                    trend=(f"+{move}" if move > 0 else str(move) if move < 0 else "-"),
                    player_id=str(pl.get("id") or "") or None,
                )
            )
    if not out:
        raise SourceError("WTA 官方接口返回空")
    return out


# live-tennis.eu 实时榜（全量 ~2000 名，比官方周更还新；用于补充 ESPN Top150 之外）
LIVE_TENNIS_ATP = "https://live-tennis.eu/en/atp-live-ranking"
_LT_ROW = re.compile(r'<tr class="[A-Z]{3}[^"]*">(.*?)</tr>', re.S)
_LT_RANK = re.compile(r"<td class=rk>(\d+)</td>")
_LT_NAME = re.compile(r"<td class=pn>([^<]+)</td>")


def _fetch_live_tennis_atp(
    session, timeout: int, max_rank: int = 600
) -> list[RankEntry]:
    resp = session.get(
        LIVE_TENNIS_ATP,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    out: list[RankEntry] = []
    for row in _LT_ROW.finditer(resp.text):
        body = row.group(1)
        mr, mn = _LT_RANK.search(body), _LT_NAME.search(body)
        if not mr or not mn:
            continue
        rank = int(mr.group(1))
        if rank > max_rank:
            break
        name = mn.group(1).strip()
        if name:
            out.append(RankEntry(rank=rank, name=name))
    if len(out) < 100:
        raise SourceError(f"解析行数异常: {len(out)}")
    return out


def _fetch_espn(session, league: str, timeout: int) -> list[RankEntry]:
    resp = session.get(URL.format(league=league), timeout=timeout)
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    return _parse(resp.json())


def fetch_rankings(timeout: int = 30) -> Rankings:
    """抓取 ATP + WTA 单打排名；单边失败不阻塞另一边.

    WTA 优先官方全量接口（Top500 实时），失败回退 ESPN（Top150）；
    ATP 用 ESPN（Top150），再尝试 live-tennis.eu 补充 150 名开外。
    """
    session = make_session()
    result = Rankings()

    try:
        result.wta = _fetch_wta_official(session, timeout)
        logger.info("WTA 官方排名 %d 条", len(result.wta))
    except Exception as e:  # noqa: BLE001
        logger.warning("WTA 官方排名失败，回退 ESPN: %s", e)
        try:
            result.wta = _fetch_espn(session, "wta", timeout)
            logger.info("WTA ESPN 排名 %d 条", len(result.wta))
        except Exception as e2:  # noqa: BLE001
            logger.warning("WTA 排名抓取失败: %s", e2)

    try:
        result.atp = _fetch_espn(session, "atp", timeout)
        logger.info("ATP ESPN 排名 %d 条", len(result.atp))
    except Exception as e:  # noqa: BLE001
        logger.warning("ATP 排名抓取失败: %s", e)
    try:
        extra = _fetch_live_tennis_atp(session, timeout)
        have = {e.rank for e in result.atp}
        added = [e for e in extra if e.rank not in have]
        if added:
            result.atp = sorted(result.atp + added, key=lambda e: e.rank)
            logger.info("live-tennis.eu 补充 ATP %d 条（>150 名）", len(added))
    except Exception as e:  # noqa: BLE001
        logger.info("live-tennis.eu 补充不可用（不影响）: %s", e)
    return result


def rank_map(entries: list[RankEntry] | Rankings) -> dict[str, int]:
    """姓名（含词序反转）→ 排名 的查找表，用于补全比赛数据.

    传入单巡回赛的榜单（rankings.atp 或 rankings.wta）可避免
    ATP/WTA 同名球员的跨巡回赛误匹配。
    """
    if isinstance(entries, Rankings):
        entries = entries.atp + entries.wta
    m: dict[str, int] = {}
    for entry in entries:
        key = " ".join(entry.name.strip().lower().split())
        m.setdefault(key, entry.rank)
        words = key.split(" ")
        if 2 <= len(words) <= 3:
            m.setdefault(" ".join(reversed(words)), entry.rank)
    return m
