"""GitHub Actions 内容编排：自动选题、频控与去重。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import Match, MatchStatus
from .render.hotspot import hotspot_candidates, hotspot_score
from .timeutil import BEIJING
from .zh.terms import round_zh

PREVIEW_THRESHOLD = 38
RESULT_DAILY_LIMIT = 3
PREVIEW_DAILY_LIMIT = 2
RUN_LIMIT = 2


@dataclass(frozen=True)
class ContentPick:
    """一次内容生产选择。"""

    kind: str  # result / preview
    match: Match
    score: int

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.match.tour.value}:{self.match.match_id}"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_qualifying(match: Match) -> bool:
    raw = (match.round_name or "").lower()
    translated = round_zh(match.round_name) or ""
    return "qualif" in raw or "资格" in translated


def preview_candidates(
    matches: list[Match],
    *,
    now: datetime,
    min_lead_minutes: int = 45,
    max_lead_minutes: int = 210,
    limit: int = 10,
) -> list[Match]:
    """选出进入发布窗口的高价值赛前对阵。"""
    now_utc = _aware_utc(now)
    earliest = now_utc + timedelta(minutes=min_lead_minutes)
    latest = now_utc + timedelta(minutes=max_lead_minutes)
    selected: dict[tuple[str, str], Match] = {}

    for match in matches:
        if (
            match.status != MatchStatus.SCHEDULED
            or match.start_utc is None
            or not match.is_singles
            or _is_qualifying(match)
            or hotspot_score(match) < PREVIEW_THRESHOLD
        ):
            continue
        start = _aware_utc(match.start_utc)
        if not earliest <= start <= latest:
            continue
        key = (match.tour.value, match.match_id)
        current = selected.get(key)
        if current is None or hotspot_score(match) > hotspot_score(current):
            selected[key] = match

    return sorted(
        selected.values(),
        key=lambda match: (-hotspot_score(match), _aware_utc(match.start_utc)),
    )[:limit]


def _count_today(state: dict[str, str], kind: str, today: str) -> int:
    return sum(
        1
        for key, value in state.items()
        if key.startswith(f"{kind}:") and value == today
    )


def select_content(
    matches: list[Match],
    *,
    now: datetime,
    state: dict[str, str] | None = None,
    legacy_result_ids: set[str] | None = None,
) -> list[ContentPick]:
    """结果优先，剩余名额给赛前；同时执行每日频控和历史去重。"""
    state = state or {}
    legacy_result_ids = legacy_result_ids or set()
    today = now.astimezone(BEIJING).date().isoformat()
    result_slots = max(
        0, RESULT_DAILY_LIMIT - _count_today(state, "result", today)
    )
    preview_slots = max(
        0, PREVIEW_DAILY_LIMIT - _count_today(state, "preview", today)
    )

    picks: list[ContentPick] = []
    results = hotspot_candidates(matches, now=now, limit=10)
    for match in results:
        pick = ContentPick("result", match, hotspot_score(match))
        if (
            len([item for item in picks if item.kind == "result"]) >= result_slots
            or pick.key in state
            or match.match_id in legacy_result_ids
        ):
            continue
        picks.append(pick)
        if len(picks) >= RUN_LIMIT:
            return picks

    for match in preview_candidates(matches, now=now):
        pick = ContentPick("preview", match, hotspot_score(match))
        if (
            len([item for item in picks if item.kind == "preview"]) >= preview_slots
            or pick.key in state
        ):
            continue
        picks.append(pick)
        if len(picks) >= RUN_LIMIT:
            break
    return picks


def prune_state(
    state: dict[str, str], *, today, retention_days: int = 14
) -> dict[str, str]:
    """只保留近期发布记录，避免状态文件无限增长。"""
    cutoff = (today - timedelta(days=retention_days)).isoformat()
    return {key: value for key, value in state.items() if value >= cutoff}
