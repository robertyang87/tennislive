"""标题全自动生成与选择：用可解释评分挑当天最值得点击的故事."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from ..zh.terms import discipline_zh, round_zh
from .common import is_chinese_involved, match_round_display
from .rating import (
    deciding_set_tiebreak,
    find_upset,
    is_upset,
    match_score,
    select_lead_story,
    top_results,
    top_schedule,
)
from .story import china_summary, chinese_side_won, is_chinese_player


@dataclass(frozen=True)
class _Candidate:
    text: str
    score: int
    kind: str


@dataclass(frozen=True)
class _HistoricalProfile:
    peak_rank: int
    legacy: str
    source_url: str


# Curated, source-backed context for cover hooks. Keep this list deliberately
# small: an absent profile falls back to match facts instead of invented lore.
_HISTORICAL_PROFILES = {
    "Stefanos Tsitsipas": _HistoricalProfile(
        peak_rank=3,
        legacy="两进大满贯决赛",
        source_url="https://www.atptour.com/en/players/tsitsipas-stefanos/te51/bio",
    ),
}


def _cn_side(players) -> bool:
    return any(is_chinese_player(p) for p in players)


def _flat_round(m) -> str:
    return (match_round_display(m) or "").replace("·", "")


_NEXT_ROUND = {
    "第一轮": "第二轮",
    "64强赛": "32强赛",
    "第二轮": "第三轮",
    "32强赛": "16强赛",
    "第三轮": "第四轮",
    "第四轮": "四分之一决赛",
    "16强赛": "四分之一决赛",
    "四分之一决赛": "半决赛",
    "半决赛": "决赛",
}


def _advance_round(m) -> str:
    current = round_zh(m.round_name) or ""
    upcoming = _NEXT_ROUND.get(current, "下一轮")
    discipline = discipline_zh(m.discipline) or ""
    return f"{discipline}{upcoming}"


def cover_fact_bundle(m, *, source: str = "") -> dict:
    """封面允许使用的比赛事实与人工审核历史档案。"""
    winner = (m.winner_players() or [None])[0]
    profile = _HISTORICAL_PROFILES.get(winner.name) if winner is not None else None
    players = [
        {
            "name": player.name,
            "display_name": player_zh(player.name),
            "country": player.country,
            "seed": player.seed,
            "rank": player.rank,
        }
        for player in m.home + m.away
    ]
    sets = [
        {
            "home": item.home,
            "away": item.away,
            "home_tiebreak": item.home_tiebreak,
            "away_tiebreak": item.away_tiebreak,
        }
        for item in m.sets
    ]
    number_sources = [
        m.round_name or "",
        m.tournament.name,
        m.tournament.level or "",
        m.start_utc.isoformat() if m.start_utc is not None else "",
        fmt_time_beijing(m.start_utc),
    ]
    number_sources.extend(
        str(value)
        for player in players
        for value in (player["seed"], player["rank"])
        if value is not None
    )
    number_sources.extend(
        str(value)
        for item in sets
        for value in item.values()
        if value is not None
    )
    # Reviewed editorial notes may contribute stable time spans or career
    # counts. They only enter the cover fact gate when a source URL is kept.
    if m.editorial_note and m.editorial_url:
        number_sources.append(m.editorial_note)
    historical = None
    if profile is not None:
        historical = {
            "peak_rank": profile.peak_rank,
            "legacy": profile.legacy,
            "source_url": profile.source_url,
        }
        number_sources.extend((str(profile.peak_rank), profile.legacy))
    return {
        "match_id": m.match_id,
        "source": source,
        "tournament": m.tournament.name,
        "round": m.round_name,
        "status": m.status.value,
        "winner": m.winner,
        "players": players,
        "sets": sets,
        "historical_profile": historical,
        "allowed_numbers": sorted(
            set(re.findall(r"\d+", " ".join(number_sources)))
        ),
    }


def cover_fact_errors(m, main: str, secondary: str) -> list[str]:
    """检查封面完整数字声明和主角姓名是否能回溯到证据包。"""
    bundle = cover_fact_bundle(m)
    allowed_numbers = set(bundle["allowed_numbers"])
    claimed_numbers = set(re.findall(r"\d+", f"{main} {secondary}"))
    errors = [
        f"封面数字无证据: {number}"
        for number in sorted(claimed_numbers - allowed_numbers)
    ]
    if m.winner is not None:
        names = {player["display_name"] for player in bundle["players"]}
        if not any(name and name in main for name in names):
            errors.append("封面主标题未包含证据包内球员")
    return errors


def _cn_match_headline(m) -> str | None:
    w = m.winner_players()
    if not w:
        return None
    r = _flat_round(m)
    if chinese_side_won(m):
        cn_winner = next((p for p in w if is_chinese_player(p)), w[0])
        if r.endswith("决赛") and "半" not in r and "四" not in r:
            return f"{player_zh(cn_winner.name)}夺冠！"
        return f"{player_zh(cn_winner.name)}晋级{_advance_round(m)}"
    loser = next(
        (p for p in (m.loser_players() or []) if is_chinese_player(p)), None
    )
    if loser is not None:
        return f"{player_zh(loser.name)}止步{r or '本轮'}"
    return None


def _cn_candidates(digest: Digest) -> list[_Candidate]:
    """V1 §2.2：标题分 = match_score（其中中国相关性已固定 +35）.

    只保留 ±10 内的编辑偏好（胜场 > 出战预告 > 失利），不再用手工基分
    制造"中国场次永远第一"的旁路——大满贯决赛可以正常压过常规中国胜场。
    """
    candidates: list[_Candidate] = []
    for m in digest.results:
        if not is_chinese_involved(m):
            continue
        text = _cn_match_headline(m)
        if not text:
            continue
        nudge = 10 if chinese_side_won(m) else 0
        candidates.append(_Candidate(text, match_score(m) + nudge, "china"))

    for m in digest.schedule:
        if not (is_chinese_involved(m) and m.is_singles):
            continue
        p = next((p for p in m.home + m.away if is_chinese_player(p)), None)
        if p is None:
            continue
        t = fmt_time_beijing(m.start_utc)
        when = f"{t}出战" if t != "待定" else "今日出战"
        candidates.append(
            _Candidate(f"{player_zh(p.name)}{when}", match_score(m) + 5, "china")
        )

    summary = china_summary(digest)
    if summary:
        wins = sum(
            1 for m in digest.results if is_chinese_involved(m) and chinese_side_won(m)
        )
        # 汇总句只在没有更强的单场故事时兜底，分数刻意压低
        candidates.append(_Candidate(summary, 20 + wins * 5, "china-summary"))
    return candidates


def cn_headline(digest: Digest) -> str | None:
    candidates = _cn_candidates(digest)
    return max(candidates, key=lambda c: c.score).text if candidates else None


def upset_headline(digest: Digest) -> str | None:
    m = find_upset(digest.results)
    if m is None:
        return None
    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w or not l:
        return None
    return f"爆冷！{player_zh(w.name)}掀翻{player_zh(l.name)}"


def star_headline(digest: Digest) -> str | None:
    for m in top_results([x for x in digest.results if x.is_singles], 3):
        if is_chinese_involved(m):
            continue  # 中国角度另有候选
        w = m.winner_players()
        if w:
            from .common import group_by_tournament

            g = group_by_tournament([m])[0]
            r = _flat_round(m)
            if r == "决赛":
                return f"{player_zh(w[0].name)}问鼎{g.name_zh}"
            return f"{player_zh(w[0].name)}晋级{g.name_zh}{_advance_round(m)}"
    tonight = top_schedule([x for x in digest.schedule if x.is_singles], 1)
    if tonight:
        m = tonight[0]
        a = player_zh(m.home[0].name)
        b = player_zh(m.away[0].name)
        return f"今晚焦点：{a}对阵{b}"
    return None


def _tonight_headline(digest: Digest) -> str | None:
    """③ 今晚悬念：来自可核实的今晚焦点对阵."""
    tonight = top_schedule([x for x in digest.schedule if x.is_singles], 1)
    if not tonight:
        return None
    m = tonight[0]
    a, b = player_zh(m.home[0].name), player_zh(m.away[0].name)
    return f"今晚焦点：{a}对阵{b}"


def daily_lead_match(digest: Digest):
    """唯一头条入口，选择逻辑与可解释分项统一由 rating 管理。"""
    selection = select_lead_story(digest)
    return selection.match if selection is not None else None


def _match_title(match) -> str:
    if match.status.is_final:
        return cover_result_hook(match)[0]
    chinese = next(
        (player for player in match.home + match.away if is_chinese_player(player)),
        None,
    )
    if chinese is not None:
        time = fmt_time_beijing(match.start_utc)
        when = f"{time}出战" if time != "待定" else "今日出战"
        return f"{player_zh(chinese.name)}{when}"
    left = player_zh(match.home[0].name) if match.home else "焦点"
    right = player_zh(match.away[0].name) if match.away else "对决"
    return f"今晚焦点：{left}对阵{right}"


def _trim_candidate(text: str, limit: int = 20) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def title_candidates(digest: Digest) -> list[str]:
    """V1 §3.1：固定输出 3 个候选——事件意义 / 人物处境 / 今晚悬念.

    每个 ≤20 字且可被证据支持；素材不足时用中性速览句补足，不硬造。
    """
    lead = daily_lead_match(digest)
    all_matches = digest.results + digest.live + digest.schedule
    chinese = sorted(
        [match for match in all_matches if is_chinese_involved(match)],
        key=match_score,
        reverse=True,
    )
    tonight = top_schedule(
        [match for match in digest.schedule if match.is_singles], 1
    )
    other_results = top_results(
        [match for match in digest.results if match.is_singles],
        len(digest.results),
        cn_boost=True,
    )

    out: list[str] = []
    used_matches: set[str] = set()

    def add_match(match) -> None:
        if match is None or match.match_id in used_matches:
            return
        used_matches.add(match.match_id)
        add_text(_match_title(match))

    def add_text(text: str | None) -> None:
        if not text:
            return
        candidate = _trim_candidate(text)
        if candidate not in out:
            out.append(candidate)

    add_match(lead)                       # ① 当日真正头条
    add_match(chinese[0] if chinese else None)  # ② 中国焦点（若与头条不同）
    add_match(tonight[0] if tonight else None)  # ③ 今晚悬念
    for match in other_results:
        if len(out) >= 3:
            break
        add_match(match)
    for filler in (
        china_summary(digest),
        "每日赛程赛果速览",
        "昨夜赛果与今晚看点",
        "网球晨报：今日一页看懂",
    ):
        if len(out) >= 3:
            break
        add_text(filler)
    return out[:3]


def cover_highlights(digest: Digest) -> tuple[str, str]:
    """Main cover hook plus a distinct secondary proof point."""
    lead = daily_lead_match(digest)
    candidates = title_candidates(digest)
    if lead is not None and lead.status.is_final:
        primary, lead_secondary = cover_result_hook(lead)
    else:
        primary = _match_title(lead) if lead is not None else candidates[0]
        lead_secondary = ""
    secondary = next((h for h in candidates[1:] if h != primary), "")
    if lead_secondary:
        secondary = lead_secondary
    if not secondary:
        secondary = "昨夜赛果与今晚重点，一页看懂"
    return primary, secondary


def pick_headline_auto(digest: Digest) -> str:
    return title_candidates(digest)[0]


def flash_headline(m) -> str:
    """单场比赛的闪发标题，如 '郑钦文晋级！雅典公开赛八强'."""
    from .common import group_by_tournament

    g = group_by_tournament([m])[0]
    r = _flat_round(m)
    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w:
        return f"{g.name_zh}{r}战报"
    is_final = r.endswith("决赛") and "半" not in r and "四" not in r
    cn_won = _cn_side(m.winner_players() or [])
    cn_lost = _cn_side(m.loser_players() or [])
    if cn_won:
        # 双打时用中国球员的名字打头
        cn_w = next(
            (p for p in (m.winner_players() or []) if _cn_side([p])), w
        )
        if is_final:
            return f"{player_zh(cn_w.name)}夺冠！{g.name_zh}登顶"
        return f"{player_zh(cn_w.name)}晋级{_advance_round(m)}！{g.name_zh}过关"
    if cn_lost and l is not None:
        return f"{player_zh(l.name)}止步{g.name_zh}{r or '本轮'}"
    if is_final:
        return f"{player_zh(w.name)}问鼎{g.name_zh}"
    return f"{player_zh(w.name)}晋级{g.name_zh}{_advance_round(m)}"


def _whitelist_meaning(m) -> str | None:
    """V1 意义句白名单的机械模式：证据不足返回 None（调用方降级为结果句）.

    仅覆盖可从当日数据机械验证的四类：退赛、爆冷、先丢一盘逆转、
    决胜盘抢七/抢十。退赛不得推断原因；历史类表述走人工档案。
    """
    from ..models import MatchStatus

    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w or not l:
        return None
    wn, ln = player_zh(w.name), player_zh(l.name)
    r = _flat_round(m)
    # 决赛的赢家措辞是"夺冠"而非"晋级"——冠军没有下一轮
    is_final = r.endswith("决赛") and "半" not in r and "四" not in r

    if m.status is MatchStatus.RETIRED:
        if is_final:
            return f"{ln}退赛，{wn}夺冠"
        return f"{ln}退赛，{wn}晋级{_advance_round(m)}"
    if is_upset(m):
        return f"爆冷：{wn}掀翻{ln}"
    sets = m.sets or []
    decided = [s for s in sets if s.home != s.away]
    if len(decided) >= 2:
        first = decided[0]
        winner_is_home = m.winner == 0
        lost_first = (first.home < first.away) if winner_is_home else (first.home > first.away)
        if lost_first:
            return f"{wn}先丢一盘，逆转{'夺冠' if is_final else '晋级'}"
        how = deciding_set_tiebreak(m)
        if how:
            return f"决胜盘{how}，{wn}{'夺冠' if is_final else '惊险过关'}"
    return None


def cover_result_hook(m) -> tuple[str, str]:
    """Turn the lead result into a significance-first cover hook.

    Historical claims come only from reviewed profiles. Everyone else keeps the
    conservative, match-derived headline and insight path.
    """
    from .story import result_insight

    winner = (m.winner_players() or [None])[0]
    if winner is None:
        return flash_headline(m), result_insight(m)

    profile = _HISTORICAL_PROFILES.get(winner.name)
    if profile is None:
        mechanical = _whitelist_meaning(m)
        if mechanical:
            return mechanical, result_insight(m)
        return flash_headline(m), result_insight(m)

    name = player_zh(winner.name)
    round_name = _flat_round(m)
    is_final = round_name.endswith("决赛") and "半" not in round_name and "四" not in round_name
    if is_final and m.editorial_url and m.editorial_note:
        wait = re.search(r"时隔\s*(\d+)\s*个?月", m.editorial_note)
        if wait:
            months = wait.group(1)
            return (
                f"时隔{months}个月，{name}再夺冠",
                f"{profile.legacy}仍是过去；这座奖杯为低谷期写下新的起点",
            )

    if is_final:
        return (
            f"{profile.legacy}，{name}再迎冠军夜",
            "这不只是一场决赛胜利，更是生涯坐标上的新节点",
        )
    return flash_headline(m), f"{profile.legacy}再度过关，胜负之外更要看状态走向"
