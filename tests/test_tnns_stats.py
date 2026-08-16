"""TNNS 单场统计载荷的解码判据。

⚠️ **fixture 是真数据，不是手搓的。** 下面那份 `_REAL` 是 2026-08-16 从
runner 上真抓回来的 `mode=match_info&submode=stats` 响应里，兹维列夫-诺里
那场分盘三块的**原文片段**（`probe-blocked` run 31952241542 的日志，
`--print-body` 打出来的 `[body 3000]`~`[body 7500]`），K/P 两张表按同一份
响应里打出来的顺序补齐到用得着的下标。

CLAUDE.md：**手搓的 fixture 只能验函数的局部行为，验不了它和真页面对不对
得上**。所以这条测试的核心断言不是「函数能从 dict 里抠字」，而是

    分盘三块的制胜分/非受迫失误加起来，必须等于 app 上显示的全场数字

——解错任何一个 base36 下标都不可能同时对上四个数。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))

import tnns_stats  # noqa: E402


# `K` 是这份响应真实打印出来的 20 项，顺序没动。
_K = ["data", "Match", "title", "players", "key", "values", "replace",
      "Set 1", "keys", "missing", "Set 2", "Set 3", "ZVE by court",
      "NOR by court", "hasExtendedStats", "tabs", "id", "period",
      "refresh_time", "success"]

# `P` 只补到用得着的下标（0~e）——再往后是发球/接发那几组的键名和值，
# 这条测试不碰。⚠️ 顺序不能动：下标就是语义。
_P = ["Zverev", "Norrie", "service_games_won", "Service Games",
      "92% (12/13)", "79% (11/14)", "return_games_won", "Return Games",
      "21% (3/14)", "8% (1/13)", "Key Stats", "dominance_ratio",
      "Dominance Ratio", "Winners", "Unforced Errors"]

# 每一盘的 Key Stats 那一组，原文照抄（`"2"`=title `"4"`=key `"5"`=values）。
def _key_stats(dr, winners, ue):
    return [{"0": [{"2": "p:c", "4": "p:b", "5": dr},
                   {"2": "p:d", "5": winners},
                   {"2": "p:e", "5": ue}],
             "2": "p:a", "3": ["p:0", "p:1"]}]


_REAL = json.dumps({
    "K": _K,
    "P": _P,
    "_": {
        # "1"=Match  "7"=Set 1  "a"=Set 2  "b"=Set 3  "e"=hasExtendedStats
        "0": {
            "1": _key_stats(["1.47", "0.68"], [41, 25], [35, 36]),
            "7": _key_stats(["0.86", "1.16"], [11, 7], [17, 10]),
            "a": _key_stats(["4.77", "0.21"], [13, 8], [5, 9]),
            "b": _key_stats(["1.31", "0.77"], [17, 10], [13, 17]),
            "e": True,
        },
        "j": True,
    },
}, ensure_ascii=False, separators=(",", ":"))


def test_键走K表值走P表两张表不许混用():
    """解码的核心：对象的键是 `K` 的裸 base36 下标，值里 `p:` 才查 `P`。

    混用会解出一堆看着像模像样、实则张冠李戴的字段，而那种错**不报错**。
    """
    got = tnns_stats.decode(_REAL)
    assert set(got) == {"data", "success"}, f"顶层没解对：{sorted(got)}"
    data = got["data"]
    assert "Match" in data and "Set 1" in data and "Set 3" in data, sorted(data)
    row = data["Set 1"][0]["data"][1]
    assert row["title"] == "Winners", row          # p:d → P[13]
    assert row["values"] == [11, 7], row
    # 分组自己的标题也走同一张池
    assert data["Set 1"][0]["title"] == "Key Stats"
    assert data["Set 1"][0]["players"] == ["Zverev", "Norrie"]


def test_分盘加起来必须等于全场():
    """**这条才是「解对了」的判据**，不是上面那条。

    2026-08-16 就是靠它确认下标读法没错：三盘的制胜分 11+13+17=41、7+8+10=25，
    非受迫失误 17+5+13=35、10+9+17=36，四个数同时和 app 上那一屏对上。
    """
    got = tnns_stats.decode(_REAL)
    whole = tnns_stats.winners_ue(got, "Match")
    assert whole == {"winners": [41, 25], "ue": [35, 36]}, whole
    for field, expect in (("winners", [41, 25]), ("ue", [35, 36])):
        total = [0, 0]
        for period in ("Set 1", "Set 2", "Set 3"):
            part = tnns_stats.winners_ue(got, period)
            assert part is not None, f"{period} 少了这两行"
            for i in (0, 1):
                total[i] += part[field][i]
        assert total == expect, f"{field} 分盘合计 {total} ≠ 全场 {expect}"


def test_有没有扩展统计读接口自己声明的那个键():
    """`hasExtendedStats` 比「从缺字段反推」可靠——「这场没有」和「我解错了」
    在产物上长得一模一样，所以要读它自己说的那句。

    ⚠️ 拿不到这个键要返回 `None` 而不是 `False`：默认成 False 就把
    「没查到」说成了「没有」。
    """
    assert tnns_stats.has_extended_stats(tnns_stats.decode(_REAL)) is True
    empty = json.dumps({"K": _K, "P": _P, "_": {"0": {}}})
    assert tnns_stats.has_extended_stats(tnns_stats.decode(empty)) is None


def test_不是这个形状要抛不许静默当成没数据():
    """接口换了形状和「这场没有统计」长得一样——必须抛，不能返回空。"""
    import pytest
    with pytest.raises(ValueError) as err:
        tnns_stats.decode(json.dumps({"matches": []}))
    assert "别当成" in str(err.value)


def test_池下标越界原样留着不许变成None():
    """越界静默变 None，下游会把它当成「这一项没有」——又一次「不吭声」。"""
    assert tnns_stats._from_pool("p:zzz", ["a"]) == "p:zzz"
    assert tnns_stats._from_pool("p:0", ["a"]) == "a"
    # 池里本来就有 "92% (12/13)" 这种值，裸串不许被当成下标
    assert tnns_stats._from_pool("1a", ["a", "b"]) == "1a"
