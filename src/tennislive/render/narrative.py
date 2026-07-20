"""Evidence-led human angles for previews and opinion copy."""

from __future__ import annotations

from datetime import date

from ..models import Match
from ..research.media import brief_for_match
from ..zh import player_zh
from .common import match_round_display
from .story import is_chinese_player, schedule_insight
from .tournament_story import direct_story_for_match


_PLAYER_PREVIEWS = {
    "yuan-yue": "2024年奥斯汀首夺WTA冠军并跻身前50，今晚看她能否重新接上那段上升势头",
    "gao-xinyu": "她曾在联合杯爆冷世界第17的玛雅；回到巡回赛，韧性能否再次兑现",
    "barbora-krejcikova": "法网与温网冠军都写在履历里；首轮真正看的是变化与手感能否上线",
    "tsitsipas": "结束16个月冠军等待后，他接下来要证明这不是一座孤立的奖杯",
}


def preview_angle(match: Match, today: date | None = None) -> str:
    """Explain why a match matters without treating ranking as the story."""
    media = brief_for_match(match, today) if today is not None else None
    if media is not None:
        return media.consensus
    if match.editorial_note and match.editorial_url:
        return match.editorial_note

    story = direct_story_for_match(match, prefer_player=True)
    if story is not None and story.kind == "player":
        return _PLAYER_PREVIEWS.get(story.slug, story.hero_fact)

    chinese = next(
        (player for player in match.home + match.away if is_chinese_player(player)),
        None,
    )
    if chinese is not None:
        stage = match_round_display(match).replace("·", "") or "本轮"
        return f"{player_zh(chinese.name)}的{stage}，值得看的不是纸面排名，而是能否把比赛带进自己的节奏。"

    if story is not None:
        return f"这场发生在{story.title}的历史现场；胜负之外，也会成为本届赛事的新坐标。"
    return schedule_insight(match)


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
