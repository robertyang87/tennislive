#!/usr/bin/env python3
"""按赛历逐站对账：这一站的场上采访，库里到底有没有、有多少、从哪来。

写这个的由来：之前统计覆盖率靠的是我手搓的赛事清单，**漏掉的赛事在报表上
根本不出现**——看着一片绿，其实半张日历没查过。拿到完整赛历之后，
把「有多少」和「有没有查过」分开，缺口才看得见。

判据两条，缺一不可：

    赛事识别   `pat` 正则**同时匹配标题和 page_url**——tennistv 的条目
               赛事名只在 URL 里（`/tournaments/422_2025/cincinnati`），
               光看标题会把 42 条辛辛那提全判成「不属于任何赛事」
    男女分流   同名不同巡回的（迪拜、华盛顿、印第安维尔斯、罗马……）
               按球员性别分开数，因为 ATP 和 WTA 那一站的来源常常完全不同

**性别以 ATP / WTA 各 500 人的官方排名快照为准**（`side()`），认出率 88%。
认不出的一律返回 None，**不猜**——`--unmatched` 会把它们打出来，
只报命中的没法证明名单是全的。

注意这里和 `oncourt_match_coverage.py` **故意不一致**：那边算的是占签表的
百分比，认不出性别的条目会在男单女单各算一次，所以一律不算；这边报的是
「这一站有没有覆盖、有几条」，多算不致命而漏算会让缺口从报表上消失，所以放过去。

用法：
    python tools/oncourt_coverage.py                 # 全量对账
    python tools/oncourt_coverage.py --tier WTA500   # 只看某一档
    python tools/oncourt_coverage.py --gaps          # 只列零覆盖和薄覆盖的
    python tools/oncourt_coverage.py --unmatched     # 认不出赛事/性别的条目
    python tools/oncourt_coverage.py --md            # 输出 Markdown 表
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "oncourt_interviews.json"
CALENDAR = ROOT / "data" / "tour_calendar_2026.json"

sys.path.insert(0, str(ROOT))

SNAPSHOT = ROOT / "src" / "tennislive" / "zh" / "player_names_top500.json"


def _fold(s: str) -> str:
    """去掉音标。`Karolína Muchová` 和快照里的 `Karolina Muchova` 得能对上。"""
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def _roster() -> tuple[list, list, list, list]:
    """从 ATP / WTA 各 500 人的官方排名快照里造匹配器。

    **这才是权威名单。** 原来只有下面那两串手搓正则，认出率 78%——
    剩下 22% 在单巡回赛事里会「男女两边各算一次」，直接把覆盖率算虚。

    快照的两个性质是实测过的，不是假设：
      · **全名零重叠**——ATP 500 和 WTA 500 没有一个同名，所以全名命中即可定案
      · **姓氏有 10 个两边都有**（Zhang / Zheng / Sun / Smith / Jones …），
        所以姓氏只用两边独占的那部分，共用姓一律判不出

    顺序也是有讲究的：全名 → 补充名单 → 独占姓氏。补充那份排在姓氏前面，
    因为它装的是**退役传奇**（纳达尔、费德勒、大小威、桑普拉斯这一档），
    这些人早不在 top 500 里了，但库里跨 2017–2026 全是他们。
    """
    with SNAPSHOT.open(encoding="utf-8") as fh:
        snap = json.load(fh)

    def full(tour):
        return [re.compile(r"\b" + re.escape(_fold(e["name_en"])).replace(r"\ ", r"\s+") + r"\b",
                           re.I) for e in snap["tours"][tour]]

    sur = {t: {_fold(e["name_en"]).split()[-1] for e in snap["tours"][t]} for t in ("ATP", "WTA")}
    only = lambda a, b: [re.compile(rf"\b{re.escape(s)}\b", re.I) for s in sur[a] - sur[b]]
    return full("ATP"), full("WTA"), only("ATP", "WTA"), only("WTA", "ATP")


# 补充名单：**只放快照里没有的人**——退役的、掉出 top 500 的、以及双打专精
# 选手（双打排名不进单打 500）。原来这两串是唯一的判据，塞了 249 个词，
# 其中 191 个现役球员现在由快照覆盖，**留在这里只会和快照打架**：
#
#     Cristian   雅克琳·克里斯蒂安（女）匹上了 Cristian Garín（男）
#     Jovic      伊娃·约维奇（女）匹上了 Dusan Lajovic（男）
#     Paul       汤米·保罗（男）匹上了 Paula Badosa —— **旧版没有词边界**，
#                短姓氏会匹进长名字里：Lys→Halys、Day→Dayana
#     Day        凯拉·戴（女）匹上了 "a tough day at the office"
#
# 所以现在两条规矩：**词边界必须有**（`_word()` 统一加），
# **快照里有的人不许写在这**（有测试拦，见 test_supplementary_roster_does_not_duplicate_the_snapshot）。
def _word(*names: str) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(names) + r")\b", re.I)


WOMEN = _word(
    # 退役 / 早已掉出 top 500
    "Serena", "Venus Williams", "Wozniacki", "Mandlikova", "Peng",
    "Hsieh", "Gajdosova", "Puig", "Errani", "Jabeur",
    # 双打专精，单打排名不进 500
    "Krejikova", "Danilina", "Krunic", "Schuurs", "Sutjiadi", "Babel", "Bassols",
    # 中国球员的另一种写法（快照里是 "Shuai Zhang" 这一种语序）
    "Zhang Shuai", "Shuai Zhang",
    # 姓氏拼法与快照不同
    "Haddad", "Fajmonova",
)

MEN = _word(
    # 退役 / 早已掉出 top 500
    "Nadal", "Federer", "Murray", "Thiem", "Nishikori", "Gasquet", "Kyrgios",
    "Tsonga", "Agassi", "Ferrero", "Tipsarevic", "Janowicz", r"Ivani[sš]evi[cć]",
    "Sousa",
    # 双打专精
    "Patten", "Heliovaara", "Pavic", "Arevalo", r"Ajdukovi[cć]",
    # 姓氏拼法 / 语序与快照不同
    r"Auger[\s-]?Aliassime", "de Minaur", "van de Zandschulp", "Van Assche",
    "Mpetshi", r"Gar[ií]n", "Carballes", "Montiero", "Barrios", "Jarry",
    "Yunchaokete", "Zhizhen Zhang",
    # 赛事官员 / 教练，出现在标题里时按男子算比判不出好
    "Kermode", "Norman", "Olivetti",
)


def load() -> tuple[dict, list]:
    with STORE.open(encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    with CALENDAR.open(encoding="utf-8") as fh:
        events = json.load(fh)["events"]
    return items, events


def haystack(item: dict) -> str:
    """赛事名可能只在 URL 里，标题和 URL 一起匹配。

    实测：tennistv 的 42 条辛辛那提条目标题里一个 `Cincinnati` 都没有
    （`Alcaraz Reacts To The Final`），赛事名只出现在
    `/tournaments/422_2025/cincinnati`。只看标题会把它们全判成孤儿。
    """
    return f"{item.get('title', '')} {item.get('page_url') or ''} {item.get('url', '')}"


@functools.lru_cache(maxsize=1)
def _matchers():
    return _roster()


def _named(text: str, pats: list) -> bool:
    """这些名字模式里，有没有一个匹在**真的像个名字**的地方。

    判据是大小写：**人名在标题里一定不是全小写的。**

    起因是快照里真有几个姓氏本身就是英文常用词——`Day`（凯拉·戴，WTA 独占姓）
    匹上了 `Sinner: 'Today was a very difficult day in the office'`，
    于是这条被判成「男女都命中」，直接算不出性别。全小写的 `day` 一律不认之后
    它就干净了。

    不用「首字母大写」而用「不全小写」，是因为标题常常整句大写
    （`WORLD NO.1 IGA SWIATEK ON COURT INTERVIEW`）——那种也得认。
    """
    return any(m.group(0) != m.group(0).lower()
               for rx in pats if (m := rx.search(text)))


def side(item: dict) -> str | None:
    """这条是男子还是女子。认不出返回 None，**不猜**。

    三级判据，越靠前越硬：

        ① 官方排名快照里的**全名**     ATP/WTA 各 500 人，全名零重叠，命中即定案
        ② 手写的退役球员名单           纳达尔、费德勒、大小威……快照里没有
        ③ 快照里**某一边独占的姓氏**   共用姓（Zhang/Zheng/Sun/Smith…）不算

    男女两边都命中就返回 None——霍普曼杯的混合队（`Karen Khachanov and
    Anastasia Pavlyuchenkova`）和「斯维托丽娜夸丈夫蒙菲尔斯」都长这样，
    **强行选一边不如承认认不出来**。

    认出率从 78%（只有手写名单）提到 88%。剩下 12% 大多是 2017–2021 的
    老条目（巴蒂、科贝尔、库兹涅佐娃、拉奥尼奇）和霍普曼杯的 `Team Germany`。
    """
    t = _fold(item.get("title", ""))
    atp_f, wta_f, atp_s, wta_s = _matchers()
    a, w = _named(t, atp_f), _named(t, wta_f)
    if a != w:
        return "atp" if a else "wta"
    if a and w:
        return None
    raw = item.get("title", "")
    w, m = bool(WOMEN.search(raw)), bool(MEN.search(raw))
    if w != m:
        return "wta" if w else "atp"
    a, w = _named(t, atp_s), _named(t, wta_s)
    if a != w:
        return "atp" if a else "wta"
    return None


def tally(items: dict, events: list) -> tuple[list, list]:
    """每站数一遍。返回 (逐站结果, 没归到任何赛事的条目)。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("feed", ROOT / "tools" / "oncourt_feed.py")
    feed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(feed)

    compiled = [(e, re.compile(e["pat"], re.I)) for e in events]
    rows, claimed = [], set()
    for ev, rx in compiled:
        # `srcs` 里的源一律算这一站——频道本身就说明了赛事，
        # 标题写不写无所谓（汉堡写 HEO2021，迪拜干脆什么都不写）
        own = set(ev.get("srcs", ()))
        hits = []
        for vid, it in items.items():
            if it.get("source") not in own and not rx.search(haystack(it)):
                continue
            s = side(it)
            # tour=both 的（大满贯、联合杯）两边都算；单侧的要对得上，
            # 认不出性别的**也算进去**——宁可多算也别把真条目丢在报表外面
            if ev["tour"] != "both" and s is not None and s != ev["tour"]:
                continue
            hits.append(it)
            claimed.add(vid)
        rounds = Counter(feed.parse_round(h) for h in hits)
        key = rounds["决赛"] + rounds["半决赛"] + rounds["四分之一决赛"]
        rows.append({**ev, "n": len(hits), "key": key,
                     "f": rounds["决赛"], "sf": rounds["半决赛"], "qf": rounds["四分之一决赛"],
                     "srcs": Counter(h["source"] for h in hits)})
    orphans = [it for vid, it in items.items() if vid not in claimed]
    return rows, orphans


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", help="只看某一档（大满贯 / ATP1000 / WTA500 …）")
    ap.add_argument("--gaps", action="store_true", help="只列关键轮次不足 4 条的")
    ap.add_argument("--unmatched", action="store_true", help="列出没归到任何赛事的条目")
    ap.add_argument("--md", action="store_true", help="输出 Markdown 表")
    args = ap.parse_args()

    items, events = load()
    rows, orphans = tally(items, events)

    if args.unmatched:
        print(f"没归到任何赛事的 {len(orphans)} 条（占库存 {len(orphans)/len(items):.0%}）：")
        for src, n in Counter(o["source"] for o in orphans).most_common():
            print(f"  {n:>4}  {src}")
        print("\n样例：")
        for o in orphans[:25]:
            print(f"  [{o['source'][:20]:20s}] {o.get('title', '')[:72]}")
        return 0

    show = [r for r in rows if not args.tier or r["tier"] == args.tier]
    if args.gaps:
        show = [r for r in show if r["key"] < 4]

    if args.md:
        print("| 赛事 | 日期 | 级别 | 库内 | 决 | 半 | 八 | 主要来源 |")
        print("| --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
        for r in show:
            top = "、".join(f"{k}{v}" for k, v in r["srcs"].most_common(2)) or "—"
            print(f"| {r['zh']} | {r['start']}–{r['end']} | {r['tier']} | {r['n']} | "
                  f"{r['f']} | {r['sf']} | {r['qf']} | {top} |")
    else:
        print(f"{'赛事':22s} {'日期':12s} {'级别':8s} {'库内':>4} {'决':>3} {'半':>3} {'八':>3}  主要来源")
        for r in show:
            top = "、".join(f"{k[:14]}{v}" for k, v in r["srcs"].most_common(2)) or "—— 零覆盖"
            print(f"{r['zh'][:20]:22s} {r['start']}–{r['end']}  {r['tier']:8s} "
                  f"{r['n']:>4} {r['f']:>3} {r['sf']:>3} {r['qf']:>3}  {top}")

    zero = [r for r in show if r["n"] == 0]
    thin = [r for r in show if 0 < r["key"] < 4]
    print(f"\n合计 {len(show)} 站：零覆盖 {len(zero)}，关键轮次不足 4 条 {len(thin)}，"
          f"归不到赛事的条目 {len(orphans)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
