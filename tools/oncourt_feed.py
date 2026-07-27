#!/usr/bin/env python3
"""从 data/oncourt_interviews.json 里筛出**值得看的那几条**，并推到微信。

采集器（`collect_oncourt_interviews.py`）是全量的——八百多条，什么轮次都有。
这个脚本是它的下游，只做一件事：**按两个条件筛，然后推送**。

    条件一：关键场次 —— 决赛 / 半决赛 / 四分之一决赛
    条件二：有中国球员 —— 名单在 data/cn_players.json

两个条件是**或**的关系：郑钦文的第二轮要，辛纳的决赛也要。

范围限定在 **ATP / WTA 巡回赛与四大满贯的单打**，两道硬过滤：

    双打        滤掉（`--include-doubles` 放开），库里 103 条
    非巡回赛    滤掉（`--include-team` 放开）：拉沃尔杯（无积分，表演性质）、
                霍普曼杯与戴维斯杯（ITF）、比莉·简·金杯。**United Cup 不算在内**——
                它是 ATP 与 WTA 官方联办、计双方积分、在两边日历上，属巡回赛

## 轮次是从标题里解析的，不是元数据

各家写法差得很远，实测收集到的写法都写进 `_ROUNDS` 了：

    罗马    `… On-Court Interview | Quarterfinal | Rome 2026`
    Dubai   `Post-Match Interview: … after QF of 2026 Dubai …`
    澳网    `… On-Court Interview | Australian Open 2026 Final`
    温网    `… | Semi-Finals Post-match Interview | Wimbledon 2026`
    tennistv.com 例外：它有 `metadataRound` 字段，采集时已存进 `round`

**解析不出轮次的不当作关键场次**，宁可漏推也不误推——这类东西一旦开始
误推，人就不看了。解析不出但有中国球员的照样推。

## 中国球员匹配：两种姓名顺序都要试

标题里 `Qinwen Zheng` 和 `Zheng Qinwen` 两种写法都出现过。只匹配姓会炸——
Zheng / Wang / Zhang / Li / Sun 这些姓名单里到处都是，而且外国球员也有
（Ann Li 是美国人，Lulu Sun 是新西兰人），所以**只认全名**，
名单里明确列了排除项。

用法：
    # 看看会推什么，不真推
    python tools/oncourt_feed.py --dry-run

    # 生成 HTML 并推送（需要 PUSHPLUS_TOKEN）
    python tools/oncourt_feed.py --push

    # 只要中国球员那部分
    python tools/oncourt_feed.py --only-cn --dry-run

退出码 0＝正常（哪怕这轮没有新条目）；2＝配置缺失或推送失败。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "oncourt_interviews.json"
CN = ROOT / "data" / "cn_players.json"
SENT = ROOT / "data" / "oncourt_feed_sent.json"

# 轮次写法，按"越具体越先匹配"排。半决赛必须排在决赛前面——
# `Semi-Finals` 里含 `Final`，顺序反了半决赛会被判成决赛。
_ROUNDS: list[tuple[str, str]] = [
    (r"\bsemi[\s-]?finals?\b|\bSF\b", "半决赛"),
    (r"\bquarter[\s-]?finals?\b|\bQF\b", "四分之一决赛"),
    (r"\bfinals?\b", "决赛"),
    (r"\bround\s*(?:of\s*)?16\b|\bR16\b|\bfourth\s+round\b|\bround\s*4\b", "十六强"),
    (r"\bthird\s+round\b|\bround\s*3\b|\bR3\b", "第三轮"),
    (r"\bsecond\s+round\b|\bround\s*2\b|\bR2\b", "第二轮"),
    (r"\bfirst\s+round\b|\bround\s*1\b|\bR1\b", "第一轮"),
]
_ROUND_RE = [(re.compile(p, re.I), name) for p, name in _ROUNDS]

# 关键场次＝这三个轮次
KEY_ROUNDS = {"决赛", "半决赛", "四分之一决赛"}


def parse_round(item: dict) -> str | None:
    """标题里的轮次。tennistv.com 的条目自带 `round` 字段，优先用它。"""
    raw = (item.get("round") or "").strip()
    if raw:
        for rx, name in _ROUND_RE:
            if rx.search(raw):
                return name
    for rx, name in _ROUND_RE:
        if rx.search(item.get("title", "")):
            return name
    return None


def load_cn() -> tuple[list[dict], list, list, list]:
    """返回 (名单, 全名模式, 姓氏模式, 消歧用的排除全名模式)。

    **全名和姓氏两套都要**。只认全名会漏掉一大半——实测漏的正是最关键的
    那几条：`Zheng Quarter-final post-match interview | Roland-Garros 2025`
    （郑钦文法网八强，标题只写姓）、`Zhu/Zhang On-Court Interview |
    United Cup 2026`（双打配对，写两个姓）。

    但姓氏歧义大，所以姓氏匹配前必须先过 excluded_full：Michael Zheng 是
    美国人、Lulu Sun 是新西兰人、Ann Li 是美国人，他们的姓都在名单里。
    """
    with CN.open(encoding="utf-8") as fh:
        cfg = json.load(fh)
    full = []
    for p in cfg["players"]:
        parts = p["en"].split()
        if len(parts) < 2:
            continue
        given, family = " ".join(parts[:-1]), parts[-1]
        # 两种顺序都认；\b 两端保证不会把 Sun 匹配进 Sunday 之类
        full.append((p, re.compile(
            rf"\b{re.escape(given)}\s+{re.escape(family)}\b"
            rf"|\b{re.escape(family)}\s+{re.escape(given)}\b", re.I)))
    sur = [(sn, re.compile(rf"\b{re.escape(sn)}\b", re.I))
           for sn in cfg.get("surnames", [])]
    excl = [re.compile(rf"\b{re.escape(n)}\b", re.I)
            for n in cfg.get("excluded_full", [])]
    return cfg["players"], full, sur, excl


# 不属于 ATP / WTA 巡回赛的赛事。要的是「巡回赛 + 四大满贯」，
# 所以这些一律不推：
#
#   拉沃尔杯   ATP 承办但**不算积分**，性质是表演赛
#   霍普曼杯   ITF 混合团体赛，不在 ATP/WTA 日历上
#   戴维斯杯   ITF 国家团体赛
#   比莉·简·金杯  ITF（原联合会杯）
#
# **United Cup 不在此列**——它是 ATP 与 WTA 官方联办、计入双方排名积分、
# 同时出现在两边的赛季日历上，属巡回赛。而且它是中国球员场上采访的重要
# 来源（张之臻、高馨妤两条都出自这里），砍掉会让本就稀少的中国球员条目
# 再少三分之一。
_NON_TOUR = re.compile(
    r"\blaver\s+cup\b|\bhopman\s+cup\b|\bdavis\s+cup\b"
    r"|\bbillie\s+jean\s+king\s+cup\b|\bfed\s+cup\b|\bATP\s+Cup\b"
    r"|\bworld\s+tennis\s+challenge\b|\bultimate\s+tennis\s+showdown\b"
    r"|\bexhibition\b|\bcharity\s+match\b", re.I)


def is_tour_event(item: dict) -> bool:
    """这条是不是 ATP / WTA 巡回赛或四大满贯的。

    判据放在标题上而不是源上——转播方和搬运号的条目混着各种赛事，
    只按源过滤会连它们的巡回赛内容一起砍掉。
    """
    return not _NON_TOUR.search(item.get("title", ""))


# 双打识别。**只认配对写法和带限定词的 doubles**，不能认光秃秃的 "doubles"
# ——实测三条误伤全是单打球员在谈双打：
#   `"I need a crash course in doubles" | Emma Raducanu | Third round On-court…`
#   `Playing her former doubles partner | Iga Swiatek | On-Court Interview | …`
#   `Why she'll play doubles with Andy | Emma Raducanu | Second round …`
# 真双打的写法是 `Zhu/Zhang`、`Collins/Harrison` 这种斜杠配对（库里 102 条），
# 或者 `Wheelchair Doubles` / `Men's Doubles` 这种带限定词的。
_DOUBLES = [
    re.compile(r"\b[A-Z][\w'\u00C0-\u024F-]+\s*/\s*[A-Z][\w'\u00C0-\u024F-]+"),
    re.compile(r"\b(?:men'?s|women'?s|ladies'?|mixed|wheelchair|quad)\s+doubles\b", re.I),
]


def is_doubles(item: dict) -> bool:
    """这条是不是双打。tennistv.com 自带 matchType，比标题可靠，优先用。"""
    mt = (item.get("matchType") or item.get("match_type") or "").lower()
    if mt:
        return "doubles" in mt
    return any(rx.search(item.get("title", "")) for rx in _DOUBLES)


# 名字前面出现这些词，说明这人是**被打败的对手**，不是受访者。
# 起因是一条真实误收：
#   `On-Court Interview: Jasmine Paolini feels 'elated' with her stunning
#    win against Sijia Wei 💪`
# 韦思佳确实在标题里，但这是 Paolini 赢球后的采访，正好相反。
# 要的是「中国球员赢球后」，所以这类必须剔掉。
# 词表是逐条从真实误收里补出来的，别凭空精简。
# `overcomes` 是第二批补的：`Musetti overcomes Bu in Monte Carlo` —— 布云朝克特
# 是输的那个，这是 Musetti 赢球后的采访，方向正好相反。
_BEATEN = re.compile(
    r"\b(?:against|beating|beat(?:s|en)?|defeat(?:s|ing|ed)?|over|past|vs\.?|versus|"
    r"knocks?\s+out|ousts?|sees?\s+off|edges?|downs?|overcomes?|overcame|"
    r"outlasts?|dispatch(?:es|ed)?|stuns?|upsets?|topples?|halts?|ends?)\s*$", re.I)


def cn_hit(title: str, rules) -> tuple[dict, bool] | None:
    """标题里的中国球员，以及他/她是不是受访者。

    返回 `(球员, 是受访者吗)`；没有中国球员则 None。
    判据是名字**前面**那一小段：出现 against / beating / over 这类词，
    说明这人是被打败的一方。剩下的情况当作受访者——包括名字打头
    （`Zhizhen Zhang On-Court Interview | United Cup 2026`）和冒号后紧跟
    （`On-Court Interview: Zheng Qinwen says …`），这两种实测都是受访者。
    """
    full, sur, excl = rules

    def _is_subject(at: int) -> bool:
        before = title[max(0, at - 28):at]
        return not _BEATEN.search(before.rstrip())

    # 一、全名优先，能确定是哪一位
    for player, rx in full:
        m = rx.search(title)
        if m:
            return player, _is_subject(m.start())

    # 二、只写姓的情况。先排除同姓的非大陆球员——Michael Zheng（美国）、
    #     Lulu Sun（新西兰）、Ann Li（美国）都会被姓氏规则误收。
    if any(rx.search(title) for rx in excl):
        return None
    for sn, rx in sur:
        m = rx.search(title)
        if m:
            # 只有姓，不断言是哪一位，标成待确认交人工看。
            return ({"en": sn, "zh": f"{sn}（姓氏匹配·待确认）", "surname_only": True},
                    _is_subject(m.start()))
    return None


def pick(items: dict, rules, only_cn: bool = False, include_doubles: bool = False,
         include_team: bool = False, n_doubles=None, n_team=None) -> list[dict]:
    n_doubles = n_doubles if n_doubles is not None else [0]
    n_team = n_team if n_team is not None else [0]
    out = []
    for it in items.values():
        rnd = parse_round(it)
        hit = cn_hit(it.get("title", ""), rules)
        # 中国球员**是受访者**才算数；作为被打败的对手出现的不算。
        cn = hit[0] if (hit and hit[1]) else None
        beaten = hit[0] if (hit and not hit[1]) else None
        is_key = rnd in KEY_ROUNDS
        if not include_doubles and is_doubles(it):
            n_doubles[0] += 1
            continue
        if not include_team and not is_tour_event(it):
            n_team[0] += 1
            continue
        if only_cn and not cn:
            continue
        if not (cn or is_key):
            continue
        out.append({**it, "round_zh": rnd, "cn_player": cn, "cn_beaten": beaten})
    # 中国球员优先，其次决赛 > 半决赛 > 四分之一
    order = {"决赛": 0, "半决赛": 1, "四分之一决赛": 2}
    out.sort(key=lambda x: (bool(x.get("unofficial")), not x["cn_player"],
                            order.get(x["round_zh"], 9)))
    return out


def render_html(rows: list[dict]) -> str:
    # 官方 / 搬运分开列。搬运号补的是官方确实没有的那几处（亚洲赛季、
    # 七个大师赛），但来源不规范、可能删档，所以要让人一眼看出是哪一类。
    cn = [r for r in rows if r["cn_player"] and not r.get("unofficial")]
    key = [r for r in rows if not r["cn_player"] and not r.get("unofficial")]
    unof = [r for r in rows if r.get("unofficial")]
    parts = ["<div style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
             "font-size:15px;line-height:1.7;color:#1a1a1a'>"]

    def block(title: str, items: list[dict]) -> None:
        if not items:
            return
        parts.append(f"<h3 style='margin:18px 0 8px;font-size:16px'>{title}"
                     f"<span style='color:#8a8a8a;font-weight:400'>（{len(items)}）</span></h3>")
        for r in items:
            secs = r.get("duration_s") or 0
            dur = f"{secs // 60}:{secs % 60:02d}" if secs else "—"
            tag = r["cn_player"]["zh"] if r["cn_player"] else (r["round_zh"] or "")
            parts.append(
                "<div style='margin:0 0 12px;padding:10px 12px;background:#f6f8f7;"
                "border-radius:8px'>"
                f"<div style='font-size:12px;color:#5b7a68;margin-bottom:4px'>"
                f"{html.escape(tag)} · {dur} · {html.escape(r.get('source',''))}</div>"
                f"<a href='{html.escape(r['url'])}' "
                "style='color:#1a1a1a;text-decoration:none;font-weight:500'>"
                f"{html.escape(r.get('title',''))}</a></div>")

    block("🇨🇳 中国球员", cn)
    block("🎾 关键场次", key)
    if unof:
        block("📎 非官方搬运（亚洲赛季 / 大师赛补漏）", unof)
        parts.append(
            "<p style='font-size:12px;color:#8a8a8a;margin:4px 0 0'>"
            "上面这一区来自粉丝搬运号，不是赛事官方发布。收它们是因为亚洲赛季"
            "（北京 / 武汉等）和七个大师赛的场上采访官方确实不发切片。"
            "可能删档、元数据不规范，转发前请自行核对。</p>")
    if not rows:
        parts.append("<p style='color:#8a8a8a'>这一轮没有新的关键场次或中国球员场上采访。</p>")
    parts.append("</div>")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只打印，不推送也不记已发")
    ap.add_argument("--push", action="store_true", help="推到微信（需要 PUSHPLUS_TOKEN）")
    ap.add_argument("--only-cn", action="store_true", help="只要有中国球员的")
    ap.add_argument("--include-doubles", action="store_true",
                    help="连双打一起收（默认只要单打）")
    ap.add_argument("--include-team", action="store_true",
                    help="连拉沃尔杯/霍普曼杯/戴维斯杯等非巡回赛一起收"
                         "（默认只要 ATP/WTA 巡回赛与四大满贯）")
    ap.add_argument("--all", action="store_true", help="不去重，把库里所有符合条件的都列出来")
    ap.add_argument("--out", help="把 HTML 写到这个文件")
    ap.add_argument("--gaps", help="oncourt_gaps.py 生成的缺口片段，附在推送末尾")
    ap.add_argument("--seed", action="store_true",
                    help="把当前库里符合条件的全部标记为已推送，但不真推。"
                         "首次接上时用一次——否则第一条推送会是两百多条历史存量。")
    args = ap.parse_args()

    if not STORE.exists():
        print(f"{STORE.relative_to(ROOT)} 不存在，先跑 collect_oncourt_interviews.py",
              file=sys.stderr)
        return 2
    items = json.loads(STORE.read_text(encoding="utf-8"))["items"]
    _players, *rules = load_cn()
    n_doubles, n_team = [0], [0]
    rows = pick(items, rules, only_cn=args.only_cn,
                include_doubles=args.include_doubles,
                include_team=args.include_team,
                n_doubles=n_doubles, n_team=n_team)

    sent = set()
    if SENT.exists() and not args.all:
        sent = set(json.loads(SENT.read_text(encoding="utf-8")).get("ids", []))
    fresh = [r for r in rows if r["id"] not in sent]

    html_body = render_html(fresh)
    # 缺口附在最后：采集保证不了每场都有采访，把「赢了但没采访」的列出来，
    # 比让人以为「这天没比赛」强。见 tools/oncourt_gaps.py。
    if args.gaps and Path(args.gaps).exists():
        gap_html = Path(args.gaps).read_text(encoding="utf-8").strip()
        if gap_html:
            html_body += gap_html

    # **先落盘，再打印。** 和采集器同一个坑：下面的清单有几十行，
    # 下游一个 `| head -4` 就会 SIGPIPE 掉进程，`--out` 永远走不到，
    # 而报告看起来跑完了。查产物不查信号。
    if args.out:
        Path(args.out).write_text(html_body, encoding="utf-8")

    print(f"库内 {len(items)} 条 -> 符合条件 {len(rows)} 条 -> 未推送过 {len(fresh)} 条")
    if n_doubles[0]:
        print(f"  （已滤掉双打 {n_doubles[0]} 条，要的话加 --include-doubles）")
    if n_team[0]:
        print(f"  （已滤掉非巡回赛 {n_team[0]} 条：拉沃尔杯/霍普曼杯/戴维斯杯等，"
              "要的话加 --include-team）")
    n_cn = sum(1 for r in fresh if r["cn_player"])
    print(f"  其中中国球员 {n_cn} 条，关键场次 {len(fresh) - n_cn} 条\n")
    for r in fresh[:25]:
        secs = r.get("duration_s") or 0
        dur = f"{secs // 60}:{secs % 60:02d}" if secs else "—"
        tag = r["cn_player"]["zh"] if r["cn_player"] else (r["round_zh"] or "?")
        print(f"  [{tag}] {dur:>6}  {r.get('title','')[:66]}")
    if len(fresh) > 25:
        print(f"  …… 另有 {len(fresh) - 25} 条")

    if args.seed:
        # 只写已发状态，不推送。「后续」的意思是从现在起——历史存量
        # 一次性推两百多条，人只会把它当垃圾消息关掉。
        SENT.write_text(json.dumps(
            {"ids": sorted(sent | {r["id"] for r in rows})},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n已把 {len(rows)} 条现有条目标记为已推送（未真推）。"
              "往后只推新出现的。")
        return 0

    if args.out:
        print(f"\nHTML 已写到 {args.out}")
    if args.dry_run or not fresh:
        if not fresh:
            print("\n没有新条目，不推送。")
        return 0

    if args.push:
        token = os.environ.get("PUSHPLUS_TOKEN")
        if not token:
            print("缺 PUSHPLUS_TOKEN，没推。", file=sys.stderr)
            return 2
        sys.path.insert(0, str(ROOT / "src"))
        from tennislive.publish.pushplus import PushPlusError, push
        title = f"场上采访 {len(fresh)} 条"
        if n_cn:
            title = f"🇨🇳 中国球员 {n_cn} 条 · " + title
        try:
            push(token=token, title=title, content=html_body, template="html")
        except PushPlusError as exc:
            print(f"推送失败：{exc}", file=sys.stderr)
            return 2
        print(f"\n已推送 {len(fresh)} 条。")

    # 只有真推出去了才记已发——dry-run 记了会导致下次静默跳过。
    if args.push:
        SENT.write_text(json.dumps(
            {"ids": sorted(sent | {r["id"] for r in fresh})},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
