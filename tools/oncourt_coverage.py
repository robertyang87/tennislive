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

**性别是按名单认的，不是猜的。** 名单不全会低估 WTA 那一侧，所以
`--unmatched` 会把认不出性别的条目打出来，用来补名单——只报命中的
没法证明名单是全的。

用法：
    python tools/oncourt_coverage.py                 # 全量对账
    python tools/oncourt_coverage.py --tier WTA500   # 只看某一档
    python tools/oncourt_coverage.py --gaps          # 只列零覆盖和薄覆盖的
    python tools/oncourt_coverage.py --unmatched     # 认不出赛事/性别的条目
    python tools/oncourt_coverage.py --md            # 输出 Markdown 表
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "oncourt_interviews.json"
CALENDAR = ROOT / "data" / "tour_calendar_2026.json"

sys.path.insert(0, str(ROOT))

# 女子球员标记。**只用来把同名赛事的男女两侧分开**，不参与收录判断。
# 名单必然不全——所以 --unmatched 会把认不出的打出来，用来补。
WOMEN = re.compile(
    r"Sabalenka|Swiatek|Gauff|Rybakina|Paolini|Pegula|Andreeva|Keys|Navarro|Kasatkina|"
    r"Vekic|Ostapenko|Muchova|Krejcikova|Krejikova|Badosa|Kostyuk|Samsonova|Alexandrova|"
    r"Haddad|Collins|Azarenka|Osaka|Raducanu|Boulter|Kartal|Svitolina|Shnaider|Noskova|"
    r"Bouzkova|Fernandez|Mboko|Anisimova|Tauson|Bencic|Siniakova|Linette|Frech|Sakkari|"
    r"Jabeur|Garcia|Potapova|Kalinina|Marcinko|Tagger|Snigur|Havlickova|Valentova|"
    r"Starodubtseva|Bejlek|Salkova|Yastremska|Putintseva|Rakhimova|Eala|Kalinskaya|Lys|"
    r"Begu|Ruse|Kessler|Baptiste|Parks|Danilina|Krunic|Mertens|Pliskova|Townsend|"
    r"Andreescu|Jovic|Grant|Semenistaja|Gjorcheska|Bolkvadze|Venus Williams|Serena|"
    r"Stearns|Dolehide|Avanesyan|Gracheva|Kudermetova|Tomljanovic|Sherif|Cristian|"
    r"Bronzetti|Cocciaretto|Errani|Wozniacki|Zvonareva|Siegemund|Schuurs|Perez|Sutjiadi|"
    r"Zheng|Xinyu Wang|Xiyu Wang|Zhang Shuai|Shuai Zhang|Xinyu Gao|Sijia Wei|Lulu Sun|"
    r"Hontama|Tararudee|Bartunkova|Kovackova|Siskova|Fajmonova|Valdmannova|Martincova|"
    r"Grabher|Day|Hibino|Tjen|Ferro|Babel|Oliynykova|Korneeva|Trevisan|Brancaccio|"
    r"Zakharova|Erjavec|Bassols|Vandewinkel|Mandlikova|Peng|Hsieh|Gajdosova|Puig",
    re.I)

MEN = re.compile(
    r"Sinner|Alcaraz|Djokovic|Zverev|Medvedev|Rublev|Tsitsipas|Ruud|Fritz|Shelton|"
    r"Musetti|Rune|Draper|Paul|Tiafoe|Humbert|Khachanov|Auger[\s-]?Aliassime|Felix|"
    r"Dimitrov|Bublik|Cerundolo|Cobolli|Fonseca|Mensik|Berrettini|Arnaldi|Nadal|Federer|"
    r"Murray|Wawrinka|Thiem|Nishikori|Monfils|Gasquet|Evans|Norrie|Kyrgios|de Minaur|"
    r"Griekspoor|Struff|Popyrin|Baez|Darderi|Vacherot|Collignon|Moutet|Korda|Tabilo|"
    r"Jarry|Gar[íi]n|Barrios|Vallejo|Tirante|Travaglia|Borges|Pellegrino|Carabelli|"
    r"Misolic|van de Zandschulp|Dzumhur|Montiero|Carballes|Skatov|Machac|Bergs|Hurkacz|"
    r"Shevchenko|Fils|Mpetshi|Perricard|Blockx|Van Assche|Halys|Basilashvili|Choinski|"
    r"Faria|Mochizuki|Tarvet|Rodesch|Stewart|Basing|Harris|Zhukayev|Kouame|Gaston|"
    r"Schoolkate|Fucsovics|Safiullin|Ofner|Ymer|Sousa|Stebe|Tipsarevic|Janowicz|"
    r"Ramos|Kolar|Atmane|Bonzi|Fery|Patten|Heliovaara|Pavic|Arevalo|Zhizhen Zhang|"
    r"Yunchaokete|\bBu\b|Shang|\bWu\b|Nishioka|Etcheverry|Munar|Ivani[šs]evi[ćc]|"
    r"Ajdukovi[ćc]|Lehecka|Kermode|Norman|Olivetti|Prizmic|Tsonga|Agassi|Ferrero",
    re.I)


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


def side(item: dict) -> str | None:
    """这条是男子还是女子。认不出返回 None，**不猜**。"""
    t = item.get("title", "")
    w, m = bool(WOMEN.search(t)), bool(MEN.search(t))
    if w and not m:
        return "wta"
    if m and not w:
        return "atp"
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
