#!/usr/bin/env python3
"""T0 探测：一场比赛打完，自动探测官方集锦视频的 YouTube URL。

这是「半小时出片协议」最前端一直缺的那一步——之前集锦上线后，账号所有者要
自己去 YouTube 搜 URL，再填进 match-reel 的 probe。这个工具把「搜」这一步
机械化，编进编排器之后，赛果一出来就能自动拿 URL → dispatch probe。

⚠️ 探测 = 拿 YouTube 搜索当信号源，**不是官方来源**：它只能回答「搜到一条像
集锦的结果」或「还没搜到」。搜到不代表就是官方集锦（可能是自媒体搬运），
「没搜到」也不代表不存在（可能是标题没带球员姓、或晚几分钟才传）。所以
产出的 URL 要交给人/下游 probe 再核一眼，别当成「官方集锦已上线」的铁证。

用法：
    python tools/detect_highlights.py --home Eala --away Pegula --event Washington --year 2026
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oncourt_hunt import short_event  # noqa: E402

# 集锦标题里的关键词。宁可漏（"没搜到"）也不要错（拿一条无关视频当集锦）。
HIGHLIGHT_HINTS = re.compile(
    r"highlight|集锦|extended|full match|全场|highlights", re.I)


def query_for(home: str, away: str, event: str, year: int) -> str:
    """拼搜索词：两个球员姓 + 赛事简称 + 年份 + highlights。

    用姓不写全名——YouTube 标题里通常只有姓（`Eala vs Pegula`），写全名反而
    命中率低。赛事走 `short_event`（剥赞助商前缀）。
    """
    surname = lambda n: (n or "").strip().split()[-1]  # noqa: E731
    return f"{surname(home)} {surname(away)} {short_event(event)} {year} highlights"


def search(query: str, per: int = 6, timeout: int = 120) -> list[tuple[str, str]]:
    """yt-dlp 的 ytsearch 拿 (title, url) 列表。空结果/超时都返回 []——「没搜到」
    是正常态（集锦还没传），不该把整条探测带崩。"""
    try:
        proc = subprocess.run(
            ["yt-dlp", "--flat-playlist",
             "--print", "%(title)s ||| %(webpage_url)s",
             f"ytsearch{max(1, min(per, 20))}:{query}"],
            capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if proc.returncode != 0:
        return []
    out = []
    for line in proc.stdout.strip().split("\n"):
        if " ||| " not in line:
            continue
        title, url = line.split(" ||| ", 1)
        out.append((title.strip(), url.strip()))
    return out


def pick_highlight(results: list[tuple[str, str]], home: str, away: str) -> str | None:
    """从搜索结果里挑一条像本场集锦的。判据**宁可窄**：标题要带集锦关键词、
    且带两位球员的姓——两条都不满足就 None（「没搜到」好过「拿错」）。"""
    hn = (home or "").strip().split()[-1].lower()
    an = (away or "").strip().split()[-1].lower()
    for title, url in results:
        t = title.lower()
        if HIGHLIGHT_HINTS.search(t) and hn in t and an in t:
            return url
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--event", required=True, help="赛事名，如 Washington")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--per", type=int, default=6)
    args = ap.parse_args()

    q = query_for(args.home, args.away, args.event, args.year)
    print(f"搜索词：{q}")
    results = search(q, per=args.per)
    url = pick_highlight(results, args.home, args.away)
    if url:
        print(f"探到：{url}")
        print(f"  候选 {len(results)} 条，第一条对题的是：{url}")
        return 0
    print(f"还没探到（搜了 {len(results)} 条，没一条同时带集锦关键词和两位球员姓）")
    print("集锦可能还没传，或标题写法对不上——晚几分钟再探。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
