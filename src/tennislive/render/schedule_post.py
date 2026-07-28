"""今日赛程的推送文案：标题（引爆看点）+ 正文（具体赛程）。

两条要求有先后，顺序不能倒（见 CLAUDE.md）：**先精准，再引爆**。所以这里的
标题看点只用数据里能核实的东西——谁打谁、第几轮、哪块场、几点——不写
"生死战""复仇"这类站不住的形容。一句煽得起来但站不住的话，比一句平淡的真话
糟得多。

正文是赛程本身，按赛事分组逐场列出，供直接粘贴。
"""

from __future__ import annotations

from collections.abc import Sequence

from ..models import Match
from ..timeutil import to_beijing
from ..zh import player_zh, surface_zh
from ..zh.tournaments import tournament_surface
from .common import group_by_tournament, match_round_display
from .schedule_time import match_key
from .story import is_chinese_player


def _names(players: Sequence) -> str:
    """一边的中文名；译名表里没有的按原样，不自己现编。"""
    return "/".join(player_zh(p.name) for p in players)


def _versus(m: Match) -> str:
    return f"{_names(m.home)} vs {_names(m.away)}"


def _chinese_side(m: Match) -> str:
    """这场里的中国球员名字（用于标题）。"""
    for p in m.home + m.away:
        if is_chinese_player(p):
            return player_zh(p.name)
    return ""


def _opponent_of(m: Match, name: str) -> str:
    for side in (m.home, m.away):
        if name not in _names(side):
            return _names(side)
    return ""


# 标题里用短轮次：「女单·第一轮」是表格写法，读者一眼扫过去只想知道"第几轮"
_SHORT_ROUND = {
    "第一轮": "首轮",
    "第二轮": "次轮",
    "第三轮": "第三轮",
    "16强赛": "16 强",
    "四分之一决赛": "八强战",
    "半决赛": "半决赛",
    "决赛": "决赛",
}
# 只译通用叫法。Grandstand / John Harris 这些是球场自己的专名，不硬翻
_COURT_ZH = {"stadium": "中央球场", "centre court": "中央球场", "center court": "中央球场"}


def _short_round(m: Match) -> str:
    full = match_round_display(m) or ""
    tail = full.split("·")[-1].strip()
    return _SHORT_ROUND.get(tail, tail)


def _court_zh(m: Match) -> str:
    court = (m.court or "").strip()
    return _COURT_ZH.get(court.casefold(), court)


def _clock_zh(m: Match) -> str:
    """「凌晨 1 点」这种说法——比「01:00」更像人话，也更能提示这是哪个时段。"""
    if m.start_utc is None:
        return ""
    b = to_beijing(m.start_utc)
    hour, minute = b.hour, b.minute
    period = (
        "凌晨" if hour < 6 else "早上" if hour < 11
        else "中午" if hour < 13 else "下午" if hour < 18 else "晚上"
    )
    clock = f"{hour}点" if minute == 0 else f"{hour}点{minute}分"
    return period + clock


# 小红书标题超过 20 字左右就会被截断，读者看到的是半句话。这个预算算的是
# 整条标题（含「7.28 今日赛程 | 」那截前缀），西文按半个汉字宽计。
TITLE_MAX = 20


def _width(text: str) -> float:
    """汉字算 1，西文/数字/空格算 0.5——和标题被截断的实际观感对得上。"""
    return sum(1.0 if ord(ch) > 0x2E80 else 0.5 for ch in text)


def headline_hook(m: Match, time_text: str = "", budget: float | None = None) -> str:
    """标题里那半句看点，按 ``budget`` 逐级砍到放得下。

    只用数据能自证的东西：谁、第几轮、对手排名、几点在哪块场。不写"生死战"
    "复仇"这类站不住的形容——一句煽得起来但站不住的话，比一句平淡的真话糟
    得多（见 CLAUDE.md）。对手排名本身就是最硬的"引爆点"：「世界第 28」比
    任何形容词都具体。

    砍的顺序按信息价值从低到高：球场 → 对手排名 → 轮次 → 时段。**中国球员和
    对手的名字永远留着**，那是读者点进来的理由，砍掉就什么都不剩了。
    """
    limit = TITLE_MAX if budget is None else budget
    cn = _chinese_side(m)
    opponent = _opponent_of(m, cn) if cn else ""
    rank = next(
        (p.rank for p in m.home + m.away
         if p.rank and not is_chinese_player(p)), None
    ) if cn else None
    clock, court, rnd = _clock_zh(m), _court_zh(m), _short_round(m)

    if not cn:
        candidates = [
            f"{rnd}{_versus(m)}，{clock}{court}",
            f"{rnd}{_versus(m)}，{clock}",
            f"{_versus(m)}",
        ]
    else:
        candidates = [
            f"{cn}{rnd}对上世界第 {rank} 的{opponent}，{clock}{court}",
            f"{cn}{rnd}对上世界第 {rank} 的{opponent}，{clock}",
            f"{cn}{rnd}战世界第 {rank} 的{opponent}",
            f"{cn}{rnd}战{opponent}，{clock}",
            f"{cn}{clock}战{opponent}",
            f"{cn}战{opponent}",
        ]
    # 只有排名/时段/场地缺失时才会留下空档，顺手清掉
    cleaned = [
        c.replace("世界第 None 的", "").replace("，，", "，").strip("，·")
        for c in candidates
    ]
    for text in cleaned:
        if _width(text) <= limit:
            return text
    return cleaned[-1]


def pick_lead(matches: Sequence[Match]) -> Match | None:
    """标题该讲哪一场。

    中国单打优先；同为中国单打时**看对手的排名**——对手越强，这一问越有分量。
    郑钦文对埃亚拉（世界第 28）和王欣瑜对一位无排名对手，前者才是这天的题眼。
    没有中国单打时退回排名最好的那场单打。
    """
    def best_rank(m: Match, exclude_chinese: bool) -> int:
        ranks = [
            p.rank for p in m.home + m.away
            if p.rank and not (exclude_chinese and is_chinese_player(p))
        ]
        return min(ranks) if ranks else 9999

    singles = [m for m in matches if m.is_singles]
    if not singles:
        return None
    chinese = [
        m for m in singles
        if any(is_chinese_player(p) for p in m.home + m.away)
    ]
    pool = chinese or singles
    return min(pool, key=lambda m: (best_rank(m, bool(chinese)), _start_key(m)))


def _start_key(m: Match) -> float:
    return m.start_utc.timestamp() if m.start_utc else float("inf")


def post_title(day, lead: Match | None, time_text: str = "") -> str:
    """`7.28 今日赛程 | <看点>`，整条控制在 TITLE_MAX 宽度内。"""
    stem = f"{day.month}.{day.day} 今日赛程"
    if lead is None:
        return stem
    prefix = f"{stem} | "
    hook = headline_hook(lead, time_text, budget=TITLE_MAX - _width(prefix))
    return prefix + hook


def _event_heading(group) -> str:
    tournament = group.matches[0].tournament
    surface = tournament.surface or tournament_surface(tournament.name)
    label = surface_zh(surface)
    return f"{group.compact_level} {group.name_zh}" + (f"（{label}）" if label else "")


def post_body(
    pages_matches: Sequence[Match],
    display: dict[str, str],
) -> str:
    """正文：按赛事分组，逐场「轮次 对阵 时间 场地」。

    只列真正上卡的那些场次——正文和图不一致的话，读者第一眼就发现了。
    """
    blocks: list[str] = []
    for group in group_by_tournament(list(pages_matches)):
        lines = [f"🎾 {_event_heading(group)}"]
        for m in group.matches:
            when = display.get(match_key(m), "")
            court = (m.court or "").strip()
            bits = [match_round_display(m) or "", _versus(m), when]
            if court:
                bits.append(court)
            mark = "🇨🇳 " if any(is_chinese_player(p) for p in m.home + m.away) else ""
            lines.append(mark + " · ".join(b for b in bits if b))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


TAGS = "#网球 #网球时差 #今日赛程 #ATP #WTA"


def schedule_post(
    day,
    pages_matches: Sequence[Match],
    display: dict[str, str],
    lead: Match | None,
) -> str:
    """整篇：首行标题、空行、正文、标签。格式与知识帖一致，可直接喂 to_copy_page。"""
    lead_time = display.get(match_key(lead), "") if lead is not None else ""
    title = post_title(day, lead, lead_time)
    body = post_body(pages_matches, display)
    note = "带 * 为按同赛事场序推算的预计时间，以官方排期为准；时间为北京时间。"
    return f"{title}\n\n{body}\n\n{note}\n\n{TAGS}\n"
