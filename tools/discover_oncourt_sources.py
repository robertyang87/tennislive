#!/usr/bin/env python3
"""自动发现还没收录的场上采访来源，别每次都靠人手搜。

注册表里最有价值的几个源全是**手动搜出来的**：Eurosport（78 条）、
TNT Sports（44）、United Cup（84）、Hopman Cup（118）、Stefan P.（6 条
全补缺口）。它们不在任何"官方频道清单"上，是换了查询词才撞见的。

**新的还会不断冒出来**——搬运号尤其如此，开了又关。所以把发现这件事
本身自动化：每周搜一轮，把「在发场上采访、但注册表里没有」的频道列出来，
人扫一眼决定收不收。

方法是**搜索反推频道**，不是猜句柄。猜句柄我错过四个（蒙特卡洛、迈阿密、
加拿大、Queen's）；一轮搜索找出了四个根本没想到的源。

查询词分三组，覆盖不同的漏法：

    通用     `on-court interview tennis 2026`
    按球员   中国球员 + 头部球员，能捞到专号（Team Swiatek、ElenaRybakinaHD）
    按缺口   官方不发的那些赛事（北京/武汉/迈阿密/辛辛那提…）

用法：
    python tools/discover_oncourt_sources.py              # 列出候选
    python tools/discover_oncourt_sources.py --min 3      # 只看命中 3 条以上的
    python tools/discover_oncourt_sources.py --json out.json

退出码永远 0——发现不到新源是正常状态，不是错误。
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "oncourt_sources.json"
CN = ROOT / "data" / "cn_players.json"

# 只认真正的场上采访写法，别用宽口径——宽了会把一堆集锦频道拉进来。
HIT = re.compile(r"on.?court\s+interview|post.?match\s+interview", re.I)

# 官方不发场上采访的赛事，搜索时重点照顾
GAP_EVENTS = ["Beijing China Open", "Wuhan Open", "Miami Open", "Indian Wells",
              "Cincinnati Open", "Shanghai Masters", "Monte Carlo Masters",
              "Canada National Bank Open", "ATP Finals Turin", "WTA Finals"]


def _norm(name: str) -> str:
    """频道名归一化，用于跟注册表比对。

    去掉赛事名里常见的后缀词——注册表写「US Open」，YouTube 频道名叫
    「US Open Tennis Championships」，不归一化就会把已收录的源当成新发现，
    每周重复报一遍。
    """
    n = name.lower()
    for w in ("tennis championships", "championships", "tennis", "official",
              "open", "masters", "cup", "the"):
        n = n.replace(w, " ")
    return re.sub(r"[^a-z0-9]+", "", n)


def registry_channels() -> tuple[set[str], set[str]]:
    cfg = json.loads(SOURCES.read_text(encoding="utf-8"))
    urls, names = set(), set()
    for s in cfg["sources"]:
        urls.add(s["url"].rstrip("/").removesuffix("/videos"))
        # 注册表里同一频道可能写成 @句柄 或 /channel/ID 两种形式，
        # URL 比对认不出是同一个，所以名字也要留一份做兜底。
        n = _norm(s["name"])
        if n:
            names.add(n)
    return urls, names


def already_known(ch: str, u: str, known_urls: set[str], known_names: set[str]) -> bool:
    if u.rstrip("/").removesuffix("/videos") in known_urls:
        return True
    n = _norm(ch)
    if not n:
        return False
    for k in known_names:
        if n == k:
            return True
        # 子串匹配只在两边都够长时才用。踩过：「Tennis Channel」归一化后
        # 只剩 `channel`（7 字符），任何名字里带 channel 的频道都会被它
        # 子串命中，`Some Random Fan Channel` 就这么被误判成已收录。
        if len(n) >= 8 and len(k) >= 8 and (n in k or k in n):
            return True
    return False


def queries() -> list[str]:
    qs = ["on-court interview tennis 2026", "post-match interview ATP 2026",
          "post-match interview WTA 2026", "on court interview after win tennis"]
    try:
        cn = json.loads(CN.read_text(encoding="utf-8"))["players"]
        qs += [f"{p['en']} on court interview" for p in cn[:6]]
    except (OSError, ValueError, KeyError):
        pass
    qs += [f"{e} on-court interview" for e in GAP_EVENTS]
    return qs


def sweep(qs: list[str], per: int) -> tuple[collections.Counter, dict, dict]:
    hits: collections.Counter = collections.Counter()
    url: dict[str, str] = {}
    sample: dict[str, str] = {}
    for q in qs:
        try:
            proc = subprocess.run(
                ["yt-dlp", "--flat-playlist",
                 "--print", "%(channel)s ||| %(channel_url)s ||| %(title)s",
                 f"ytsearch{per}:{q}"],
                capture_output=True, text=True, timeout=160)
        except subprocess.TimeoutExpired:
            print(f"  （超时跳过：{q[:40]}）", file=sys.stderr)
            continue
        for line in proc.stdout.strip().split("\n"):
            parts = line.split(" ||| ")
            if len(parts) < 3 or not HIT.search(parts[2]):
                continue
            ch, u, title = parts[0], parts[1].strip(), parts[2]
            hits[ch] += 1
            url.setdefault(ch, u)
            sample.setdefault(ch, title)
    return hits, url, sample


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min", type=int, default=1, help="至少命中几条才列出（默认 1）")
    ap.add_argument("--per", type=int, default=10, help="每个查询取几条（默认 10）")
    ap.add_argument("--json", help="把候选写成 JSON")
    args = ap.parse_args()

    known_urls, known_names = registry_channels()
    qs = queries()
    print(f"用 {len(qs)} 组查询词搜索…（注册表已有 {len(known_names)} 个源）\n")
    hits, url, sample = sweep(qs, args.per)

    new = []
    for ch, n in hits.most_common():
        u = url.get(ch, "")
        if n < args.min:
            continue
        if already_known(ch, u, known_urls, known_names):
            continue
        new.append({"channel": ch, "url": u, "hits": n, "sample": sample.get(ch, "")})

    known_hit = sum(n for ch, n in hits.items()
                    if already_known(ch, url.get(ch, ""), known_urls, known_names))
    print(f"命中 {sum(hits.values())} 条，其中已收录源贡献 {known_hit} 条。")
    if not new:
        print("\n没有发现新源——这是正常状态，不是出错。")
        return 0

    print(f"\n**未收录的候选 {len(new)} 个**（按命中数排）：\n")
    for c in new:
        print(f"  {c['hits']:>3} 条  {c['channel']}")
        print(f"          {c['url']}")
        print(f"          例：{c['sample'][:76]}")
    print("\n下一步：挑有量的，用 --only 深扫确认，再加进 data/oncourt_sources.json。"
          "\n非赛事官方的记得打 unofficial 标记。")

    if args.json:
        Path(args.json).write_text(
            json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n候选已写到 {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
