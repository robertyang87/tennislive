#!/usr/bin/env python3
"""把成片压成一个能发给账号所有者看的**审片版**（默认 ≤28 MiB）。

来路：账号所有者 2026-08-05「**那以后你要单独发出来我看一下呀，你不发出来我
怎么在这里看呀？**」。而 `SendUserFile` 的上限是 **30 MiB**，这条线的成片按
实测 5700 kb/s 算 **90 秒就 63 MiB**——**基本每一条都超**，不是边角情况。
`wang-kasatkina` 那次 37.7 MiB 被退回，我当场临时切片段，属于现搓；写成脚本
是为了别再搓第二次。

⚠️ **审片版只用来看，不许当成片。** 发微信的永远是 `output/` 里那份原码率的。
所以输出文件名硬性带 `-审片版`，肉眼就能分出来——这条线为「两个地址两条片子，
谁也没说哪个是哪个」栽过（见 CLAUDE.md 里 Release 那节）。

用法：
    python3 tools/review_copy.py output/2026-08-05/reel/shang-rublev/shang-rublev.mp4
    python3 tools/review_copy.py <成片> --mib 20 --width 640
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

MIB = 1024 * 1024
# 30 MiB 是硬上限，留 2 MiB 给容器开销和码率控制的抖动
DEFAULT_TARGET_MIB = 28
# 音轨给足：审片最要紧的一维是配音（断句、气口、音色），不能为了省体积压糊
AUDIO_KBPS = 96


def probe_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"ffprobe 读不出 {path}：{out.stderr.strip()[:200]}")
    return float(json.loads(out.stdout)["format"]["duration"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("film", type=Path)
    ap.add_argument("--mib", type=float, default=DEFAULT_TARGET_MIB)
    ap.add_argument("--width", type=int, default=720,
                    help="缩到这个宽度；审片看的是内容和节奏，不是画质")
    # ⚠️ **默认不写进 `output/`。** 第一版写在成片旁边，当场发现它会被
    # `git add` 吃进仓库——一个 27 MiB 的、谁也说不清是不是成片的文件。
    # 这条线为「两个地址两条片子，谁也没说哪个是哪个」栽过一次，不再来第二次。
    ap.add_argument("--out-dir", type=Path, default=Path(tempfile.gettempdir()),
                    help="审片版落在哪，默认临时目录（**不进仓库**）")
    args = ap.parse_args()

    if not args.film.is_file():
        raise SystemExit(f"成片不在：{args.film}")
    src_mib = args.film.stat().st_size / MIB
    secs = probe_seconds(args.film)

    if src_mib <= args.mib:
        print(f"[审片版] 原片 {src_mib:.1f} MiB 已经在 {args.mib} MiB 以内，"
              "直接发原片就行，不用压")
        print(args.film)
        return 0

    # 反算视频码率：目标体积扣掉音轨，再留 3% 给封装
    budget_kbit = args.mib * MIB * 8 / 1000
    video_kbps = int((budget_kbit / secs - AUDIO_KBPS) * 0.97)
    if video_kbps < 200:
        raise SystemExit(
            f"{secs:.0f} 秒要压进 {args.mib} MiB，视频只剩 {video_kbps} kbps，"
            "压出来没法看。\n改发**片段 + 全片音轨**："
            "音轨 1.5 MB 上下，而配音和断句正是最需要耳朵的那一维。")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{args.film.stem}-审片版.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(args.film),
           "-vf", f"scale={args.width}:-2",
           "-c:v", "libx264", "-preset", "medium",
           "-b:v", f"{video_kbps}k", "-maxrate", f"{int(video_kbps*1.3)}k",
           "-bufsize", f"{video_kbps*2}k",
           "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k",
           "-movflags", "+faststart", str(out)]
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit("ffmpeg 压制失败")

    got = out.stat().st_size / MIB
    print(f"[审片版] {src_mib:.1f} → {got:.1f} MiB"
          f"（{secs:.0f}s，{args.width}px 宽，视频 {video_kbps}k + 音频 {AUDIO_KBPS}k）")
    if got > 30:
        raise SystemExit(f"⚠️ 压完还是 {got:.1f} MiB，超过 30 MiB 上限——"
                         "调小 --mib 或 --width 再来一次")
    print(f"⚠️ 这是**审片版**，只用来看。发微信的仍然是 {args.film.name}")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
