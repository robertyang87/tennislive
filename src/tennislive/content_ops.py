"""GitHub Actions 内容编排：自动选题、频控与去重。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import Match, MatchStatus
from .render.hotspot import hotspot_candidates, hotspot_score
from .timeutil import BEIJING
from .zh.terms import round_zh

PREVIEW_THRESHOLD = 38
# **即时赛果推送停了（2026-07-31）。** 账号所有者：「即时赛果推送也不要了」。
#
# 这两个名额本来一天各一条：`result` 是刚完赛的高价值比赛（即时赛果），
# `preview` 是赛前焦点。停的只有前者——账号所有者同一句话里说「其他的可以
# 保留」，赛前焦点不是赛果，留着。
#
# **改这个数就够了，不用动工作流**：`select_content` 按名额取，`result_slots`
# 算出来是 0，`hotspot_candidates` 那一轮一条都取不进去，`preview` 照常。
# 内容雷达（flash.yml）于是变成「只发赛前焦点」。
#
# 要恢复改回 1，**并且改掉 test_即时赛果推送已经停掉**——让它是一次看得见
# 的决定，别哪天悄悄回来。
RESULT_DAILY_LIMIT = 0

# **2026-08-05：赛前焦点的「每天最多 1 条」放开了。** 账号所有者：
# 「不要限制只有一条」。
#
# 那个 1 是**冷启动期的频控**，不是编辑判断——`docs/xiaohongshu-playbook.md`
# 写着「避免低粉阶段高频刷屏」。它挡掉的是「今天已经发过一条了」，而不是
# 「这条不值得发」。真正的编辑闸一直是另外两个，它们没动：
#
#   · `PREVIEW_THRESHOLD = 38`  热度分不够就不进候选
#   · 45–210 分钟的发布窗口     太早太晚都不算
#
# 现在这两个数只是**跑飞的兜底**，不是日常会碰到的上限：取 10 是跟
# `preview_candidates(limit=10)` 对齐——一个天花板写一处，别两处各拍一个数。
#
# ⚠️ **代价是微信条数**：`publish content` 是**一条 item 一条微信**
# （`cmd_publish_flash` 里那个 for 循环），所以一轮取到 N 条就发 N 条。
# 嫌吵就把这两个数调小，或者提高 `PREVIEW_THRESHOLD`——**提门槛是调
# 「值不值得发」，调条数是调「今天够了没有」，两件事别混**。
#
# ⚠️ 这个数**没有从真实产出量倒推过**：沙箱 IP 被 ESPN / SofaScore 双双
# 403（「数据中心 IP 可能被封」），量不到「一天到底有几条过 38 分」。
# 头几趟真实 run 之后看一眼 `queue/` 里实际出了几条，再决定要不要收。
PREVIEW_DAILY_LIMIT = 10
RUN_LIMIT = 10


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
