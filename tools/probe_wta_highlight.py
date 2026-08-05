#!/usr/bin/env python3
"""WTA 官网出没出某场球的集锦——盯的是**官网 Brightcove，不是 YouTube**。

来路：`zhang-putintseva` 那条的源片就是官网 Brightcove 资产（`_source` 里写着
「WTA 官方 YouTube 一直没传这场」，等了两轮共 170 分钟才改用官网 720p）。
所以这条线要盯的入口和 match-reel 平时用的不是一个。

⚠️ **列表页是只有 10 条的滚动窗口，`?page=2` 返回同样 10 条（前端分页）。**
所以「列表里没有」**证明不了「没有片源」**——2026-08-05 实测：张帅对普汀塞娃
那条集锦确确实实存在（Brightcove `6402712674112`，我们用它出过片），可它
**不在任何一个列表页里**。这正是这个仓库反复栽的「空结果先自证是真空」。

所以这个脚本**只回答一件事：现在列表里有没有**。答「没有」的时候必须同时
把窗口边界打出来（最新一条是几点的），让读的人自己判断是「还没出」还是
「出了但被挤出窗口」。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
PAGES = ("https://www.wtatennis.com/videos/highlights",
         "https://www.wtatennis.com/videos/singles",
         "https://www.wtatennis.com/videos")


def get(url: str) -> str:
    r = subprocess.run(["curl", "-sS", "--max-time", "30",
                        "-H", f"User-Agent: {UA}", url],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", nargs="+", required=True,
                    help="要找的姓，如 zhang ostapenko")
    args = ap.parse_args()

    found: dict[str, str] = {}
    for url in PAGES:
        for vid, slug in re.findall(r"/videos/(\d+)/([a-z0-9\-]+)", get(url)):
            found[vid] = slug
    if not found:
        print("[异常] 三个列表页一条视频都没抓到——多半是页面结构变了，"
              "别当成「没有片源」")
        return 2

    want = [w.lower() for w in args.who]
    hits = {v: s for v, s in found.items() if all(w in s for w in want)
            or any(w in s for w in want)}
    newest = max(found, key=lambda v: int(v))
    print(f"窗口里共 {len(found)} 条，最新一条 /videos/{newest}/{found[newest]}")
    if hits:
        print(f"\n✅ 命中 {len(hits)} 条：")
        for v, s in sorted(hits.items(), key=lambda kv: -int(kv[0])):
            print(f"   https://www.wtatennis.com/videos/{v}/{s}")
        print("\n下一步：打开视频页，抠 players.brightcove.net/(账号)/(player) "
              "和 videoId，写进 spec 的 source_url（要**播放器地址**不是文章页，"
              "yt-dlp 对 /videos/… 报 Unsupported URL）")
        return 0
    print(f"\n❌ 窗口里没有 {' '.join(args.who)}。")
    print("⚠️ **这不等于没有片源**——列表只有 10 条且是滚动窗口，实测连"
          "已知存在的张帅 R1 集锦都不在里面。")
    print("   判据是上面那条「最新一条」：它比目标那场晚，才说明是真没出；"
          "它比目标那场早，就只是还没轮到。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
