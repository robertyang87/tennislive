"""Editorial story helpers shared by cards and social copy."""

from __future__ import annotations

from ..digest import Digest
from ..models import Match
from ..zh import player_zh
from ..zh.terms import round_zh
from .common import CHINESE_PLAYER_NAMES, is_chinese_involved
from .rating import is_upset, match_score, stay_up_stars


_CN_COUNTRIES = {"CHN", "CN"}
_CN_NUMERALS = {2: "双", 3: "三", 4: "四", 5: "五", 6: "六"}


def is_chinese_player(player) -> bool:
    return (player.country or "").upper() in _CN_COUNTRIES or player_zh(
        player.name
    ) in CHINESE_PLAYER_NAMES


def chinese_players(match: Match) -> list:
    return [p for p in match.home + match.away if is_chinese_player(p)]


def chinese_side_won(match: Match) -> bool:
    winners = match.winner_players() or []
    return bool(winners and any(is_chinese_player(p) for p in winners))


def china_wins(digest: Digest) -> list[Match]:
    return [
        m
        for m in digest.results
        if is_chinese_involved(m) and chinese_side_won(m)
    ]


def china_summary(digest: Digest) -> str | None:
    """Return a compact positive Team China summary for a secondary hook."""
    wins = china_wins(digest)
    if not wins:
        return None
    doubles = [m for m in wins if m.is_doubles]
    if len(doubles) == len(wins) and len(doubles) >= 2:
        number = _CN_NUMERALS.get(len(doubles), str(len(doubles)))
        return f"中国双打{number}线告捷"
    if len(wins) >= 2:
        return f"中国军团收获{len(wins)}场胜利"
    # 单场胜利已经有独立候选，重复概括会让封面主副标题说同一件事。
    return None


def sort_china_matches(matches: list[Match]) -> list[Match]:
    """Positive results and singles leads first, then importance."""
    return sorted(
        matches,
        key=lambda m: (
            0 if chinese_side_won(m) else 1,
            0 if m.is_singles else 1,
            -match_score(m),
        ),
    )


def _winner_lost_first_set(match: Match) -> bool:
    if not match.sets or match.winner not in (0, 1):
        return False
    first = match.sets[0]
    if match.winner == 0:
        return first.home < first.away
    return first.away < first.home


def _tiebreak_count(match: Match) -> int:
    count = 0
    for s in match.sets:
        if s.home_tiebreak is not None or s.away_tiebreak is not None:
            count += 1
        elif {s.home, s.away} == {6, 7}:
            count += 1
    return count


def result_insight(match: Match) -> str:
    """A short, fact-based interpretation using only scoreboard data."""
    sets = [s for s in match.sets if s.home != s.away]
    losers = match.loser_players() or []
    loser_seed = losers[0].seed if losers else None
    tiebreaks = _tiebreak_count(match)

    if is_upset(match):
        if len(sets) >= 3 and tiebreaks >= 3 and loser_seed:
            return f"三盘全部进入抢七，硬仗掀翻{loser_seed}号种子"
        if len(sets) >= 3 and loser_seed:
            return f"鏖战三盘，掀翻{loser_seed}号种子"
        if loser_seed:
            return f"非种子球员击败{loser_seed}号种子，冷门成色十足"
        return "以低排名身份击败强敌，打出昨夜最大冷门"

    if _winner_lost_first_set(match) and len(sets) >= 3:
        return "先丢一盘后完成逆转，比赛韧性是胜负手"
    if len(sets) == 2:
        return "直落两盘拿下，关键分处理更加稳定"
    if len(sets) >= 3:
        return "鏖战三盘过关，决胜盘把握住了关键机会"
    if match.is_doubles:
        return "双打配合经受住关键分考验"
    return "这场结果值得继续关注后续走势"


def schedule_insight(match: Match) -> str:
    """Explain why the match matters using only current, verifiable context."""
    if match.editorial_note:
        return match.editorial_note

    from .common import group_by_tournament

    def identity(player) -> str:
        name = player_zh(player.name)
        if player.rank is not None:
            return f"{name}（世界第{player.rank}）"
        if player.seed is not None:
            return f"{name}（{player.seed}号种子）"
        return name

    home = identity(match.home[0]) if match.home else "主队"
    away = identity(match.away[0]) if match.away else "客队"
    r = round_zh(match.round_name) or ""
    target = {
        "决赛": "冠军",
        "半决赛": "决赛席位",
        "四分之一决赛": "四强席位",
        "八分之一决赛": "八强席位",
    }.get(r, "下一轮席位")

    if match.is_doubles:
        sides = " / ".join(player_zh(p.name) for p in match.home[:2])
        opponents = " / ".join(player_zh(p.name) for p in match.away[:2])
        return f"{sides}与{opponents}争夺{target}"

    cn = chinese_players(match)
    if cn:
        chinese = cn[0]
        chinese_text = identity(chinese)
        opponent = match.away[0] if chinese in match.home else match.home[0]
        return f"{chinese_text}冲击{target}，对手{identity(opponent)}"

    event = group_by_tournament([match])[0].name_zh
    if r == "决赛":
        return f"{home}与{away}争夺{event}冠军"
    if r in {"半决赛", "四分之一决赛", "八分之一决赛"}:
        return f"{home}与{away}争夺{target}"
    if match.is_doubles:
        return f"{home}与{away}争夺{target}"
    if r:
        return f"{home}对阵{away}，胜者进入{target}"
    return f"{home}对阵{away}，本场决定下一轮席位"


def recommendation_label(match: Match) -> str:
    stars = stay_up_stars(match)
    if stars >= 5:
        return "必看"
    if stars >= 4:
        return "推荐"
    if stars >= 3:
        return "关注"
    return "可选"
