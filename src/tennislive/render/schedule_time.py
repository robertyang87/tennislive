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
from ..timeutil import fmt_schedule_time, fmt_time_beijing
from ..zh.terms import round_zh
from .common import round_order

# 只有「确实不知道」的这两种才补推算：「时间待核」是多源冲突，覆盖它等于
# 把冲突藏起来；已有确切时间的更不该动。
ESTIMABLE_PLACEHOLDERS = frozenset({"待官方排期", "待定"})


def match_key(m: Match) -> str:
    """与 digest 去重用的是同一个键：match_id 在两个巡回赛之间不保证唯一。"""
    return f"{m.tour.value}:{m.match_id}"


def _event_key(m: Match) -> tuple[str, str]:
    return (m.tour.value, m.tournament.name)


def round_rank(m: Match) -> int:
    """沿用 render.common 的轮次权重：**越大越靠前**（第一轮 6、决赛 0）。"""
    return round_order(round_zh(m.round_name))


def _estimate(m: Match, siblings: Sequence[Match]) -> str | None:
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
            return f"{fmt_time_beijing(max(s.start_utc for s in earlier))} 后*"

    # 2) 同轮次：同一轮通常排在同一时段，取最早的一场作预计开赛。
    for same_discipline in (True, False):
        peers = [
            s
            for s in siblings
            if round_rank(s) == rank
            and (not same_discipline or s.is_singles == m.is_singles)
        ]
        if peers:
            return f"预计 {fmt_time_beijing(min(s.start_utc for s in peers))}*"

    return None


def schedule_time_display(matches: Iterable[Match]) -> dict[str, str]:
    """返回 ``match_key -> 时间显示``；能推的补预计时间，推不出的保持原样。

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
            base = _estimate(m, known.get(_event_key(m), ())) or base
        display[match_key(m)] = base
    return display


def has_estimated_times(displays: Iterable[str]) -> bool:
    """页脚那句「*为预计时间」要不要出现。"""
    return any("*" in text for text in displays)
