#!/usr/bin/env python3
"""场次覆盖率：这个赛事一共打了多少场单打，其中多少场有场上采访。

和 `oncourt_coverage.py` 的区别是**分母**。那个算的是「关键轮次占理论 8」，
回答不了「一共打了多少场、覆盖了几成」——被问到才发现口径不对。

    oncourt_coverage.py   分母 = 8（决赛 2 + 半决 2 + 八强 4）
    这个脚本              分母 = 签表 − 1，该赛事单打总场次

**逐轮封顶**是必须的：库里跨 2022–2026 多届，美网「决赛」有 7 条（七届各一条），
不封顶算出来是 700%。封顶之后这个数的意思是「**最好的一届能覆盖到几成**」，
是上限不是均值——报的时候要说清楚。

用法：
    python tools/oncourt_match_coverage.py                 # 全部
    python tools/oncourt_match_coverage.py --min-tier 500  # 只看 500 及以上
    python tools/oncourt_match_coverage.py --target 80     # 标出没达标的
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.oncourt_coverage import haystack, load, side  # noqa: E402

# **只算单打正赛**。分母是单打签表，分子里混进双打/轮椅/青少年就是虚高——
# 澳网那 835 条新增里有 213 条是双打（`Kostyuk/Ruse On-Court Interview`
# 这种斜杠配对），不滤掉的话「100%」是假的。
# 双打识别用 feed.is_doubles（斜杠配对 + 带限定词的 doubles，
# 光秃秃的 "doubles" 不认——那会误伤单打球员在谈双打的条目）。
_NOT_SINGLES = re.compile(r"wheelchair|quad\b|\bjunior|\bboys'?\b|\bgirls'?\b"
                          r"|legends|invitational|exhibition", re.I)


def is_main_singles(item: dict) -> bool:
    """这条算不算单打正赛。双打、轮椅、青少年、传奇表演赛都不算。"""
    return not feed.is_doubles(item) and not _NOT_SINGLES.search(item.get("title", ""))

_spec = importlib.util.spec_from_file_location("feed", ROOT / "tools" / "oncourt_feed.py")
feed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(feed)

# 各轮场次数，从决赛倒推。签表小的赛事前面的轮次不存在。
_SIZES = {"决赛": 1, "半决赛": 2, "四分之一决赛": 4, "十六强": 8,
          "第三轮": 16, "第二轮": 32, "第一轮": 64}
TIER_RANK = {"大满贯": 4, "ATP1000": 3, "WTA1000": 3, "ATP500": 2, "WTA500": 2,
             "ATP250": 1, "WTA250": 1}


def rounds_of(draw: int) -> dict[str, int]:
    """这个签表里每一轮有几场。

    倒推而不是正推：**轮次名是按「离决赛多远」定的**，
    32 签的「第一轮」有 16 场，128 签的「第一轮」有 64 场，同名不同量。
    """
    keep, used = {}, 0
    for r in ["决赛", "半决赛", "四分之一决赛", "十六强", "第三轮", "第二轮", "第一轮"]:
        if _SIZES[r] == 1 or _SIZES[r] * 2 <= draw:
            keep[r] = min(_SIZES[r], max(draw - used, 0) or _SIZES[r])
        used = sum(keep.values())
    return keep


def coverage(items: dict, events: list) -> list[dict]:
    rows = []
    for ev in events:
        if not ev.get("matches"):
            continue
        rx, own = re.compile(ev["pat"], re.I), set(ev.get("srcs", ()))
        hits, unknown = [], 0
        for it in items.values():
            if it.get("source") not in own and not rx.search(haystack(it)):
                continue
            if not is_main_singles(it):
                continue
            s = side(it)
            # **认不出性别的不算进单巡回赛事的分子。**
            #
            # `oncourt_coverage.py` 那边是放过去的（宁可多算也别把真条目丢在
            # 报表外面），那里报的是「有没有覆盖」，多算不致命。**这里报的是
            # 占某一张签表的百分比，多算就是虚高**：一条认不出性别的条目会
            # 在男单和女单**各算一次**，两个 127 的分母同时被它填。
            #
            # 实测过洞有多大：澳网男单进入统计的 847 条里 365 条认不出性别
            # （43%），女单 799 条里 365 条——**就是同一批**。那时男单报 100%、
            # 女单 99%。改用 top 500 排名快照认人之后认出率 78% → 88%，
            # 剩下认不出的一律不算。
            if ev["tour"] != "both" and s != ev["tour"]:
                unknown += s is None
                continue
            hits.append(it)
        if not hits:
            continue
        tbl = rounds_of(ev["draw"])
        byr = collections.defaultdict(set)
        for h in hits:
            rd = feed.parse_round(h)
            if rd in tbl:
                # 球员指纹：标题前 34 字去掉非字母，够区分同轮不同人
                byr[rd].add(re.sub(r"[^a-z]", "", h["title"][:34].lower())[:14])
        covered = sum(min(len(v), tbl[k]) for k, v in byr.items())
        rows.append({**ev, "hits": len(hits), "covered": covered, "unknown": unknown,
                     "rate": covered / ev["matches"],
                     "byround": {k: (len(v), tbl[k]) for k, v in sorted(byr.items())}})
    return sorted(rows, key=lambda r: -r["rate"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-tier", type=int, default=0,
                    help="只看这个级别及以上：250/500/1000（大满贯永远算在内）")
    ap.add_argument("--target", type=float, help="达标线（百分数），标出没到的")
    args = ap.parse_args()

    items, events = load()
    rank = {0: 0, 250: 1, 500: 2, 1000: 3}[args.min_tier] if args.min_tier in (0, 250, 500, 1000) else 0
    rows = [r for r in coverage(items, events) if TIER_RANK.get(r["tier"], 0) >= rank]

    print(f"{'赛事':20s}{'级别':9s}{'总场次':>5}{'有采访':>6}{'覆盖率':>7}  逐轮（有/该轮场次）")
    miss = []
    for r in rows:
        det = " ".join(f"{k[:2]}{a}/{b}" for k, (a, b) in r["byround"].items())
        flag = ""
        if args.target and r["rate"] * 100 < args.target:
            flag = " ←未达标"
            miss.append(r)
        print(f"{r['zh'][:18]:20s}{r['tier']:9s}{r['matches']:>5}{r['covered']:>7}"
              f"{r['rate']:>8.0%}  {det[:52]}{flag}")
    tm = sum(r["matches"] for r in rows)
    tc = sum(r["covered"] for r in rows)
    tu = sum(r["unknown"] for r in rows)
    print(f"\n{len(rows)} 站合计：总场次 {tm}，有采访 {tc}，整体 {tc/tm:.0%}")
    if tu:
        # 被丢掉的也要报出来。只在成功时出声的检查，没法证明它真的看过。
        print(f"另有 {tu} 条**认不出球员性别**，没算进任何一侧的分子"
              f"（认出率 88%，剩下多是 2017–2021 的老条目）")
    if args.target:
        need = sum(int(r["matches"] * args.target / 100) - r["covered"] for r in miss)
        print(f"达标线 {args.target:.0f}%：{len(miss)}/{len(rows)} 站未达标，"
              f"补齐还差 **{need} 场**")
    print("\n口径：库里跨多届，逐轮封顶统计——这个数是「最好的一届能覆盖到几成」，是上限不是均值。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
