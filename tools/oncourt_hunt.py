#!/usr/bin/env python3
"""拿缺口当种子去反查：谁赢了球却没采访，就用「球员 + 赛事」直接搜。

这条路比通用查询强得多，**而且能找到通用查询根本找不到的源**。

实例：2026-07-27 的缺口里有 `Lilli Tagger · Livesport Prague Open · Final`。
通用查询 `on-court interview tennis 2026` 搜不到她，但拿
`Lilli Tagger Prague 2026 interview` 一搜就撞见了 `Tennis Interviews`
这个频道——234 条，覆盖马德里 31、迈阿密 17、印第安维尔斯 9，全是官方缺口。

**为什么通用查询找不到它**：它的标题写作 `Lilli Tagger Champion Prague 2026`，
不含 `on-court` / `post-match` / `interview` 任何一个词。按标题搜、按标题筛
都碰不到它，只有从「这个人这场球」出发才能撞上。

所以流程是：

    赛果（build_digest）→ 该有采访的场次 → 库里没有的 → 按球员+赛事搜
        → 找到视频 → 顺带看它出自哪个频道 → 没收录的报出来

第二步的副产品比第一步更值钱：**新频道**。一条缺口只补一条视频，
但一个新频道能补几百条。

用法：
    python tools/oncourt_hunt.py                  # 查今天的缺口
    python tools/oncourt_hunt.py --date 2026-07-26
    python tools/oncourt_hunt.py --days 7         # 往前查一周

退出码永远 0——找不到是常态。
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tools.oncourt_gaps import (  # noqa: E402
    KEY_ROUNDS_EN, find_interview, is_singles, shanghai_today, winner_of,
)
from tools.discover_oncourt_sources import (  # noqa: E402
    already_known, registry_channels,
)

STORE = ROOT / "data" / "oncourt_interviews.json"

# 搜出来的东西得跟采访沾边才算。**别用严格的 on-court 模式**——
# 正是因为有的频道标题不含那些词，才要靠这一步找它们。
LOOSE = re.compile(r"interview|on.?court|post.?match|reacts?|champion|final|"
                   r"semi|quarter|r\d\d|round", re.I)


def short_event(name: str) -> str:
    """赛事名里最有搜索价值的那部分。

    `Livesport Prague Open` 要搜 `Prague`——带上赞助商前缀反而搜不到，
    因为视频标题里写的是简称。
    """
    drop = re.compile(r"\b(livesport|msc|mubadala|citi|rolex|bnp\s+paribas|mutua|"
                      r"nitto|hsbc|internazionali|bnl|d'italia|open|ladies|"
                      r"championships|international|presented\s+by|tennis)\b", re.I)
    return re.sub(r"\s+", " ", drop.sub(" ", name)).strip() or name


def hunt(player: str, tournament: str, year: int, per: int = 6) -> list[tuple[str, str, str]]:
    q = f"{player} {short_event(tournament)} {year} interview"
    try:
        proc = subprocess.run(
            ["yt-dlp", "--flat-playlist",
             "--print", "%(channel)s ||| %(channel_url)s ||| %(title)s",
             f"ytsearch{per}:{q}"],
            capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return []
    out = []
    sn = player.split()[-1].lower()
    for line in proc.stdout.strip().split("\n"):
        parts = line.split(" ||| ")
        if len(parts) < 3:
            continue
        ch, u, title = parts[0], parts[1].strip(), parts[2]
        # 姓要出现在标题里，否则搜到的是同赛事别人的视频
        if sn not in title.lower() or not LOOSE.search(title):
            continue
        out.append((ch, u, title))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="起始日（上海时间，默认今天）")
    ap.add_argument("--days", type=int, default=1, help="往前查几天（默认 1）")
    ap.add_argument("--per", type=int, default=6, help="每条缺口取几个搜索结果")
    args = ap.parse_args()

    start = date.fromisoformat(args.date) if args.date else shanghai_today()
    items = json.loads(STORE.read_text(encoding="utf-8"))["items"] if STORE.exists() else {}
    known_urls, known_names = registry_channels()

    from tennislive.digest import build_digest

    gaps = []
    for i in range(args.days):
        day = start - timedelta(days=i)
        try:
            digest = build_digest(day)
        except Exception as exc:  # noqa: BLE001
            print(f"{day} 赛果抓取失败：{exc}", file=sys.stderr)
            continue
        for m in digest.results:
            if not is_singles(m):
                continue
            w = winner_of(m)
            if not w:
                continue
            win = w[0]
            if not ((win.country or "").upper() == "CHN"
                    or KEY_ROUNDS_EN.search(m.round_name or "")):
                continue
            if find_interview(items, win.name, m.tournament.name):
                continue
            gaps.append((win.name, m.tournament.name, day.year,
                         (win.country or "").upper() == "CHN"))

    # 同一球员同一赛事只搜一次
    gaps = list(dict.fromkeys(gaps))
    if not gaps:
        print("没有缺口可查——要么都收到了，要么赛果抓不到。")
        return 0

    print(f"{len(gaps)} 条缺口，逐条反查…\n")
    found_ch: collections.Counter = collections.Counter()
    ch_url, ch_sample = {}, {}
    hits_total = 0
    for player, ev, year, is_cn in gaps:
        rows = hunt(player, ev, year, args.per)
        hits_total += len(rows)
        tag = "🇨🇳 " if is_cn else ""
        print(f"  {tag}{player} / {short_event(ev)} -> {len(rows)} 条")
        for ch, u, title in rows[:3]:
            mark = " " if already_known(ch, u, known_urls, known_names) else "★"
            print(f"     {mark} [{ch}] {title[:64]}")
            if mark == "★":
                found_ch[ch] += 1
                ch_url.setdefault(ch, u)
                ch_sample.setdefault(ch, title)

    print(f"\n共搜到 {hits_total} 条相关视频。")
    if found_ch:
        print(f"\n**未收录的频道 {len(found_ch)} 个** —— 这才是这一步真正的收获，"
              "一条缺口只补一条视频，一个新频道能补几百条：\n")
        for ch, n in found_ch.most_common():
            print(f"  {n:>2} 次  {ch}")
            print(f"        {ch_url.get(ch, '')}")
            print(f"        例：{ch_sample.get(ch, '')[:70]}")
        print("\n注意：这类频道的标题**可能不含 on-court/interview 字样**"
              "（`Tennis Interviews` 就写作『球员 轮次 赛事 年份』），"
              "收录时要打 assume_oncourt，否则标题正则一条都收不到。")
    else:
        print("没有发现未收录的频道。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
