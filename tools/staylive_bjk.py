#!/usr/bin/env python3
"""金杯 / 戴维斯杯官网视频库（StayLive）的取数工具。

2026-09-18 撞出来的：`billiejeankingcup.com/en/video` 是 JS 壳，正文一个条目都没有，
但它底下调的是 **StayLive** 的公开接口，两条：

    GET https://api.staylive.tv/tags/videos/feed?limit=1000&sort=desc[&page=2][&tags=highlights]
        必须带请求头 x-staylive-channels: <频道号,逗号分隔>（少了它回「No channel ID given」）
    GET https://api.staylive.tv/videos/<id>
        不要任何头，回 playback_url —— 带 token 的 HLS master.m3u8，约 12 小时有效，
        1080p，ffmpeg -headers Referer 直接能下，yt-dlp 也认

频道号是扫 3000–7400 扫出来的（`research/zheng-bjk-cup-olympic-rule-2026.md` §七）：

    金杯     5662 bjkc-2024-finals（马拉加）  6417 bjkc-2025（含深圳总决赛）  7179 bjkc-2026  6828 pressarea
    戴维斯杯 6261 davis-cup-2025  6263/6264/6265 highlights 2023/24/25  6267/6268 additional  7078/7079/7080 2026

⚠️ 库从 2025-03 起才有货：2024 长沙、2022 韦莱涅这类更老的比赛**不在里面**，别再翻。
⚠️ 一节直播回放 7 个多小时一条（名字是「A vs. B」没有「Highlights」字样）**锁地域**：
   `geo_restricted.allowed=false` 时接口根本不给 playback_url（沙箱和 runner 都是美国 IP，两边都拿不到）；
   集锦（约 3 分钟一场）不锁。拿得到的话按段 `-ss` 取。

用法：
    python3 tools/staylive_bjk.py list --channels 6417 --grep 'CHN|China'     # 列条目
    python3 tools/staylive_bjk.py url 441895                                   # 取播放地址
    python3 tools/staylive_bjk.py grab 441895 --ss 03:00:00 --t 30 -o clip.mp4  # 下一段
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request

API = "https://api.staylive.tv"
ORIGIN = "https://www.billiejeankingcup.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0"

BJK_CHANNELS = {
    "5662": "bjkc-2024-finals",
    "6417": "bjkc-2025",
    "7179": "bjkc-2026",
    "6828": "pressarea",
}
DAVIS_CHANNELS = {
    "6261": "davis-cup-2025",
    "6263": "davis-cup-2023-highlights",
    "6264": "davis-cup-2024-highlights",
    "6265": "davis-cup-2025-highlights",
    "6267": "davis-cup-2024-additional-content",
    "6268": "davis-cup-2025-additional-content",
    "7078": "davis-cup-2026",
    "7079": "davis-cup-2026-additional-content",
    "7080": "davis-cup-2026-highlights",
}


def _get(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Origin": ORIGIN,
            **headers,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def feed(
    channels: str, *, tags: str | None = None, page: int = 1, limit: int = 1000
) -> list[dict]:
    """一个频道（或几个）一页；page 从 1 起，翻到 404 就是到底了。"""
    q = f"limit={limit}&sort=desc&page={page}"
    if tags:
        q += f"&tags={tags}"
    try:
        d = _get(f"{API}/tags/videos/feed?{q}", {"x-staylive-channels": channels})
    except urllib.error.HTTPError as e:  # 404 = 这一页没有
        if e.code == 404:
            return []
        raise
    msg = d.get("message")
    return msg if isinstance(msg, list) else []


def feed_all(channels: str, *, tags: str | None = None) -> list[dict]:
    out: dict[int, dict] = {}
    for page in range(1, 20):
        items = feed(channels, tags=tags, page=page)
        if not items:
            break
        for v in items:
            out[v["id"]] = v
    return sorted(out.values(), key=lambda v: v.get("created_at", ""))


def video(video_id: int | str) -> dict:
    return _get(f"{API}/videos/{video_id}", {})["message"]


def playback_url(v: dict) -> str:
    """锁地域的条目没有 playback_url——把原因说出来，别让 KeyError 替它说。"""
    if "playback_url" not in v:
        geo = v.get("geo_restricted") or {}
        raise SystemExit(
            f"没有播放地址：{v.get('name')} | geo allowed={geo.get('allowed')} "
            f"currentCountry={geo.get('currentCountry')}（整节回放锁地域，集锦才开放）"
        )
    return v["playback_url"]


def kind(name: str) -> str:
    """按标题分四类；「A vs. B」没有 Highlights 字样的是整节直播回放。"""
    if "Highlights" in name:
        return "highlights"
    if re.search(r"press|conference", name, re.I):
        return "press"
    if re.search(r"interview|feature|reaction", name, re.I):
        return "interview"
    if re.search(r"\bvs\.?\b", name):
        return "replay"
    return "other"


def matches(v: dict, pattern: str) -> bool:
    hay = f"{v.get('name', '')} {v.get('description') or ''}"
    return re.search(pattern, hay, re.I) is not None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument(
        "--channels",
        default=",".join(BJK_CHANNELS),
        help="频道号，逗号分隔（默认金杯四个）",
    )
    p.add_argument("--tags", default=None)
    p.add_argument("--grep", default=None, help="正则，扫标题和描述")
    p.add_argument(
        "--kind",
        default=None,
        choices=["highlights", "press", "interview", "replay", "other"],
    )
    p = sub.add_parser("url")
    p.add_argument("id")
    p = sub.add_parser("grab")
    p.add_argument("id")
    p.add_argument("--ss", default=None)
    p.add_argument("--t", default=None)
    p.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "list":
        items = feed_all(a.channels, tags=a.tags)
        if a.grep:
            items = [v for v in items if matches(v, a.grep)]
        if a.kind:
            items = [v for v in items if kind(v.get("name", "")) == a.kind]
        for v in items:
            print(
                f"{v['id']}\t{v.get('created_at', '')[:10]}\t{v.get('duration')}\t{v.get('channelPath')}\t{kind(v.get('name', ''))}\t{v.get('name')}"
            )
        print(f"# {len(items)} 条", file=sys.stderr)
        return 0
    if a.cmd == "url":
        v = video(a.id)
        print(playback_url(v))
        print(
            f"# {v['name']} | {v['duration']} | {v.get('max_resolution_tier')} | geo allowed={v.get('geo_restricted', {}).get('allowed')}",
            file=sys.stderr,
        )
        return 0
    if a.cmd == "grab":
        v = video(a.id)
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-headers",
            f"Referer: {ORIGIN}/\r\n",
        ]
        if a.ss:
            cmd += ["-ss", a.ss]
        cmd += ["-i", playback_url(v)]
        if a.t:
            cmd += ["-t", a.t]
        cmd += ["-c", "copy", "-y", a.out]
        return subprocess.call(cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main())
