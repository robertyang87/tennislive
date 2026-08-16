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


def pick_highlight(results: list[tuple[str, str]], home: str, away: str,
                   event: str = "", year: int | None = None) -> str | None:
    """从搜索结果里挑一条像本场集锦的。判据**宁可窄**：标题要带集锦关键词、
    带两位球员的姓，**而且是这一站这一年的**——都满足才收（「没搜到」好过「拿错」）。

    ⚠️ **`event` / `year` 这两道是 2026-08-16 补的，补之前它真的拿错过一条。**
    实跑「商竣程 vs 索内戈 / Cincinnati / 2026」，它探回来的是

        Bublik Headlines; Sonego vs Shang; Khachanov & More | **Hong Kong 2026 Day 4** Highlights

    ——两位球员的姓都在、`Highlights` 也在，于是过关；而它是**另一站、另一个
    月份的当日综述片**，根本不是这场球。⚠️ **后果不是探不到，是探到一条错的**：
    编排器会拿这个 URL 去 dispatch probe，整条片子照着一场不相干的比赛渲出来，
    而记分条上写的是 Hong Kong——**流水线上没有任何一步会拦它**，只有人打开看
    才发现。

    两个不给的时候退回老行为（只查姓 + 关键词），因为**这个函数的老调用方
    不知道赛事**；生产路径 `find_highlight()` 一律把两个都传进来。
    """
    hn = (home or "").strip().split()[-1].lower()
    an = (away or "").strip().split()[-1].lower()
    # 赛事名可能是多词的（`Hong Kong`），逐词都要在标题里——`short_event` 已经
    # 把赞助商前缀剥掉了，剩下的就是地名。
    ev = [w for w in short_event(event or "").lower().split() if w]
    for title, url in results:
        t = title.lower()
        if not (HIGHLIGHT_HINTS.search(t) and hn in t and an in t):
            continue
        if ev and not all(w in t for w in ev):
            continue
        if year is not None and str(year) not in t:
            continue
        return url
    return None


def tennistv_fallback(home: str, away: str, *, pages: int = 3) -> str | None:
    """YouTube 没搜到时，去 Tennis TV 的**免费短集锦**里找这一场。

    ⚠️ 这条只对 **ATP** 有货（Tennis TV 是 ATP 的平台），WTA 场次必然返回 None
    ——那不是故障，是这条源本来的覆盖范围。

    判据和 `pick_highlight` 一样**宁可窄**：slug 里要同时出现两位球员的姓。
    Tennis TV 的 slug 是 `<城市>-<年>-<轮次>-<甲>-<乙>-short-highlights`，
    姓的顺序按 ATP 的排法，和我们的 home/away 不一定一致，所以只查「都在」，
    不查先后。

    ⚠️ **取的是最近 N 页，不是全库**：这个函数服务的是「一场球刚打完」那一刻，
    而全库 58000 条翻不动。默认 3×100 条，够盖住好几天。
    """
    hn = (home or "").strip().split()[-1].lower()
    an = (away or "").strip().split()[-1].lower()
    if not hn or not an:
        return None
    try:
        from tennistv_catalog import (  # noqa: PLC0415
            TAG_SHORT_HIGHLIGHTS, is_real_short_highlight, rows, video_url,
        )
        items = rows(tag_ids=str(TAG_SHORT_HIGHLIGHTS), pages=pages)
    except (Exception, SystemExit):
        # 探测这一步「没探到」是正常态，**不许把整条编排带崩**——和上面
        # `search()` 吞掉超时是同一个理由。
        #
        # ⚠️ **`SystemExit` 要单独列出来**：它继承的是 `BaseException` 不是
        # `Exception`，光写 `except Exception` 接不住。而 `tennistv_catalog._get`
        # 在接口回 HTML（参数名写错会 400）时抛的正是 `SystemExit`——那是给
        # 命令行准备的「说人话再退出」，被当成库用的时候就成了一颗炸弹。
        # 判据抓到过这个洞。
        return None
    for item in items:
        if not is_real_short_highlight(item):
            continue
        slug = str(item.get("titleUrlSegment") or "").lower()
        if hn in slug and an in slug:
            return video_url(item)
    return None


def find_highlight(home: str, away: str, event: str, year: int,
                   *, per: int = 6) -> tuple[str | None, str]:
    """按账号所有者定的顺序找这一场的源片，返回 `(url, 走的哪条路)`。

        主路   YouTube（ATP Tour / Tennis TV / 赛事自己的官方频道都在搜索里）
        备选   Tennis TV 的免费短集锦
        都没有 → (None, "")

    ⚠️ **优先级链只有这一处实现。** 编排器和命令行都走它——写两处必分叉，
    而分叉的样子是「手动跑说探到了，自动班次说没探到」。
    """
    url = pick_highlight(search(query_for(home, away, event, year), per=per),
                         home, away, event, year)
    if url:
        return url, "youtube"
    url = tennistv_fallback(home, away)
    return (url, "tennistv-short") if url else (None, "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--event", required=True, help="赛事名，如 Washington")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--per", type=int, default=6)
    ap.add_argument("--no-fallback", action="store_true",
                    help="只探 YouTube，不查 Tennis TV 短集锦")
    args = ap.parse_args()

    q = query_for(args.home, args.away, args.event, args.year)
    print(f"搜索词：{q}")
    if args.no_fallback:
        url, via = pick_highlight(search(q, per=args.per), args.home, args.away), "youtube"
    else:
        url, via = find_highlight(args.home, args.away, args.event, args.year,
                                  per=args.per)
    if url:
        # **走了哪条路要说出来**，和「图片通道 pushplus / jsdelivr」同一条：
        # 一个月后有人问「这条片子的源是哪来的」，答案在当天的日志里。
        print(f"探到（{via}）：{url}")
        if via == "tennistv-short":
            print("  ⚠️ 这是 Tennis TV 的**免费短集锦**（定长 2 分半左右，"
                  "是被剪短的那一版）——YouTube 上没搜到这一场才走的它。")
        return 0
    print("还没探到：YouTube 没有一条同时带集锦关键词和两位球员姓，"
          "Tennis TV 最近几页的免费短集锦里也没有这一场。")
    print("集锦可能还没传，或标题写法对不上——晚几分钟再探。"
          "⚠️ WTA 场次没有 Tennis TV 这条备选，只有 YouTube 一条路。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
