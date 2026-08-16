#!/usr/bin/env python3
"""TNNS Live 的单场技术统计：**制胜分和非受迫失误在这儿**。

来路：2026-08-16 账号所有者问「怎么 ATP 的比赛统计卡片里没有制胜分和 UE 了」，
我按 flashscore 量了一遍答「这两场接口里没有」——**范围说窄了**。他甩来一张
TNNS Live 的截图，那两行就在上面。这正是 CLAUDE.md 那条「查空一类不等于查空
全部」：flashscore 没有 ≠ 没有。

⚠️ **而 CLAUDE.md 里「WTA 巡回赛这一段探到底了」那张表，从来没有 TNNS 这一行**
——当年的结论是「要开 Chromium，成本大于收益，不接入」，于是它连「查过」的
资格都没拿到。

## 接口：两跳，都要真浏览器

    ① 当天赛程   GET api.tnnslive.com/v1/matches?date=YYYY-MM-DD&web=true
                 → all_matches[] 里按球员名找，拿数字 id（`k`，如 "73465930"）
    ② 这一场     GET api.tnnslive.com/v1/web?id=<数字id>&mode=match&web=true
                 → 返回里带**文档 id**（Firestore 风格，如 uQOZWJNEaZOS9ZAc0rlj）
    ③ 统计       GET api.tnnslive.com/v1/web?id=<文档id>&mode=match_info&submode=stats&web=true

⚠️ **`context.request` 和 curl 都是 403**（Cloudflare 的 `Just a moment` 挑战页，
五六千字节 HTML），只有**真浏览器加载页面之后在页面里 fetch** 才过得去。见
`tools/probe_tnns.py`。所以这条只能在 runner 上跑，一次 25~30 秒且不可缓存。

⚠️ **响应的 `content-type` 是 `text/html; charset=utf-8`，不是 json。** 按类型
过滤会把整份正文丢掉——`probe_tnns.py` 原来就是这么丢的，白跑了两趟 runner。

## 载荷是字典压缩，不是普通 JSON

    {"K": [...键名...], "P": [...字符串池...], "_": {真数据}}

* `_` 里对象的**键**是 **base36 下标**，指向 `K`：`"0"`→K[0]、`"a"`→K[10]、`"10"`→K[36]
* 值里凡是 `"p:XX"` 形式的字符串，是 **`P[base36(XX)]`**
* 嵌套里两条规则一直生效

这一场（兹维列夫-诺里）解出来的 K 是

    data Match title players key values replace "Set 1" keys missing
    "Set 2" "Set 3" "ZVE by court" "NOR by court" hasExtendedStats tabs
    id period refresh_time success

所以 `data` 底下按 `Match` / `Set 1` / `Set 2` / `Set 3` / 按发球区分块；每块是
若干**分组**（Key Stats / Service / Return / Points Won / Games Won…），每组
`{title, key, values, keys, missing}`，每行 `{title, key, values:[主, 客]}`。

## 判据：三盘加起来必须等于全场

解错任何一个下标都不可能同时对上四个数，所以这是**自证**，不是声明：

    Set1 W 11/7  + Set2 13/8  + Set3 17/10 = 41/25   ← 和 app 上的 Winners 一致
    Set1 UE 17/10 + Set2 5/9  + Set3 13/17 = 35/36   ← 和 app 上的 Unforced 一致

顺带七项和 flashscore 逐个对得上（Ace 16/3、双误 5/6、一发得分 33/39 与 42/64、
二发 20/35 与 23/47、破发点救下 2/3 与 13/16 ＝ 转化 1/3 与 3/16），所以这两行
不是另一套口径。

⚠️ **一发的分母不要从这儿取**：TNNS 给诺里 `57% (64/113)`，而 `first_in +
second_total` 是 64+47=**111**。数据图画的是 `first_in / first_total`，用和式才
自洽（CLAUDE.md 早写过）。**只从 TNNS 取 Winners / UE**，其余照旧 flashscore。

    python3 tools/tnns_stats.py decode <正文文件>       # 解一份已经拿到手的正文
    python3 tools/tnns_stats.py decode - < body.txt
"""

from __future__ import annotations

import json
import sys
from typing import Any

# `_` 里的键和 `p:` 后面那一段都是 base36（0-9a-z），`int(s, 36)` 直接认。
_POOL_PREFIX = "p:"


def _from_pool(value: Any, pool: list) -> Any:
    """`"p:1a"` → `pool[46]`；其余原样。

    ⚠️ **只认 `p:` 前缀，别对所有字符串都试 base36**——池里本来就有
    `"92% (12/13)"` 这种值，而 `"1a"` 这样的裸串在真实数据里也可能是个值。
    """
    if isinstance(value, str) and value.startswith(_POOL_PREFIX):
        try:
            return pool[int(value[len(_POOL_PREFIX):], 36)]
        except (ValueError, IndexError):
            return value          # 下标越界就原样留着，别静默变成 None
    return value


def expand(node: Any, keys: list, pool: list) -> Any:
    """把 `K`/`P`/`_` 那套索引压缩还原成人读得懂的结构。

    ⚠️ **键和值走的是两张表**：键是 `K` 的 base36 下标（**裸的**，没有前缀），
    值是 `P` 的下标（**带 `p:` 前缀**）。两张表混着用会解出一堆看着像模像样、
    实则张冠李戴的字段——而那种错**不报错**，只会让数据图上多两行假数。
    这一条的判据是「三盘加起来等于全场」，见模块 docstring。
    """
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            try:
                name = keys[int(str(k), 36)]
            except (ValueError, IndexError):
                name = str(k)     # 解不出来就留原样，好排查
            out[name] = expand(v, keys, pool)
        return out
    if isinstance(node, list):
        return [expand(v, keys, pool) for v in node]
    return _from_pool(node, pool)


def decode(body: str) -> dict:
    """整份响应 → 还原后的 dict。不是这个形状就抛，别猜。"""
    data = json.loads(body)
    if not (isinstance(data, dict) and {"K", "P", "_"} <= set(data)):
        raise ValueError(
            "不是 TNNS 的 K/P/_ 索引压缩载荷——顶层键是 "
            f"{sorted(data)[:8] if isinstance(data, dict) else type(data).__name__}。"
            "⚠️ 别当成「这场没有统计」：接口换了形状和这场没数据长得一样。")
    return expand(data["_"], data["K"], data["P"])


def _rows(block: Any) -> list[dict]:
    """一块（Match / Set 1 / …）里所有行摊平成 `{title, key, values}`。"""
    out: list[dict] = []
    for group in block if isinstance(block, list) else []:
        for row in (group or {}).get("data") or []:
            if isinstance(row, dict) and "title" in row:
                out.append(row)
    return out


def winners_ue(decoded: dict, period: str = "Match") -> dict | None:
    """取某一块的制胜分和非受迫失误；这一块没有这两行就返回 None。

    ⚠️ **返回 None 要和「拿不到数据」分开报**：`hasExtendedStats` 是接口自己
    声明的，读它比从缺字段反推可靠——「没有这两行」和「我解错了」在产物上
    长得一模一样。
    """
    block = (decoded.get("data") or {}).get(period)
    if block is None:
        return None
    found: dict[str, list] = {}
    for row in _rows(block):
        if row.get("title") == "Winners":
            found["winners"] = row.get("values")
        elif row.get("title") == "Unforced Errors":
            found["ue"] = row.get("values")
    if "winners" not in found or "ue" not in found:
        return None
    return found


def has_extended_stats(decoded: dict) -> bool | None:
    """接口自己声明这场有没有扩展统计。拿不到这个键就返回 None，别默认 False。"""
    return (decoded.get("data") or {}).get("hasExtendedStats")


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] != "decode":
        print(__doc__)
        return 2
    src = sys.argv[2]
    body = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    decoded = decode(body)
    data = decoded.get("data") or {}
    print(f"hasExtendedStats: {has_extended_stats(decoded)}")
    print(f"分块：{[k for k in data if isinstance(data[k], list)]}")
    for period in ("Match", "Set 1", "Set 2", "Set 3"):
        got = winners_ue(decoded, period)
        if got:
            print(f"  [{period:6s}] 制胜分 {got['winners']}　非受迫失误 {got['ue']}")
        elif period in data:
            print(f"  [{period:6s}] 这一块没有这两行")
    # 自证：分盘加起来要等于全场。对不上就是解错了，宁可红也别把假数发出去。
    sets = [winners_ue(decoded, p) for p in ("Set 1", "Set 2", "Set 3")]
    sets = [s for s in sets if s]
    whole = winners_ue(decoded, "Match")
    if whole and sets:
        for field in ("winners", "ue"):
            tot = [sum(s[field][i] for s in sets) for i in (0, 1)]
            ok = "✅" if tot == list(whole[field]) else "❌ 对不上，多半解错了"
            print(f"  自证 {field}：分盘合计 {tot} vs 全场 {whole[field]}  {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
