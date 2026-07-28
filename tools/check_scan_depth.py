#!/usr/bin/env python3
"""每个 YouTube 源的 scan_depth 够不够——**扫到底了没有**。

写这个的由来：WTA 官方频道注册的是 `scan_depth=800`，看着不小。
全量扫下来 13791 条，**86 条场上采访全部排在第 800 名之后**——
按注册的深度一条都拿不到，而报表上它只是「WTA 官网视频贡献 0 条」，
看着像「WTA 不发场上采访」。

这就是「空结果 ≠ 不存在」的又一个变种，而且是最隐蔽的一种：
**采集器没有报错，它只是没走到那里。**

判据只有一条硬的：**`--flat-playlist --playlist-end N` 返回的条数正好等于 N，
就说明后面还有。** 少于 N 才是扫全了。

用法：
    python tools/check_scan_depth.py            # 查全部 YouTube 源
    python tools/check_scan_depth.py --probe 3000   # 探到这个深度为止
    python tools/check_scan_depth.py --source WTA   # 只查某一个
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.collect_oncourt_interviews import classify, compile_rules, load_sources  # noqa: E402


def enumerate_channel(url: str, end: int, timeout: int) -> list[str] | None:
    cmd = ["yt-dlp", "--flat-playlist", "--playlist-end", str(end), "--no-warnings",
           "--print", "%(title)s", url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return [l for l in out.stdout.splitlines() if l.strip()]


def probe(src: dict, end: int, rules, timeout: int) -> dict:
    titles = enumerate_channel(src["url"], end, timeout)
    if titles is None:
        return {**src, "status": "超时", "total": None}
    depth = src.get("scan_depth", 150)
    # 注册深度之内 / 之外各有多少条场上采访。**之外的就是现在拿不到的。**
    inside = sum(classify(t, rules) == "oncourt" for t in titles[:depth])
    beyond = sum(classify(t, rules) == "oncourt" for t in titles[depth:])
    return {**src, "status": "撞顶" if len(titles) >= end else "扫全",
            "total": len(titles), "inside": inside, "beyond": beyond}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", type=int, default=3000, help="探到这个深度为止")
    ap.add_argument("--source", help="只查名字含这个子串的源")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()

    cfg = load_sources()
    rules = compile_rules(cfg)
    srcs = [s for s in cfg["sources"]
            if "youtube.com" in s["url"] and "," not in s["url"]
            and (not args.source or args.source.lower() in s["name"].lower())]

    with ThreadPoolExecutor(args.jobs) as ex:
        rows = list(ex.map(lambda s: probe(s, args.probe, rules, args.timeout), srcs))

    rows.sort(key=lambda r: -(r.get("beyond") or 0))
    print(f"{'来源':34s}{'注册深度':>7}{'实际条数':>8}{'深度内':>7}{'深度外':>7}  状态")
    short = []
    for r in rows:
        b = r.get("beyond")
        flag = ""
        if b:
            flag = "  ← 这些现在拿不到"
            short.append(r)
        print(f"{r['name'][:32]:34s}{r.get('scan_depth', 150):>7}"
              f"{str(r['total']):>8}{str(r.get('inside', '-')):>7}{str(b if b is not None else '-'):>7}"
              f"  {r['status']}{flag}")
    if short:
        print(f"\n**{len(short)} 个源的 scan_depth 不够**，漏掉 "
              f"{sum(r['beyond'] for r in short)} 条场上采访：")
        for r in short:
            need = r["total"] if r["status"] == "扫全" else f">{r['total']}"
            print(f"   {r['name']}：scan_depth {r.get('scan_depth', 150)} → 至少要 {need}")
    else:
        print("\n没有源被 scan_depth 卡住。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
