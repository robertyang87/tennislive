#!/usr/bin/env python3
"""小红书后台导出的统计表，和仓库里的成片对起来看。

后台那张表只告诉你「人均观看时长 46 秒」，不告诉你那条片子有多长。46 秒是看完了
还是刚开头就走，差别是全部——`ball-pick` 是 139.8 秒，46 秒只到三分之一。
片长在 `output/**/**.mp4` 里躺着，两边一join，平均看了多久占全片的多少就出来了。

三件事，都直接查产物：

1. **体裁/系列/时段的常规切分** —— 但曝光那一列对视频是残缺的，见下。
2. **均观看比例** = 人均观看时长 ÷ 成片时长。片长用 `mp4_duration.mvhd_seconds`
   直接量成片，不靠 ffprobe（沙箱里没有），也不靠「渲染参数应该是多少」推断。

   **这个数不是完播率，别当完播率用。** 头一版就叫它「完播率」，是错的，而且
   错在定义上，不需要任何数据来推翻：它是个**均值**。一半人 2 秒划走、一半人
   看完，和所有人都看一半，算出来一模一样。均值只回答「平均看了多久」，
   回答不了「几个人看到了结尾」——而后者才是「末屏那一问有多少人听见」要问的。

   小红书的导出表里没有真完播率这一栏，所以**这个号在小红书上的真完播率，
   目前无从得知**，别拿这个数去顶替。

   缺口能有多大？抖音后台直接给真完播率，同一批片子在抖音是：

       大师赛为什么变两周   均观看比例 22.0%   抖音真完播 6.1%
       鹰眼是怎么来的       均观看比例  8.8%   抖音真完播 1.0%
       中位（11 条）        均观看比例 10.4%   抖音真完播 2.0%

   **注意这组倍数只属于抖音那批观众**，不能搬到小红书当估计值——两个平台的
   人群、推荐机制、自动播放行为都不一样，同一条内容的播放量在两边差过 69 倍
   （三巨头图文：小红书 152，抖音 10567）也差过 25 倍（挑球视频：小红书 1581，
   抖音 69）。它在这里只说明一件事：**均值和完播能差出一个数量级**，所以名字
   必须叫对。
3. **曝光一致性自检** —— 头一回看这张表时，差点拿「图文曝光 24512 > 视频 18184」
   得出「图文分发更好」。其实是图文 12 条的 `观看/曝光` 和`封面点击率`分毫不差，
   视频 11 条全部对不上（2.2～4.6 倍）：视频有一路观看不计入曝光。所以这个自检
   固定跑，别再让人踩第二次。

## 标题怎么和成片对上

不写死映射表 —— 让产物自证：`xiaohongshu.txt` 的**第一行就是发文标题**，
和后台导出的「笔记标题」是同一个字符串。先精确匹配，对不上的再模糊匹配
（去掉 emoji 和标点之后按相似度），因为发文时标题常被手改：

    生成 🎾7.26 网球有故事｜网球为什么是黄色的
    发布 🎾7.26｜网球为什么是黄色的            ← 砍掉了「网球有故事」

模糊匹配卡三道：相似度过阈值、发布日期和产物目录日期在窗口内、和第二名拉开差距。
**三道都过不了的一律报出来**，不静默丢掉 —— 只在成功时出声的检查，没法证明它
真的看过。头一版手写映射表就把「季莫费耶娃这一拍」指到了 `official-highlight`
（那天根本没有这个文件），比例算不出来还以为是数据缺失；自动匹配指到
`yesterday-point/wta`，29.4 秒，一直好好躺在那儿。

用法：
    python tools/analyze_xhs_stats.py 笔记数据.xlsx
    python tools/analyze_xhs_stats.py 笔记数据.xlsx --json out.json
    python tools/analyze_xhs_stats.py 笔记数据.xlsx --min-ratio 0.8

退出码恒为 0：这是分析工具不是闸门。对不上的笔记打印在「未匹配」一节。
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
import zipfile
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mp4_duration import mvhd_seconds  # noqa: E402  （同目录，纯 stdlib）

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# 模糊匹配的三道闸门。阈值是量出来的：改标题的那几条落在 0.80～0.88，
# 而「网球快报｜巴尔迪科娃先丢一盘」对「今日球局｜巴尔通科娃逆转晋级」
# 只有 0.58 —— 长得像但讲的不是一回事，必须挡住。
MIN_RATIO = 0.75
MIN_MARGIN = 0.05   # 和第二名至少拉开这么多，否则算「分不清」
DATE_WINDOW = 2     # 发布日期和产物目录日期最多差几天

NUMERIC = ("曝光", "观看量", "封面点击率", "点赞", "评论", "收藏", "涨粉", "分享",
           "人均观看时长", "弹幕")
INTERACTION = ("点赞", "评论", "收藏", "分享")

# 系列名按标题里的关键词认。顺序有意义：「开赛之前」和「开球之前」是同一个
# 格式的两种写法，分开统计反而看不出量。
SERIES = ("网球有故事", "今日球局", "开赛之前", "开球之前", "昨日好球",
          "网球快报", "历史今天", "网球报告")


# ---------------------------------------------------------------- xlsx


def _col_letters(ref: str) -> str:
    return "".join(c for c in ref if c.isalpha())


def _col_index(ref: str) -> int:
    n = 0
    for c in _col_letters(ref):
        n = n * 26 + (ord(c.upper()) - 64)
    return n - 1


def read_xlsx(path: Path) -> list[list[str]]:
    """把第一张工作表读成一个二维字符串表格。

    只用 stdlib —— 这个仓库没有 openpyxl，为一个分析脚本加一条依赖不值当。
    xlsx 就是个 zip：共享字符串在 sharedStrings.xml，单元格 t="s" 时存的是
    它在里面的下标。
    """
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{_NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        sheets = sorted(n for n in z.namelist()
                        if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sheets:
            raise SystemExit(f"{path} 里没有工作表")
        root = ElementTree.fromstring(z.read(sheets[0]))

    rows: list[list[str]] = []
    for row in root.iter(f"{_NS}row"):
        cells: dict[int, str] = {}
        for c in row.findall(f"{_NS}c"):
            ref = c.get("r") or ""
            idx = _col_index(ref) if ref else len(cells)
            kind = c.get("t")
            if kind == "s":
                v = c.find(f"{_NS}v")
                text = shared[int(v.text)] if v is not None and v.text else ""
            elif kind == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
            else:
                v = c.find(f"{_NS}v")
                text = v.text if v is not None and v.text else ""
            cells[idx] = text
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


def _to_num(s: str):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


_TIME_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日(\d{1,2})时(\d{1,2})分")


def _parse_time(s: str) -> datetime | None:
    m = _TIME_RE.search(s or "")
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    return datetime(y, mo, d, h, mi)


def load_notes(path: Path) -> list[dict]:
    """表格 → 笔记列表。表头那一行自己找，别假定在第几行。

    导出的表第 0 行是「最多导出排序后前1000条笔记」铺满整行的水印，第 1 行才是
    表头。写死行号的话，哪天导出格式变一下就全错位了，还不报错。
    """
    rows = read_xlsx(path)
    header_at = next((i for i, r in enumerate(rows) if "笔记标题" in r), None)
    if header_at is None:
        raise SystemExit(f"{path} 里找不到「笔记标题」表头")
    header = rows[header_at]
    notes = []
    for row in rows[header_at + 1:]:
        rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header) if h}
        if not rec.get("笔记标题"):
            continue
        for key in NUMERIC:
            rec[key] = _to_num(rec.get(key, ""))
        rec["_time"] = _parse_time(rec.get("首次发布时间", ""))
        rec["_互动"] = sum(rec.get(k) or 0 for k in INTERACTION)
        rec["_系列"] = next((s for s in SERIES if s in rec["笔记标题"]), "其他")
        notes.append(rec)
    return notes


# ------------------------------------------------------- 标题 → 成片


def normalize(title: str) -> str:
    """去掉 emoji、标点、空白，只留下用来比对的字。

    发文标题和生成标题的差异几乎都在装饰上（emoji 换了、`｜` 变 `|`、日期
    写法从 `7.24` 变成 `7月24日`），把这些去掉之后剩下的才是内容。
    """
    out = []
    for ch in title:
        cat = unicodedata.category(ch)
        if cat[0] in "LN":          # 字母、数字（含汉字）
            out.append(ch)
    return "".join(out)


def _dir_date(path: Path) -> date | None:
    for part in path.parts:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", part)
        if m:
            return date(*(int(x) for x in m.groups()))
    return None


def index_output(root: Path) -> list[dict]:
    """扫出所有「已生成的一篇内容」：标题 + 目录日期 + 同目录的成片。

    以 `xiaohongshu.txt` 为锚 —— 有它才算一篇可发的内容。mp4 在同目录下找；
    找不到不是错（图文本来就没有），只是这条算不出均观看比例。
    """
    items = []
    for txt in sorted(root.rglob("xiaohongshu.txt")):
        try:
            first = txt.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        title = next((ln.strip() for ln in first if ln.strip()), "")
        if not title:
            continue
        mp4s = sorted(txt.parent.glob("*.mp4"))
        items.append({
            "title": title,
            "norm": normalize(title),
            "dir": txt.parent,
            "date": _dir_date(txt.parent),
            "mp4": mp4s[0] if mp4s else None,
        })
    return items


def match_note(note: dict, items: list[dict], min_ratio: float) -> tuple[dict | None, str]:
    """把一条笔记指到一个产物目录上。返回 (命中, 说明)。

    先精确后模糊。模糊要过三道闸门，任何一道没过都把原因说出来 —— 不然
    「没匹配上」和「压根没生成过」在输出里长得一模一样，又是空结果那个坑。
    """
    title = note["笔记标题"]
    exact = [it for it in items if it["title"] == title]
    if len(exact) == 1:
        return exact[0], "精确"
    if len(exact) > 1:
        # 同一个标题生成过多次（重跑、改版），用发布日期挑最近的那份。
        best = _nearest_by_date(note, exact)
        if best:
            return best, "精确（同名多份，按日期取最近）"
        return None, f"标题精确命中 {len(exact)} 份，日期也分不出"

    norm = normalize(title)
    scored = sorted(
        ((SequenceMatcher(None, norm, it["norm"]).ratio(), it) for it in items),
        key=lambda x: x[0], reverse=True,
    )
    if not scored:
        return None, "output/ 下没有任何 xiaohongshu.txt"
    top_score, top = scored[0]
    if top_score < min_ratio:
        return None, f"最像的也只有 {top_score:.2f}（{top['title']}），低于 {min_ratio}"
    runner = scored[1][0] if len(scored) > 1 else 0.0
    if top_score - runner < MIN_MARGIN:
        return None, (f"{top_score:.2f} vs {runner:.2f} 分不清："
                      f"{top['title']} / {scored[1][1]['title']}")
    if note["_time"] and top["date"]:
        gap = abs((note["_time"].date() - top["date"]).days)
        if gap > DATE_WINDOW:
            return None, f"最像的是「{top['title']}」({top_score:.2f}) 但日期差 {gap} 天"
    return top, f"模糊 {top_score:.2f}"


def _nearest_by_date(note: dict, cands: list[dict]) -> dict | None:
    if not note["_time"]:
        return None
    dated = [c for c in cands if c["date"]]
    if not dated:
        return None
    return min(dated, key=lambda c: abs((note["_time"].date() - c["date"]).days))


# ---------------------------------------------------------------- 报告


def _fmt(x, spec="{:.0f}", dash="—"):
    return dash if x is None else spec.format(x)


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _table(rows: list[list[str]], heads: list[str]) -> str:
    """等宽表格。中文按两格算，不然列头永远对不齐。"""
    def width(s):
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))
    cols = list(zip(*([heads] + rows))) if rows else [[h] for h in heads]
    widths = [max(width(c) for c in col) for col in cols]
    out = []
    for i, row in enumerate([heads] + rows):
        cells = []
        for j, c in enumerate(row):
            pad = widths[j] - width(c)
            cells.append((" " * pad) + str(c) if j else str(c) + (" " * pad))
        out.append("  ".join(cells))
        if i == 0:
            out.append("  ".join("-" * w for w in widths))
    return "\n".join(out)


def report_overview(notes: list[dict]) -> None:
    span = [n["_time"] for n in notes if n["_time"]]
    print(f"\n共 {len(notes)} 条笔记", end="")
    if span:
        print(f"，{min(span):%Y-%m-%d} ~ {max(span):%Y-%m-%d}", end="")
    print()
    total = {k: sum(n.get(k) or 0 for n in notes) for k in
             ("曝光", "观看量", "点赞", "评论", "收藏", "分享", "涨粉")}
    views = total["观看量"]
    inter = sum(n["_互动"] for n in notes)
    print(f"曝光 {total['曝光']:.0f}   观看 {views:.0f}   互动 {inter:.0f}"
          f"（{inter / views:.2%}）   涨粉 {total['涨粉']:.0f}" if views else "观看为 0")


def report_exposure_check(notes: list[dict]) -> dict:
    """曝光那一列对不对得上封面点击率 —— 按体裁分开看。

    对得上说明「观看量就是点击数」，曝光可以当分母用；对不上说明这个体裁还有
    一路观看不走封面点击（视频的沉浸式自动播放），此时表里的曝光是残缺的，
    真实曝光得按 观看量÷CTR 还原。
    """
    print("\n### 曝光一致性自检（CTR 是否等于 观看/曝光）")
    by_kind: dict[str, list[dict]] = {}
    for n in notes:
        if (n.get("曝光") or 0) > 0 and n.get("封面点击率"):
            by_kind.setdefault(n.get("体裁", "?"), []).append(n)
    rows, verdicts = [], {}
    for kind, group in sorted(by_kind.items()):
        gaps = [n["观看量"] / n["曝光"] - n["封面点击率"] for n in group]
        worst = max(gaps)
        implied = sum(n["观看量"] / n["封面点击率"] for n in group)
        recorded = sum(n["曝光"] for n in group)
        ok = worst < 0.02
        verdicts[kind] = {
            "一致": ok, "条数": len(group), "记录曝光": round(recorded),
            "还原曝光": round(implied), "最大偏差": round(worst, 4),
        }
        rows.append([kind, str(len(group)), f"{worst:+.1%}", f"{recorded:.0f}",
                     f"{implied:.0f}", f"{implied / recorded:.2f}x" if recorded else "—",
                     "一致" if ok else "对不上"])
    print(_table(rows, ["体裁", "条数", "最大偏差", "记录曝光", "还原曝光", "倍数", "判定"]))
    bad = [k for k, v in verdicts.items() if not v["一致"]]
    if bad:
        print(f"\n  ⚠ {'、'.join(bad)} 的曝光列是残缺的：这些体裁还有不计入曝光的观看来源。")
        print("    跨体裁比曝光时用「还原曝光」，别用表里那一列。")
    return verdicts


def report_by(notes: list[dict], key: str, label: str) -> None:
    print(f"\n### 按{label}")
    groups: dict[str, list[dict]] = {}
    for n in notes:
        groups.setdefault(str(n.get(key) or "?"), []).append(n)
    rows = []
    for name, g in groups.items():
        views = sum(n.get("观看量") or 0 for n in g)
        inter = sum(n["_互动"] for n in g)
        fans = sum(n.get("涨粉") or 0 for n in g)
        rows.append([
            name, str(len(g)), f"{views:.0f}", f"{views / len(g):.0f}",
            _fmt(_median([n.get("封面点击率") for n in g]), "{:.1%}"),
            f"{inter / views:.2%}" if views else "—",
            f"{fans:.0f}", f"{fans / views * 1000:.2f}" if views else "—",
            _fmt(_median([n.get("人均观看时长") for n in g]), "{:.0f}s"),
        ])
    rows.sort(key=lambda r: float(r[3]), reverse=True)
    print(_table(rows, [label, "条数", "总观看", "均观看", "CTR中位",
                        "互动率", "涨粉", "千观看涨粉", "时长中位"]))


def report_completion(matched: list[tuple[dict, dict, str]]) -> list[dict]:
    """均观看比例 —— 小红书后台给不出的一栏。注意它不是完播率，见模块开头。"""
    print("\n### 均观看比例（人均观看时长 ÷ 成片时长，不是完播率）")
    rows, records = [], []
    for note, item, how in matched:
        if not item["mp4"]:
            continue
        try:
            length = mvhd_seconds(item["mp4"].read_bytes())
        except (OSError, ValueError) as exc:
            print(f"  量不出 {item['mp4']}：{exc}")
            continue
        watched = note.get("人均观看时长")
        rate = watched / length if watched and length else None
        records.append({
            "标题": note["笔记标题"], "成片": str(item["mp4"].relative_to(REPO)),
            "片长": round(length, 1), "人均观看": watched, "均观看比例": rate,
            "观看量": note.get("观看量"), "涨粉": note.get("涨粉"), "匹配": how,
        })
        rows.append([note["笔记标题"], f"{length:.1f}s", _fmt(watched, "{:.0f}s"),
                     _fmt(rate, "{:.0%}"), _fmt(note.get("观看量")),
                     _fmt(note.get("涨粉")), how])
    if not rows:
        print("  没有能对上成片的笔记 —— 先看「未匹配」一节，别当成没有视频。")
        return records
    rows.sort(key=lambda r: float(r[3].rstrip("%")) if r[3] != "—" else -1, reverse=True)
    print(_table(rows, ["笔记标题", "片长", "人均观看", "均观看比例", "观看量", "涨粉", "匹配"]))

    live = [r for r in records if r["均观看比例"] and r["人均观看"]]
    if live:
        print(f"\n  {len(live)} 条有效：片长中位 {_median([r['片长'] for r in live]):.0f}s，"
              f"人均观看中位 {_median([r['人均观看'] for r in live]):.0f}s，"
              f"均观看比例中位 {_median([r['均观看比例'] for r in live]):.1%}")
        if len(live) > 2:
            xs = [r["片长"] for r in live]
            ys = [r["均观看比例"] for r in live]
            print(f"  片长 vs 均观看比例 相关性 {_pearson(xs, ys):+.2f}"
                  f"　片长 vs 人均观看 相关性 "
                  f"{_pearson(xs, [r['人均观看'] for r in live]):+.2f}")
    return records


def _pearson(xs, ys) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return num / den if den else 0.0


def report_lengths(root: Path) -> None:
    """仓库里各类成片多长 —— 不管发没发，看的是生产端的现状。"""
    print("\n### 各类成片片长（output/ 全量）")
    buckets: dict[str, list[float]] = {}
    for mp4 in sorted(root.rglob("*.mp4")):
        rel = str(mp4.relative_to(root))
        if "/explainer/" in rel or rel.endswith("explainer.mp4"):
            kind = "知识解说"
        elif "yesterday-point" in rel:
            kind = "昨日好球"
        elif "daily-brief" in rel:
            kind = "每日速报"
        elif "official-highlight" in rel:
            kind = "官方集锦"
        else:
            kind = "其他"
        try:
            buckets.setdefault(kind, []).append(mvhd_seconds(mp4.read_bytes()))
        except (OSError, ValueError):
            continue
    rows = []
    for kind, xs in buckets.items():
        xs.sort()
        rows.append([kind, str(len(xs)), f"{xs[0]:.1f}s",
                     f"{statistics.median(xs):.1f}s", f"{xs[-1]:.1f}s",
                     f"{statistics.fmean(xs):.1f}s"])
    rows.sort(key=lambda r: float(r[3].rstrip("s")), reverse=True)
    print(_table(rows, ["类别", "条数", "最短", "中位", "最长", "均值"]))


def report_unmatched(unmatched: list[tuple[dict, str]]) -> None:
    """对不上的一律列出来，连原因一起。

    只在成功时出声的检查没法证明它真的看过 —— 这一节就是它的证明。
    """
    print(f"\n### 未匹配到产物（{len(unmatched)} 条）")
    if not unmatched:
        print("  全部对上了。")
        return
    rows = [[n["笔记标题"], n.get("体裁", ""), why] for n, why in unmatched]
    print(_table(rows, ["笔记标题", "体裁", "为什么没对上"]))
    print("\n  发文时改过标题、或那条内容不是这个仓库生成的，都会落在这里。")
    print("  想放宽用 --min-ratio，但放太松会把「巴尔迪科娃」错配到「巴尔通科娃」。")


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", type=Path, help="小红书后台导出的笔记数据表")
    ap.add_argument("--output-root", type=Path, default=REPO / "output",
                    help="成片所在目录，默认 output/")
    ap.add_argument("--min-ratio", type=float, default=MIN_RATIO,
                    help=f"模糊匹配的相似度下限，默认 {MIN_RATIO}")
    ap.add_argument("--json", type=Path, help="把均观看比例明细另存一份 JSON")
    args = ap.parse_args()

    notes = load_notes(args.xlsx)
    items = index_output(args.output_root)
    print(f"读到 {len(notes)} 条笔记，{len(items)} 份已生成的内容"
          f"（{sum(1 for i in items if i['mp4'])} 份带成片）")

    matched, unmatched = [], []
    for note in notes:
        hit, why = match_note(note, items, args.min_ratio)
        (matched.append((note, hit, why)) if hit else unmatched.append((note, why)))

    report_overview(notes)
    report_exposure_check(notes)
    report_by(notes, "体裁", "体裁")
    report_by(notes, "_系列", "系列")
    report_lengths(args.output_root)
    records = report_completion(matched)
    report_unmatched(unmatched)

    if args.json:
        args.json.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\n均观看比例明细已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
