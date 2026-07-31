#!/usr/bin/env python3
"""哪几条场上采访**有热度**——按播放量排，用来挑选题。

库里四千多条，但「能用」和「值得做」是两回事。这个工具回答后者。

两个实现细节是踩出来的：

- **播放量从 `--flat-playlist` 拿，不要逐条取元数据。** 逐条 `yt-dlp` 请求
  几十次之后 YouTube 就开始要机器人验证（`Sign in to confirm you're not a
  bot`），而列表接口一次给几百条、带 `view_count`，稳得多。
- **`@wta` 的条目要走时长判据**，不能只看标题。它的场上采访接在逐场集锦的
  尾巴上，标题里没有 interview 字样——见 `_tail_interview`。

用法：
    python tools/oncourt_hot.py                # 各官方源，取前 20
    python tools/oncourt_hot.py --recent 70    # 只看每个源最新的 70 条
    python tools/oncourt_hot.py --top 40
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.collect_oncourt_interviews import (  # noqa: E402
    _tail_interview,
    classify,
    compile_rules,
    load_sources,
)

# 官方源和各自的取样深度。深度按出片密度定：@wta 一天十几条，大满贯只在赛期发。
CHANNELS = [("@wta", 400), ("@Wimbledon", 200), ("@australianopen", 150),
            ("@rolandgarros", 150), ("@usopen", 150), ("@EurosportTennis", 200)]


def pull(channel: str, depth: int) -> list[tuple[int, int, str, str]]:
    try:
        proc = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--playlist-end", str(depth), "--no-warnings",
             "--print", "%(view_count)s|%(duration)s|%(id)s|%(title)s",
             f"https://www.youtube.com/{channel}/videos"],
            capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        rows.append((int(parts[0]), int(parts[1]), parts[2], parts[3]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--recent", type=int, default=0,
                    help="只看每个源最新的 N 条（默认 0＝按注册深度全取）")
    args = ap.parse_args()

    cfg = load_sources()
    rules = compile_rules(cfg)
    tail_cfg = next(s for s in cfg["sources"]
                    if "youtube.com/@wta" in s["url"].lower())["tail_interview"]

    hits, empty = [], []
    for channel, depth in CHANNELS:
        rows = pull(channel, args.recent or depth)
        if not rows:
            # **取不到也要列出来**——只报有结果的源，没法证明它真的看过。
            empty.append(channel)
            continue
        # **播放量的绝对值不能跨频道比。** @wta 一条常规集锦就有几万，
        # 大满贯频道的日常条目只有几千。判「有没有话题」要看它**跑赢自己
        # 频道常态多少倍**，那才是传播度；绝对值只反映频道体量。
        base = sorted(v for v, *_ in rows)[len(rows) // 2] or 1
        for rank, (views, secs, vid, title) in enumerate(rows, 1):
            tail = channel == "@wta" and _tail_interview(
                {"duration_s": secs, "title": title}, tail_cfg)
            if tail or classify(title, rules) == "oncourt":
                hits.append((views / base, views, secs, vid, title, channel,
                             "尾巴" if tail else "整条", rank, base))
    hits.sort(reverse=True)

    print(f"{len(hits)} 条场上采访，按**跑赢本频道中位数的倍数**排前 {args.top}：\n")
    for mult, views, secs, vid, title, channel, kind, rank, base in hits[:args.top]:
        print(f"  ×{mult:>5.1f}  {views:>9,} 播放（本频道中位 {base:,}）  "
              f"{secs // 60}:{secs % 60:02d}  [{kind}] {channel}")
        print(f"          {title[:86]}")
        print(f"          https://youtu.be/{vid}")
    if empty:
        print(f"\n这些源一条都没取到（**不代表它们没有采访**，多半是限流）：{'、'.join(empty)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
