"""小红书文案：一篇只讲三件事，热点另发单场闪报。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..digest import Digest
from ..models import Match, MatchStatus
from ..zh import player_zh
from ..timeutil import fmt_time_beijing
from .common import (
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    side_display,
)
from .focus import focus_comparison, has_detailed_stats, select_focus_match
from .rating import match_score, select_lead_story, tonight_focus
from .story import (
    chinese_side_won,
    is_chinese_player,
    result_insight,
    schedule_insight,
)

MAX_BODY = 700
BASE_TAGS = ["#网球", "#网球时差"]

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


def xhs_title_len(text: str) -> float:
    """小红书标题字数：全角/汉字/emoji 记 1，半角字符记 0.5."""
    return sum(0.5 if ord(c) < 128 else 1 for c in text)


def _title_emoji(hook: str) -> str:
    """按钩子内容挑 emoji：夺冠🏆 / 爆冷💥 / 今晚看点🔥 / 默认🎾."""
    if any(k in hook for k in ("夺冠", "问鼎", "捧杯", "冠军", "登顶")):
        return "🏆"
    if any(k in hook for k in ("爆冷", "掀翻")):
        return "💥"
    if any(k in hook for k in ("出战", "对阵", "今晚", "焦点")):
        return "🔥"
    return "🎾"


def decorate_title(digest: Digest, hook: str) -> str:
    """发布标题 = emoji + 日期 + 钩子，如 '🏆7.20｜跌至世界第85，西西帕斯终于捧杯'.

    按小红书 20 字预算（半角记 0.5）裁剪钩子，日期与 emoji 不挤占核心信息。
    """
    prefix = f"{_title_emoji(hook)}{digest.today.month}.{digest.today.day}｜"
    budget = 20 - xhs_title_len(prefix)
    if xhs_title_len(hook) > budget:
        out = ""
        for ch in hook:
            if xhs_title_len(out + ch) > budget - 1:
                break
            out += ch
        hook = out.rstrip("，。、：") + "…"
    return prefix + hook


def post_title(digest: Digest) -> str:
    """V1 §3.1：发布标题 = 头条候选 ①（与封面主钩子同源）+ 日期与 emoji.

    备选 ②③ 由复制页提供，人工从 3 个候选里选 1 个。
    """
    from .titles import pick_headline_auto

    return decorate_title(digest, pick_headline_auto(digest))


def _tags(matches: list[Match]) -> list[str]:
    """冷启动标签：主角和赛事词优先，避免给正文未出现的球员蹭标签。"""
    tags = list(BASE_TAGS)

    def add(value: str) -> None:
        tag = f"#{value}"
        if value and tag not in tags:
            tags.append(tag)

    if matches:
        lead = matches[0]
        lead_players = lead.winner_players() or lead.home[:1]
        if lead_players:
            add(player_zh(lead_players[0].name))
        add(group_by_tournament([lead])[0].name_zh)

    for tour in dict.fromkeys(match.tour.value for match in matches):
        add(tour)

    for match in matches:
        if not match.is_singles:
            continue
        for player in match.home + match.away:
            if is_chinese_player(player):
                add(player_zh(player.name))

    for match in matches:
        for player in match.home + match.away:
            if is_chinese_player(player):
                add(player_zh(player.name))
        group = group_by_tournament([match])[0]
        add(group.name_zh)
    return tags[:8]


@dataclass(frozen=True)
class XhsSection:
    label: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class XhsPostPlan:
    """可审计的小红书正文计划；渲染前先决定主线和证据。"""

    title: str
    hook: tuple[str, ...]
    lead_match_id: str | None
    lead_score: int | None
    lead_reasons: tuple[str, ...]
    sections: tuple[XhsSection, ...]
    opinion: str
    question: str
    signature: str
    tags: tuple[str, ...]
    evidence: tuple[dict[str, str], ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _short(text: str, limit: int) -> str:
    cleaned = " ".join(text.strip().split()).rstrip("。；;，,")
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip("，,；;") + "…"


def _matchup(match: Match) -> str:
    return (
        f"{side_display(match.home, with_seed=False)} vs "
        f"{side_display(match.away, with_seed=False)}"
    )


_RESULT_OPENINGS = (
    "昨夜先别急着翻完整赛果。",
    "一觉醒来，先说昨夜最值得记住的一件事。",
    "昨夜比赛不少，但头条其实很清楚。",
    "今天先把最重要的一条放在前面。",
    "比分很多，真正会留在记忆里的通常只有一场。",
    "昨夜最值得回看的，不是所有比赛。",
    "先用半分钟，把昨夜最重要的一条说清楚。",
)

_SCHEDULE_OPENINGS = (
    "今晚不用把所有比赛都守完。",
    "今晚的赛程很长，我只先圈最值得看的一场。",
    "时间有限，今晚先把这一场留出来。",
    "今晚看球不贪多，先抓住最重要的一条线。",
    "赛程表很满，但真正需要定闹钟的比赛不多。",
    "今晚只留一个黄金时段，先给最值得看的比赛。",
    "不必从第一场守到最后，今晚先看重点。",
)


def _lead_hook(digest: Digest, match: Match | None) -> tuple[str, ...]:
    if match is None:
        return ("今天的赛程不算拥挤。", "把真正值得看的几件事挑出来就够了。")
    index = digest.today.toordinal() % 7
    if match.status.is_final:
        return (_RESULT_OPENINGS[index],)
    if match.status == MatchStatus.LIVE:
        return ("比赛正在进行，先看今天最重要的一条线。",)
    return (_SCHEDULE_OPENINGS[index],)


def _lead_section(match: Match, *, compact: bool) -> XhsSection:
    if match.status.is_final:
        from .titles import cover_result_hook

        headline, meaning = cover_result_hook(match)
        detail = meaning or result_insight(match)
        return XhsSection(
            "🎾 今天先看这一件事",
            (headline.rstrip("。") + "。", _short(detail, 44 if compact else 58) + "。"),
        )

    status = "进行中" if match.status == MatchStatus.LIVE else fmt_time_beijing(match.start_utc)
    group = group_by_tournament([match])[0]
    stage = f"{group.compact_title}·{match_round_display(match)}".rstrip("·")
    return XhsSection(
        "🎾 今天先看这一件事",
        (
            f"{status}｜{stage}",
            _matchup(match),
            _short(schedule_insight(match), 40 if compact else 52) + "。",
        ),
    )


def _china_matches(digest: Digest, lead: Match | None) -> list[Match]:
    matches = [
        match
        for match in digest.results + digest.live + digest.schedule
        if is_chinese_involved(match)
        and (lead is None or match.match_id != lead.match_id)
    ]
    return sorted(matches, key=match_score, reverse=True)[:2]


def _china_line(match: Match) -> str:
    chinese = [
        player for player in match.home + match.away if is_chinese_player(player)
    ]
    name = side_display(chinese, with_seed=False) if chinese else "中国球员"
    group = group_by_tournament([match])[0]
    if match.status.is_final:
        round_name = (match_round_display(match) or "本轮").replace("·", "")
        if chinese_side_won(match):
            action = "捧杯" if round_name == "决赛" else "过关"
            return f"✅ {name}{action}｜{group.compact_title}·{round_name}"
        return f"▫️ {name}止步{round_name}｜{group.compact_title}"
    status = "正在比赛" if match.status == MatchStatus.LIVE else f"{fmt_time_beijing(match.start_utc)}出战"
    return f"⏰ {name}{status}｜{group.compact_title}"


def _china_section(digest: Digest, lead: Match | None) -> XhsSection | None:
    matches = _china_matches(digest, lead)
    if not matches:
        return None
    return XhsSection("🇨🇳 中国球员速报", tuple(_china_line(match) for match in matches))


def _tonight_section(digest: Digest, *, compact: bool) -> tuple[XhsSection | None, list[Match]]:
    matches = tonight_focus(digest.schedule, min_n=3, max_n=3)
    if not matches:
        return None, []
    lines: list[str] = []
    for index, match in enumerate(matches):
        group = group_by_tournament([match])[0]
        round_name = match_round_display(match).replace("·", "")
        stage = f"{group.name_zh}·{round_name}".rstrip("·")
        if index:
            lines.append("")
        lines.extend(
            [
                f"⏰ {fmt_time_beijing(match.start_utc)}｜{stage}",
                _matchup(match),
                "看点：" + _short(schedule_insight(match), 32 if compact else 42) + "。",
            ]
        )
    return XhsSection("🌙 今晚只看这三场", tuple(lines)), matches


def _opinion(lead: Match | None, tonight: list[Match], *, compact: bool) -> str:
    if tonight:
        choice = tonight[0]
        reason = _short(schedule_insight(choice), 28 if compact else 38)
        return f"我会先看{_matchup(choice)}。\n因为{reason}。"
    if lead is not None and lead.status.is_final:
        return f"我更在意的不是一场比分，而是{_short(result_insight(lead), 38)}。"
    return "今天没有必要追满所有场次，把时间留给真正重要的比赛。"


def _discussion_question(match: Match | None) -> str:
    """Generate one low-friction tennis question that can be answered in a comment."""
    if match is None:
        return "今天这条主线里，你最想继续追哪位球员？"

    chinese = [
        player for player in match.home + match.away if is_chinese_player(player)
    ]
    if chinese:
        name = player_zh(chinese[0].name)
        return f"{name}想赢这场，你会先盯发球还是接发？"

    left = side_display(match.home, with_seed=False)
    right = side_display(match.away, with_seed=False)
    return f"只选一边：{left}还是{right}？"


def _evidence(digest: Digest, matches: list[Match]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in matches:
        if match.match_id in seen:
            continue
        seen.add(match.match_id)
        rows.append(
            {
                "match_id": match.match_id,
                "source": match.editorial_source or digest.source or "赛程数据",
                "url": match.editorial_url or "",
            }
        )
        if match is matches[0]:
            from .titles import cover_fact_bundle

            historical = cover_fact_bundle(match).get("historical_profile")
            if historical and historical.get("source_url"):
                rows.append(
                    {
                        "match_id": match.match_id,
                        "source": "ATP Tour 人工核验球员档案",
                        "url": str(historical["source_url"]),
                    }
                )
    return tuple(rows)


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


def build_post_plan(digest: Digest, *, compact: bool = False) -> XhsPostPlan:
    selection = select_lead_story(digest)
    lead = selection.match if selection is not None else None
    sections: list[XhsSection] = []
    evidence_matches: list[Match] = []
    if lead is not None:
        sections.append(_lead_section(lead, compact=compact))
        evidence_matches.append(lead)

    china = _china_section(digest, lead)
    if china is not None:
        sections.append(china)
        evidence_matches.extend(_china_matches(digest, lead))

    tonight, tonight_matches = _tonight_section(digest, compact=compact)
    if tonight is not None:
        sections.append(tonight)
        evidence_matches.extend(tonight_matches)

    focus = _focus_block(digest)
    if focus:
        sections.append(XhsSection(focus[0], tuple(focus[1:])))

    if tonight_matches:
        question = _discussion_question(tonight_matches[0])
        global _LAST_QUIZ
        top = tonight_matches[0]
        _LAST_QUIZ = {
            "date": digest.today.isoformat(),
            "players": [p.name for p in top.home + top.away],
        }
    else:
        question = _discussion_question(lead)

    reveal = _quiz_reveal(digest)
    if reveal:
        sections.append(XhsSection("📢 昨日竞猜", (reveal.removeprefix("📢 "),)))

    return XhsPostPlan(
        title=post_title(digest),
        hook=_lead_hook(digest, lead),
        lead_match_id=lead.match_id if lead is not None else None,
        lead_score=selection.score if selection is not None else None,
        lead_reasons=selection.reasons if selection is not None else (),
        sections=tuple(sections),
        opinion=_opinion(lead, tonight_matches, compact=compact),
        question=question,
        signature="关注 @网球时差｜明早用赛果和胜负手，把今天这场接着讲完。",
        tags=tuple(_tags(evidence_matches)),
        evidence=_evidence(digest, evidence_matches),
    )


def render_post_plan(plan: XhsPostPlan) -> list[str]:
    lines = [plan.title, "", *plan.hook, ""]
    for section in plan.sections:
        lines.extend([section.label, *section.lines, ""])
    lines.extend(
        [
            "📝 我的一票",
            plan.opinion,
            "",
            "💬 留个答案",
            plan.question,
            "",
            plan.signature,
            "",
            " ".join(plan.tags),
        ]
    )
    return lines


def plan_post(digest: Digest) -> tuple[XhsPostPlan, str]:
    plan = build_post_plan(digest)
    post = "\n".join(render_post_plan(plan))
    body = post.split("\n", 2)[2] if "\n\n" in post else ""
    if len(body) > MAX_BODY:
        plan = build_post_plan(digest, compact=True)
        post = "\n".join(render_post_plan(plan))
    return plan, post


def to_post(digest: Digest) -> str:
    return plan_post(digest)[1]
