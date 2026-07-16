"""ATP/WTA 世界排名（ESPN 公开接口，已实测）.

    https://site.api.espn.com/apis/site/v2/sports/tennis/{atp|wta}/rankings

返回结构自带 current / previous / trend，无需自己维护历史快照。
用途：比赛数据的排名补全（冷门检测）、周一排名卡、中国球员雷达。
"""

from __future__ import annotations

import logging
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


def fetch_rankings(timeout: int = 30) -> Rankings:
    """抓取 ATP + WTA 单打排名；单边失败不阻塞另一边."""
    session = make_session()
    result = Rankings()
    for league in ("atp", "wta"):
        try:
            resp = session.get(URL.format(league=league), timeout=timeout)
            if resp.status_code != 200:
                raise SourceError(f"HTTP {resp.status_code}")
            entries = _parse(resp.json())
            setattr(result, league, entries)
            logger.info("%s 排名 %d 条", league.upper(), len(entries))
        except Exception as e:
            logger.warning("%s 排名抓取失败: %s", league.upper(), e)
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
