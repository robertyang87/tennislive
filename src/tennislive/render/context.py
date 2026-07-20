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
    media_headline: str = ""
    media_consensus: str = ""
    media_divergence: str = ""
    media_data_point: str = ""
    media_takeaway: str = ""
    media_sources: tuple[tuple[str, str], ...] = ()


def _profile_context(match, profile: dict) -> HistoricalContext:
    winner = (match.winner_players() or [None])[0]
    name = player_zh(winner.name) if winner is not None else "这位球员"
    peak = int(profile["peak_rank"])
    legacy = str(profile["legacy"])
    summary = (
        f"{name}曾高居世界第{peak}，也曾{legacy}。"
        "把今天放回整段生涯里看，比分只是故事的新一页。"
    )
    facts = [(f"世界第{peak}", "生涯最高"), (legacy, "大赛履历")]
    if winner is not None and winner.rank is not None:
        facts.append((f"第{winner.rank}位", "当日排名快照"))
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
    from ..research.media import brief_for_match

    profile = cover_fact_bundle(match).get("historical_profile")
    context = _profile_context(match, profile) if profile else _story_context(match)
    memory = recent_context(match, today) if today is not None else None
    media = brief_for_match(match, today) if today is not None else None
    if context is None and memory is None and media is None:
        return None
    if context is None:
        context = HistoricalContext(
            summary=memory.summary if memory is not None else media.takeaway,
            facts=(),
            source_label=(memory.source_label if memory is not None else media.source_label),
            source_url=("" if memory is not None else media.primary_url),
        )
    continuity = memory.summary if memory is not None else context.continuity
    if media is None:
        if not continuity:
            return context
        return HistoricalContext(
            summary=context.summary,
            facts=context.facts,
            source_label=context.source_label,
            source_url=context.source_url,
            continuity=continuity,
        )
    return HistoricalContext(
        summary=context.summary,
        facts=context.facts,
        source_label=context.source_label,
        source_url=context.source_url,
        continuity=continuity,
        media_headline=media.headline,
        media_consensus=media.consensus,
        media_divergence=media.divergence,
        media_data_point=media.data_point,
        media_takeaway=media.takeaway,
        media_sources=tuple((source.name, source.url) for source in media.sources),
    )
