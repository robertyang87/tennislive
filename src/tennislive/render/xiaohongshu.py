"""小红书文案：事件型标题、明确结论、专业复盘与互动入口."""

from __future__ import annotations

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from .common import (
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .focus import focus_comparison, has_detailed_stats, select_focus_match
from .rating import tonight_focus, top_results
from .story import (
    chinese_side_won,
    result_insight,
    schedule_insight,
    sort_china_matches,
)
from .titles import cover_highlights
from .tournament_story import pick_tournament_story

MAX_BODY = 950
BASE_TAGS = ["#网球", "#WTA", "#ATP", "#网球时差", "#网球晨报"]
_QUOTAS = [(4, 4, 5), (4, 3, 4), (3, 3, 3), (2, 2, 3)]


def _compact_secondary(text: str) -> str:
    return (
        text.replace("中国双打", "双打")
        .replace("中国军团", "中国队")
        .replace("收获", "拿下")
    )


def post_title(digest: Digest) -> str:
    """用当天最大事件做标题，不浪费字符重复栏目名和日期."""
    primary, secondary = cover_highlights(digest)
    combined = f"{primary}｜{_compact_secondary(secondary)}"
    title = combined if len(combined) <= 20 else primary
    return title if len(title) <= 20 else title[:19] + "…"


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


def _china_block(digest: Digest, cap: int) -> list[str]:
    matches = sort_china_matches(
        [
            m
            for m in digest.results + digest.live + digest.schedule
            if is_chinese_involved(m)
        ]
    )[:cap]
    if not matches:
        return []
    lines = ["🇨🇳 中国军团"]
    for m in matches:
        group = group_by_tournament([m])[0]
        label = f"{group.name_zh}·{match_round_display(m)}".rstrip("·")
        if m.status.is_final:
            marker = "✅" if chinese_side_won(m) else "◽"
            lines.append(f"{marker} {label}")
            lines.append(result_line(m))
        else:
            lines.append(f"⏰ {fmt_time_beijing(m.start_utc)} {label}")
            lines.append(
                f"{side_display(m.home, with_seed=False)} vs "
                f"{side_display(m.away, with_seed=False)}"
            )
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


def _build(digest: Digest, quota: tuple[int, int, int]) -> list[str]:
    cn_cap, result_cap, schedule_cap = quota
    primary, secondary = cover_highlights(digest)
    lines = [
        "今天先抓两条主线：",
        f"① {primary}",
        f"② {secondary}",
        "",
    ]

    china = _china_block(digest, cn_cap)
    if china:
        lines.extend(china + [""])

    results = top_results(
        [m for m in digest.results if m.is_singles], result_cap, cn_boost=False
    )
    if results:
        lines.append("🏆 昨夜值得记住")
        for m in results:
            group = group_by_tournament([m])[0]
            lines.append(f"▪ {group.name_zh}·{match_round_display(m)}")
            lines.append(result_line(m))
            lines.append(f"↳ {result_insight(m)}")
        lines.append("")

    schedule = tonight_focus(digest.schedule, min_n=min(3, schedule_cap), max_n=schedule_cap)
    if schedule:
        lines.append("⏰ 今晚焦点（北京时间）")
        for m in schedule:
            group = group_by_tournament([m])[0]
            lines.append(
                f"▪ {fmt_time_beijing(m.start_utc)} {group.name_zh}·"
                f"{match_round_display(m)}"
            )
            lines.append(
                f"{side_display(m.home, with_seed=False)} vs "
                f"{side_display(m.away, with_seed=False)}"
            )
            source = f"{m.editorial_source}｜" if m.editorial_url and m.editorial_source else ""
            lines.append(f"↳ {source}{schedule_insight(m)}")
        lines.append("")

    focus = _focus_block(digest)
    if focus:
        lines.extend(focus + [""])

    story = pick_tournament_story(digest)
    if story:
        lines.extend(["📚 赛事一分钟", f"{story.title}｜{story.level}｜{story.surface}"])
        for moment in story.moments[:2]:
            lines.append(
                f"▪ {moment.date[:4]} {moment.player}（{moment.age}）：{moment.headline}"
            )
        lines.append("")

    lines.extend(
        [
            "你最想看哪场？评论区留下球员名，我优先跟进呼声最高的一场。",
            "关注 @网球时差｜持续更新，不堆数据，只讲重点。",
            "",
            " ".join(_tags(digest)),
        ]
    )
    return lines


def to_post(digest: Digest) -> str:
    body = _build(digest, _QUOTAS[0])
    for quota in _QUOTAS[1:]:
        if len("\n".join(body)) <= MAX_BODY:
            break
        body = _build(digest, quota)
    return "\n".join([post_title(digest), ""] + body)
