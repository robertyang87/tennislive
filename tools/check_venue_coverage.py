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

# 已经翻到底、确实拿不到的站——**写在这里是为了别再重跑一遍**。
# 「缺」有两种：一种是还没去找，一种是找过了拿不到，两者在输出里长得一模一样，
# 而后者会被反复重找（孟菲斯那一站就被重找过三轮）。键按赛历里的 `en` 写。
#
# ⚠️ **写进这里之前，先把 CLAUDE.md 里已有的那几条路挨个试一遍。**
# 罗马在这儿躺过一轮：我列了五条走不通的路（Commons 五个年份分类、fitp.it 相册、
# 官网 SPA、意大利语信息页、猜文件名），写得很详细，看起来很尽责——
# 而真正解开它的是 `/-/media/images/atp-tournaments/tournament-images/`，
# **那条规矩早就写在 CLAUDE.md 的「ATP 总站封，赛事域名镜像着同一批图」里**，
# 只是我没往罗马身上试。「某一个源上没有 ≠ 不存在」这次换的壳是
# **「我试过的源里没有 ≠ 我把该试的都试了」**。
KNOWN_GAPS = {
    "Grand Prix Auvergne-Rhone-Alpes":
        "2026 年首办、首届还没打（10-18 起），LDLC Arena 没有网球布置的实拍。"
        "官网唯一一张 LDLCARENA_Tenniscourt.jpg 是 3D 效果图——观众是重复贴图、"
        "人物是 CG，正是「新赛事新场馆先放渲染图」那一类。Commons 的 "
        "Category:LDLC Arena 只有演唱会、施工和外立面。**打完首届再来取**。",
    "Abierto Mexicano Telcel":
        "场馆是 Arena GNP Seguros（2022 起，室内外混合的新馆）。官网"
        "abiertomexicanodetenis.com（WordPress）媒体库里 1500px 以上的 142 张——"
        "⚠️ **这一档还没查完**：抓联系表时 24 张里有 11 张取不到（限流，不是不存在），"
        "看过的 13 张是球员动作、发布会、颁奖。搜到的场馆全景两类都不合格："
        "一类是**空场**（开赛前的宣传照，看台全空），一类是开幕式夜景"
        "（GQ 那张 1600x1067：均值 40.3 / 中位 **16** / 69% 暗于 50，"
        "属于「中位数接近 0 就是一半以上纯黑」那一类，怎么裁都救不回来）。"
        "**下次从这儿接着做**：把媒体库剩下的 118 张分批抓完再判。",
    "Grand Prix Lalla Meryem":
        "官方域名没找到活的（grandprixlallasalmameryem.com 解析不了）；"
        "摩洛哥网球协会 frmt.ma 是 WordPress，但站上是协会通用内容。"
        "搜到的两类都不合格：bakir.co 那批 1800x1195 是**空场**（蓝天、无观众），"
        "其余是颁奖典礼特写。**还没试的**：摩洛哥媒体（Le Matin、Medias24、le360）"
        "的赛事图集，以及 WTA 官方图库按赛事 id 取 hero。",
    "Mérida Open":
        "官方站是 wtameridaopen.com（WordPress，**不是** meridaopen.mx / abiertogntmerida，"
        "那两个域名解析不了）。媒体库 279 条全量分页取下、按尺寸筛出 78 张、拼成两张"
        "联系表逐格看过——**全是球员动作和颁奖**，唯一一张全景是空场白天的航拍。"
        "⚠️ 网上广泛转载的那张「梅里达中央球场」（rastroinformativo 等站，1600x1067，"
        "蓝色球场 + 满场看台 + 黄昏）**是瓜达拉哈拉**——远端建筑上印着 GUADALAJARA。"
        "转载站配了别站的图，标题却写着梅里达。**还没试的**：尤卡坦本地媒体"
        "（Diario de Yucatán、La Jornada Maya）的赛事图集。",
    "ATX Open":
        "官方站 atxopen.com（WordPress）媒体库全量列过：球员动作 + 两张 DJI 航拍。"
        "航拍是**整个球场群**（Westwood Country Club 一片场地 + 奥斯汀天际线），"
        "中心球场只占一角，竖切会把它切掉。官网那张 1800x929 的 stadium 图**是效果图**"
        "——文件名自己写着 `ATX Open Unveils Stadium Rendering`。"
        "**还没试的**：奥斯汀本地媒体（Austin American-Statesman、KVUE）的赛事图集。",
    "Grand Prix Hassan II":
        "ATP 主视觉（marrakech_tournimage_2019）是**场地平视**：下半屏全是空红土，"
        "近端没有看台，碗读不出来。官网 grandprixhassan2.com（WordPress+Elementor）"
        "媒体库里 1750x1163 那一批是**赛事简报的版面图**（La Gazette 的 PDF 转图），"
        "不是照片；唯一一张场地照 CHF_2050 是从底线平视，同样只有一侧看台。"
        "**还没试的**：摩洛哥媒体（Le Matin、Medias24）与皇家网球俱乐部自己的社媒。",
    "Gonet Geneva Open":
        "ATP 赛事域名上有一张 2560x1440 的无人机图，但那是**整个 Parc des Eaux-Vives**"
        "（球场群 + 日内瓦湖 + 大喷泉），中心球场在左下角只占一块，竖切留中间 42% 正好"
        "把它切掉。裁出中心球场那一块只有约 900x700，放大 2 倍以上，太软。"
        "站上其余的图是球员照和 VIP 区。**还没试的**：Tribune de Genève / RTS 的赛事图集。",
    "Berlin Open":
        "官方站是 berlintennisopen.com（Webflow，**不是** berlin-tennis-open.com/.de，"
        "那些解析不了）。站上的图统一压到 **1030x618**，套到 1080x1440 的卡上要放大 2.33 倍。"
        "搜到的 Steffi-Graf-Stadion 全景清一色在 alamy / getty / dreamstime 上（带水印）。"
        "**还没试的**：主办方 LTTC Rot-Weiß Berlin 自己的站（rot-weiss-berlin.de，通）、"
        "Tagesspiegel / rbb24 的赛事图集原图。",
    "Almaty Open":
        "官方图库在 ktf.kz（almatyopen.kz 的相册全指过去，六本 290 张）。"
        "沙箱里 curl / urllib / Chromium 三条路都是 CERTIFICATE_VERIFY_FAILED，"
        "我据此写过「换个能出网的环境重跑即可」——**那句是错的，已经验过**："
        "2026-07-31 从 GitHub Actions 的 runner（另一个出口、正常的 CA）再探两张，"
        "报的是 `ERR URLError`，连不上。同一次跑里里约那张对照图 200 + 2048x929 取到了，"
        "所以不是工具的问题。**换出口这条路对 ktf.kz 无效**，"
        "这个主机从两个完全不同的网络都到不了。"
        "Commons 只有冰球馆外景和大运会开幕式。"
        "下一步只能换源：哈萨克斯坦本地新闻站（tengrinews / vesti.kz / sports.kz）的赛事图集。",
}


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
        note = "  ← 已查明拿不到" if r["slug"] is None and r["en"] in KNOWN_GAPS else ""
        print(f"{r['start']}  {r['tier']:<8} {flag:<8} {r['zh'][:22]:<24}"
              f" {r['loc'][:10]:<12} {r['slug'] or ''}{note}")

    gaps = [r for r in shown if r["slug"] is None and r["en"] in KNOWN_GAPS]
    if gaps:
        print("\n已查明拿不到的站（别再重找，换环境或等赛事打完再说）：")
        for r in gaps:
            print(f"  · {r['zh']}：{KNOWN_GAPS[r['en']]}")

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
