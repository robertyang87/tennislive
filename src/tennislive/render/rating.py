"""比赛重要性评分：全自动选题的核心规则.

用于：昨夜焦点三场的挑选、今晚看球的推荐与熬夜指数、冷门检测、标题自动选择。
规则可调，全部集中在这里。
"""

from __future__ import annotations

from ..models import Match
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


def _level_of(m: Match) -> str | None:
    return m.tournament.level or tournament_level(m.tournament.name, m.tour.value)


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


def match_score(m: Match, cn_boost: bool = True) -> int:
    """比赛重要性总分，越高越值得报道.

    cn_boost=False 时不给中国球员场次加权（赛果速递卡用：
    中国军团有专页，速递页按比赛本身分量排序，出现时只打标签）。
    """
    s = 0
    if cn_boost and is_chinese_involved(m):
        s += 100
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
    decided = [x for x in m.sets if x.home != x.away]
    if len(decided) >= 3:
        s += 10
    if any({x.home, x.away} == {1, 0} for x in m.sets):
        s += 5
    if m.is_doubles and not is_chinese_involved(m):
        s -= 40
    return s


def top_results(matches: list[Match], n: int = 3, cn_boost: bool = True) -> list[Match]:
    """昨夜焦点：评分最高的 n 场已完赛单打（cn_boost 见 match_score）."""
    finished = [m for m in matches if m.status.is_final]
    return sorted(
        finished, key=lambda m: match_score(m, cn_boost=cn_boost), reverse=True
    )[:n]


def top_schedule(matches: list[Match], n: int = 5) -> list[Match]:
    """今晚看球：评分最高的 n 场未开赛."""
    upcoming = [m for m in matches if not m.status.is_final]
    return sorted(upcoming, key=match_score, reverse=True)[:n]


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
