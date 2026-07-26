"""Evidence-led human angles for previews and opinion copy."""

from __future__ import annotations

from collections.abc import Container
from datetime import date

from ..models import Match
from ..research.media import brief_for_match
from ..zh import player_zh
from ..zh.terms import round_zh
from .common import match_round_display
from .context import historical_context
from .rating import went_to_deciding_set
from .story import is_chinese_player, schedule_insight
from .tournament_story import direct_story_for_match


# 每条的第一个分句都要能单独成句、并且点出主语：正文渲染层按标点截断时
# 只会留下开头。生产环境曾印出"看点｜法网与温网冠军都写在履历里"——两位
# 球员都在同一行里，读者根本不知道说的是谁；也印出过"看点｜结束16个月冠军
# 等待后"这样的半截状语从句。
_PLAYER_PREVIEWS = {
    "yuan-yue": "袁悦2024年在奥斯汀首夺WTA冠军并跻身前50；今晚看她能否重新接上那段上升势头",
    "gao-xinyu": "高馨钰曾在联合杯爆冷世界第17的玛雅；回到巡回赛，韧性能否再次兑现",
    "barbora-krejcikova": "克雷吉茨科娃的履历里有法网与温网两座冠军；首轮真正看的是手感能否上线",
    "tsitsipas": "西西帕斯结束了16个月的冠军等待；接下来要证明这不是一座孤立的奖杯",
}


_PLAYER_PREVIEW_VARIANTS = {
    "yuan-yue": (
        "\u8881\u60a6\u7684\u5965\u65af\u6c40\u9996\u51a0\u8bc1\u660e\u8fc7\u5979\u80fd\u6253\u786c\u4ed7\uff1b\u8fd9\u6b21\u91cd\u56de\u7ea2\u571f\u9996\u8f6e\uff0c\u5148\u770b\u8282\u594f\u80fd\u5426\u7ad9\u7a33",
        "\u8881\u60a6\u7684\u5de1\u56de\u8d5b\u4e0a\u5347\u671f\u4e0d\u7f3a\u9ad8\u5149\uff0c\u4eca\u665a\u66f4\u5173\u952e\u7684\u662f\u628a\u9996\u8f6e\u538b\u529b\u62c6\u6210\u4e00\u5c40\u4e00\u5c40",
        "\u4ece\u5965\u65af\u6c40\u5230\u5e03\u62c9\u683c\uff0c\u8881\u60a6\u8981\u627e\u56de\u7684\u4e0d\u53ea\u662f\u80dc\u573a\uff0c\u8fd8\u6709\u628a\u5bf9\u624b\u62d6\u8fdb\u81ea\u5df1\u8282\u594f\u7684\u80fd\u529b",
    ),
    "gao-xinyu": (
        "\u9ad8\u99a8\u94b0\u5728\u8054\u5408\u676f\u7684\u9ad8\u5149\u4e0d\u4f1a\u81ea\u52a8\u5e26\u6765\u80dc\u5229\uff0c\u4f46\u80fd\u63d0\u9192\u4eba\uff1a\u5979\u6253\u9006\u98ce\u7403\u6709\u5e95\u6c14",
        "\u9ad8\u99a8\u94b0\u66fe\u5728\u8054\u5408\u676f\u7206\u51b7\u4e16\u754c\u7b2c17\u7684\u739b\u96c5\uff1b\u56de\u5230\u5de1\u56de\u8d5b\uff0c\u97e7\u6027\u80fd\u5426\u518d\u6b21\u5151\u73b0",
    ),
    "barbora-krejcikova": (
        "\u514b\u96f7\u5409\u8328\u79d1\u5a03\u7684\u5c65\u5386\u91cc\u6709\u6cd5\u7f51\u4e0e\u6e29\u7f51\u4e24\u5ea7\u51a0\u519b\uff1b\u9996\u8f6e\u771f\u6b63\u770b\u7684\u662f\u624b\u611f\u80fd\u5426\u4e0a\u7ebf",
        "\u4e24\u5ea7\u5927\u6ee1\u8d2f\u51a0\u519b\u5c5e\u4e8e\u514b\u96f7\u5409\u8328\u79d1\u5a03\uff1b\u8fd9\u4e00\u8f6e\u8981\u770b\u7684\u662f\u72b6\u6001\uff0c\u800c\u4e0d\u662f\u5c65\u5386",
        "\u514b\u96f7\u5409\u8328\u79d1\u5a03\u5e26\u7740\u5927\u6ee1\u8d2f\u51a0\u519b\u7684\u5c65\u5386\u51fa\u6218\uff1b\u9996\u8f6e\u5148\u770b\u5979\u7684\u624b\u611f\u4e0e\u8282\u594f",
    ),
    "tsitsipas": (
        "\u897f\u897f\u5e15\u65af\u7ed3\u675f\u4e8616\u4e2a\u6708\u7684\u51a0\u519b\u7b49\u5f85\uff1b\u63a5\u4e0b\u6765\u8981\u8bc1\u660e\u8fd9\u4e0d\u662f\u4e00\u5ea7\u5b64\u7acb\u7684\u5956\u676f",
        "\u897f\u897f\u5e15\u65af\u521a\u62ff\u56de\u4e45\u8fdd\u7684\u51a0\u519b\u624b\u611f\uff1b\u8fd9\u4e00\u573a\u770b\u4ed6\u80fd\u4e0d\u80fd\u8fde\u7740\u6253\u51fa\u6765",
        "16\u4e2a\u6708\u7684\u7b49\u5f85\u521a\u88ab\u897f\u897f\u5e15\u65af\u7ec8\u7ed3\uff1b\u771f\u6b63\u7684\u8003\u9a8c\u662f\u4e0b\u4e00\u5ea7\u5956\u676f\u6765\u5f97\u6709\u591a\u5feb",
    ),
}


def _player_preview(slug: str, today: date | None) -> str | None:
    choices = _PLAYER_PREVIEW_VARIANTS.get(slug)
    if not choices:
        return None
    if today is None:
        return choices[0]
    return choices[today.toordinal() % len(choices)]


_TOPICALITY_HEAT_THRESHOLD = 20


def _topicality_angle(match: Match) -> str | None:
    """A grounded 'this match already has real buzz' note based on the trend
    radar's per-match heat score, not the raw headline text.

    Two reasons to stay at the score level: (1) apply_trend_signals() attaches
    the same tournament-wide news batch to every match at that event — a
    signal being present does not mean its headline is actually about these
    two players, only the aggregated heat score already discounts tournament-
    only hits versus player-specific ones; (2) an external headline is
    arbitrary length and language, and quoting it verbatim can be mangled by
    the render layer's punctuation-based truncation.
    """
    heat = max(match.media_heat or 0, match.search_heat or 0)
    if heat >= _TOPICALITY_HEAT_THRESHOLD:
        return "这场已经带着真实话题度，官方与搜索热度都在往上走。"
    return None


def data_angle(match: Match, limit: int) -> str:
    """一行装得下的数据看点：短、带数字、只用这场比赛真有的字段。

    preview_angle 与 schedule_insight 写得比这一行的预算长得多（决赛那句
    44 字、账号连载那句 59 字），一旦都截不出完整句子，看点就跌回赛段套话
    ——"最后一场定归属，谁先扛住谁捧杯"这种任何一场决赛都能印的话。
    这里按排名 → 种子 → 中国球员 → 纯对阵逐级降，每一级都先量长度，
    装不下就换下一级，保证落到套话之前还有一句带信息的。

    原来住在 xiaohongshu.py 里只给推送正文用。它是全篇唯一**逐场不同**的
    兜底句，preview_angle 的收尾也需要：赛段套话是按轮次写的，同一轮的两场
    比赛会拿到一模一样的一句（五场页上"四强席位就在眼前…"印过两遍）。
    """
    stage = round_zh(match.round_name) or ""
    home = match.home[0] if match.home else None
    away = match.away[0] if match.away else None
    if home is None or away is None:
        return ""
    home_name, away_name = player_zh(home.name), player_zh(away.name)
    prefix = f"{stage}：" if stage else ""

    candidates: list[str] = []
    if home.rank is not None and away.rank is not None:
        candidates.append(
            f"{prefix}世界第{home.rank}的{home_name}对上第{away.rank}的{away_name}。"
        )
        candidates.append(f"{prefix}{home_name}第{home.rank}，{away_name}第{away.rank}。")
    if home.seed is not None and away.seed is not None:
        candidates.append(
            f"{prefix}{home.seed}号种子{home_name}对{away.seed}号种子{away_name}。"
        )
    chinese = [p for p in match.home + match.away if is_chinese_player(p)]
    if chinese:
        name = player_zh(chinese[0].name)
        opponent = away if chinese[0] is home else home
        if opponent.rank is not None:
            candidates.append(f"{name}打{stage or '这一轮'}，对手世界第{opponent.rank}。")
        candidates.append(f"{name}的{stage or '这一轮'}，今晚这场先看她。")
    candidates.append(f"{prefix}{home_name}对{away_name}。")

    for line in candidates:
        if len(line) <= limit:
            return line
    return ""


# data_angle 收尾时给的字数上限。看点行最宽是两行 74 字（见 webcards 的
# REASON_LIMIT_TWO_LINES），这里放宽一点，让渲染层自己再裁。
_DATA_ANGLE_LIMIT = 80


def preview_angle(
    match: Match, today: date | None = None, *, used: Container[str] = ()
) -> str:
    """Explain why a match matters, weighing media opinion, both sides'
    topicality, and historical relevance before falling back to mechanical
    rank/seed facts.

    Priority: reviewed media consensus > curated editorial note > a tracked
    player's own story > Chinese-player schedule facts > tournament story >
    account continuity (this player's last appearance in our own coverage) >
    automated trend-radar topicality (real, sourced buzz, not yet reviewed) >
    mechanical schedule_insight as the final, always-available fallback.

    ``used`` 是同一页上已经印出去的角度。赛事故事那一档是**赛事级**的——同一
    站的每场比赛都会拿到同一句"…又要添一位新主角；这场不只抢晋级，也抢本届
    赛事的叙事中心"，五场的今晚焦点页上曾一字不差地重复三遍。传入 used 后，
    已经出现过的那句会被跳过，掉到下面按比赛本身取材的档位（往绩、热度、
    赛程事实），赛事故事仍然保留、但一页只讲一次。
    """
    candidates: list[str] = []

    def offer(value: str | None) -> str | None:
        """记下候选；没被用过就直接采纳。"""
        if not value:
            return None
        candidates.append(value)
        return value if value not in used else None

    media = brief_for_match(match, today) if today is not None else None
    if media is not None and (picked := offer(media.consensus)):
        return picked
    if match.editorial_note and (
        match.editorial_url or match.editorial_source == "背景编辑"
    ):
        if picked := offer(match.editorial_note):
            return picked

    story = direct_story_for_match(match, prefer_player=True)
    if story is not None and story.kind == "player":
        if picked := offer(
            _player_preview(story.slug, today)
            or _PLAYER_PREVIEWS.get(story.slug, story.hero_fact)
        ):
            return picked

    chinese = next(
        (player for player in match.home + match.away if is_chinese_player(player)),
        None,
    )
    if chinese is not None and (picked := offer(schedule_insight(match, today))):
        return picked

    if story is not None and (picked := offer(
        f"{story.title}又要添一位新主角；这场不只抢晋级，也抢本届赛事的叙事中心。"
    )):
        return picked

    if today is not None:
        historical = historical_context(match, today)
        if historical is not None and (picked := offer(historical.summary)):
            return picked

    if picked := offer(_topicality_angle(match)):
        return picked
    if picked := offer(schedule_insight(match, today)):
        return picked
    # schedule_insight 是按**轮次**写的，同一轮的两场会拿到同一句。收尾换成
    # 逐场取材的数据句，否则"已经用过就往下走"到这里就断了。
    if picked := offer(data_angle(match, _DATA_ANGLE_LIMIT)):
        return picked
    # 全都用过了：宁可重复也不能让这一行空着。
    return candidates[-1] if candidates else schedule_insight(match, today)


def editor_takeaway(match: Match, today: date | None = None) -> str:
    """Priority: reviewed media takeaway > a tracked player's own storyline >
    a grounded, match-specific line derived from real facts (round stakes,
    tiebreak count, decider) -- never a boilerplate sentence that could be
    pasted onto any match."""
    media = brief_for_match(match, today) if today is not None else None
    if media is not None and media.takeaway:
        return media.takeaway
    story = direct_story_for_match(match, prefer_player=True)
    if story is not None and story.kind == "player":
        return f"我更想继续追踪的，是{story.title}如何把今天接进自己的生涯时间线。"
    return _grounded_takeaway(match)


def _grounded_takeaway(match: Match) -> str:
    winners = match.winner_players() or []
    losers = match.loser_players() or []
    if not winners or not losers:
        return "这场比赛的看点，留到下一场用数据说话。"
    winner_name = player_zh(winners[0].name)
    loser_name = player_zh(losers[0].name)

    r = round_zh(match.round_name) or ""
    stakes = {
        "决赛": "冠军奖杯",
        "半决赛": "决赛门票",
        "四分之一决赛": "四强席位",
        "八分之一决赛": "八强门票",
    }.get(r)
    if stakes:
        return f"{winner_name}把{stakes}的悬念留到了下一场；{loser_name}这个赛季，还得找别的地方把状态找回来。"

    tiebreaks = sum(
        1
        for s in match.sets
        if s.home_tiebreak is not None or s.away_tiebreak is not None
    )
    if tiebreaks >= 2:
        return f"两盘抢七都被{winner_name}拿下，这份关键分的稳定性，比比分更值得记一笔。"
    if went_to_deciding_set(match):
        return f"顶住决胜盘的是{winner_name}；{loser_name}最遗憾的，是没能把领先优势保持到最后一分。"
    return f"{winner_name}这场赢得干脆，下一轮才是真正检验状态的时候。"


def apply_knowledge_angles(digest) -> int:
    """Attach reviewed player/tournament context before model rewrites."""
    applied = 0
    for match in digest.schedule:
        if match.editorial_note:
            continue
        story = direct_story_for_match(match, prefer_player=True)
        if story is None:
            continue
        match.editorial_note = preview_angle(match, digest.today)
        match.editorial_source = story.source_label
        match.editorial_url = story.source_url
        applied += 1
    return applied
