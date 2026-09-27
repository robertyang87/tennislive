"""字幕换算的一个补丁：同一个数不许一半中文、一半阿拉伯。

`explainer.arabic_numerals` 对裸的「一」「两」、以及后面不跟量词的数一律不动——
那是为了「唯一一次」「两盘」「三分之一」不被误伤。可同一个数的两截只要有一截
含十/百/千（或后面跟着量词），那一截照换，于是屏幕上是**半中半洋**：

    两小时四十分钟 → 两小时40分钟      九月一号 → 9月一号
    十二胜三负     → 12胜三负          一月十九号 → 一月19号

来路：2026-09-27 返工取证（P1 第 ⑥ 项）把全库 305 条 reel spec 的旁白按
`subtitle_lines` 逐行换算量了一遍——时长 111 处、日期 12 处、胜负 4 处，分布在
98 条 spec 里，全都已经这样印在已发片子的字幕上（接上这个补丁之后 0 处）。CLAUDE.md「给人看的字一律
阿拉伯数字」那条，和 `_NUM_UNITS` 注释里记的「北京时间8月三号零点」，是同一个形状；
当时只补了量词表，没补「另一半在场」这一种。

⚠️ 判据**只认这三种结构**，每一种都要求另一半真的在场（后面跟着分／号／负），
所以「一小时之后」「两胜」「一月」这种单独出现的照旧留中文，裸「一」「两」那条
豁免在别处一个字不松。判据 `tests/test_reel_asset_gates.py::test_同一个数不许一半中文一半阿拉伯`。

放在单独的模块里，是因为 `explainer.py` 已经一万三千多行：那边只接一刀
（`arabic_numerals` 里 `one()` 的一个分支）。
"""
from __future__ import annotations

import re

#: 和 `explainer._NUM_CHARS` 同一组字（`_DIGIT` 的键 ＋ 十百千两）。
#: `test_同一个数不许一半中文一半阿拉伯` 钉着两边一致。
NUM = "〇零一二三四五六七八九十百千两"
#: 「X 小时」后面那半截分钟：带「分」的（「四十分钟」「零八分」），或者不带「分」、
#: 但本身含十/百/千会被换成阿拉伯数字的（「一小时十二」→ 不补就是「一小时12」，
#: sabalenka-gibson 已发的那一处）。⚠️ 后面跟「几」的是约数（「一小时十几分钟」），
#: 那一半留中文，这一半也不动——否则成了「1小时十几分钟」，反倒是新的半截。
_MINUTES = rf"(?:[{NUM}]+分|[{NUM}]*[十百千][{NUM}]*(?![几{NUM}]))"


def other_half_is_arabic(text: str, start: int, end: int, run: str, nxt: str) -> bool:
    """这一截裸数字，是不是**同一个数**里另一截会被换成阿拉伯数字的那一半。

    `start`/`end` 是 `one()` 那次匹配（数字＋后面一个字）在 `text` 里的位置，
    `run` 是数字那一截，`nxt` 是紧跟着的那个字。
    """
    before = text[start - 1] if start else ""
    after = text[end:]
    if nxt == "小" and re.match(rf"时{_MINUTES}", after):
        return True                      # 【两】小时四十分钟、【一】小时十二
    if nxt == "个" and re.match(rf"小时{_MINUTES}", after):
        return True                      # 【两】个小时四十分钟
    if text[max(0, start - 2):start] == "小时" and nxt == "分":
        return True                      # 两小时【零八】分、两小时【五】分钟
    if before == "月" and nxt in "号日":
        return True                      # 九月【一】号
    if run == "一" and nxt == "月" and re.match(rf"[{NUM}]+[号日]", after):
        return True                      # 【一】月十九号
    if before == "胜" and nxt == "负":
        return True                      # 十二胜【三】负
    return nxt == "胜" and bool(re.match(rf"[{NUM}]+负", after))   # 【五】胜十九负
