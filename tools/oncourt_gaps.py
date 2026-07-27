#!/usr/bin/env python3
"""比对「昨天谁赢了」和「收到了哪些场上采访」，把缺口列出来。

**采集器保证不了每场都有采访**，这是源头决定的：

1. 场上采访本身不是每场都有——只有中心球场、有分量的胜利才安排
2. 有采访也不一定发切片——亚洲赛季（北京/武汉等）官方一条不发
3. 采集只能收「已经发出来的」

所以与其让缺口静默存在，不如**把它列出来**。这个脚本拿仓库现成的赛果
（`build_digest`，ESPN / SofaScore 等源）和采集库对一遍，回答两个问题：

    昨天有哪些「该有采访」的场次？   —— 中国球员赢球，或决赛/半决赛/四分之一
    其中哪些实际收到了采访？         —— 没收到的明确列出来，别假装不存在

**按国籍认中国球员，不按名字。** `Player.country == "CHN"` 比从标题里
猜名字可靠得多——标题会写成 `Zheng`、`Zheng Qinwen`、`Qinwen Zheng` 三种，
还得跟 Michael Zheng（美国）、Lulu Sun（新西兰）消歧；国籍字段没这些麻烦。

用法：
    python tools/oncourt_gaps.py                 # 看昨天的缺口
    python tools/oncourt_gaps.py --date 2026-07-26
    python tools/oncourt_gaps.py --html out.html # 生成可推送的片段

退出码 0＝正常（有没有缺口都是 0）；2＝赛果抓不到，无法比对。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
STORE = ROOT / "data" / "oncourt_interviews.json"

KEY_ROUNDS_EN = re.compile(r"\bfinal\b|\bsemifinal\b|\bquarterfinal\b"
                           r"|\bsemi-final\b|\bquarter-final\b", re.I)


def shanghai_today() -> date:
    """产物按上海时间算——工作流里是 TZ=Asia/Shanghai，沙箱跑在 UTC，
    16:00 UTC 之后两者差一天。见 CLAUDE.md。"""
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date()


def is_singles(m) -> bool:
    return "singles" in (m.discipline or "").lower()


def winner_of(m):
    if m.winner is None:
        return None
    return (m.home if m.winner == 0 else m.away)


def surname(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return parts[-1] if parts else name


def event_words(tournament: str) -> list[str]:
    """赛事名里够特征的词，用来跟视频标题对。

    去掉 Open / Championships / Masters 这类通用词——`Estoril Open` 要靠
    `Estoril` 去对，靠 `Open` 会命中一整年的所有赛事。
    """
    stop = {"open", "championships", "masters", "cup", "international", "tennis",
            "atp", "wta", "the", "of", "presented", "by", "ladies", "mens",
            "women's", "men's", "tour", "1000", "500", "250"}
    return [w for w in re.findall(r"[A-Za-zÀ-ɏ']{3,}", tournament)
            if w.lower() not in stop]


def find_interview(items: dict, player: str, tournament: str) -> dict | None:
    """库里有没有这位球员在这项赛事的场上采访。

    对法是**姓 + 赛事特征词**都要出现。只对姓会跨赛事误配，
    只对赛事会把同场的对手也算上。

    **标题和 URL 一起找**，别只看标题——踩过：tennistv.com 那条
    `Van Assche discusses successful 2026!` 标题里没有赛事名，赛事在
    URL slug 里（`estoril-2026-final-luca-van-assche-interview`）。
    只对标题会把它报成「缺口」，而它明明收到了。
    """
    sn = surname(player).lower()
    evs = [w.lower() for w in event_words(tournament)]
    for it in items.values():
        hay = (it.get("title", "") + " " + it.get("url", "")).lower()
        if sn not in hay:
            continue
        if evs and not any(e in hay for e in evs):
            continue
        return it
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="按哪天算（上海时间，默认今天）")
    ap.add_argument("--html", help="把缺口片段写到这个文件")
    args = ap.parse_args()

    day = date.fromisoformat(args.date) if args.date else shanghai_today()

    from tennislive.digest import build_digest
    try:
        digest = build_digest(day)
    except Exception as exc:  # noqa: BLE001 - 抓不到就明说，别静默返回空
        print(f"赛果抓取失败，无法比对：{exc}", file=sys.stderr)
        return 2
    if not digest.results:
        print(f"{day} 没有已完赛记录（数据源 {digest.source or '未知'}）——"
              "可能是休赛期，也可能是抓取失败。**这两种情况看起来一样**，"
              "别当成『没有缺口』。", file=sys.stderr)
        return 0

    items = json.loads(STORE.read_text(encoding="utf-8"))["items"] if STORE.exists() else {}

    have, missing = [], []
    for m in digest.results:
        if not is_singles(m):
            continue
        w = winner_of(m)
        if not w:
            continue
        win = w[0]
        is_cn = (win.country or "").upper() == "CHN"
        is_key = bool(KEY_ROUNDS_EN.search(m.round_name or ""))
        if not (is_cn or is_key):
            continue
        row = {"player": win.name, "cn": is_cn, "tournament": m.tournament.name,
               "round": m.round_name, "tour": m.tour.value}
        got = find_interview(items, win.name, m.tournament.name)
        (have if got else missing).append({**row, "url": got["url"] if got else None,
                                           "title": got["title"] if got else None})

    print(f"{day}（上海时间）已完赛 {len(digest.results)} 场，数据源 {digest.source}")
    print(f"其中「该有场上采访」的 {len(have) + len(missing)} 场："
          f"收到 {len(have)}，**缺 {len(missing)}**\n")

    if have:
        print("已收到:")
        for r in have:
            tag = "🇨🇳" if r["cn"] else "  "
            print(f"  {tag} {r['player']:<22} {r['tournament'][:24]:<24} {r['round']}")
    if missing:
        print("\n该有但没收到（源头就没发，不是采集漏了）:")
        for r in missing:
            tag = "🇨🇳" if r["cn"] else "  "
            print(f"  {tag} {r['player']:<22} {r['tournament'][:24]:<24} {r['round']}")

    if args.html:
        parts = []
        if missing:
            parts.append("<h3 style='margin:18px 0 8px;font-size:16px'>⚠️ 赢了但没有场上采访"
                         f"<span style='color:#8a8a8a;font-weight:400'>（{len(missing)}）</span></h3>")
            for r in missing:
                tag = "🇨🇳 " if r["cn"] else ""
                parts.append(
                    "<div style='margin:0 0 8px;padding:8px 12px;background:#faf7f2;"
                    "border-left:3px solid #d8c9a8;border-radius:4px;font-size:14px'>"
                    f"{tag}{html.escape(r['player'])} · {html.escape(r['tournament'])}"
                    f" · {html.escape(r['round'] or '')}</div>")
            parts.append("<p style='font-size:12px;color:#8a8a8a;margin:4px 0 0'>"
                         "这些场次赢了球但没找到场上采访视频。多数是源头没发——"
                         "场上采访本就不是每场都有，亚洲赛季的赛事更是一条不发切片。</p>")
        Path(args.html).write_text("".join(parts), encoding="utf-8")
        print(f"\nHTML 已写到 {args.html}（{len(missing)} 条缺口）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
