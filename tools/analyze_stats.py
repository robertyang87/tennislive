#!/usr/bin/env python3
"""把小红书 / 抖音 / 视频号的后台导出读成同一种东西，和成片对起来看。

    python tools/analyze_stats.py 笔记数据.xlsx
    python tools/analyze_stats.py 小红书.xlsx 抖音.xlsx 视频号.csv   # 多给几份就出横比
    python tools/analyze_stats.py 抖音.xlsx --json out.json --fresh-hours 48

平台自动认（按标题列：笔记标题 / 作品名称 / 视频描述），列名映射见
`platform_stats.PLATFORMS`。**每一节都按「这个平台有没有这一列」决定出不出**，
出不来的会明说是平台不给，不是这个号没有数据 —— 空结果先自证是真空。

退出码恒为 0：分析工具，不是闸门。对不上产物的作品列在「未匹配」一节。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_stats import (  # noqa: E402
    FRESH_HOURS,
    INTERACTION,
    REPO,
    Work,
    attach,
    duration_of,
    fmt,
    fresh_cutoff,
    index_output,
    load,
    median,
    pearson,
    table,
)


def _rate(part: float, whole: float, spec="{:.2%}") -> str:
    return spec.format(part / whole) if whole else "—"


def overview(works: list[Work]) -> None:
    plat = works[0].platform
    span = [w.published for w in works if w.published]
    head = f"\n## {plat.name}　{len(works)} 条"
    if span:
        head += f"　{min(span):%Y-%m-%d} ~ {max(span):%Y-%m-%d}"
    print(head)
    plays = sum(w.get("plays") or 0 for w in works)
    if not plays:
        print("播放为 0")
        return
    # 只印这个平台真给的指标。踩过：抖音的「视频数据」视图不导点赞和涨粉，
    # 无条件打印会印成「互动 0　涨粉 0」——和「真的没人互动」长得一模一样，
    # 正是这个工具处处在防的那种假空值。
    bits = [f"播放 {plays:.0f}"]
    if any(plat.has(k) for k in INTERACTION):
        inter = sum(w.interaction for w in works)
        bits.append(f"互动 {inter:.0f}（{_rate(inter, plays)}）")
    if plat.has("follows"):
        fans = sum(w.get("follows") or 0 for w in works)
        bits.append(f"涨粉 {fans:.0f}（每千播放 {fans / plays * 1000:.2f}）")
    if plat.has("home_visits"):
        home = sum(w.get("home_visits") or 0 for w in works)
        bits.append(f"主页访问 {home:.0f}（{_rate(home, plays)}）")
    print("　".join(bits))
    absent = [n for k, n in (("follows", "涨粉"), ("likes", "点赞"),
                             ("true_completion", "真完播率"),
                             ("cover_ctr", "封面点击率"))
              if not plat.has(k)]
    if absent:
        print(f"　（{plat.name}这个视图不给：{'、'.join(absent)}——空着，不是 0）")


def by_kind(works: list[Work]) -> None:
    """图文和视频分开。

    它们的「完播率」根本不是一回事：图文的完播是翻完几张图，抖音那份数据里
    图文 13.6%～24.2%、视频只有 0%～9.9%。混在一起算中位会得出「完播率还
    不错」的假象。
    """
    plat = works[0].platform
    if not plat.kind_col:
        return
    groups: dict[str, list[Work]] = {}
    for w in works:
        groups.setdefault("图文" if w.is_photo else "视频", []).append(w)
    if len(groups) < 2:
        return
    print("\n### 按体裁（图文的完播是「翻完图」，和视频不可比）")
    rows = []
    for name, g in sorted(groups.items()):
        plays = sum(w.get("plays") or 0 for w in g)
        row = [name, str(len(g)), f"{plays:.0f}", f"{plays / len(g):.0f}",
               _rate(sum(w.interaction for w in g), plays),
               f"{sum(w.get('follows') or 0 for w in g):.0f}",
               f"{sum(w.get('follows') or 0 for w in g) / plays * 1000:.2f}"
               if plays else "—"]
        if plat.has("true_completion"):
            row.append(fmt(median([w.get("true_completion") for w in g]), "{:.1%}"))
        if plat.has("home_visits"):
            row.append(f"{sum(w.get('home_visits') or 0 for w in g):.0f}")
        rows.append(row)
    heads = ["体裁", "条数", "总播放", "均播放", "互动率", "涨粉", "千播涨粉"]
    if plat.has("true_completion"):
        heads.append("真完播中位")
    if plat.has("home_visits"):
        heads.append("主页访问")
    print(table(rows, heads))


def exposure_check(works: list[Work]) -> dict:
    """曝光那一列对不对得上封面点击率 —— 按体裁分开看。

    第一次看小红书那张表时差点得出「图文分发更好」：图文曝光 24512 比视频的
    18184 高。其实图文 12 条的 `观看/曝光` 和封面点击率分毫不差，视频 11 条
    全部对不上（2.2～4.6 倍）—— 视频有一路沉浸式自动播放的观看不计入曝光。
    按 `观看÷CTR` 还原，视频真实曝光约 55000，是图文的 2.2 倍，方向正好反过来。
    """
    plat = works[0].platform
    if not (plat.has("exposure") and plat.has("cover_ctr")):
        return {}
    usable = [w for w in works
              if (w.get("exposure") or 0) > 0 and w.get("cover_ctr")]
    if not usable:
        print(f"\n### 曝光一致性自检　—— {plat.name} 这份里没有曝光>0 且有 CTR 的作品")
        return {}
    print("\n### 曝光一致性自检（CTR 是否等于 播放/曝光）")
    groups: dict[str, list[Work]] = {}
    for w in usable:
        groups.setdefault("图文" if w.is_photo else "视频", []).append(w)
    rows, verdicts = [], {}
    for kind, g in sorted(groups.items()):
        worst = max(w.get("plays") / w.get("exposure") - w.get("cover_ctr") for w in g)
        implied = sum(w.get("plays") / w.get("cover_ctr") for w in g)
        recorded = sum(w.get("exposure") for w in g)
        ok = worst < 0.02
        verdicts[kind] = {"一致": ok, "条数": len(g), "记录曝光": round(recorded),
                          "还原曝光": round(implied), "最大偏差": round(worst, 4)}
        rows.append([kind, str(len(g)), f"{worst:+.1%}", f"{recorded:.0f}",
                     f"{implied:.0f}", f"{implied / recorded:.2f}x" if recorded else "—",
                     "一致" if ok else "对不上"])
    print(table(rows, ["体裁", "条数", "最大偏差", "记录曝光", "还原曝光", "倍数", "判定"]))
    bad = [k for k, v in verdicts.items() if not v["一致"]]
    if bad:
        print(f"\n  ⚠ {'、'.join(bad)} 的曝光列是残缺的：还有不计入曝光的播放来源。")
        print("    跨体裁比曝光时用「还原曝光」，别用表里那一列。")
    return verdicts


def funnel(works: list[Work]) -> list[dict]:
    """留存漏斗 —— 只有抖音给得出，因为只有它有 2s跳出率和 5s完播率。

    有了这两列，「前几秒决定一切」不再是口号：抖音这批 11 条视频的中位漏斗是
    100 → 63（2s）→ 38（5s）→ 2（结尾），五秒内走掉 62%。
    """
    plat = works[0].platform
    if not (plat.has("bounce_2s") and plat.has("retain_5s")):
        print(f"\n### 留存漏斗　—— {plat.name} 不给 2s跳出率 / 5s完播率，这一节出不来")
        print("　（不是这个号没有数据，是平台后台没有这两列）")
        return []
    vids = [w for w in works if not w.is_photo
            and w.get("bounce_2s") is not None and w.get("retain_5s") is not None]
    if not vids:
        print("\n### 留存漏斗　—— 没有带留存列的视频")
        print("　先确认导出时勾了「2s跳出率」「5s完播率」，别当成没有数据。")
        return []
    print("\n### 留存漏斗（只算视频）")
    rows, recs = [], []
    for w in vids:
        alive2, s5 = 1 - w.get("bounce_2s"), w.get("retain_5s")
        recs.append({"标题": w.label, "2s存活": alive2, "5s存活": s5,
                     "真完播": w.get("true_completion"), "播放量": w.get("plays")})
        rows.append([w.label, fmt(w.get("plays")), f"{alive2:.0%}", f"{s5:.0%}",
                     fmt(w.get("true_completion"), "{:.1%}"),
                     f"{(alive2 - s5) / alive2:.0%}" if alive2 else "—"])
    rows.sort(key=lambda r: float(r[3].rstrip("%")), reverse=True)
    print(table(rows, ["作品", "播放", "2s还在", "5s还在", "看到底", "2s→5s流失"]))

    # 三段一律从「2 秒后还活着」这一个中位数往下推。踩过：一边用跳出率的中位、
    # 一边用存活率的中位，两个中位数不互补，三段加起来对不上一百。
    alive2 = median([1 - w.get("bounce_2s") for w in vids])
    s5 = median([w.get("retain_5s") for w in vids])
    # 没有真完播率就别印「看到结尾 0 人」——那是这个视图不给，不是真的没人看完。
    fin_med = median([w.get("true_completion") for w in vids])
    fin = fin_med or 0.0
    print(f"\n  中位漏斗（{len(vids)} 条）：开播 100 人")
    print(f"    2 秒后还剩 {alive2 * 100:>3.0f} 人　← 这 2 秒走掉 {(1 - alive2) * 100:.0f} 人")
    print(f"    5 秒后还剩 {s5 * 100:>3.0f} 人　← 这 3 秒又走掉 {(alive2 - s5) * 100:.0f} 人")
    if fin_med is None:
        print(f"    看到结尾   —— {plat.name}不给真完播率，这一格空着")
    else:
        print(f"    看到结尾   {fin * 100:>3.0f} 人")
    print(f"  5 秒内累计走掉 {(1 - s5) * 100:.0f}%")

    lens = [d for d in (duration_of(w) for w in vids) if d]
    if lens:
        body = median(lens) - 5
        head_rate = (1 - alive2) * 100 / 2
        tail_rate = (s5 - fin) * 100 / body if body > 0 else 0
        print(f"\n  流失速度：前 2 秒 {head_rate:.1f} 人/秒，"
              f"5 秒到片尾 {tail_rate:.2f} 人/秒"
              + (f"　—— 差 {head_rate / tail_rate:.0f} 倍" if tail_rate else ""))
        if len(lens) < len(vids):
            print(f"  （{len(vids) - len(lens)} 条没对上成片，正片段按其余 {len(lens)} 条算）")
    return recs


def watch_ratio(works: list[Work]) -> list[dict]:
    """均观看比例 = 平均播放时长 ÷ 成片时长。**它不是完播率。**

    错在定义上，不需要数据来推翻：它是个均值，答不了「几个人看到了结尾」——
    一半人两秒划走、一半人看完，和所有人都看一半，算出来一模一样。而「末屏
    那一问有多少人听见」问的正是后者。

    平台给了真完播率的，这里顺手把两个数并排放出来校准。视频号上两者相关性
    +0.96（够用来排序），但系统性虚高 2.2～6.4 倍（不能用来读水平）。
    """
    plat = works[0].platform
    if not plat.has("avg_watch"):
        return []
    print("\n### 均观看比例（平均播放时长 ÷ 成片时长，不是完播率）")
    rows, recs, pairs, pending = [], [], [], []
    for w in works:
        if w.is_photo:
            continue
        # 平均播放时长为 0 = 后台还没统计出来（当天刚发的常常是这样），不是
        # 「没人看」。算成 0% 会把中位数拖垮：小红书这批里两条今天发的会把
        # 中位从 19.5% 压到 15.5%，而且看不出是数据没到还是片子太差。
        if not w.get("avg_watch"):
            if w.get("avg_watch") == 0:
                pending.append(w)
            continue
        length = duration_of(w)
        if not length:
            continue
        ratio = w.get("avg_watch") / length
        true = w.get("true_completion")
        recs.append({"标题": w.label, "片长": round(length, 1),
                     "均时长": w.get("avg_watch"), "均观看比例": ratio,
                     "真完播": true, "播放量": w.get("plays"), "匹配": w.match_note})
        row = [w.label, f"{length:.0f}s", f"{w.get('avg_watch'):.1f}s", f"{ratio:.1%}"]
        if plat.has("true_completion"):
            pairs.append((ratio, true))
            row += [fmt(true, "{:.1%}"), f"{ratio / true:.1f}x" if true else "—"]
        row.append(fmt(w.get("plays")))
        rows.append(row)
    if not rows:
        print("  没有能同时拿到片长和播放时长的作品 —— 先看「未匹配」一节，"
              "别当成没有视频。")
        return []
    rows.sort(key=lambda r: float(r[3].rstrip("%")), reverse=True)
    heads = ["作品", "片长", "均时长", "均观看比例"]
    if plat.has("true_completion"):
        heads += ["真完播", "虚高"]
    heads.append("播放")
    print(table(rows, heads))
    print(f"\n  {len(recs)} 条：片长中位 {median([r['片长'] for r in recs]):.0f}s，"
          f"均观看比例中位 {median([r['均观看比例'] for r in recs]):.1%}")
    if pending:
        print(f"  另有 {len(pending)} 条平均播放时长还是 0，后台没统计出来，未计入："
              + "、".join(w.label[:18] for w in pending))
    if pairs and len(pairs) > 2:
        good = [(a, b) for a, b in pairs if b is not None]
        if len(good) > 2:
            print(f"  真完播中位 {median([b for _, b in good]):.1%}"
                  f"　均观看比例 vs 真完播 相关性 "
                  f"{pearson([a for a, _ in good], [b for _, b in good]):+.2f}")
            print("  —— 相关性高说明它够用来排序；倍数说明它不能用来读水平。")
    elif not plat.has("true_completion"):
        print(f"  {plat.name} 不给真完播率，所以这个号在{plat.name}上的真完播率"
              "无从得知 —— 空着，别拿别家的倍数去填。")
    return recs


def correlations(works: list[Work], fresh_hours: int) -> None:
    """相关性 —— 全部打上「线索不是结论」的标签，因为 n 就这么大。"""
    plat = works[0].platform
    vids = [w for w in works if not w.is_photo and w.get("plays") is not None]
    cut = fresh_cutoff(vids, fresh_hours)
    keep = [w for w in vids if w.published and w.published <= cut] if cut else vids
    dropped = len(vids) - len(keep)
    print(f"\n### 相关性（剔除最近 {fresh_hours} 小时发布的 {dropped} 条，"
          f"剩 {len(keep)} 条）")
    if len(keep) < 4:
        print("  样本不够算 —— 不出数好过出个假的。")
        return
    # 平台不给的因变量不出这一栏。踩过：抖音的「视频数据」视图没有点赞和涨粉，
    # 照样算出来全是 +0.00，看着像「留存和涨粉毫无关系」这个实打实的结论。
    outs = [("plays", "vs 播放", lambda w: w.get("plays"))]
    if any(plat.has(k) for k in INTERACTION):
        outs.append(("interaction", "vs 互动", lambda w: w.interaction))
    if plat.has("follows"):
        outs.append(("follows", "vs 涨粉", lambda w: w.get("follows") or 0))
    rows = []
    for key, name in (("bounce_2s", "2s跳出率"), ("retain_5s", "5s完播率"),
                      ("true_completion", "真完播率"), ("avg_watch", "平均播放时长"),
                      ("cover_ctr", "封面点击率")):
        xs = [w.get(key) for w in keep]
        if any(x is None for x in xs):
            continue
        rows.append([name] + [f"{pearson(xs, [f(w) for w in keep]):+.2f}"
                              for _, _, f in outs])
    if not rows:
        print("  这个平台给的列不足以算相关性。")
        return
    print(table(rows, [""] + [n for _, n, _ in outs]))
    print(f"\n  n={len(keep)}，全部当线索看。播放量本身由算法决定、算法又用留存，")
    print("  这里有循环成分，别读成「提高留存就能换来播放」。实测过：剔除窗口")
    print("  从 24 小时改成「只剔当天」，抖音的 5s完播率 vs 真完播率就从 +0.38")
    print("  翻到 -0.07 —— 单个系数撑不住结论。")


def unmatched(works: list[Work]) -> None:
    """对不上的一律列出来，连原因一起。

    只在成功时出声的检查，没法证明它真的看过 —— 这一节就是它的证明。
    """
    miss = [w for w in works if not w.item]
    print(f"\n### 未匹配到产物（{len(miss)}/{len(works)} 条）")
    if not miss:
        print("  全部对上了。")
        return
    print(table([[w.label, "图文" if w.is_photo else "视频", w.match_note]
                 for w in miss], ["作品", "体裁", "为什么没对上"]))
    print("\n  发文时改过标题、或那条内容不是这个仓库生成的，都会落在这里。")


def cross_platform(loaded: list[tuple[str, list[Work]]]) -> None:
    """同一条内容在几家的表现。只报事实，不给「某平台更好」的结论。

    8 条三边都发过的内容里，抖音赢 4、视频号赢 2、小红书赢 2，而且**排序都
    不一样**：「大师赛为什么变两周」在抖音是冠军（3066）、在视频号垫底（216）。
    人群、推荐机制、自动播放行为都不同，不能互相代入。
    """
    if len(loaded) < 2:
        return
    print("\n## 跨平台横比")
    names = [n for n, _ in loaded]
    by_title: dict[str, dict[str, Work]] = {}
    for name, works in loaded:
        for w in works:
            if w.item:
                by_title.setdefault(w.item["title"], {})[name] = w
    shared = {t: d for t, d in by_title.items() if len(d) == len(loaded)}
    if not shared:
        print("  没有一条内容在所有平台都对上了产物，横比不了。")
        print("  （先看各平台的「未匹配」一节 —— 多半是发文时改过标题）")
        return
    rows = []
    for title, d in sorted(shared.items(),
                           key=lambda kv: -max(w.get("plays") or 0
                                               for w in kv[1].values())):
        plays = {n: d[n].get("plays") or 0 for n in names}
        best = max(plays, key=plays.get)
        low = min(plays.values()) or 1
        rows.append([title[:30]] + [f"{plays[n]:.0f}" for n in names]
                    + [f"{best}（{plays[best] / low:.0f}倍）"])
    print(table(rows, ["内容"] + names + ["最强"]))
    print(f"\n  {len(shared)} 条内容在 {len(names)} 家都对上了产物。")

    print()
    tally = {n: 0 for n in names}
    for _, d in shared.items():
        tally[max(names, key=lambda n: d[n].get("plays") or 0)] += 1
    print("  各家拿第一的条数：" + "　".join(f"{n} {c}" for n, c in tally.items()))
    if max(tally.values()) < len(shared):
        print("  没有一家是稳定更好的 —— 连排序都不一样，所以不能一次调优管三家。")

    rows = []
    for name, works in loaded:
        vids = [w for w in works if not w.is_photo]
        plays = sum(w.get("plays") or 0 for w in vids)
        fans = sum(w.get("follows") or 0 for w in vids)
        true = median([w.get("true_completion") for w in vids])
        rows.append([name, str(len(vids)), f"{plays:.0f}", f"{fans:.0f}",
                     f"{fans / plays * 1000:.2f}" if plays else "—",
                     fmt(true, "{:.1%}", dash="平台不给")])
    print()
    print(table(rows, ["平台", "视频数", "视频播放", "涨粉", "千播涨粉", "真完播中位"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tables", type=Path, nargs="+",
                    help="后台导出的表，xlsx 或 csv；给多份就出跨平台横比")
    ap.add_argument("--output-root", type=Path, default=REPO / "output")
    ap.add_argument("--fresh-hours", type=int, default=FRESH_HOURS)
    ap.add_argument("--json", type=Path, help="把明细另存一份 JSON")
    args = ap.parse_args()

    items = index_output(args.output_root)
    print(f"output/ 下 {len(items)} 份已生成的内容"
          f"（{sum(1 for i in items if i['mp4'])} 份带成片）")

    loaded, dump = [], {}
    for path in args.tables:
        plat, works = load(path)
        attach(works, items)
        loaded.append((plat.name, works))
        overview(works)
        by_kind(works)
        exposure_check(works)
        dump[plat.name] = {"漏斗": funnel(works), "均观看比例": watch_ratio(works)}
        correlations(works, args.fresh_hours)
        unmatched(works)

    cross_platform(loaded)

    if args.json:
        args.json.write_text(json.dumps(dump, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\n明细已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
