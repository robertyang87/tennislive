#!/usr/bin/env python3
"""从 data/oncourt_interviews.json 里筛出**值得看的那几条**，并推到微信。

采集器（`collect_oncourt_interviews.py`）是全量的——八百多条，什么轮次都有。
这个脚本是它的下游，只做一件事：**按两个条件筛，然后推送**。

    条件一：关键场次 —— 决赛 / 半决赛 / 四分之一决赛
    条件二：有中国球员 —— 名单在 data/cn_players.json

两个条件是**或**的关系：郑钦文的第二轮要，辛纳的决赛也要。

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


def load_cn() -> tuple[list[dict], list[re.Pattern]]:
    with CN.open(encoding="utf-8") as fh:
        cfg = json.load(fh)
    pats = []
    for p in cfg["players"]:
        parts = p["en"].split()
        if len(parts) < 2:
            continue
        given, family = " ".join(parts[:-1]), parts[-1]
        # 两种顺序都认；\b 两端保证不会把 Sun 匹配进 Sunday 之类
        pats.append((p, re.compile(
            rf"\b{re.escape(given)}\s+{re.escape(family)}\b"
            rf"|\b{re.escape(family)}\s+{re.escape(given)}\b", re.I)))
    return cfg["players"], pats


# 名字前面出现这些词，说明这人是**被打败的对手**，不是受访者。
# 起因是一条真实误收：
#   `On-Court Interview: Jasmine Paolini feels 'elated' with her stunning
#    win against Sijia Wei 💪`
# 韦思佳确实在标题里，但这是 Paolini 赢球后的采访，正好相反。
# 要的是「中国球员赢球后」，所以这类必须剔掉。
_BEATEN = re.compile(
    r"\b(?:against|beating|beat|defeat(?:s|ing|ed)?|over|past|vs\.?|versus|"
    r"knocks?\s+out|ousts?|sees?\s+off|edges?|downs?)\s*$", re.I)


def cn_hit(title: str, pats) -> tuple[dict, bool] | None:
    """标题里的中国球员，以及他/她是不是受访者。

    返回 `(球员, 是受访者吗)`；没有中国球员则 None。
    判据是名字**前面**那一小段：出现 against / beating / over 这类词，
    说明这人是被打败的一方。剩下的情况当作受访者——包括名字打头
    （`Zhizhen Zhang On-Court Interview | United Cup 2026`）和冒号后紧跟
    （`On-Court Interview: Zheng Qinwen says …`），这两种实测都是受访者。
    """
    for player, rx in pats:
        m = rx.search(title)
        if not m:
            continue
        before = title[max(0, m.start() - 28):m.start()]
        return player, not _BEATEN.search(before.rstrip())
    return None


def pick(items: dict, pats, only_cn: bool = False) -> list[dict]:
    out = []
    for it in items.values():
        rnd = parse_round(it)
        hit = cn_hit(it.get("title", ""), pats)
        # 中国球员**是受访者**才算数；作为被打败的对手出现的不算。
        cn = hit[0] if (hit and hit[1]) else None
        beaten = hit[0] if (hit and not hit[1]) else None
        is_key = rnd in KEY_ROUNDS
        if only_cn and not cn:
            continue
        if not (cn or is_key):
            continue
        out.append({**it, "round_zh": rnd, "cn_player": cn, "cn_beaten": beaten})
    # 中国球员优先，其次决赛 > 半决赛 > 四分之一
    order = {"决赛": 0, "半决赛": 1, "四分之一决赛": 2}
    out.sort(key=lambda x: (not x["cn_player"], order.get(x["round_zh"], 9)))
    return out


def render_html(rows: list[dict]) -> str:
    cn = [r for r in rows if r["cn_player"]]
    key = [r for r in rows if not r["cn_player"]]
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
    ap.add_argument("--all", action="store_true", help="不去重，把库里所有符合条件的都列出来")
    ap.add_argument("--out", help="把 HTML 写到这个文件")
    ap.add_argument("--seed", action="store_true",
                    help="把当前库里符合条件的全部标记为已推送，但不真推。"
                         "首次接上时用一次——否则第一条推送会是两百多条历史存量。")
    args = ap.parse_args()

    if not STORE.exists():
        print(f"{STORE.relative_to(ROOT)} 不存在，先跑 collect_oncourt_interviews.py",
              file=sys.stderr)
        return 2
    items = json.loads(STORE.read_text(encoding="utf-8"))["items"]
    _players, pats = load_cn()
    rows = pick(items, pats, only_cn=args.only_cn)

    sent = set()
    if SENT.exists() and not args.all:
        sent = set(json.loads(SENT.read_text(encoding="utf-8")).get("ids", []))
    fresh = [r for r in rows if r["id"] not in sent]

    print(f"库内 {len(items)} 条 -> 符合条件 {len(rows)} 条 -> 未推送过 {len(fresh)} 条")
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

    html_body = render_html(fresh)
    if args.out:
        Path(args.out).write_text(html_body, encoding="utf-8")
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
