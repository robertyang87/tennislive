"""渲染共用逻辑：比赛 → 中文展示字符串、分组与排序."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..models import Match, MatchStatus, Player, Tour
from ..timeutil import fmt_time_beijing
from ..zh import country_flag, player_zh, tournament_zh
from ..zh.terms import discipline_zh, round_zh
from ..zh.tournaments import tournament_level

# 级别排序权重（越小越靠前）
LEVEL_ORDER = {
    "GS": 0,
    "Finals": 1,
    "M1000": 2,
    "W1000": 2,
    "ATP500": 3,
    "WTA500": 3,
    "ATP250": 4,
    "WTA250": 4,
    "TeamCup": 5,
    None: 6,
}

LEVEL_BADGE = {
    "GS": "大满贯",
    "M1000": "1000大师赛",
    "W1000": "WTA 1000",
    "ATP500": "ATP 500",
    "WTA500": "WTA 500",
    "ATP250": "ATP 250",
    "WTA250": "WTA 250",
    "Finals": "年终总决赛",
    "TeamCup": "团体赛",
}

# 轮次排序权重（决赛最前）
_ROUND_ORDER = [
    ("决赛", 0),
    ("半决赛", 1),
    ("四分之一决赛", 2),
    ("16强赛", 3),
    ("32强赛", 4),
    ("64强赛", 5),
    ("第四轮", 3),
    ("第三轮", 4),
    ("第二轮", 5),
    ("第一轮", 6),
    ("小组赛", 4),
    ("资格赛", 8),
]


def round_order(round_name_zh: str | None) -> int:
    if not round_name_zh:
        return 7
    for key, order in _ROUND_ORDER:
        if key == round_name_zh:
            return order
    return 7


def player_display(p: Player, with_flag: bool = True, with_seed: bool = True) -> str:
    """'🇮🇹 辛纳' 或 '🇮🇹 [1]辛纳'."""
    name = player_zh(p.name)
    parts = []
    if with_flag:
        flag = country_flag(p.country)
        if flag:
            parts.append(flag)
    if with_seed and p.seed:
        parts.append(f"[{p.seed}]{name}")
    else:
        parts.append(name)
    return " ".join(parts)


def side_display(players: list[Player], with_flag: bool = True, with_seed: bool = True) -> str:
    """单打给单人，双打给 'A/B' 组合."""
    if len(players) == 1:
        return player_display(players[0], with_flag, with_seed)
    return "/".join(player_display(p, with_flag=with_flag, with_seed=False) for p in players)


def status_display(m: Match) -> str:
    if m.status == MatchStatus.SCHEDULED:
        return fmt_time_beijing(m.start_utc)
    if m.status == MatchStatus.LIVE:
        return f"进行中 {m.status_detail or ''}".strip()
    if m.status == MatchStatus.RETIRED:
        return "完赛(退赛)"
    if m.status == MatchStatus.WALKOVER:
        return "不战而胜"
    if m.status == MatchStatus.CANCELLED:
        return "已取消"
    if m.status == MatchStatus.POSTPONED:
        return "推迟"
    return "完赛"


def result_line(m: Match) -> str:
    """赛果一行：'[1]辛纳 2-0 [5]德约科维奇（6-4 7-6(3)）'，从胜者视角."""
    if m.winner is None:
        home_s, away_s = side_display(m.home), side_display(m.away)
        score = m.score_display(from_winner=False)
        return f"{home_s} vs {away_s}" + (f"（{score}）" if score else "")
    w = m.winner_players() or []
    l = m.loser_players() or []
    w_sets = sum(
        1
        for s in m.sets
        if (s.home > s.away) == (m.winner == 0) and s.home != s.away
    )
    l_sets = len([s for s in m.sets if s.home != s.away]) - w_sets
    score = m.score_display(from_winner=True)
    line = f"{side_display(w)} {w_sets}-{l_sets} {side_display(l)}"
    extras = []
    if score:
        extras.append(score)
    if m.status == MatchStatus.RETIRED:
        extras.append("对手退赛")
    elif m.status == MatchStatus.WALKOVER:
        extras.append("W.O.")
    if extras:
        line += f"（{' '.join(extras)}）"
    return line


def schedule_line(m: Match) -> str:
    """赛程一行：'14:30 辛纳 vs 德约科维奇'（北京时间）."""
    t = fmt_time_beijing(m.start_utc)
    return f"{t} {side_display(m.home)} vs {side_display(m.away)}"


@dataclass
class TournamentGroup:
    tour: Tour
    name_en: str
    name_zh: str
    level: str | None
    matches: list[Match]

    @property
    def title(self) -> str:
        """'温布尔登网球锦标赛（大满贯）' 或 'ATP 巴斯塔德站（ATP 250）'."""
        badge = LEVEL_BADGE.get(self.level or "")
        prefix = "" if self.name_zh.startswith(("ATP", "WTA")) else f"{self.tour.value} "
        title = f"{prefix}{self.name_zh}"
        if badge and badge not in title:
            title += f"（{badge}）"
        return title


def group_by_tournament(matches: Iterable[Match]) -> list[TournamentGroup]:
    """按 (巡回赛, 赛事) 分组，组间按级别排序，组内按轮次+时间排序."""
    groups: dict[tuple[str, str], TournamentGroup] = {}
    for m in matches:
        key = (m.tour.value, m.tournament.name)
        if key not in groups:
            level = m.tournament.level or tournament_level(
                m.tournament.name, m.tour.value
            )
            groups[key] = TournamentGroup(
                tour=m.tour,
                name_en=m.tournament.name,
                name_zh=tournament_zh(m.tournament.name) or m.tournament.name,
                level=level,
                matches=[],
            )
        groups[key].matches.append(m)

    for g in groups.values():
        g.matches.sort(
            key=lambda m: (
                0 if m.is_singles else 1,
                round_order(round_zh(_round_of(m))),
                m.start_utc.timestamp() if m.start_utc else float("inf"),
            )
        )

    return sorted(
        groups.values(),
        key=lambda g: (LEVEL_ORDER.get(g.level, 6), g.tour.value, g.name_zh),
    )


def _round_of(m: Match) -> str | None:
    return m.round_name


def match_round_display(m: Match) -> str:
    """'女单·半决赛' / '男双·决赛' / '16强赛'."""
    parts = []
    d = discipline_zh(m.discipline)
    if d:
        parts.append(d)
    elif m.is_doubles:
        parts.append("双打")
    r = round_zh(m.round_name)
    if r:
        # 轮次字符串可能混入了项目名（如 "Men's Singles - Round of 16" 已翻译），只保留轮次
        parts.append(r)
    return "·".join(dict.fromkeys(parts)) if parts else ""
