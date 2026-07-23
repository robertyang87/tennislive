"""Editorial story helpers shared by cards and social copy."""

from __future__ import annotations

from ..digest import Digest
from ..models import Match
from ..zh import player_zh, surface_zh
from ..zh.terms import round_zh
from ..zh.tournaments import tournament_surface
from .common import CHINESE_PLAYER_NAMES, is_chinese_involved
from .rating import is_upset, match_score, stay_up_stars, went_to_deciding_set


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
    if went_to_deciding_set(match):
        length = (
            "三盘" if len(sets) == 3 else "五盘" if len(sets) == 5 else "多盘"
        )
        return f"鏖战{length}过关，决胜盘把握住了关键机会"
    if len(sets) >= 3:
        return f"用{len(sets)}盘结束比赛，没有把胜负拖入决胜盘"
    if match.is_doubles:
        return "双打配合经受住关键分考验"
    return "这场结果值得继续关注后续走势"


def schedule_insight(match: Match) -> str:
    """Write a compact hook from verifiable identity, stage, and surface facts."""
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

    home_player = match.home[0] if match.home else None
    away_player = match.away[0] if match.away else None
    home = identity(home_player) if home_player else "主队"
    away = identity(away_player) if away_player else "客队"
    r = round_zh(match.round_name) or ""
    target = {
        "决赛": "冠军",
        "半决赛": "决赛席位",
        "四分之一决赛": "四强席位",
        "八分之一决赛": "八强席位",
    }.get(r, "下一轮席位")

    event = group_by_tournament([match])[0].name_zh
    surface = surface_zh(
        match.tournament.surface or tournament_surface(match.tournament.name)
    )

    if match.is_doubles:
        sides = " / ".join(player_zh(p.name) for p in match.home[:2])
        opponents = " / ".join(player_zh(p.name) for p in match.away[:2])
        if target == "下一轮席位":
            return f"双打最怕默契还没上线：{sides}与{opponents}，首轮就得把组合感打出来。"
        return f"{sides}与{opponents}只差这一场，就能把默契换成{target}。"

    cn = chinese_players(match)
    if cn:
        chinese = cn[0]
        opponent = match.away[0] if chinese in match.home else match.home[0]
        cn_name = player_zh(chinese.name)
        if target != "下一轮席位":
            return f"{cn_name}离{target}只差一场；排名只是入场券，真正要兑现的是热门身份。"
        if chinese.rank is not None and opponent.rank is not None:
            gap = abs(chinese.rank - opponent.rank)
            if chinese.rank > opponent.rank and gap >= 20:
                return f"{cn_name}要跨过{gap}位排名差；这不是来陪跑，而是一次硬仗成色测试。"
            if chinese.rank < opponent.rank and gap >= 20:
                return f"{cn_name}背着更高排名进场，首轮最大的考题，是扛住“必须拿下”的压力。"
            return f"{cn_name}与对手只差{gap}位，纸面没有安全边；这场从开局就值得盯紧。"
        return f"{cn_name}的{r or '首轮'}不缺关注，真正的悬念是她能否一上来就接管比赛。"

    if r == "决赛":
        return f"{event}只剩最后一问：{home}和{away}，谁能把这一周换成奖杯？"

    # 淘汰赛阶段（决赛除外）：同一赛事常常一次出现好几场同轮次比赛
    # （比如四强/八强战一晚打完），必须按具体排名/种子差异区分文案，
    # 否则同一张卡片里会出现好几场比赛复用同一句"分水岭"套话。
    stakes = {"半决赛": "决赛门票", "四分之一决赛": "四强席位", "八分之一决赛": "八强门票"}.get(r)
    if stakes and home_player and away_player:
        ranks = [home_player.rank, away_player.rank]
        if all(rank is not None for rank in ranks):
            gap = abs(ranks[0] - ranks[1])
            favorite = home_player if ranks[0] < ranks[1] else away_player
            favorite_name = player_zh(favorite.name)
            # 下方三句刻意把第一个分句写成独立完整的句子：正文渲染层会
            # 按标点截断长文案，球员姓名（尤其未译名的长拼写）会让总长
            # 超出上限；前半句独立成句，被截断也不会留下读不完的残句。
            if gap >= 35:
                return f"排名差{gap}位不算保险，{stakes}这一轮谁都想抢。"
            if gap >= 12:
                return f"{favorite_name}占{gap}位排名优势，但{stakes}最考验心态。"
            return f"排名只差{gap}位，{stakes}谁都想要；这种分差走到抢七不奇怪。"
        seeded = next(
            (player for player in (home_player, away_player) if player.seed), None
        )
        if seeded is not None:
            return f"{stakes}谁都想拿，{player_zh(seeded.name)}带着{seeded.seed}号种子出战也得先扛住压力。"
        return f"{stakes}就在眼前，两人都清楚这一轮没有“下次再拼”的余地。"
    if stakes:
        # 缺少排名/种子数据时的机械兜底，仍按赛事阶段区分文案
        return {
            "决赛门票": "离决赛只差一场，纸面身份不再是答案，只会变成必须兑现的压力。",
            "四强席位": "八强是签表真正的分水岭：这场赢下来的不只是四强席位，还有争冠声量。",
            "八强门票": "八强门票摆在眼前，比赛也从热身阶段切进真正的淘汰压力。",
        }[stakes]

    if home_player and away_player:
        ranks = [home_player.rank, away_player.rank]
        if all(rank is not None for rank in ranks):
            gap = abs(ranks[0] - ranks[1])
            favorite = home_player if ranks[0] < ranks[1] else away_player
            favorite_name = player_zh(favorite.name)
            if gap >= 35:
                return f"排名差{gap}位，{favorite_name}背着纸面优势；越像“该赢”的球，越怕慢热。"
            if gap >= 12:
                return f"{favorite_name}占着{gap}位排名优势，但首轮没有存款：优势得现场兑现。"
            return f"排名只差{gap}位，这不是谁压着谁打的签；第一轮就有五五开的火药味。"

        seeded = next(
            (player for player in (home_player, away_player) if player.seed), None
        )
        if seeded is not None:
            return f"{player_zh(seeded.name)}背着{seeded.seed}号种子的签位，首轮先过“必须赢”这一关。"
        if (home_player.country or "") == (away_player.country or "") and home_player.country:
            return "同国对决自带比较：首轮不只争晋级，也争谁先在本站留下名字。"

    surface_openers = {
        "红土": "红土首轮最会放大耐心差距",
        "草地": "草地不给慢热留下多少时间",
        "硬地": "硬地首轮的节奏来得很快",
        "室内硬地": "室内硬地把每一次犹豫都放大",
    }
    opener = surface_openers.get(surface, "首轮没有纸面答案")
    return f"{opener}；双方都没有明显身份光环，反而更像一场抢戏之战。"


def recommendation_label(match: Match) -> str:
    stars = stay_up_stars(match)
    if stars >= 5:
        return "必看"
    if stars >= 4:
        return "重点"
    if stars >= 3:
        return "悬念"
    return "有看头"
