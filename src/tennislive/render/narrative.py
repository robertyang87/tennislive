"""Evidence-led human angles for previews and opinion copy."""

from __future__ import annotations

from datetime import date

from ..models import Match
from ..research.media import brief_for_match
from ..zh import player_zh
from .common import match_round_display
from .context import historical_context
from .story import is_chinese_player, schedule_insight
from .tournament_story import direct_story_for_match


_PLAYER_PREVIEWS = {
    "yuan-yue": "2024年奥斯汀首夺WTA冠军并跻身前50，今晚看她能否重新接上那段上升势头",
    "gao-xinyu": "她曾在联合杯爆冷世界第17的玛雅；回到巡回赛，韧性能否再次兑现",
    "barbora-krejcikova": "法网与温网冠军都写在履历里；首轮真正看的是变化与手感能否上线",
    "tsitsipas": "结束16个月冠军等待后，他接下来要证明这不是一座孤立的奖杯",
}


_PLAYER_PREVIEW_VARIANTS = {
    "yuan-yue": (
        "\u5965\u65af\u6c40\u9996\u51a0\u8bc1\u660e\u8fc7\u5979\u80fd\u6253\u786c\u4ed7\uff1b\u8fd9\u6b21\u91cd\u56de\u7ea2\u571f\u9996\u8f6e\uff0c\u5148\u770b\u8282\u594f\u80fd\u5426\u7ad9\u7a33",
        "\u5979\u7684\u5de1\u56de\u8d5b\u4e0a\u5347\u671f\u4e0d\u7f3a\u9ad8\u5149\uff0c\u4eca\u665a\u66f4\u5173\u952e\u7684\u662f\u628a\u9996\u8f6e\u538b\u529b\u62c6\u6210\u4e00\u5c40\u4e00\u5c40",
        "\u4ece\u5965\u65af\u6c40\u5230\u5e03\u62c9\u683c\uff0c\u5979\u8981\u627e\u56de\u7684\u4e0d\u53ea\u662f\u80dc\u573a\uff0c\u8fd8\u6709\u5148\u628a\u5bf9\u624b\u62d6\u8fdb\u81ea\u5df1\u8282\u594f\u7684\u80fd\u529b",
    ),
    "gao-xinyu": (
        "\u8054\u5408\u676f\u7684\u9ad8\u5149\u4e0d\u4f1a\u81ea\u52a8\u5e26\u6765\u80dc\u5229\uff0c\u4f46\u80fd\u63d0\u9192\u4eba\uff1a\u5979\u6253\u9006\u98ce\u7403\u6709\u5e95\u6c14",
        "\u5979\u66fe\u5728\u8054\u5408\u676f\u7206\u51b7\u4e16\u754c\u7b2c17\u7684\u739b\u96c5\uff1b\u56de\u5230\u5de1\u56de\u8d5b\uff0c\u97e7\u6027\u80fd\u5426\u518d\u6b21\u5151\u73b0",
    ),
}


def _player_preview(slug: str, today: date | None) -> str | None:
    choices = _PLAYER_PREVIEW_VARIANTS.get(slug)
    if not choices:
        return None
    if today is None:
        return choices[0]
    return choices[today.toordinal() % len(choices)]


def _topicality_angle(match: Match) -> str | None:
    """A grounded 'this match already has real buzz' note from the automated
    trend radar (ATP/WTA/major-event news feeds plus search-trend signals).

    Unlike brief_for_match, these signals are not human-reviewed, so the line
    stays limited to citing the real, sourced headline rather than passing
    editorial judgment on it.
    """
    signals = [s for s in (match.trend_signals or []) if isinstance(s, dict)]
    news = next(
        (
            s
            for s in signals
            if s.get("kind") == "official-news" and s.get("title") and s.get("source")
        ),
        None,
    )
    if news:
        return f"{news['source']}近期报道《{news['title']}》，这场已经带着真实话题度。"
    if (match.search_heat or 0) >= 20:
        return "搜索热度正在走高，这场吸引的不只是赛程爱好者。"
    return None


def preview_angle(match: Match, today: date | None = None) -> str:
    """Explain why a match matters, weighing media opinion, both sides'
    topicality, and historical relevance before falling back to mechanical
    rank/seed facts.

    Priority: reviewed media consensus > curated editorial note > a tracked
    player's own story > Chinese-player schedule facts > tournament story >
    account continuity (this player's last appearance in our own coverage) >
    automated trend-radar topicality (real, sourced buzz, not yet reviewed) >
    mechanical schedule_insight as the final, always-available fallback.
    """
    media = brief_for_match(match, today) if today is not None else None
    if media is not None:
        return media.consensus
    if match.editorial_note and (
        match.editorial_url or match.editorial_source == "背景编辑"
    ):
        return match.editorial_note

    story = direct_story_for_match(match, prefer_player=True)
    if story is not None and story.kind == "player":
        return _player_preview(story.slug, today) or _PLAYER_PREVIEWS.get(story.slug, story.hero_fact)

    chinese = next(
        (player for player in match.home + match.away if is_chinese_player(player)),
        None,
    )
    if chinese is not None:
        return schedule_insight(match)

    if story is not None:
        return f"{story.title}又要添一位新主角；这场不只抢晋级，也抢本届赛事的叙事中心。"

    if today is not None:
        historical = historical_context(match, today)
        if historical is not None and historical.summary:
            return historical.summary

    return _topicality_angle(match) or schedule_insight(match)


def editor_takeaway(match: Match, today: date | None = None) -> str:
    media = brief_for_match(match, today) if today is not None else None
    if media is not None and media.takeaway:
        return media.takeaway
    story = direct_story_for_match(match, prefer_player=True)
    if story is not None and story.kind == "player":
        return f"我更想继续追踪的，是{story.title}如何把今天接进自己的生涯时间线。"
    return "我更在意比赛留下的变化，而不是只把最终比分再念一遍。"


def apply_knowledge_angles(digest) -> int:
    """Attach reviewed player/tournament context before model rewrites."""
    applied = 0
    for match in digest.schedule:
        if match.editorial_note:
            continue
        story = direct_story_for_match(match, prefer_player=True)
        if story is None:
            continue
        match.editorial_note = preview_angle(match, digest.today)
        match.editorial_source = story.source_label
        match.editorial_url = story.source_url
        applied += 1
    return applied
