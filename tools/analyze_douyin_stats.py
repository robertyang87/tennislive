#!/usr/bin/env python3
"""抖音后台导出的作品数据 —— 重点是那三列小红书给不出的留存。

抖音比小红书多给三样东西，而且都是小红书**完全没有**的：

    2s跳出率     开播两秒内划走的比例
    5s完播率     看到第 5 秒还在的比例
    完播率       看到结尾的比例（真完播，不是估的）

有了这三列，「前几秒决定一切」就不再是行业口号，是能算的。当前这份数据里
11 条视频的中位漏斗是 100 → 63（2s）→ 38（5s）→ 2（结尾）：**五秒内走掉
62%**，而前 2 秒的流失速度是正片的六十多倍。

顺带它还能校准小红书那个自制指标：`analyze_xhs_stats.py` 里的「均观看比例」
（人均观看时长÷片长）在这批片子上中位 10.4%，抖音的真完播中位只有 2.0%。
所以那个数**不是完播率**，改名的依据就在这儿。但注意——

## 两个平台的人群不一样，别把倍数搬来搬去

同一条内容在两边差得离谱：三巨头图文在小红书 152 播放、抖音 10567（69 倍）；
挑球视频在小红书 1581、抖音 69（1/23）。所以：

- **抖音的留存漏斗只描述抖音的观众**，不能当小红书的估计值。
- 小红书那份导出压根没有这三列，所以那边的真完播率**目前无从得知** ——
  空着就空着，别拿抖音的数去填。

## 还有两个坑，都在报告里挡掉了

- **图文的「完播率」和视频的不是一回事。** 图文的完播是「翻完几张图」，
  门槛低得多（这份数据里 13.6%～24.2%，视频只有 0%～9.9%）。混在一起算
  中位数会得出「完播率还不错」的假象，所以分开统计。
- **刚发的作品播放量天然低**，把它算进相关性会把系数压平：5s完播率 vs 播放量
  全量算是 +0.46，剔掉当天发的两条变成 +0.77。相关性一节默认剔除最近
  `FRESH_HOURS` 小时内发布的，并把剔了几条打印出来。

用法：
    python tools/analyze_douyin_stats.py 作品数据.xlsx
    python tools/analyze_douyin_stats.py 作品数据.xlsx --fresh-hours 48
    python tools/analyze_douyin_stats.py 作品数据.xlsx --json out.json

退出码恒为 0：分析工具，不是闸门。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_xhs_stats import (  # noqa: E402  （同目录，共用 xlsx 解析和标题匹配）
    _fmt,
    _median,
    _pearson,
    _table,
    index_output,
    mvhd_seconds,
    normalize,
    read_xlsx,
)

REPO = Path(__file__).resolve().parents[1]

# 剔除「刚发出去还没跑完分发」的作品，只影响相关性一节。24 小时是量出来的：
# 7-27 那两条发出不到一天，播放 42 和 617，而同格式的老作品在 1300～3000。
FRESH_HOURS = 24

# 模糊回退的三个数，都是从这批数据量出来的，别拍脑袋改：
#   0.706  网球为什么是黄色的（发文时砍掉了「网球有故事」）—— 要收
#   0.611  11 小时 5 分钟的图文，两个日期的版本只差 0.011 —— 分不清，要挡
#   0.500  三巨头，三个候选并列 —— 要挡
MIN_RATIO = 0.70          # 相似度下限
TIE_WINDOW = 0.08         # 分数差在这以内算「并列」，改按日期分
MIN_MARGIN = 0.10         # 和并列组之外的次优至少要拉开这么多
DATE_WINDOW = 2           # 发布日期和产物目录日期最多差几天
NUMERIC = ("播放量", "完播率", "5s完播率", "封面点击率", "2s跳出率", "平均播放时长",
           "点赞量", "分享量", "评论量", "收藏量", "主页访问量", "粉丝增量")
INTERACTION = ("点赞量", "分享量", "评论量", "收藏量")


def _to_num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None      # 导出里拿不到的格子写的是 "-"


def load_works(path: Path) -> list[dict]:
    """表格 → 作品列表。

    抖音的「作品名称」一列装的是**标题加上整段正文**（换行都在里面），不像
    小红书那样只有标题。所以这里留着原文，标题交给 `match_work` 去认 ——
    它有比切字符串更硬的办法。
    """
    rows = read_xlsx(path)
    header_at = next((i for i, r in enumerate(rows) if "作品名称" in r), None)
    if header_at is None:
        raise SystemExit(f"{path} 里找不到「作品名称」表头")
    header = rows[header_at]
    works = []
    for row in rows[header_at + 1:]:
        rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header) if h}
        if not rec.get("作品名称"):
            continue
        for key in NUMERIC:
            rec[key] = _to_num(rec.get(key, ""))
        rec["_time"] = _parse_time(rec.get("发布时间", ""))
        rec["_norm"] = normalize(rec["作品名称"])
        rec["_首行"] = rec["作品名称"].split("\n")[0]
        # 显示名先占位，对上产物之后由 `label` 换成干净的标题
        rec["_标题"] = rec["_首行"][:28]
        rec["_互动"] = sum(rec.get(k) or 0 for k in INTERACTION)
        rec["_图文"] = rec.get("体裁") == "图文"
        works.append(rec)
    return works


def _parse_time(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def match_work(work: dict, items: list[dict]) -> tuple[dict | None, str]:
    """把一条作品指到一个产物目录上。

    **主判据是前缀自证**：抖音的「作品名称」是标题接正文拼出来的，所以
    去掉装饰之后，它必然**以**那条内容的标题开头。这比切字符串硬得多 ——
    不用猜标题在第几个空格处结束，让数据自己对上。命中多个时取最长的那个
    前缀（`网球有故事｜11 小时 5 分钟` 比 `网球有故事｜11` 更具体）。

    前缀对不上的（发文时改过标题）再走模糊：拿首行去比，过阈值才算。
    """
    pre = [it for it in items if work["_norm"].startswith(it["norm"]) and it["norm"]]
    if pre:
        best = max(pre, key=lambda it: len(it["norm"]))
        return best, f"前缀自证 {len(best['norm'])} 字"

    # 回退也按前缀比：拿作品名称开头**同样长度**的一段去比，而不是整条首行 ——
    # 首行里带着正文，长度差出十几倍，相似度必然被拉到 0.5 上下，好的候选和
    # 坏的候选一起沉底。yellow-ball 就是这么漏掉的（0.52，看着像「真的不像」）。
    full = work["_norm"]
    scored = sorted(
        ((SequenceMatcher(None, full[:len(it["norm"])], it["norm"]).ratio(), it)
         for it in items if it["norm"]), key=lambda x: x[0], reverse=True)
    if not scored:
        return None, "output/ 下没有任何 xiaohongshu.txt"
    top, item = scored[0]
    if top < MIN_RATIO:
        return None, f"前缀对不上；最像的「{item['title']}」也只有 {top:.2f}"

    # 同一个选题重跑过几版时，几个候选的分数会挤在一起（金满贯：0.812 / 0.750，
    # 只差 0.06）。这种「谁都像」不能靠分数排先后，要按日期分 —— 发布那天的
    # 那一版才是它。而分数真的平手又分不出日期的（三巨头：三个 0.500），
    # 就该老实认输，不是随手挑第一个。
    tied = [(s, it) for s, it in scored if top - s <= TIE_WINDOW]
    if len(tied) > 1:
        picked = _nearest_by_date(work, [it for _, it in tied])
        if picked is None:
            names = " / ".join(it["title"] for _, it in tied[:3])
            return None, f"{top:.2f} 有 {len(tied)} 个候选分不出：{names}"
        item = picked
    rest = [s for s, _ in scored if top - s > TIE_WINDOW]
    if rest and top - rest[0] < MIN_MARGIN:
        return None, (f"{top:.2f} 和次优 {rest[0]:.2f} 拉不开"
                      f"（要求差 {MIN_MARGIN}），分不清是哪一条")
    if work["_time"] and item["date"]:
        gap = abs((work["_time"].date() - item["date"]).days)
        if gap > DATE_WINDOW:
            return None, f"最像的是「{item['title']}」({top:.2f}) 但日期差 {gap} 天"
    return item, f"模糊 {top:.2f}"


def _nearest_by_date(work: dict, cands: list[dict]) -> dict | None:
    """同分候选里按「发布日期离产物目录日期最近」挑一个，挑不出就返回 None。"""
    if not work["_time"]:
        return None
    dated = [c for c in cands if c["date"]]
    if not dated:
        return None
    gaps = sorted((abs((work["_time"].date() - c["date"]).days), i, c)
                  for i, c in enumerate(dated))
    if len(gaps) > 1 and gaps[0][0] == gaps[1][0]:
        return None      # 两版离得一样近，日期也分不出
    return gaps[0][2]


# ---------------------------------------------------------------- 报告


def label(works: list[dict], items: list[dict]) -> None:
    """给每条作品定一个能看的显示名。

    抖音的「作品名称」是标题接整段正文，直接截断会把正文的头几个字带进表里
    （`…十届温网十个女冠军 同样十届温网，女`）。对上产物的就用产物自己的标题，
    对不上的才退回截断，并留个省略号说明这是截出来的。
    """
    for w in works:
        hit, _ = match_work(w, items)
        w["_标题"] = hit["title"] if hit else (w["_首行"][:26] + "…")


def report_overview(works: list[dict]) -> None:
    span = [w["_time"] for w in works if w["_time"]]
    print(f"\n共 {len(works)} 条作品", end="")
    if span:
        print(f"，{min(span):%Y-%m-%d} ~ {max(span):%Y-%m-%d}", end="")
    print()
    plays = sum(w.get("播放量") or 0 for w in works)
    inter = sum(w["_互动"] for w in works)
    home = sum(w.get("主页访问量") or 0 for w in works)
    fans = sum(w.get("粉丝增量") or 0 for w in works)
    print(f"播放 {plays:.0f}   互动 {inter:.0f}（{inter / plays:.2%}）"
          f"   主页访问 {home:.0f}（{home / plays:.2%}）   涨粉 {fans:.0f}"
          f"（每千播放 {fans / plays * 1000:.2f}）" if plays else "播放为 0")


def report_by_kind(works: list[dict]) -> None:
    """图文和视频分开 —— 它们的「完播率」不是同一件事。"""
    print("\n### 按体裁（图文的完播率是「翻完图」，和视频不可比）")
    groups: dict[str, list[dict]] = {}
    for w in works:
        groups.setdefault("图文" if w["_图文"] else "视频", []).append(w)
    rows = []
    for name, g in sorted(groups.items()):
        plays = sum(w.get("播放量") or 0 for w in g)
        rows.append([
            name, str(len(g)), f"{plays:.0f}",
            f"{plays / len(g):.0f}",
            _fmt(_median([w.get("完播率") for w in g]), "{:.1%}"),
            f"{sum(w['_互动'] for w in g) / plays:.2%}" if plays else "—",
            f"{sum(w.get('主页访问量') or 0 for w in g):.0f}",
            f"{sum(w.get('粉丝增量') or 0 for w in g):.0f}",
        ])
    print(_table(rows, ["体裁", "条数", "总播放", "均播放", "完播率中位",
                        "互动率", "主页访问", "涨粉"]))


def report_funnel(works: list[dict]) -> list[dict]:
    """留存漏斗 —— 这份数据独有的一节，也是最有信息量的一节。

    只算视频：图文没有「第 2 秒」这回事。
    """
    print("\n### 留存漏斗（只算视频）")
    vids = [w for w in works if not w["_图文"]
            and w.get("2s跳出率") is not None and w.get("5s完播率") is not None]
    if not vids:
        print("  没有带留存列的视频 —— 先确认导出时勾了「2s跳出率」「5s完播率」，"
              "别当成没有数据。")
        return []
    rows, recs = [], []
    for w in vids:
        alive2 = 1 - w["2s跳出率"]
        s5, fin = w["5s完播率"], w.get("完播率")
        recs.append({"标题": w["_标题"], "2s存活": alive2, "5s存活": s5,
                     "真完播": fin, "播放量": w.get("播放量")})
        rows.append([w["_标题"], _fmt(w.get("播放量")), f"{alive2:.0%}",
                     f"{s5:.0%}", _fmt(fin, "{:.1%}"),
                     f"{(alive2 - s5) / alive2:.0%}" if alive2 else "—"])
    rows.sort(key=lambda r: float(r[3].rstrip("%")), reverse=True)
    print(_table(rows, ["作品", "播放", "2s还在", "5s还在", "看到底", "2s→5s流失"]))

    b2 = _median([1 - w["2s跳出率"] for w in vids])
    s5 = _median([w["5s完播率"] for w in vids])
    fin = _median([w["完播率"] for w in vids if w.get("完播率") is not None]) or 0
    print(f"\n  中位漏斗（{len(vids)} 条）：开播 100 人")
    print(f"    2 秒后还剩 {b2 * 100:>3.0f} 人   ← 这 2 秒走掉 {(1 - b2) * 100:.0f} 人")
    print(f"    5 秒后还剩 {s5 * 100:>3.0f} 人   ← 这 3 秒又走掉 {(b2 - s5) * 100:.0f} 人")
    print(f"    看到结尾   {fin * 100:>3.0f} 人")
    print(f"  5 秒内累计走掉 {(1 - s5) * 100:.0f}%")
    return recs


def report_rates(works: list[dict], funnel: list[dict], root: Path) -> None:
    """流失速度 —— 同样是「走掉一个人」，前两秒和正片里差着两个数量级。

    需要片长才能算正片那一段，所以这里要和成片对上。对不上的照实说。
    """
    print("\n### 流失速度（人/秒）")
    vids = [w for w in works if not w["_图文"] and w.get("2s跳出率") is not None]
    items = index_output(root)
    lens, unmatched = [], []
    for w in vids:
        hit, why = match_work(w, items)
        if hit and hit["mp4"]:
            try:
                lens.append((w, mvhd_seconds(hit["mp4"].read_bytes())))
                continue
            except (OSError, ValueError):
                why = "成片量不出时长"
        unmatched.append((w, why))
    if not lens:
        print("  没有能对上成片的视频，算不出正片段的速度。")
    else:
        # 一律从「2 秒后还活着」这一个中位数往下推，别一边用跳出率的中位、
        # 一边用存活率的中位 —— 两个中位数不互补，表格会自己和自己对不上。
        b2 = _median([1 - w["2s跳出率"] for w, _ in lens])
        a2 = 1 - b2
        s5 = _median([w["5s完播率"] for w, _ in lens])
        fin = _median([w["完播率"] for w, _ in lens if w.get("完播率") is not None]) or 0
        body = _median([L for _, L in lens]) - 5
        print(_table([
            ["0–2 秒", f"{a2 * 100:.0f}", "2", f"{a2 * 100 / 2:.1f}"],
            ["2–5 秒", f"{(b2 - s5) * 100:.0f}", "3", f"{(b2 - s5) * 100 / 3:.1f}"],
            ["5 秒–片尾", f"{(s5 - fin) * 100:.0f}", f"{body:.0f}",
             f"{(s5 - fin) * 100 / body:.2f}" if body > 0 else "—"],
        ], ["阶段", "走掉(每百人)", "秒数", "人/秒"]))
        head = a2 * 100 / 2
        tail = (s5 - fin) * 100 / body if body > 0 else 0
        if tail:
            print(f"\n  前 2 秒的流失速度是正片的 {head / tail:.0f} 倍。")
    if unmatched:
        print(f"\n  {len(unmatched)} 条没对上成片，未计入正片段：")
        for w, why in unmatched:
            print(f"    {w['_标题']} —— {why}")


def report_correlations(works: list[dict], fresh_hours: int) -> None:
    """相关性 —— 全部打上「线索不是结论」的标签，因为 n 就这么大。"""
    print(f"\n### 相关性（剔除最近 {fresh_hours} 小时发布的）")
    vids = [w for w in works if not w["_图文"] and w.get("5s完播率") is not None]
    latest = max((w["_time"] for w in vids if w["_time"]), default=None)
    if latest:
        cut = latest - timedelta(hours=fresh_hours)
        keep = [w for w in vids if w["_time"] and w["_time"] <= cut]
        dropped = len(vids) - len(keep)
    else:
        keep, dropped = vids, 0
    if len(keep) < 4:
        print(f"  样本只剩 {len(keep)} 条，不够算 —— 不出数好过出个假的。")
        return
    print(f"  剔除 {dropped} 条刚发的，剩 {len(keep)} 条")
    rows = []
    for key in ("2s跳出率", "5s完播率", "完播率"):
        xs = [w[key] for w in keep if w.get(key) is not None]
        if len(xs) != len(keep):
            continue
        rows.append([key,
                     f"{_pearson(xs, [w['播放量'] for w in keep]):+.2f}",
                     f"{_pearson(xs, [w['_互动'] for w in keep]):+.2f}"])
    print(_table(rows, ["", "vs 播放量", "vs 互动"]))
    s5 = [w["5s完播率"] for w in keep]
    fin = [w["完播率"] for w in keep if w.get("完播率") is not None]
    if len(fin) == len(keep):
        r = _pearson(s5, fin)
        verdict = ("两者基本无关：开头抓住和留到最后是两件事" if abs(r) < 0.3
                   else "两者同向，但样本太小，换个剔除窗口就可能翻号")
        print(f"\n  5s完播率 vs 真完播率 {r:+.2f}  ← {verdict}")
        print("  实测过：剔除窗口从 24 小时改成「只剔当天」，n 从 7 变 9，"
              "这个系数就从 +0.38 变 -0.07。")
    print(f"\n  n={len(keep)}，全部当线索看。而且播放量本身由算法决定、算法又用留存，")
    print("  这里有循环成分，别读成「提高留存就能换来播放」。")


def report_vs_ratio(works: list[dict], root: Path) -> None:
    """真完播率 vs 均观看比例 —— 校准小红书那个自制指标到底虚了多少。"""
    print("\n### 真完播率 vs 均观看比例（校准 analyze_xhs_stats 的自制指标）")
    items = index_output(root)
    rows, pairs = [], []
    for w in works:
        if w["_图文"] or w.get("平均播放时长") is None or w.get("完播率") is None:
            continue
        hit, _ = match_work(w, items)
        if not (hit and hit["mp4"]):
            continue
        try:
            length = mvhd_seconds(hit["mp4"].read_bytes())
        except (OSError, ValueError):
            continue
        ratio = w["平均播放时长"] / length
        pairs.append((ratio, w["完播率"]))
        rows.append([w["_标题"], f"{length:.0f}s",
                     f"{w['平均播放时长']:.1f}s", f"{ratio:.1%}",
                     f"{w['完播率']:.1%}",
                     f"{ratio / w['完播率']:.1f}x" if w["完播率"] else "—"])
    if not rows:
        print("  没有能同时拿到片长和真完播率的作品。")
        return
    rows.sort(key=lambda r: float(r[3].rstrip("%")), reverse=True)
    print(_table(rows, ["作品", "片长", "均时长", "均观看比例", "真完播", "虚高"]))
    print(f"\n  中位：均观看比例 {_median([p[0] for p in pairs]):.1%}，"
          f"真完播 {_median([p[1] for p in pairs]):.1%}")
    print("  均观看比例是个均值，回答不了「几个人看到了结尾」——这就是它不叫完播率的原因。")
    print("  但这组倍数只属于抖音这批观众，别搬去估小红书。")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", type=Path, help="抖音后台导出的作品数据表")
    ap.add_argument("--output-root", type=Path, default=REPO / "output")
    ap.add_argument("--fresh-hours", type=int, default=FRESH_HOURS,
                    help=f"相关性一节剔除最近多少小时发的，默认 {FRESH_HOURS}")
    ap.add_argument("--json", type=Path, help="把漏斗明细另存一份 JSON")
    args = ap.parse_args()

    works = load_works(args.xlsx)
    label(works, index_output(args.output_root))
    print(f"读到 {len(works)} 条作品"
          f"（视频 {sum(1 for w in works if not w['_图文'])}，"
          f"图文 {sum(1 for w in works if w['_图文'])}）")

    report_overview(works)
    report_by_kind(works)
    funnel = report_funnel(works)
    report_rates(works, funnel, args.output_root)
    report_correlations(works, args.fresh_hours)
    report_vs_ratio(works, args.output_root)

    if args.json:
        args.json.write_text(json.dumps(funnel, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\n漏斗明细已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
