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

LEVEL_COMPACT_BADGE = {
    "GS": "大满贯",
    "M1000": "ATP1000",
    "W1000": "WTA1000",
    "ATP1000": "ATP1000",
    "WTA1000": "WTA1000",
    "ATP500": "ATP500",
    "WTA500": "WTA500",
    "W500": "WTA500",
    "ATP250": "ATP250",
    "WTA250": "WTA250",
    "W250": "WTA250",
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


def _abbrev_en(name: str) -> str:
    """未翻译的英文全名缩写化：'Federico Agustin Gomez' → 'F.A. Gomez'."""
    words = name.split()
    if len(words) < 2:
        return name
    return "".join(w[0] + "." for w in words[:-1]) + " " + words[-1]


def player_display(
    p: Player,
    with_flag: bool = True,
    with_seed: bool = True,
    short_en: bool = False,
) -> str:
    """'🇮🇹 辛纳' 或 '🇮🇹 [1]辛纳'；short_en=True 时英文名缩写（卡片版面用）."""
    name = player_zh(p.name)
    if short_en and name == p.name and name.isascii():
        name = _abbrev_en(name)
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


def side_display(
    players: list[Player],
    with_flag: bool = True,
    with_seed: bool = True,
    short_en: bool = False,
) -> str:
    """单打给单人，双打给 'A/B' 组合."""
    if len(players) == 1:
        return player_display(players[0], with_flag, with_seed, short_en=short_en)
    return "/".join(
        player_display(p, with_flag=with_flag, with_seed=False, short_en=short_en)
        for p in players
    )


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


def result_line(m: Match, short_en: bool = False) -> str:
    """赛果一行：'[1]辛纳 2-0 [5]德约科维奇（6-4 7-6(3)）'，从胜者视角."""
    if m.winner is None:
        home_s = side_display(m.home, short_en=short_en)
        away_s = side_display(m.away, short_en=short_en)
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
    line = (
        f"{side_display(w, short_en=short_en)} {w_sets}-{l_sets} "
        f"{side_display(l, short_en=short_en)}"
    )
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
    def compact_level(self) -> str:
        """比分卡紧凑级别：ATP250 / WTA1000 / 大满贯。"""
        level = self.level or ""
        if level in ("1000", "500", "250"):
            return f"{self.tour.value}{level}"
        return LEVEL_COMPACT_BADGE.get(level, self.tour.value)

    @property
    def compact_title(self) -> str:
        return f"{self.compact_level}·{self.name_zh}"

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


# 中国大陆球员中文名（用于「中国军团」板块与内容精选）
CHINESE_PLAYER_NAMES = {
    "郑钦文", "王欣瑜", "王曦雨", "袁悦", "王雅繁", "朱琳", "张帅", "韩馨蕴",
    "郑赛赛", "杨钊煊", "蒋欣玗", "汤千慧", "郭涵煜", "徐一幡", "马烨欣",
    "孙心然", "魏思佳", "高馨妤", "张之臻", "商竣程", "布云朝克特", "吴易昺",
    "周意", "孙发京",
}


def is_chinese_involved(m: Match) -> bool:
    """比赛双方是否有中国大陆球员（国籍 CHN 或译名命中名单）."""
    for p in m.home + m.away:
        if (p.country or "").upper() in ("CHN", "CN"):
            return True
        if player_zh(p.name) in CHINESE_PLAYER_NAMES:
            return True
    return False


def curate_for_social(matches: list[Match]) -> list[Match]:
    """社媒版精选：全部单打 + （中国球员参与或决赛的）双打.

    一天可能有 8 站 200+ 场比赛，卡片图与文章需要控制篇幅；
    完整数据保留在 digest.json。
    """
    kept = []
    for m in matches:
        if m.is_singles:
            kept.append(m)
            continue
        r = round_zh(m.round_name)
        if r == "决赛" or is_chinese_involved(m):
            kept.append(m)
    return kept


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
