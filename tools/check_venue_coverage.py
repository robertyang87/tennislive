#!/usr/bin/env python3
"""拿 2026 赛历逐站去对场馆图，缺哪站一目了然。

场馆图这条线一直是**按遇到的站补**——今天日报里出现哪站就去找哪站的图。
好处是永远在做最急的；坏处是**永远不知道还差多少**，也不知道八月要开的站
现在有没有图。这个脚本把赛历当清单，用**渲染时真正走的那条路**
（`venue_asset_for_match`）逐站问一遍「这站有图吗」，答案分三档：

- `centre-court` —— 有图，而且已经验过是中心球场全景
- `landmark`     —— 有图，但还是兜底（地标 / 没有看台的俱乐部）
- `缺`           —— 一张都没有，卡片会退回通用底

判据是**真的调匹配函数**，不是比对 slug 字符串：别名写错、host_years 写错、
credits 缺字段导致整条被丢弃，这些都只有走一遍才看得见。

用法：
    python tools/check_venue_coverage.py            # 全年，按日期排
    python tools/check_venue_coverage.py --missing  # 只列缺的
    python tools/check_venue_coverage.py --from 07  # 只看 7 月起
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennislive.models import Match, MatchStatus, Player, Tour, Tournament  # noqa: E402
from tennislive.render.venue_assets import venue_asset_for_match  # noqa: E402

CALENDAR = ROOT / "data" / "tour_calendar_2026.json"
MANIFEST = ROOT / "data" / "venue_assets.json"

# 不算进覆盖率的：团体赛和年终总决赛没有固定主场馆；125 不在账号所有者定的
# 范围里（他给的清单只含 250 / 500 / 1000 + 大满贯）。
# ⚠️ 125 这一档要单独排除，不能靠「manifest 里没有就算了」——伊斯坦布尔和
# 罗马 ATV 这两条恰好就是 125，留在分母里会让覆盖率永远差两站。
SKIP_TIERS = {"团体", "年终", "WTA125", "ATP125"}


def _match_for(event: dict, year: int = 2026) -> Match:
    """按赛历条目造一场假比赛——**start 要给**，加拿大那条按年份挑城市。"""
    month, day = (int(x) for x in str(event.get("start", "01-01")).split("-")[:2])
    tour = Tour.WTA if str(event.get("tour")) == "wta" else Tour.ATP
    return Match(
        match_id="coverage", tour=tour,
        # city/country 留空，复刻真实 digest 的样子——真实数据里它们恒为 None，
        # 按城市写的别名在线上根本不会命中，这里也不能给它作弊的机会
        tournament=Tournament(name=str(event.get("en") or ""), tour=tour),
        home=[Player(name="A")], away=[Player(name="B")],
        status=MatchStatus.SCHEDULED, round_name="R32", discipline="Singles",
        start_utc=datetime(year, month, day, 12, tzinfo=timezone.utc),
        sets=[], winner=None,
    )


def survey(year: int = 2026) -> list[dict]:
    events = json.loads(CALENDAR.read_text(encoding="utf-8"))["events"]
    shots = {row["slug"]: row.get("shot") for row in
             json.loads(MANIFEST.read_text(encoding="utf-8"))}
    out = []
    for event in events:
        if event.get("tier") in SKIP_TIERS:
            continue
        asset = venue_asset_for_match(_match_for(event, year))
        out.append({
            "start": event.get("start", ""),
            "tier": event.get("tier", ""),
            "tour": event.get("tour", ""),
            "zh": event.get("zh", ""),
            "en": event.get("en", ""),
            "loc": event.get("loc", ""),
            "slug": asset.slug if asset else None,
            "shot": shots.get(asset.slug) if asset else None,
        })
    out.sort(key=lambda r: (r["start"], r["tier"], r["zh"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--missing", action="store_true", help="只列没有场馆图的")
    ap.add_argument("--from", dest="since", default="", help="只看这个月份起，如 07")
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()

    rows = survey(args.year)
    if args.since:
        rows = [r for r in rows if r["start"][:2] >= args.since]

    mark = {"centre-court": "✅", "landmark": "⚠️ 兜底", None: "❌ 缺"}
    shown = [r for r in rows if not args.missing or r["slug"] is None]
    for r in shown:
        flag = mark.get(r["shot"], "⚠️ 兜底")
        print(f"{r['start']}  {r['tier']:<8} {flag:<8} {r['zh'][:22]:<24}"
              f" {r['loc'][:10]:<12} {r['slug'] or ''}")

    total = len(rows)
    ok = sum(1 for r in rows if r["shot"] == "centre-court")
    fall = sum(1 for r in rows if r["slug"] and r["shot"] != "centre-court")
    miss = total - ok - fall
    print(f"\n共 {total} 站（不含团体赛、年终总决赛与 125）："
          f"中心球场 {ok} / 兜底 {fall} / 缺 {miss}"
          f"　—— 覆盖 {ok * 100 // total}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
