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

# 不算进覆盖率的几档。**「不算进分母」不等于「不用有图」**——这两件事我混过一次，
# 于是七条团体／年终就这么从视野里消失了，卡片一直在用通用底。
#
# ⚠️ 我原来在这儿写的理由是「团体赛和年终总决赛没有固定主场馆」。
# **对团体赛成立，对年终总决赛不成立**：都灵、吉达是签了多年的固定场馆，
# 比利·简·金杯也定在深圳。真正没有固定主场的只有联合杯（珀斯／悉尼两城）
# 和拉沃尔杯（每年换国家）。
#
# 排除在分母外仍然对——账号所有者给的清单是 250 / 500 / 1000 + 大满贯——
# 但它们**会出现在日报里**（ATP 年终是全年最大的赛事之一），所以下面单列一节
# 报出来，别让「没算」再变成「看不见」。
#
# ⚠️ 125 这一档要单独排除，不能靠「manifest 里没有就算了」——伊斯坦布尔和
# 罗马 ATV 这两条恰好就是 125，留在分母里会让覆盖率永远差两站。
SKIP_TIERS = {"团体", "年终", "WTA125", "ATP125"}

# 这几条虽然不算进覆盖率，但场馆是定死的，**必须有图**。
# 联合杯（两座城市轮流）和拉沃尔杯（每年换国家）不在此列。
FIXED_VENUE_OFF_LEDGER = {
    "Nitto ATP Finals", "WTA Finals Indian Wells",
    "Next Gen ATP Finals", "Billie Jean King Cup Finals", "Davis Cup Finals",
}

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
    "Grand Prix Lalla Meryem":
        "官方域名没找到活的（grandprixlallasalmameryem.com 解析不了）；"
        "摩洛哥网球协会 frmt.ma 是 WordPress，但站上是协会通用内容。"
        "搜到的两类都不合格：bakir.co 那批 1800x1195 是**空场**（蓝天、无观众），"
        "其余是颁奖典礼特写。"
        "WTA 主视觉**是有的**（`.../1005-Rabat.JPG?width=2400` → 2400x983）——"
        "⚠️ 我第一遍扫赛事页时说「没有」，那是**我的正则漏了大小写**："
        "扩展名写的是大写 `.JPG`，而我按 `\\.(jpg|jpeg|png|webp)` 不带 re.I 匹配。"
        "拿到之后打开看：**court-level 视角、一侧看台都没有**，背后是公寓楼和棕榈树，"
        "碗读不出来，仍然过不了闸门。"
        "摩洛哥媒体 2026-08-03 **试过了**：le360 / lematin / medias24 / h24info / "
        "hespress.fr / 2m / mapexpress 各走自己站内的搜索（WebSearch 是美国口径，"
        "对法语站几乎没覆盖，**零命中先怀疑查询渠道**）——只有 hespress 和 h24info 有稿，"
        "配图全是球员和捧杯特写。最大的一张 3000x1556 是布龙泽蒂跪在红土上捧杯"
        "（h24info，`-scaled` 去掉才是原图），**画面里一格看台都没有**。"
        "**还没试的**：赛事转播方的成片抽帧（和马拉喀什同一条路）。",
    "Grand Prix Hassan II":
        "ATP 主视觉（marrakech_tournimage_2019）是**场地平视**：下半屏全是空红土，"
        "近端没有看台，碗读不出来。官网 grandprixhassan2.com（WordPress+Elementor）"
        "媒体库里 1750x1163 那一批是**赛事简报的版面图**（La Gazette 的 PDF 转图），"
        "不是照片；唯一一张场地照 CHF_2050 是从底线平视，同样只有一侧看台。"
        "摩洛哥媒体**试过了**，法语和阿拉伯语两套检索词各跑一轮"
        "（snrtnews / k24 / hespress / kech24 / marrakech7 / latribunedemarrakech 等）："
        "拿到的三类全不合格——颁奖特写、开幕式、以及场地平视且只有一侧看台的空场。"
        "**还没试的**：皇家网球俱乐部自己的社媒，以及赛事转播方的成片抽帧"
        "（孟菲斯那站就是这么解决的，见 CLAUDE.md「新闻台的成片是个被忽略的源」）。",
    "Almaty Open":
        "⚠️ **这一条我连着写错过两版，两版都是照着报错下的结论。**"
        "第一版写「换个能出网的环境重跑即可」；第二版拿 runner 验完写成"
        "「这个主机从两个完全不同的网络都到不了」——**也是错的**。"
        "2026-08-03 真查了一次证书：ktf.kz 和 almatyopen.kz **是同一个 IP**"
        "（195.210.47.247），后者 200、前者验不过，差别在于 **ktf.kz 只发叶子证书、"
        "不带中间证书**（verify error 21，AIA 指着 Thawte TLS RSA CA G1）。"
        "补上那张中间证书就全部取得到（`tools/probe_blocked_sources.py` 现在自己会补），"
        "**跟出口、跟 IP 一点关系都没有**。"
        "所以现在这条是**看过之后的结论，不是取不到**："
        "按 id 直接探 250–429 拿到 92 本相册（索引页只列 12 本，**别信索引页**），"
        "其中 ATP 250 Almaty Open 只有 366–371 六本、290 张，全部逐张看过——"
        "Media Day 是发布会，另五本是抽签和颁奖，**一张宽景都没有**。"
        "最接近的 368_16 是沿长轴的全场机位，但仪式时全场熄灯："
        "均值 39.4 / 中位 22 / 暗于 50 占 73%，卡片裁完上半屏纯黑、看台不可见，"
        "过不了「看得见看台」。ktf.kz 新闻正文图（1200x675）和 ATP 共享媒体"
        "（almaty_tournimage_* 十年 × 十种后缀全扫过）都是零。"
        "**还没试的**：哈萨克斯坦本地新闻站（tengrinews / vesti.kz / sports.kz）的赛事图集；"
        "场馆运营方 dss-almatyarena.kz 从本环境是 502 CONNECT（ps.kz 那段网络），换出口再试。",
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


def off_ledger(year: int = 2026) -> list[dict]:
    """分母外那几档——**单独报出来，别让「没算」变成「看不见」**。"""
    events = json.loads(CALENDAR.read_text(encoding="utf-8"))["events"]
    shots = {row["slug"]: row.get("shot") for row in
             json.loads(MANIFEST.read_text(encoding="utf-8"))}
    out = []
    for event in events:
        if event.get("tier") not in {"团体", "年终"}:
            continue
        asset = venue_asset_for_match(_match_for(event, year))
        out.append({
            "start": event.get("start", ""), "tier": event.get("tier", ""),
            "zh": event.get("zh", ""), "en": event.get("en", ""),
            "loc": event.get("loc", ""), "slug": asset.slug if asset else None,
            "shot": shots.get(asset.slug) if asset else None,
            "fixed": event.get("en") in FIXED_VENUE_OFF_LEDGER,
        })
    out.sort(key=lambda r: r["start"])
    return out


def _report_off_ledger(year: int) -> None:
    rows = off_ledger(year)
    if not rows:
        return
    print("\n不算进覆盖率的团体赛与年终总决赛（它们照样会出现在日报里）：")
    for r in rows:
        flag = "✅" if r["shot"] == "centre-court" else ("⚠️ 兜底" if r["slug"] else "❌ 缺")
        why = "" if r["fixed"] else "   ← 场馆每年换，本来就没有固定主场"
        print(f"  {r['start']}  {r['tier']:<6} {flag:<8} {r['zh'][:20]:<22}"
              f" {r['loc'][:14]:<16} {r['slug'] or ''}{why}")
    bad = [r for r in rows if r["fixed"] and r["shot"] != "centre-court"]
    if bad:
        print("  ⚠️ 上面这几条场馆是**定死的**，应该有图：" +
              "、".join(r["zh"] for r in bad))


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

    if not args.since:
        _report_off_ledger(args.year)

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
