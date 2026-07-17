"""ATP/WTA world rankings from the configured score-data fallback.

Rankings are enrichment only. GitHub Actions deliberately avoids scraping ATP,
WTA, and third-party ranking pages; a partial ranking list must never block the
daily content package.
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


def _fetch_espn(session, league: str, timeout: int) -> list[RankEntry]:
    resp = session.get(URL.format(league=league), timeout=timeout)
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    return _parse(resp.json())


def fetch_rankings(timeout: int = 30) -> Rankings:
    """Fetch ATP and WTA singles rankings; one failed tour does not block the other."""
    session = make_session()
    result = Rankings()

    for league in ("atp", "wta"):
        try:
            entries = _fetch_espn(session, league, timeout)
            setattr(result, league, entries)
            logger.info("%s ESPN 排名 %d 条", league.upper(), len(entries))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s 排名抓取失败: %s", league.upper(), exc)
    return result


def norm_name(name: str) -> str:
    """匹配键：小写 + 去重音 + 归一空白."""
    import unicodedata

    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(folded.strip().lower().split())


def rank_map(entries: list[RankEntry] | Rankings) -> dict[str, int]:
    """姓名（含词序反转）→ 排名 的查找表，用于补全比赛数据.

    传入单巡回赛的榜单（rankings.atp 或 rankings.wta）可避免
    ATP/WTA 同名球员的跨巡回赛误匹配。
    """
    if isinstance(entries, Rankings):
        entries = entries.atp + entries.wta
    m: dict[str, int] = {}
    for entry in entries:
        key = norm_name(entry.name)
        m.setdefault(key, entry.rank)
        words = key.split(" ")
        if 2 <= len(words) <= 3:
            m.setdefault(" ".join(reversed(words)), entry.rank)
    return m
