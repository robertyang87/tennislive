#!/usr/bin/env python3
"""YouTube 地址 → 仓库里已经存档的那份 Release 源片（有就用，没有就原样返回）。

2026-10-12 `wangxiyu-wangxinyu-wuhan-2026-r1`：`download-video.yml` 14:29 就把源片存进了
Release `source-y9d6IHw0cZk`，而 14:30 拨的 probe 仍按 YouTube 地址去下，yt-dlp 在
runner 上挂了 23 分钟才被发现，换成 Release 直链重拨之后 5 分钟出结果。**同一条片子
在仓库里已经有一份了，就别再去 YouTube 碰运气**——Release 直链是 curl 一次的事。

只认 `download-video.yml` 的命名：tag `source-<11 位 id>`、附件 `<id>.mp4`。探活用
`Range: bytes=0-99`（和 download-video 上传后那道探活同一个判据），200/206 才算有。

⚠️ 只用标准库：工作流在装依赖之前跑它。

用法::

    python3 tools/release_source.py --url URL --repo owner/name   # 打印该用的地址
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_claims import _YT  # noqa: E402  同一个 id 判断只许有一份


def release_url(video_id: str, repo: str) -> str:
    return (f"https://github.com/{repo}/releases/download/"
            f"source-{video_id}/{video_id}.mp4")


def _exists(url: str, timeout: float = 20) -> bool:
    req = urllib.request.Request(url, headers={"Range": "bytes=0-99",
                                               "User-Agent": "tennislive-probe"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 206)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def resolve(url: str, repo: str, *, exists=_exists) -> tuple[str, str]:
    """返回 `(该用的地址, 一句说明)`。不是 YouTube、或 Release 里没有，就原样返回。"""
    m = _YT.search(url or "")
    if not m or not repo:
        return url, "不是 YouTube 地址，原样使用"
    archived = release_url(m.group(1), repo)
    if exists(archived):
        return archived, f"Release 里已有存档，改用 {archived}（不再去 YouTube 下）"
    return url, f"Release 里没有 source-{m.group(1)}，照旧从 YouTube 下"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    chosen, why = resolve(args.url, args.repo)
    print(why, file=sys.stderr)
    print(chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
