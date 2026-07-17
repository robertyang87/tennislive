"""Human-readable tour coverage report for each generated digest."""

from __future__ import annotations

from collections import defaultdict

from ..digest import Digest
from .common import LEVEL_BADGE
from ..zh.tournaments import tournament_level, tournament_zh


LEVEL_ORDER = {
    "GS": 0,
    "M1000": 1,
    "W1000": 1,
    "ATP500": 2,
    "WTA500": 2,
    "ATP250": 3,
    "WTA250": 3,
}


def coverage_report(digest: Digest) -> str:
    matches = digest.results + digest.live + digest.schedule
    events: dict[tuple, dict] = defaultdict(
        lambda: {"results": 0, "live": 0, "schedule": 0}
    )
    for bucket, items in (
        ("results", digest.results),
        ("live", digest.live),
        ("schedule", digest.schedule),
    ):
        for match in items:
            level = match.tournament.level or tournament_level(
                match.tournament.name, match.tour.value
            )
            key = (match.tour.value, level or "未识别", match.tournament.name)
            events[key][bucket] += 1

    lines = [
        f"数据源：{digest.source or '未知'}",
        f"总场次：{len(matches)}（赛果 {len(digest.results)} / 直播 {len(digest.live)} / 赛程 {len(digest.schedule)}）",
        "",
        "数据源健康状态：",
        *(
            [f"- {name}｜{status}" for name, status in digest.source_status.items()]
            or ["- 未提供状态明细"]
        ),
        "",
        "ATP/WTA 巡回赛覆盖：",
    ]
    tour_events = [item for item in events.items() if item[0][1] in LEVEL_ORDER]
    for (tour, level, name), counts in sorted(
        tour_events,
        key=lambda item: (
            LEVEL_ORDER.get(item[0][1], 9), item[0][0], item[0][2]
        ),
    ):
        total = sum(counts.values())
        lines.append(
            f"- {tour} {level}｜{LEVEL_BADGE.get(level, level)}｜{tournament_zh(name)}｜{total} 场"
            f"（赛果 {counts['results']} / 直播 {counts['live']} / 赛程 {counts['schedule']}）"
        )
    if not tour_events:
        lines.append("- 当日没有已识别的 250/500/1000/大满贯场次")

    unknown = [item for item in events.items() if item[0][1] == "未识别"]
    if unknown:
        lines.extend(["", "待识别赛事（不影响收录，但需要补级别映射）："])
        for (tour, _, name), counts in sorted(unknown):
            lines.append(f"- {tour}｜{name}｜{sum(counts.values())} 场")
    return "\n".join(lines) + "\n"
