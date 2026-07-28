"""没有官方时间的场次，按同赛事当天已知场次推一个可核验的预计时间.

ESPN 的当日接口对一部分场次只给轮次不给时间——2026-07-28 这天 32 场里占了
16 场（都是已定双方的第二轮和四分之一决赛），卡上一律印「待官方排期」，等于
什么也没说。

同一赛事当天其余场次是有时间的，而**后一轮必然排在同赛事同项目前一轮的最后
一场之后**：这是赛制决定的下界，可以核验，比一句「待官方排期」有用。同轮次
的场次通常同一时段开赛，可以借用。

推不出来的（该赛事当天一个已知时间都没有）仍旧显示「待官方排期」——宁可承认
不知道，也不拿平均值之类的东西糊上去。「时间待核」（多源冲突）同样不覆盖，
那是另一回事，用推算把冲突盖掉只会更糟。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..models import Match
from ..timeutil import fmt_schedule_time, fmt_time_beijing, to_beijing
from ..zh.terms import round_zh
from .common import round_order

# 只有「确实不知道」的这两种才补推算：「时间待核」是多源冲突，覆盖它等于
# 把冲突藏起来；已有确切时间的更不该动。
ESTIMABLE_PLACEHOLDERS = frozenset({"待官方排期", "待定"})


# 「今日赛程」窗口延到次日几点（北京时间）。
#
# 北京日历会把美洲赛事的比赛日拦腰切断：华盛顿的日场 11:00 美东开打 = 北京
# 23:00，整个夜场都落在北京的次日凌晨。郑钦文 vs 埃亚拉正是这样掉出去的——
# ESPN 给的是 2026-07-28T17:00Z（美东 13:00，Stadium），换成北京是 7/29
# 01:00，espn.py 按 `astimezone(BEIJING).date() != d` 一刀切掉。前一天那张卡
# 上还有这场，只是因为当时它还没有时间、没被时间窗筛到。
#
# 对中国观众来说「今晚看什么」本来就包含凌晨那几场，所以窗口要延过午夜。
# 12:00 这个点是从赛程本身推出来的，不是拍的：美东夜场最晚打到北京次日
# 11:00 上下，而欧洲赛事最早也要北京 17:00 才开赛——12:00 落在两者之间，
# 既能把美洲这一夜收全，又不会把欧洲的下一天拉进来。
NEXT_DAY_CUTOFF_HOUR = 12


def in_schedule_window(m: Match, cutoff_hour: int = NEXT_DAY_CUTOFF_HOUR) -> bool:
    """次日的场次算不算进「今日赛程」（见 NEXT_DAY_CUTOFF_HOUR）。

    没有开赛时间的一律不收：那种场次在「今天」那一份里已经收过一次，
    这里再收就会重复；而且没有时间就无从判断它在不在这个窗口里。
    """
    if m.start_utc is None:
        return False
    return to_beijing(m.start_utc).hour < cutoff_hour


def match_key(m: Match) -> str:
    """与 digest 去重用的是同一个键：match_id 在两个巡回赛之间不保证唯一。"""
    return f"{m.tour.value}:{m.match_id}"


def _event_key(m: Match) -> tuple[str, str]:
    return (m.tour.value, m.tournament.name)


def round_rank(m: Match) -> int:
    """沿用 render.common 的轮次权重：**越大越靠前**（第一轮 6、决赛 0）。"""
    return round_order(round_zh(m.round_name))


def _clock(moment, today) -> str:
    """`01:00` 或跨天时的 `+1 01:00`。

    跨日窗口打开之后，「今日赛程」里有一半场次其实落在北京的次日凌晨（美东
    夜场 = 北京 23:00 到次日 11:00）。只印「预计 01:00」看不出是哪天的
    01:00——读者会以为是今天白天已经打完的那个点。
    """
    stamp = fmt_time_beijing(moment)
    if today is None:
        return stamp
    offset = (to_beijing(moment).date() - today).days
    return f"+{offset} {stamp}" if offset > 0 else stamp


def _estimate(m: Match, siblings: Sequence[Match], today=None) -> str | None:
    """按证据强度逐级下探；每一级都能说清凭什么。"""
    rank = round_rank(m)

    # 1) 同赛事的前一轮：后一轮排在它之后是赛制决定的，取最晚的一场作下界。
    #    先要求同项目（单打/双打），不行再放开——单双打常并行，跨项目的下界
    #    仍然成立，只是松一些。
    for same_discipline in (True, False):
        earlier = [
            s
            for s in siblings
            if round_rank(s) > rank
            and (not same_discipline or s.is_singles == m.is_singles)
        ]
        if earlier:
            anchor = max(s.start_utc for s in earlier)
            return f"{_clock(anchor, today)} 后*"

    # 2) 同轮次：同一轮通常排在同一时段，取最早的一场作预计开赛。
    for same_discipline in (True, False):
        peers = [
            s
            for s in siblings
            if round_rank(s) == rank
            and (not same_discipline or s.is_singles == m.is_singles)
        ]
        if peers:
            anchor = min(s.start_utc for s in peers)
            return f"预计 {_clock(anchor, today)}*"

    return None


def _mark_next_day(text: str, moment, today) -> str:
    """给已有确切/单源时间的那些补上跨天标识。"""
    if today is None or moment is None:
        return text
    stamp = fmt_time_beijing(moment)
    marked = _clock(moment, today)
    return text.replace(stamp, marked, 1) if stamp != marked and stamp in text else text


def schedule_time_display(
    matches: Iterable[Match], *, today=None
) -> dict[str, str]:
    """返回 ``match_key -> 时间显示``；能推的补预计时间，推不出的保持原样。

    传 ``today``（北京日期）时，落在次日的场次会标上 ``+1``——跨日窗口打开
    之后「今日赛程」里有一半场次其实是北京次日凌晨，不标出来读者分不清。

    只读，不改 Match：``schedule_time_status`` 是数据源的事实，推算是展示层的
    加工，混在一起会让下一个人以为官方真给了时间。
    """
    matches = list(matches)
    known: dict[tuple[str, str], list[Match]] = {}
    for m in matches:
        if m.start_utc is not None:
            known.setdefault(_event_key(m), []).append(m)

    display: dict[str, str] = {}
    for m in matches:
        base = fmt_schedule_time(m)
        if m.start_utc is None and base in ESTIMABLE_PLACEHOLDERS:
            base = _estimate(m, known.get(_event_key(m), ()), today) or base
        else:
            base = _mark_next_day(base, m.start_utc, today)
        display[match_key(m)] = base
    return display


def has_estimated_times(displays: Iterable[str]) -> bool:
    """页脚那句「*为预计时间」要不要出现。"""
    return any("*" in text for text in displays)


def has_next_day_times(displays: Iterable[str]) -> bool:
    """页脚那句「+1 为次日」要不要出现。"""
    return any("+1 " in text or "+2 " in text for text in displays)
