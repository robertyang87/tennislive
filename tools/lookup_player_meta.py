#!/usr/bin/env python3
"""查一个球员的**国别（IOC 码）**和**即时世界排名**，给封面的 `versus.top/bottom` 用。

账号所有者 2026-08-02：「以后封面上所有球员的名字旁边要加上他的国旗，对阵的同时
在后面括号里面加上他的即时的世界排名」。这两样**都不许手打**——和译名一样，
手打的那一刻就已经在赌记忆了。

    PYTHONPATH=src python3 tools/lookup_player_meta.py "Alexandra Eala" "Naomi Osaka"

两个数各有各的来源，别混：

- **国别**来自比赛数据（ESPN scoreboard 的 `competitor.athlete.flag.href`，
  路径末尾就是 IOC 码 `…/countries/500/phi.png`）。这是**赛事方登记的国籍**，
  比按名字猜可靠——「Eala 是菲律宾人」这种事我知道，但下一个人未必。
- **排名**来自 ESPN 的 rankings 接口（`sources/rankings.py` 已经在用）。
  ⚠️ **它只给到每个巡回赛前 150**，掉出 150 的查不到，这时候不是「没有排名」，
  是「这个源看不见」——脚本会把这两种情况分开报，别把它们写成同一个值。

**排名是快照，不是常量。** 写进 spec 的是「这条片子讲的那场球前后」的排名，
所以取数要挨着写 spec 的时间做，并在 `_why` 里记下取数日期。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

UA = {"User-Agent": "Mozilla/5.0"}
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/tennis/"
              "{league}/scoreboard?dates={date}")


def country_from_scoreboard(name: str, dates: list[str]) -> str:
    """扫这几天的赛程，找这个人，取赛事方登记的 IOC 码。"""
    want = name.strip().lower()
    for date in dates:
        for league in ("wta", "atp"):
            url = SCOREBOARD.format(league=league, date=date)
            try:
                data = json.load(urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=45))
            except Exception as exc:  # noqa: BLE001
                print(f"  [{league} {date}] 取不到：{exc}")
                continue
            for event in data.get("events") or []:
                for group in event.get("groupings") or []:
                    for comp in group.get("competitions") or []:
                        for who in comp.get("competitors") or []:
                            ath = who.get("athlete") or {}
                            if (ath.get("displayName") or "").lower() != want:
                                continue
                            href = ((ath.get("flag") or {}).get("href") or "")
                            code = href.rsplit("/", 1)[-1].split(".")[0].upper()
                            if code:
                                return code
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+", help="ESPN 上的英文名，如 \"Naomi Osaka\"")
    ap.add_argument("--dates", nargs="*", default=[],
                    help="查国别时扫哪几天的赛程（YYYYMMDD），默认只查排名")
    args = ap.parse_args()

    from tennislive.sources.rankings import fetch_rankings, rank_map  # noqa: PLC0415
    from tennislive.zh import player_zh  # noqa: PLC0415
    from tennislive.zh.countries import country_flag  # noqa: PLC0415

    ranks = fetch_rankings()
    both = {**rank_map(ranks.atp), **rank_map(ranks.wta)}
    depth = f"ATP 前 {len(ranks.atp)} / WTA 前 {len(ranks.wta)}"
    print(f"排名榜单深度：{depth}\n")

    for name in args.names:
        zh = player_zh(name)
        rank = both.get(" ".join(name.strip().lower().split()))
        code = country_from_scoreboard(name, args.dates) if args.dates else ""
        flag = country_flag(code) if code else ""
        print(f"{name}  →  {zh}")
        print(f'  "country": {code!r}   {flag or "（没查国别，给 --dates）"}')
        if rank is None:
            # **「查不到」不等于「没有排名」。** 榜单只到 150，掉出去的人在这儿
            # 一样是 None——照 null 写进 spec 就等于替他声明了一件没核过的事。
            print('  "rank": ??   ← 这个榜单里没有他。要么他在 150 名开外'
                  '（去 WTA/ATP 官网查真实名次），要么名字对不上。'
                  '确认真的没有排名再写 null')
        else:
            print(f'  "rank": {rank}')
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
