"""比赛重要性评分：全自动选题的核心规则.

用于：昨夜焦点三场的挑选、今晚看球的推荐与熬夜指数、冷门检测、标题自动选择。
规则可调，全部集中在这里。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..digest import Digest
from ..models import Match
from ..zh import player_zh
from ..zh.terms import round_zh
from ..zh.tournaments import tournament_level
from .common import is_chinese_involved

LEVEL_PTS = {
    "GS": 50,
    "Finals": 40,
    "M1000": 30,
    "W1000": 30,
    "ATP500": 15,
    "WTA500": 15,
    "ATP250": 8,
    "WTA250": 8,
    "TeamCup": 10,
}

ROUND_PTS = {
    "决赛": 30,
    "半决赛": 20,
    "四分之一决赛": 10,
    "16强赛": 5,
    "第四轮": 5,
}


# A deliberately small set for feeds that occasionally omit rankings. Rankings
# remain the primary signal; this list only keeps established headliners from
# disappearing when one upstream field is temporarily unavailable.
HEADLINER_NAMES = {
    "Carlos Alcaraz",
    "Novak Djokovic",
    "Jannik Sinner",
    "Alexander Zverev",
    "Daniil Medvedev",
    "Aryna Sabalenka",
    "Iga Swiatek",
    "Coco Gauff",
    "Qinwen Zheng",
    "Naomi Osaka",
    "Emma Raducanu",
    "Stan Wawrinka",
}

TOUR_FOCUS_LEVELS = {
    "GS",
    "Finals",
    "M1000",
    "W1000",
    "ATP500",
    "WTA500",
    "ATP250",
    "WTA250",
}

LEAD_ROUND_PTS = {
    "决赛": 35,
    "半决赛": 25,
    "四分之一决赛": 15,
    "八分之一决赛": 8,
    "16强赛": 8,
    "第四轮": 8,
}


@dataclass(frozen=True)
class LeadStoryBreakdown:
    """Auditable components used to choose the day's single lead story."""

    event: int = 0
    stage: int = 0
    china: int = 0
    headliner: int = 0
    evidence: int = 0
    result: int = 0
    format: int = 0

    @property
    def total(self) -> int:
        return sum(
            (
                self.event,
                self.stage,
                self.china,
                self.headliner,
                self.evidence,
                self.result,
                self.format,
            )
        )


@dataclass(frozen=True)
class LeadStorySelection:
    """The selected match plus a human-readable editorial rationale."""

    match: Match
    breakdown: LeadStoryBreakdown
    reasons: tuple[str, ...]

    @property
    def score(self) -> int:
        return self.breakdown.total

    @property
    def reason(self) -> str:
        return "；".join(self.reasons)


def _level_of(m: Match) -> str | None:
    return m.tournament.level or tournament_level(m.tournament.name, m.tour.value)


def is_tour_focus_match(m: Match) -> bool:
    """Return whether a match belongs in the daily public-facing digest."""
    return _level_of(m) in TOUR_FOCUS_LEVELS


def _headliner_points(match: Match) -> tuple[int, str | None]:
    players = match.home + match.away
    top_rank = min((p.rank for p in players if p.rank is not None), default=None)
    top_seed = min((p.seed for p in players if p.seed is not None), default=None)
    named = next((p for p in players if p.name in HEADLINER_NAMES), None)
    if top_rank is not None and top_rank <= 10:
        return 25, "有世界前10球员"
    if named is not None:
        return 22, f"有知名球员{player_zh(named.name)}"
    if (top_rank is not None and top_rank <= 30) or (
        top_seed is not None and top_seed <= 8
    ):
        return 14, "有前30或高排位种子"
    return 0, None


def _evidence_points(match: Match) -> tuple[int, str | None]:
    if match.editorial_url:
        source = match.editorial_source or "权威媒体"
        official_tokens = ("ATP", "WTA", "ITF", "温网", "澳网", "法网", "美网")
        if any(token.lower() in source.lower() for token in official_tokens):
            return 20, f"有{source}原文支撑"
        return 15, f"有{source}来源链接"
    if match.stats is not None and match.stats.source_url:
        return 14, f"有{match.stats.source}技术统计"
    if match.editorial_note and match.editorial_source:
        return 6, f"有{match.editorial_source}证据摘要"
    return 0, None


def lead_story_breakdown(match: Match) -> tuple[LeadStoryBreakdown, tuple[str, ...]]:
    """Score one lead-story candidate without rewarding an upset label.

    The components intentionally differ from ``match_score``: a surprise result
    is not a content pillar, while a source-backed Chinese or star match is.
    """
    level = _level_of(match) or ""
    event = LEVEL_PTS.get(level, 0)
    stage = LEAD_ROUND_PTS.get(round_zh(match.round_name) or "", 0)
    china = 45 if is_chinese_involved(match) else 0
    headliner, headliner_reason = _headliner_points(match)
    evidence, evidence_reason = _evidence_points(match)
    result = 8 if match.status.is_final else 4 if match.status.value == "live" else 0
    format_points = -35 if match.is_doubles else 0

    reasons: list[str] = []
    if china:
        reasons.append("中国球员相关")
    if headliner_reason:
        reasons.append(headliner_reason)
    if stage:
        reasons.append(f"处于{round_zh(match.round_name)}")
    if event:
        reasons.append(f"赛事级别为{level}")
    if evidence_reason:
        reasons.append(evidence_reason)
    if match.status.is_final:
        reasons.append("已有完整赛果可复盘")
    if match.is_doubles:
        reasons.append("双打题材降权")

    return (
        LeadStoryBreakdown(
            event=event,
            stage=stage,
            china=china,
            headliner=headliner,
            evidence=evidence,
            result=result,
            format=format_points,
        ),
        tuple(reasons),
    )


def select_lead_story(digest: Digest) -> LeadStorySelection | None:
    """Select one explainable editorial lead from the strongest content pool.

    A daily edition first recaps completed singles. Only when there is no such
    result does it move to live, upcoming, and finally doubles. This prevents an
    ordinary evening fixture from displacing the actual news of the day.
    """
    pools = (
        [
            match for match in digest.results
            if match.is_singles and is_tour_focus_match(match)
        ],
        [
            match for match in digest.live
            if match.is_singles and is_tour_focus_match(match)
        ],
        [
            match for match in digest.schedule
            if match.is_singles and is_tour_focus_match(match)
        ],
        [
            match for match in digest.results + digest.live + digest.schedule
            if is_tour_focus_match(match)
        ],
    )
    candidates = next((pool for pool in pools if pool), [])
    if not candidates:
        return None

    scored = []
    for index, match in enumerate(candidates):
        breakdown, reasons = lead_story_breakdown(match)
        scored.append((breakdown.total, -index, match, breakdown, reasons))
    _, _, match, breakdown, reasons = max(scored, key=lambda item: item[:2])
    return LeadStorySelection(match=match, breakdown=breakdown, reasons=reasons)


def is_upset(m: Match) -> bool:
    """冷门（从严）：种子落马，或 Top30 被排名低 30+ 位的选手掀翻.

    250 赛里排名差 30 位是常态，标准太松会让"爆冷"标签泛滥失去意义。
    """
    if m.winner is None:
        return False
    winners = m.winner_players() or []
    losers = m.loser_players() or []
    if not winners or not losers:
        return False
    w, l = winners[0], losers[0]
    if l.seed and not w.seed:
        return True
    if l.seed and w.seed and w.seed - l.seed >= 8:
        return True
    if w.rank and l.rank and l.rank <= 30 and w.rank - l.rank >= 30:
        return True
    return False


def went_to_deciding_set(m: Match) -> bool:
    """最后一盘开打前双方盘数相等，才算真正的决胜盘。"""
    decided = [item for item in m.sets if item.home != item.away]
    if len(decided) < 2:
        return False
    home_wins = sum(item.home > item.away for item in decided[:-1])
    away_wins = sum(item.away > item.home for item in decided[:-1])
    return home_wins == away_wins


def deciding_set_tiebreak(m: Match) -> str | None:
    """真正决胜盘以抢七或抢十结束时返回对应名称。"""
    if not went_to_deciding_set(m):
        return None
    decided = [item for item in m.sets if item.home != item.away]
    last = decided[-1]
    if {last.home, last.away} == {1, 0}:
        return "抢十"
    if last.home_tiebreak is not None and last.away_tiebreak is not None:
        return "抢七"
    return None


def match_score(m: Match, cn_boost: bool = True) -> int:
    """比赛重要性总分，越高越值得报道.

    cn_boost=False 时不给中国球员场次加权（赛果速递卡用：
    中国军团有专页，速递页按比赛本身分量排序，出现时只打标签）。
    """
    s = 0
    # V1 头条规则：中国相关性固定 +35（与爆冷同级），单场只加一次，
    # 不再设置"中国比赛永远第一"的旁路（见 docs/xiaohongshu-playbook.md §2.2）
    if cn_boost and is_chinese_involved(m):
        s += 35
    s += LEVEL_PTS.get(_level_of(m) or "", 0)
    r = round_zh(m.round_name) or ""
    s += ROUND_PTS.get(r, 0)
    # 球星与对决质量
    seeds = [p.seed for p in m.home + m.away if p.seed]
    ranks = [p.rank for p in m.home + m.away if p.rank]
    if any(x and x <= 4 for x in seeds) or any(x <= 10 for x in ranks):
        s += 25
    if len(seeds) >= 2:  # 种子对决
        s += 15
    if is_upset(m):
        s += 35
    # 激烈程度：决胜盘 / 抢十
    if went_to_deciding_set(m):
        s += 10
    if any({x.home, x.away} == {1, 0} for x in m.sets):
        s += 5
    # 双打是基础内容形态惩罚，与国籍无关；中国相关性仍只通过上面的
    # 单次 +35 体现，否则中国双打相对其他双打会形成隐含 +75 旁路。
    if m.is_doubles:
        s -= 40
    return s


def top_results(matches: list[Match], n: int = 3, cn_boost: bool = True) -> list[Match]:
    """昨夜焦点：评分最高的 n 场已完赛单打（cn_boost 见 match_score）."""
    finished = [
        m for m in matches
        if m.status.is_final and is_tour_focus_match(m)
    ]
    return sorted(
        finished, key=lambda m: match_score(m, cn_boost=cn_boost), reverse=True
    )[:n]


def top_schedule(matches: list[Match], n: int = 5) -> list[Match]:
    """今晚看球：评分最高的 n 场未开赛."""
    upcoming = [m for m in matches if not m.status.is_final]
    return sorted(upcoming, key=match_score, reverse=True)[:n]


def tonight_event_focus(
    matches: list[Match], min_matches: int = 2, max_matches: int = 5
) -> list[list[Match]]:
    """Select 2-5 matches per event for tour-level 250+ tournaments only."""
    buckets: dict[str, list[Match]] = {}
    for match in matches:
        if match.status.is_final:
            continue
        key = " ".join(match.tournament.name.casefold().split())
        buckets.setdefault(key, []).append(match)

    pages: list[tuple[int, int, str, list[Match]]] = []
    for event_matches in buckets.values():
        level = _level_of(event_matches[0])
        if level not in TOUR_FOCUS_LEVELS:
            continue

        singles = sorted(
            (match for match in event_matches if match.is_singles),
            key=match_score,
            reverse=True,
        )
        doubles = sorted(
            (match for match in event_matches if match.is_doubles),
            key=match_score,
            reverse=True,
        )
        chosen = singles[:max_matches]
        if len(chosen) < min_matches:
            chosen.extend(doubles[: min_matches - len(chosen)])
        if len(chosen) < min_matches:
            continue
        best_score = max(match_score(match) for match in chosen)
        pages.append(
            (
                0,
                -best_score,
                event_matches[0].tournament.name,
                chosen[:max_matches],
            )
        )
    return [row[3] for row in sorted(pages, key=lambda row: row[:3])]


def tonight_focus(matches: list[Match], min_n: int = 3, max_n: int = 5) -> list[Match]:
    """今晚焦点：优先中国/名将，同时覆盖最多四项赛事."""
    singles = [
        m
        for m in matches
        if m.is_singles
        and not m.status.is_final
        and is_tour_focus_match(m)
    ]

    def known(match: Match) -> bool:
        if is_chinese_involved(match):
            return True
        players = match.home + match.away
        return any(
            (p.rank is not None and p.rank <= 30)
            or (p.seed is not None and p.seed <= 8)
            for p in players
        )

    ranked = sorted(singles, key=match_score, reverse=True)
    preferred = [m for m in ranked if known(m)]
    ordered = preferred + [m for m in ranked if m not in preferred]
    target = min(max_n, len(ranked))
    if target < min_n:
        target = len(ranked)

    def event_key(match: Match) -> str:
        return " ".join(match.tournament.name.casefold().split())

    selected: list[Match] = []
    selected_ids: set[str] = set()
    event_counts: dict[str, int] = {}
    # First pass gives the reader a useful cross-tour slate rather than five
    # matches from whichever event happens to contain the most Chinese players.
    for match in ordered:
        key = event_key(match)
        if key in event_counts or len(event_counts) >= min(4, target):
            continue
        selected.append(match)
        selected_ids.add(match.match_id)
        event_counts[key] = 1
        if len(selected) >= target:
            return selected

    # Second pass restores depth for the strongest event, capped at two matches.
    for match in ordered:
        if len(selected) >= target:
            break
        key = event_key(match)
        if match.match_id in selected_ids or event_counts.get(key, 0) >= 2:
            continue
        selected.append(match)
        selected_ids.add(match.match_id)
        event_counts[key] = event_counts.get(key, 0) + 1
    return selected


def editorial_tonight_focus(
    matches: list[Match], min_n: int = 3, max_n: int = 5
) -> list[Match]:
    """Prefer reviewed context, then fill a useful three-to-five match list."""
    candidates = tonight_focus(matches, min_n=min_n, max_n=max_n)
    reviewed = [match for match in candidates if match.editorial_url]
    ordered = reviewed + [match for match in candidates if match not in reviewed]
    return ordered


def stay_up_stars(m: Match) -> int:
    """熬夜指数 1-5 星."""
    s = match_score(m)
    if s >= 100:
        return 5
    if s >= 60:
        return 4
    if s >= 35:
        return 3
    if s >= 15:
        return 2
    return 1


# 闪发（战报）触发级别：大满贯 / 1000 / 年终
FLASH_LEVELS = {"GS", "M1000", "W1000", "Finals"}


def flash_candidates(matches: list[Match]) -> list[Match]:
    """值得即时战报的已完赛比赛：中国球员场次，或高级别赛事单打决赛."""
    out = []
    for m in matches:
        if not m.status.is_final:
            continue
        if is_chinese_involved(m):
            out.append(m)
            continue
        r = round_zh(m.round_name) or ""
        if m.is_singles and r == "决赛" and (_level_of(m) in FLASH_LEVELS):
            out.append(m)
    return out


def find_upset(matches: list[Match]) -> Match | None:
    """昨夜最大冷门（只看单打）."""
    upsets = [
        m for m in matches if m.status.is_final and m.is_singles and is_upset(m)
    ]
    if not upsets:
        return None
    return max(upsets, key=match_score)
