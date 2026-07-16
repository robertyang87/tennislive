"""数据源注册与回退链."""

from __future__ import annotations

import logging
from datetime import date

from ..models import DailyData, Match
from ..timeutil import now_utc
from .base import SourceError, TennisSource
from .espn import EspnSource
from .sofascore import SofaScoreSource

logger = logging.getLogger(__name__)

__all__ = [
    "EspnSource",
    "SofaScoreSource",
    "SourceError",
    "TennisSource",
    "fetch_day",
    "make_source_chain",
]


def make_source_chain(prefer: str | None = None) -> list[TennisSource]:
    """按优先级返回数据源列表；prefer 可指定 'espn' 或 'sofascore' 优先."""
    chain: list[TennisSource] = [EspnSource(), SofaScoreSource()]
    if prefer:
        chain.sort(key=lambda s: 0 if s.name == prefer else 1)
    return chain


def fetch_day(d: date, prefer: str | None = None) -> DailyData:
    """依次尝试各数据源抓取北京时间 d 当天的比赛，全部失败时抛出 SourceError."""
    errors: list[str] = []
    for source in make_source_chain(prefer):
        try:
            matches: list[Match] = source.fetch_day(d)
            logger.info("数据源 %s 返回 %d 场比赛", source.name, len(matches))
            return DailyData(
                date_beijing=d.isoformat(),
                matches=matches,
                source=source.name,
                fetched_at_utc=now_utc(),
            )
        except SourceError as e:
            errors.append(f"{source.name}: {e}")
            logger.warning("数据源 %s 失败，尝试下一个: %s", source.name, e)
    raise SourceError("所有数据源均失败 — " + " | ".join(errors))
