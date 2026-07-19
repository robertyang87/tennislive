"""小红书热点选题：分钟级判断、标题候选与单场成稿。

这里只使用已经抓取并可核查的比赛事实。生成式编辑可以改写表达，
但不能绕过本模块补写纪录、伤病、排名变化或下一轮对手。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import Match
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from ..zh.terms import round_zh
from .common import (
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .rating import _level_of, is_upset, went_to_deciding_set
from .story import (
    chinese_side_won,
    is_chinese_player,
    result_insight,
    schedule_insight,
)

HOTSPOT_THRESHOLD = 50

_LEVEL_PTS = {
    "GS": 25,
    "M1000": 22,
    "W1000": 22,
    "ATP500": 14,
    "WTA500": 14,
    "ATP250": 8,
    "WTA250": 8,
    "Finals": 22,
    "TeamCup": 12,
}

_ROUND_PTS = {
    "决赛": 20,
    "半决赛": 12,
    "四分之一决赛": 8,
    "16强赛": 4,
    "第四轮": 4,
}


def _is_qualifying(match: Match) -> bool:
    raw = (match.round_name or "").lower()
    translated = round_zh(match.round_name) or ""
    return "qualif" in raw or "资格" in translated


def _chinese_player(match: Match, *, winner: bool | None = None):
    if winner is True:
        players = match.winner_players() or []
    elif winner is False:
        players = match.loser_players() or []
    else:
        players = match.home + match.away
    return next((player for player in players if is_chinese_player(player)), None)


def hotspot_score(match: Match) -> int:
    """传播价值分：用于决定单场闪报还是只进入晨报。

    赛事级别决定基础盘，中国球员、明星、爆冷和比赛戏剧性负责加权；
    资格赛与非中国双打降权，避免把账号重新做成全量比分流。
    """
    score = _LEVEL_PTS.get(_level_of(match) or "", 3)
    translated_round = round_zh(match.round_name) or ""
    score += _ROUND_PTS.get(translated_round, 0)

    if is_chinese_involved(match):
        if match.status.is_final:
            won = chinese_side_won(match)
            score += (45 if won else 30) if match.is_singles else (20 if won else 10)
        else:
            score += 36 if match.is_singles else 14

    ranks = [player.rank for player in match.home + match.away if player.rank]
    seeds = [player.seed for player in match.home + match.away if player.seed]
    if any(rank <= 10 for rank in ranks):
        score += 18
    elif any(rank <= 30 for rank in ranks):
        score += 10
    elif any(seed <= 4 for seed in seeds):
        score += 8

    if match.status.is_final and is_upset(match):
        score += 15
    if went_to_deciding_set(match):
        score += 10
    if any(
        item.home_tiebreak is not None or item.away_tiebreak is not None
        for item in match.sets
    ):
        score += 4

    if _is_qualifying(match):
        score -= 25
    if match.is_doubles and not is_chinese_involved(match):
        score -= 18
    return score


def hotspot_reasons(match: Match) -> list[str]:
    reasons: list[str] = []
    if is_chinese_involved(match):
        reasons.append("中国球员")
    if any((player.rank or 999) <= 10 for player in match.home + match.away):
        reasons.append("Top10")
    if match.status.is_final and is_upset(match):
        reasons.append("爆冷")
    translated_round = round_zh(match.round_name) or ""
    if translated_round in _ROUND_PTS:
        reasons.append(translated_round)
    if went_to_deciding_set(match):
        reasons.append("决胜盘")
    return reasons or ["焦点对阵"]


def hotspot_candidates(
    matches: list[Match],
    *,
    now: datetime | None = None,
    max_age_hours: int = 10,
    limit: int = 2,
) -> list[Match]:
    """选出仍在传播窗口内的已完赛热点，默认每批最多两场。"""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=max_age_hours)

    eligible_by_id: dict[tuple[str, str], Match] = {}
    for match in matches:
        if not match.status.is_final or hotspot_score(match) < HOTSPOT_THRESHOLD:
            continue
        if match.start_utc is not None:
            start = match.start_utc
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if start.astimezone(timezone.utc) < cutoff:
                continue
        key = (match.tour.value, match.match_id)
        current = eligible_by_id.get(key)
        if current is None or hotspot_score(match) > hotspot_score(current):
            eligible_by_id[key] = match
    return sorted(eligible_by_id.values(), key=hotspot_score, reverse=True)[:limit]


def _trim_title(text: str, limit: int = 20) -> str:
    text = text.strip().replace(" ", "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _winner_and_loser(match: Match) -> tuple[str, str]:
    winners = match.winner_players() or []
    losers = match.loser_players() or []
    winner = player_zh(winners[0].name) if winners else "比赛"
    loser = player_zh(losers[0].name) if losers else "对手"
    return winner, loser


def _scheduled_hook(match: Match) -> str:
    chinese = _chinese_player(match)
    if chinese is not None:
        opponents = [
            player
            for player in match.home + match.away
            if player is not chinese and not is_chinese_player(player)
        ]
        seeded = next((player for player in opponents if player.seed), None)
        name = player_zh(chinese.name)
        if seeded is not None:
            return f"{name}首战就遇{seeded.seed}号种子"
        time = fmt_time_beijing(match.start_utc)
        return f"{name}{time}出战" if time != "待定" else f"{name}今日出战"
    left = player_zh(match.home[0].name) if match.home else "焦点"
    right = player_zh(match.away[0].name) if match.away else "对决"
    return f"{left}对{right}，今晚必看"


def hotspot_title_candidates(match: Match) -> list[str]:
    """返回三种叙事角度；第一条作为默认标题。"""
    if not match.status.is_final:
        primary = _scheduled_hook(match)
        group = group_by_tournament([match])[0]
        time = fmt_time_beijing(match.start_utc)
        alternatives = [
            f"{time if time != '待定' else '今晚'}这场值得看",
            f"{group.compact_level}{match_round_display(match)}焦点战",
        ]
    else:
        winner, loser = _winner_and_loser(match)
        chinese_winner = _chinese_player(match, winner=True)
        chinese_loser = _chinese_player(match, winner=False)
        translated_round = round_zh(match.round_name) or ""
        if chinese_winner is not None:
            verb = "夺冠" if translated_round == "决赛" else "赢下关键战"
            primary = f"{player_zh(chinese_winner.name)}{verb}"
        elif chinese_loser is not None:
            primary = f"{player_zh(chinese_loser.name)}止步{translated_round or '本轮'}"
        elif is_upset(match):
            primary = f"{winner}爆冷淘汰{loser}"
        elif translated_round == "决赛":
            primary = f"{winner}夺冠"
        elif went_to_deciding_set(match):
            primary = f"{winner}鏖战过关"
        else:
            primary = f"{winner}直落两盘晋级"
        group = group_by_tournament([match])[0]
        alternatives = [
            f"{winner}赢下{group.name_zh}{translated_round}",
            f"{group.compact_level}{translated_round}刚刚出结果",
        ]

    output: list[str] = []
    fallbacks = (
        ["今晚这场值得看", "开赛前一分钟看懂"]
        if not match.status.is_final
        else ["一分钟看懂这场球", "刚刚结束的关键一战"]
    )
    for candidate in [primary] + alternatives + fallbacks:
        title = _trim_title(candidate)
        if title and title not in output:
            output.append(title)
    return output[:3]


def _tags(match: Match) -> list[str]:
    group = group_by_tournament([match])[0]
    tags = ["#网球", "#网球时差", f"#{match.tour.value}", f"#{group.name_zh}"]
    for player in match.home + match.away:
        name = player_zh(player.name)
        if name != player.name or not name.isascii():
            tags.append(f"#{name}")
    output: list[str] = []
    for tag in tags:
        if tag not in output:
            output.append(tag)
    return output[:8]


def hotspot_post(match: Match) -> str:
    """小红书单场成稿；首行标题，后续可直接复制发布。"""
    title = hotspot_title_candidates(match)[0]
    group = group_by_tournament([match])[0]
    label = f"{group.compact_title}·{match_round_display(match)}".rstrip("·")
    lines = [title, "", f"刚刚结束｜{label}"]
    if match.status.is_final:
        lines.extend([result_line(match), f"一句看懂：{result_insight(match)}"])
        if is_upset(match):
            question = "这场冷门，你觉得转折发生在哪一盘？"
        elif is_chinese_involved(match):
            question = "下一轮还要继续跟吗？评论区留下球员名。"
        else:
            question = "这场结果符合你的预期吗？"
    else:
        lines[2] = f"今晚焦点｜{label}"
        lines.extend(
            [
                f"{fmt_time_beijing(match.start_utc)}｜"
                f"{side_display(match.home, with_seed=False)} vs "
                f"{side_display(match.away, with_seed=False)}",
                f"为什么看：{schedule_insight(match)}",
            ]
        )
        question = "今晚只选一场，你会看这场吗？"
    lines.extend(["", question, "", " ".join(_tags(match))])
    return "\n".join(lines)
