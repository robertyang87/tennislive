#!/usr/bin/env python3
"""扫 `specs/reels/pending/` 的草稿：**赢家有没有被记反**。

来路（2026-09-16）：`keys-zheng.draft.json` 把 9 月 5 日美网第三轮记成
「凯斯 1-6 7-6(3) 7-5 郑钦文」——赢的是郑钦文。三个源核过：WTA 自己的稿
`/news/4572496/zheng-saves-match-point-rallies-from-5-0-down-in-third-set-to-stun-keys-at-us-open`、
美联社 9 月 5 日那条、以及 flashscore 逐分表本身（home 决胜盘 5-0 领先、
5-2 手里有一个赛点，之后连丢七局——那是凯斯的形状，不是郑钦文的）。

**根因是两份 feed 的 home/away 错位**，而不是哪个数抄错了：

    cover.matchup        ← matchup_order() 读 df_hh_1 的 FH/FK
    set_scores_home_away ← final_set_scores() 读 df_mh_1 的 home/away

`verified_match_fact` 拿前者当名字、后者当比分，两边一错位，算出来的赢家就是
反的——而**四道闸一道都不响**：`verified_result_problem` 是拿 `_match` 自己的
内部字段反推的，输入错了、输出照样自洽。CLAUDE.md 那条「⚠️ `versus.names`
是版式顺序，不是赛果顺序」说的正是这个形状。

错位本身在 3642d09d 修掉了（df_hh_1 里 FH/FK 每次交手都重复一遍，老代码把整份
body 收成一个 dict，取到的是**最早那次**交手的 home/away；现在按 KP 认领本场
那条记录）。**但修之前生成的草稿没有重跑**，错的赢家还躺在仓库里。

所以这个脚本不查内部自洽，查的是**草稿的 participants 顺序和 flashscore 现在
给的 home/away 对不对得上**——对不上就是修之前的产物，赢家很可能是反的。

2026-09-16 实测 103 份：对得上 75，对不上 27，没法判 1。对不上的那 27 份里，
有四份能拿公开事实当场判死（谢尔顿输给西西帕斯、兹维列夫输给阿利斯、
斯瓦泰克输给布兹科娃、莱巴金娜输给博萨斯·马内罗——这四条都和这四个人当周的
实际战绩相反）。

用法：

    python3 tools/check_draft_matchup_order.py            # 扫全部
    python3 tools/check_draft_matchup_order.py --only keys-zheng

⚠️ 它要联网（每份草稿一次 df_hh_1）。退出码 1 = 有对不上的。
⚠️ **不要拿它自动翻**：翻之前先拿一个独立源核这一场到底谁赢了。
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from assemble_spec import matchup_order  # noqa: E402

PENDING = "specs/reels/pending/*.draft.json"


def check(path: str) -> tuple[str, list | None, list | None]:
    """回 (状态, 记着的顺序, 应该的顺序)。状态是 ok / mismatch / skip。"""
    draft = json.load(open(path, encoding="utf-8"))
    match = draft.get("_match") or {}
    mid = match.get("flashscore_id")
    recorded = match.get("participants")
    matchup = (draft.get("cover") or {}).get("matchup") or []
    if not mid or not recorded or len(matchup) != 2:
        return "skip", None, None
    names_en = [str(p.get("name_en") or "") for p in matchup]
    if not all(names_en):
        return "skip", None, None
    ordered = matchup_order(names_en[0], names_en[1], mid)
    want = [zh for _en, zh in ordered]
    return ("ok" if want == recorded else "mismatch"), recorded, want


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="只查这一份草稿（slug，不带 .draft.json）")
    ap.add_argument("--sleep", type=float, default=0.2, help="每份之间歇多久")
    args = ap.parse_args()

    files = sorted(glob.glob(PENDING))
    if args.only:
        files = [f for f in files if pathlib.Path(f).stem == f"{args.only}.draft"]
        if not files:
            print(f"没有这份草稿：{args.only}")
            return 2

    ok, bad, skipped = 0, [], []
    for path in files:
        slug = pathlib.Path(path).stem
        try:
            state, recorded, want = check(path)
        except Exception as exc:  # noqa: BLE001 —— 一份读不到别拖垮整趟
            skipped.append((slug, f"{type(exc).__name__}: {exc}"))
            continue
        if state == "skip":
            skipped.append((slug, "没有 _match / matchup / name_en"))
        elif state == "ok":
            ok += 1
        else:
            bad.append((slug, recorded, want))
        time.sleep(args.sleep)

    print(f"扫了 {len(files)} 份：对得上 {ok}，对不上 {len(bad)}，没法判 {len(skipped)}")
    # ⚠️ 不合格的也要列出来（CLAUDE.md「检查工具要把不合格的也列出来」）。
    for slug, recorded, want in bad:
        print(f"  ✗ {slug}：记着 {recorded}，flashscore 现在给的是 {want}")
    for slug, why in skipped:
        print(f"  – {slug}：{why}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
