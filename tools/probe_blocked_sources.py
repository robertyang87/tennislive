#!/usr/bin/env python3
"""在 Actions 的出口网络上探那些**沙箱够不到**的源。

沙箱这台机器被挡的几处，各有各的挡法，长得却都像「没有」：

- `atptour.com` —— 全站 403，带浏览器 UA 也一样
- `live-tennis.eu` —— 403，连控制组（阿尔卡拉斯）都搜不到，是被挡不是没有
- `mextenisphoto.pixieset.com` —— 403 + 「Just a moment…」，Cloudflare 人机校验

runner 的出口 IP 不一样，这几处可能通。**通不通本身就是结论**，所以
每一条都要把状态码、Content-Type、字节数打出来——只在成功时出声的检查，
没法证明它真的看过。

    python tools/probe_blocked_sources.py --want "Coleman Wong" --want Brooksby
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

TARGETS = [
    ("ATP 洛斯卡沃斯战报（周四）",
     "https://www.atptour.com/en/news/los-cabos-2026-thursday-report"),
    ("ATP 洛斯卡沃斯赛果页",
     "https://www.atptour.com/en/scores/archive/los-cabos/8996/2026/results"),
    ("ATP 即时排名（live-tennis.eu）",
     "https://live-tennis.eu/en/atp-live-ranking"),
    ("赛事官方图库（pixieset）",
     "https://mextenisphoto.pixieset.com/mifeltenisopen2026/"),
    ("赛事官网八强战报列表",
     "https://www.loscabostennisopen.com/wp-json/wp/v2/posts"
     "?per_page=5&orderby=date&order=desc"),
]


def fetch(url: str, timeout: int = 30) -> tuple[str, str, bytes]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return str(fh.status), fh.headers.get("Content-Type", "?"), fh.read()
    except urllib.error.HTTPError as exc:
        return str(exc.code), exc.headers.get("Content-Type", "?") if exc.headers else "?", b""
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}", "?", b""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--want", action="append", default=[],
                    help="要在正文里找的词，找到就把上下文打出来")
    args = ap.parse_args()
    wants = args.want or ["Coleman Wong", "Brooksby"]

    for label, url in TARGETS:
        status, ctype, body = fetch(url)
        print(f"\n=== {label}")
        print(f"    {url}")
        print(f"    {status}  {ctype}  {len(body)} 字节")
        if not body:
            continue
        text = body.decode("utf-8", "ignore")
        # Cloudflare 的挑战页会返回 200，光看状态码分不出来
        if "Just a moment" in text or "cf-browser-verification" in text:
            print("    ⚠️ Cloudflare 人机校验页——状态码骗人，这不是内容")
            continue
        flat = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", text))
        for want in wants:
            hits = list(re.finditer(re.escape(want), flat, re.I))
            print(f"    「{want}」命中 {len(hits)} 次")
            for m in hits[:3]:
                s = max(0, m.start() - 220)
                print(f"      …{flat[s:m.end() + 220]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
