"""小红书文案：一篇只讲三件事，热点另发单场闪报。"""

from __future__ import annotations

import json
from pathlib import Path

from ..digest import Digest
from ..models import Match, MatchStatus
from ..zh import player_zh
from ..timeutil import fmt_time_beijing
from .common import (
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .focus import focus_comparison, has_detailed_stats, select_focus_match
from .hotspot import hotspot_title_candidates
from .rating import match_score, tonight_focus, top_results
from .story import (
    result_insight,
    schedule_insight,
)
from .tournament_story import pick_tournament_story
from .titles import daily_lead_match

MAX_BODY = 950
BASE_TAGS = ["#网球", "#WTA", "#ATP", "#网球时差", "#网球晨报"]

# 每日一帖模式：竞猜折叠进正文，次日开奖制造回访（data/ 随 workflow 提交）
QUIZ_PATH = Path(__file__).resolve().parents[3] / "data" / "quiz_state.json"
_LAST_QUIZ: dict | None = None


def _quiz_reveal(digest: Digest) -> str | None:
    """昨日竞猜场次已出结果 -> 开奖行；无状态/未完赛返回 None."""
    try:
        state = json.loads(QUIZ_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if state.get("date") != digest.yesterday.isoformat():
        return None
    asked = set(state.get("players") or [])
    if not asked:
        return None
    for m in digest.results:
        if asked <= {p.name for p in m.home + m.away} and m.winner is not None:
            w = (m.winner_players() or [None])[0]
            if w:
                return (
                    f"📢 昨晚竞猜开奖：{player_zh(w.name)}拿下——"
                    "猜对的评论区扣 1！"
                )
    return None


def record_quiz() -> None:
    """CLI 在生成成功后调用：保存今日竞猜场次，明早开奖."""
    if _LAST_QUIZ:
        QUIZ_PATH.parent.mkdir(parents=True, exist_ok=True)
        QUIZ_PATH.write_text(
            json.dumps(_LAST_QUIZ, ensure_ascii=False), encoding="utf-8"
        )


def post_title(digest: Digest) -> str:
    """日期 + 当天最强单场钩子；不再把两三件事挤进标题。"""
    stories = _daily_stories(digest)
    event = hotspot_title_candidates(stories[0])[0] if stories else "今日网球三件事"
    prefix = f"{digest.today.month}月{digest.today.day}日｜"
    available = 20 - len(prefix)
    if len(event) > available:
        event = event[: max(available - 1, 0)] + "…"
    return prefix + event


def _tags(digest: Digest) -> list[str]:
    from ..zh import player_zh

    tags = list(BASE_TAGS)
    for m in digest.results + digest.schedule:
        if not is_chinese_involved(m):
            continue
        for p in m.home + m.away:
            zh = player_zh(p.name)
            if zh != p.name and (p.country or "").upper() in ("CHN", "CN"):
                tag = f"#{zh}"
                if tag not in tags:
                    tags.append(tag)
    for group in group_by_tournament(digest.results + digest.schedule):
        if group.level in ("GS", "M1000", "W1000", "ATP500", "WTA500"):
            tag = f"#{group.name_zh}"
            if tag not in tags:
                tags.append(tag)
    return tags[:9]


def _daily_stories(digest: Digest) -> list[Match]:
    """真正头条、中国焦点、今晚焦点各取一条，去重后补足三条。"""
    all_matches = digest.results + digest.live + digest.schedule
    chinese = sorted(
        [match for match in all_matches if is_chinese_involved(match)],
        key=match_score,
        reverse=True,
    )
    results = top_results(
        [match for match in digest.results if match.is_singles],
        5,
        cn_boost=True,
    )
    schedule = tonight_focus(digest.schedule, min_n=1, max_n=4)

    selected: list[Match] = []
    selected_ids: set[str] = set()

    def add(match) -> None:
        if match is not None and match.match_id not in selected_ids and len(selected) < 3:
            selected.append(match)
            selected_ids.add(match.match_id)

    def add_first_distinct(candidates) -> None:
        for match in candidates:
            before = len(selected)
            add(match)
            if len(selected) > before:
                break

    add(daily_lead_match(digest))
    add_first_distinct(chinese)
    add_first_distinct(schedule)
    for match in results:
        add(match)
    for match in sorted(all_matches, key=match_score, reverse=True):
        add(match)
    return selected


def _story_lines(match: Match, number: str, *, compact: bool) -> list[str]:
    group = group_by_tournament([match])[0]
    label = f"{group.compact_title}·{match_round_display(match)}".rstrip("·")
    if match.status.is_final:
        lines = [f"{number} {label}", result_line(match)]
        if not compact:
            lines.append(f"↳ {result_insight(match)}")
        return lines

    status = (
        "进行中"
        if match.status == MatchStatus.LIVE
        else fmt_time_beijing(match.start_utc)
    )
    lines = [
        f"{number} {status}｜{label}",
        f"{side_display(match.home, with_seed=False)} vs "
        f"{side_display(match.away, with_seed=False)}",
    ]
    if not compact:
        lines.append(f"↳ {schedule_insight(match)}")
    return lines


def _focus_block(digest: Digest) -> list[str]:
    match = select_focus_match(digest)
    if not has_detailed_stats(match):
        return []
    comparison = focus_comparison(match)
    group = group_by_tournament([match])[0]
    metrics = "｜".join(
        f"{label} {left}:{right}" for label, left, right in comparison.rows[:3]
    )
    lines = [
        "🎯 一场球看细一点",
        f"{group.name_zh}｜{comparison.left_name} vs {comparison.right_name}",
        metrics,
        f"判断：{comparison.verdict}",
    ]
    if comparison.source_label:
        source = comparison.source_label
        duration = f"｜{comparison.duration_label}" if comparison.duration_label else ""
        lines.append(f"数据：{source}{duration}")
    return lines


def _build(digest: Digest, *, compact: bool = False) -> list[str]:
    stories = _daily_stories(digest)
    lines = ["今天只讲三件事：", ""]
    numbers = ("①", "②", "③")
    for index, match in enumerate(stories):
        lines.extend(_story_lines(match, numbers[index], compact=compact) + [""])

    focus = _focus_block(digest)
    if focus:
        lines.extend(focus + [""])

    story = pick_tournament_story(digest) if not compact else None
    if story is not None:
        if story.kind == "player":
            label = "🌟 球员一分钟"
        elif story.kind == "trivia":
            label = "🎾 网球冷知识"
        else:
            label = "📚 赛事一分钟"
        lines.extend([label, f"{story.title}｜{story.venue}"])
        if story.moments:
            moment = story.moments[0]
            lines.extend([f"▪ {moment.headline}", ""])

    upcoming = [match for match in stories if not match.status.is_final]
    if upcoming:
        choice = "、".join(
            hotspot_title_candidates(match)[0] for match in upcoming[:2]
        )
        question = f"今晚只选一场，你会追哪场？评论区站队：{choice}"
        global _LAST_QUIZ
        top = upcoming[0]
        _LAST_QUIZ = {
            "date": digest.today.isoformat(),
            "players": [p.name for p in top.home + top.away],
        }
    else:
        question = "这三件事里，哪一条最出乎你的意料？"

    ending = [
        question,
        "关注 @网球时差｜睡醒看懂昨夜，开赛前只提醒值得看的。",
        "",
        " ".join(_tags(digest)),
    ]
    reveal = _quiz_reveal(digest)
    if reveal:
        ending.insert(0, reveal)
    lines.extend(ending)
    return lines


def to_post(digest: Digest) -> str:
    body = _build(digest)
    if len("\n".join(body)) > MAX_BODY:
        body = _build(digest, compact=True)
    return "\n".join([post_title(digest), ""] + body)
