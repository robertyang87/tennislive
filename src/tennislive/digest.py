"""每日摘要：昨日赛果 + 今日赛程（全部按北京时间归属）."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from .models import Match
from .sources import SourceError, fetch_day

logger = logging.getLogger(__name__)


@dataclass
class Digest:
    """一期内容的数据：以北京时间 today 为基准."""

    today: date
    results: list[Match] = field(default_factory=list)   # 最新赛果（昨日完赛 + 今晨完赛）
    live: list[Match] = field(default_factory=list)      # 进行中
    schedule: list[Match] = field(default_factory=list)  # 今日未开赛
    source: str = ""

    @property
    def yesterday(self) -> date:
        return self.today - timedelta(days=1)

    @property
    def is_empty(self) -> bool:
        return not (self.results or self.live or self.schedule)


def _is_qualifying(m: Match) -> bool:
    return bool(m.round_name and "qualif" in m.round_name.lower())


def build_digest(
    today: date, prefer: str | None = None, include_qualifying: bool = False
) -> Digest:
    """抓取并组装一期内容.

    - 昨日（北京时间）已完赛 → 赛果
    - 今日（北京时间）已完赛（凌晨结束的欧美比赛）→ 也并入赛果
    - 今日进行中 → live
    - 今日未开赛 → 赛程
    - 资格赛默认不收录（篇幅原因）
    """
    yesterday_data = fetch_day(today - timedelta(days=1), prefer=prefer)
    today_data = fetch_day(today, prefer=prefer)

    if not include_qualifying:
        yesterday_data.matches = [
            m for m in yesterday_data.matches if not _is_qualifying(m)
        ]
        today_data.matches = [m for m in today_data.matches if not _is_qualifying(m)]

    results = yesterday_data.finished() + today_data.finished()
    seen: set[str] = set()
    deduped: list[Match] = []
    for m in results:
        key = f"{m.tour.value}:{m.match_id}"
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    return Digest(
        today=today,
        results=deduped,
        live=today_data.live(),
        schedule=today_data.upcoming(),
        source=today_data.source or yesterday_data.source or "",
    )
