"""Source-backed human context for the daily lead story."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..zh import player_zh
from .editorial_memory import recent_context
from .titles import cover_fact_bundle
from .tournament_story import STORIES, story_matches_match


@dataclass(frozen=True)
class HistoricalContext:
    summary: str
    facts: tuple[tuple[str, str], ...]
    source_label: str
    source_url: str = ""
    continuity: str = ""


def _profile_context(match, profile: dict) -> HistoricalContext:
    winner = (match.winner_players() or [None])[0]
    name = player_zh(winner.name) if winner is not None else "这位球员"
    peak = int(profile["peak_rank"])
    legacy = str(profile["legacy"])
    current = winner.rank if winner is not None else None
    if current is not None and current >= peak + 20:
        summary = (
            f"从世界第{peak}到如今第{current}，{name}走过的是一段漫长下坡。"
            f"{legacy}仍在那里，这座奖杯提醒人们：低谷没有抹掉曾经的高度。"
        )
    else:
        summary = (
            f"{name}曾高居世界第{peak}，也曾{legacy}。"
            "把今天放回整段生涯里看，比分只是故事的新一页。"
        )
    facts = [(f"世界第{peak}", "生涯最高"), (legacy, "大赛履历")]
    if current is not None:
        facts.append((f"世界第{current}", "当前排名"))
    return HistoricalContext(
        summary=summary,
        facts=tuple(facts[:3]),
        source_label="ATP Tour 球员档案",
        source_url=str(profile.get("source_url") or ""),
    )


def _story_context(match) -> HistoricalContext | None:
    stories = [story for story in STORIES if story_matches_match(story, match)]
    if not stories:
        return None
    stories.sort(key=lambda story: 0 if story.kind == "player" else 1)
    story = stories[0]
    if story.kind == "player":
        facts = (
            (story.surface, "生涯坐标"),
            (story.founded, "人物档案"),
            (story.level, "巡回赛"),
        )
    else:
        facts = (
            (story.level, "赛事级别"),
            (story.surface, "比赛场地"),
            (story.founded, "赛事历史"),
        )
    return HistoricalContext(
        summary=story.hero_fact,
        facts=facts,
        source_label=story.source_label,
        source_url=story.source_url,
    )


def historical_context(match, today: date | None = None) -> HistoricalContext | None:
    profile = cover_fact_bundle(match).get("historical_profile")
    context = _profile_context(match, profile) if profile else _story_context(match)
    memory = recent_context(match, today) if today is not None else None
    if context is None and memory is None:
        return None
    if context is None:
        return HistoricalContext(
            summary=memory.summary,
            facts=(),
            source_label=memory.source_label,
        )
    if memory is None:
        return context
    return HistoricalContext(
        summary=context.summary,
        facts=context.facts,
        source_label=context.source_label,
        source_url=context.source_url,
        continuity=memory.summary,
    )
