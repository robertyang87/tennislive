#!/usr/bin/env python3
"""读一个 mp4 有多长——纯 Python 解 `mvhd`，不需要 ffprobe。

沙箱里没有 ffmpeg/ffprobe，所以「片头片尾的静音到底加进去了没有」这种事，
本来只能靠看 ffmpeg 命令行推断。但命令行对不代表成片对。mp4 的时长就写在
`moov/mvhd` 里，四十行就能读出来，于是可以直接量成片本身。

用法：
    python tools/mp4_duration.py output/2026-07-26/explainer/hawkeye/explainer.mp4
    # 从 git 里读，不用先 checkout
    python tools/mp4_duration.py --ref origin/main output/.../explainer.mp4
    # 比较两个版本，看差了多少秒
    python tools/mp4_duration.py --ref HEAD~5 --vs origin/main output/.../explainer.mp4
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def mvhd_seconds(data: bytes) -> float:
    """Walk the box tree to moov/mvhd and divide duration by timescale."""

    def walk(buf: bytes, start: int, end: int) -> float | None:
        pos = start
        while pos + 8 <= end:
            size, kind = struct.unpack_from(">I4s", buf, pos)
            body = pos + 8
            if size == 1:  # 64-bit extended size
                size = struct.unpack_from(">Q", buf, body)[0]
                body += 8
            elif size == 0:  # box runs to the end of the file
                size = end - pos
            if size < 8 or pos + size > end:
                return None
            if kind == b"mvhd":
                version = buf[body]
                if version == 1:
                    timescale, duration = struct.unpack_from(">IQ", buf, body + 20)
                else:
                    timescale, duration = struct.unpack_from(">II", buf, body + 12)
                return duration / timescale if timescale else None
            if kind == b"moov":
                found = walk(buf, body, pos + size)
                if found is not None:
                    return found
            pos += size
        return None

    got = walk(data, 0, len(data))
    if got is None:
        raise ValueError("这个文件里找不到 moov/mvhd")
    return got


def _load(path: str, ref: str | None) -> bytes:
    if ref:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{path}"],
                             capture_output=True)
        if not out.stdout:
            raise SystemExit(f"{ref}:{path} 读不到")
        return out.stdout
    return Path(path).read_bytes()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--ref", help="从这个 git ref 读文件")
    ap.add_argument("--vs", help="再从这个 ref 读一份，打印两者的差")
    args = ap.parse_args()

    a = mvhd_seconds(_load(args.path, args.ref))
    print(f"{args.ref or '工作区'}  {a:.3f} 秒")
    if args.vs:
        b = mvhd_seconds(_load(args.path, args.vs))
        print(f"{args.vs}  {b:.3f} 秒")
        print(f"差 {b - a:+.3f} 秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
