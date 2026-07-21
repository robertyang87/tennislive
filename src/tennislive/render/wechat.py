"""微信公众号文案：结论先行、精选信息、专业复盘与内联样式 HTML."""

from __future__ import annotations

import re

from ..digest import Digest
from ..models import Match
from ..timeutil import fmt_date_zh, fmt_schedule_time, fmt_time_beijing
from .common import (
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .focus import focus_comparison, has_detailed_stats, select_focus_match
from .rating import is_tour_focus_match, tonight_focus, top_results
from .story import (
    chinese_side_won,
    result_insight,
    schedule_insight,
    sort_china_matches,
)
from .titles import cover_highlights, pick_headline_auto


def pick_headline(digest: Digest) -> str:
    if not (digest.results or digest.schedule):
        return "今日暂无巡回赛比赛"
    return pick_headline_auto(digest)


def article_title(digest: Digest) -> str:
    d = digest.today
    return f"网球晨报｜{d.month}月{d.day}日 {pick_headline(digest)}"


def _china_matches(digest: Digest, cap: int = 6) -> list[Match]:
    return sort_china_matches(
        [
            m
            for m in digest.results + digest.live + digest.schedule
            if is_chinese_involved(m)
            and is_tour_focus_match(m)
        ]
    )[:cap]


def _focus_results(digest: Digest, cap: int = 8) -> list[Match]:
    return top_results(
        [m for m in digest.results if m.is_singles], cap, cn_boost=False
    )


def _tonight(digest: Digest, cap: int = 5) -> list[Match]:
    return tonight_focus(digest.schedule, min_n=3, max_n=cap)


def to_markdown(digest: Digest) -> str:
    primary, secondary = cover_highlights(digest)
    lines = [
        f"# {article_title(digest)}",
        "",
        f"> {fmt_date_zh(digest.today)}（北京时间）· 替你筛完赛果，只留下值得看的重点",
        "",
        "## 今日先看",
        "",
        f"**{primary}**",
        "",
        f"第二条主线：{secondary}。",
        "",
    ]

    china = _china_matches(digest)
    if china:
        lines.extend(["## 🇨🇳 中国军团", ""])
        for m in china:
            group = group_by_tournament([m])[0]
            label = f"{group.name_zh}·{match_round_display(m)}".rstrip("·")
            if m.status.is_final:
                mark = "胜" if chinese_side_won(m) else "负"
                lines.append(f"- **{mark}｜{label}**：{result_line(m)}")
            else:
                lines.append(
                    f"- **{fmt_schedule_time(m)}｜{label}**："
                    f"{side_display(m.home)} vs {side_display(m.away)}"
                )
        lines.append("")

    results = _focus_results(digest)
    if results:
        lines.extend(["## 🏆 昨夜焦点赛果", ""])
        for m in results:
            group = group_by_tournament([m])[0]
            lines.append(
                f"- **{group.name_zh}·{match_round_display(m)}**：{result_line(m)}"
            )
            lines.append(f"  看点：{result_insight(m)}")
        lines.append("")

    schedule = _tonight(digest)
    if schedule:
        lines.extend(["## ⏰ 今晚焦点", ""])
        for m in schedule:
            group = group_by_tournament([m])[0]
            lines.append(
                f"- **{fmt_schedule_time(m)}｜{group.name_zh}**："
                f"{side_display(m.home)} vs {side_display(m.away)}"
            )
            source = ""
            if m.editorial_url and m.editorial_source:
                source = f"（[{m.editorial_source}原文]({m.editorial_url})）"
            lines.append(f"  推荐理由：{schedule_insight(m)}{source}")
        lines.append("")

    focus = select_focus_match(digest)
    if has_detailed_stats(focus):
        comparison = focus_comparison(focus)
        lines.extend(["## 🎯 焦点复盘", ""])
        lines.append(f"**{comparison.left_name} vs {comparison.right_name}**")
        lines.append("")
        for label, left, right in comparison.rows:
            lines.append(f"- {label}：{left} vs {right}")
        lines.extend(["", f"**一句判断：**{comparison.verdict}"])
        if comparison.source_label:
            source = comparison.source_label
            duration = f"｜{comparison.duration_label}" if comparison.duration_label else ""
            lines.extend([f"数据：{source}{duration}", ""])
        else:
            lines.append("")

    story = None
    if story:
        lines.extend(
            [
                "## 📚 赛事档案",
                "",
                f"**{story.title}**｜{story.location}｜{story.level}｜{story.surface}",
                "",
                f"{story.founded}。{story.hero_fact}",
                "",
            ]
        )
        lines.extend(["**冠军时间轴**", ""])
        for moment in story.moments:
            date = moment.date.replace("-", ".")
            lines.append(
                f"- **[{date}｜{moment.player}｜{moment.age}]({moment.source_url})**："
                f"{moment.headline}。{moment.detail}"
            )
        lines.append("")
        lines.extend(f"- {fact}" for fact in story.facts)
        lines.extend(["", f"[赛事官方历史资料]({story.source_url})"])
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "*时间均为北京时间；完整原始数据保留在 digest.json。数据来自公开比分接口，以赛事官方为准。*",
            "",
        ]
    )
    return "\n".join(lines)


_S = {
    "lead": (
        "margin:16px 0 24px;padding:18px 20px;background:#eff6f1;"
        "border-left:5px solid #c7f000;color:#173c2d;font-size:16px;line-height:1.8;"
    ),
    "h2": (
        "margin:30px 0 14px;padding:9px 14px;font-size:18px;font-weight:bold;"
        "color:#f7f3ea;background:#0b4d33;border-left:5px solid #c7f000;"
    ),
    "h3": "margin:18px 0 8px;font-size:16px;font-weight:bold;color:#173c2d;",
    "item": (
        "margin:0 0 12px;padding:12px 14px;background:#f8f8f5;"
        "border-bottom:1px solid #e2e7e2;font-size:15px;line-height:1.75;color:#25342d;"
    ),
    "insight": "display:block;margin-top:3px;color:#b5492f;font-size:13px;line-height:1.6;",
    "time": "color:#0b6b49;font-weight:bold;margin-right:5px;",
    "meta": "font-size:13px;color:#778179;margin:8px 0 20px;line-height:1.6;",
    "footer": "font-size:12px;color:#999;margin-top:28px;line-height:1.7;",
}


def _esc(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_FLAG_PAIR_RE = re.compile("([\U0001F1E6-\U0001F1FF])([\U0001F1E6-\U0001F1FF])")
FLAG_IMG_STYLE = (
    "width:20px;height:15px;display:inline-block;vertical-align:-2px;"
    "margin-right:3px;border-radius:2px;"
)


def _flag_img(match: re.Match) -> str:
    iso2 = "".join(chr(ord(c) - 0x1F1E6 + ord("a")) for c in match.groups())
    return (
        f'<img src="https://flagcdn.com/40x30/{iso2}.png" '
        f'alt="{iso2.upper()}" style="{FLAG_IMG_STYLE}" />'
    )


def _emoji_flags_to_img(content: str) -> str:
    return _FLAG_PAIR_RE.sub(_flag_img, content)


def _section(title: str) -> str:
    return f'<h2 style="{_S["h2"]}">{title}</h2>'


def _item(
    main: str,
    insight: str = "",
    *,
    source_name: str = "",
    source_url: str = "",
) -> str:
    source = ""
    if source_name and source_url.startswith("https://"):
        source = (
            f' <a href="{_esc(source_url)}" style="color:#0b6b49;text-decoration:none;">'
            f'来源：{_esc(source_name)} ↗</a>'
        )
    extra = (
        f'<span style="{_S["insight"]}">{_esc(insight)}{source}</span>'
        if insight or source else ""
    )
    return f'<div style="{_S["item"]}">{main}{extra}</div>'


def to_html(digest: Digest) -> str:
    primary, secondary = cover_highlights(digest)
    parts = [
        f'<p style="{_S["meta"]}">{_esc(fmt_date_zh(digest.today))}（北京时间）'
        "· WTA/ATP 每日精选</p>",
        f'<div style="{_S["lead"]}"><strong>{_esc(primary)}</strong><br/>'
        f'第二条主线：{_esc(secondary)}。</div>',
    ]

    china = _china_matches(digest)
    if china:
        parts.append(_section("🇨🇳 中国军团"))
        for m in china:
            group = group_by_tournament([m])[0]
            label = _esc(f"{group.name_zh}·{match_round_display(m)}".rstrip("·"))
            if m.status.is_final:
                mark = "胜" if chinese_side_won(m) else "负"
                main = f"<strong>{mark}｜{label}</strong><br/>{_esc(result_line(m))}"
            else:
                main = (
                    f'<strong><span style="{_S["time"]}">{_esc(fmt_schedule_time(m))}</span>'
                    f'{label}</strong><br/>{_esc(side_display(m.home))} vs {_esc(side_display(m.away))}'
                )
            parts.append(_item(main))

    results = _focus_results(digest)
    if results:
        parts.append(_section("🏆 昨夜焦点赛果"))
        for m in results:
            group = group_by_tournament([m])[0]
            main = (
                f"<strong>{_esc(group.name_zh)}·{_esc(match_round_display(m))}</strong><br/>"
                f"{_esc(result_line(m))}"
            )
            parts.append(_item(main, result_insight(m)))

    schedule = _tonight(digest)
    if schedule:
        parts.append(_section("⏰ 今晚焦点"))
        for m in schedule:
            group = group_by_tournament([m])[0]
            main = (
                f'<strong><span style="{_S["time"]}">{_esc(fmt_schedule_time(m))}</span>'
                f'{_esc(group.name_zh)}</strong><br/>'
                f'{_esc(side_display(m.home))} vs {_esc(side_display(m.away))}'
            )
            parts.append(
                _item(
                    main,
                    schedule_insight(m),
                    source_name=m.editorial_source or "",
                    source_url=m.editorial_url or "",
                )
            )

    focus = select_focus_match(digest)
    if has_detailed_stats(focus):
        comparison = focus_comparison(focus)
        parts.append(_section("🎯 焦点复盘"))
        rows = "".join(
            f'<tr><td style="padding:6px;color:#777;">{_esc(label)}</td>'
            f'<td style="padding:6px;font-weight:bold;text-align:center;">{_esc(left)}</td>'
            f'<td style="padding:6px;font-weight:bold;text-align:center;">{_esc(right)}</td></tr>'
            for label, left, right in comparison.rows
        )
        table = (
            '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
            f'<tr><th></th><th>{_esc(comparison.left_name)}</th><th>{_esc(comparison.right_name)}</th></tr>'
            f"{rows}</table>"
        )
        if comparison.source_label:
            source = comparison.source_label
            duration = f"｜{comparison.duration_label}" if comparison.duration_label else ""
            table += (
                '<p style="margin:8px 0 0;text-align:right;font-size:12px;color:#778179;">'
                f"数据：{_esc(source + duration)}</p>"
            )
        parts.append(_item(table, comparison.verdict))

    story = None
    if story:
        parts.append(_section("📚 赛事档案"))
        facts = "<br/>".join(f"· {_esc(fact)}" for fact in story.facts)
        moments = "".join(
            '<div style="margin:10px 0;padding:11px 12px;background:#eef3ed;'
            'border-left:4px solid #d5b44d;line-height:1.7;">'
            f'<strong>{_esc(moment.date.replace("-", "."))}｜'
            f'{_esc(moment.player)}｜{_esc(moment.age)}</strong><br/>'
            f'{_esc(moment.headline)}<br/>'
            f'<span style="color:#66756d;">{_esc(moment.detail)}</span><br/>'
            f'<a href="{_esc(moment.source_url)}" style="color:#0b6b49;'
            'text-decoration:none;font-size:12px;">官方资料 ↗</a></div>'
            for moment in story.moments
        )
        parts.append(
            _item(
                f"<strong>{_esc(story.title)}</strong>｜{_esc(story.level)}｜{_esc(story.surface)}<br/>"
                f"{_esc(story.founded)} · {_esc(story.location)}<br/><br/>"
                f"{moments}{facts}<br/>"
                f'<a href="{_esc(story.source_url)}" style="color:#0b6b49;'
                'text-decoration:none;font-size:12px;">赛事官方历史 ↗</a>',
                story.hero_fact,
            )
        )

    parts.append(
        f'<p style="{_S["footer"]}">时间均为北京时间；完整原始数据保留在 digest.json。'
        "数据来自公开比分接口，以赛事官方为准。</p>"
    )
    return _emoji_flags_to_img("\n".join(parts))
