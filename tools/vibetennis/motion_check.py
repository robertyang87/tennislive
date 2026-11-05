"""vibetennis 转场与运镜全局标准：成片里不许有硬切和跳帧（所有者 2026-11-05「动画的转场和运镜要做的丝滑且有吸引力」）。

逐帧（30 fps，缩到 320×180 灰度）算相邻两帧的平均绝对差（0–255）：
- 硬切／机位跳变：一帧之内画面整体换掉，差值冲到几十；交叉溶解把它摊到 0.6 秒里，每帧只剩几
- 门槛 JUMP_MAX（见下）。字幕、品牌这些叠加层逐帧淡入淡出，不会单帧冲高

    python3 tools/vibetennis/motion_check.py 成片.mp4 [--from 0 --to 999]
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import numpy as np

JUMP_MAX = 12.0   # 定门槛那一轮：EP07 改前成片（硬切＋闪白）尖峰 30～90，改后（交叉溶解）见 docs/vibetennis.md「转场与运镜」


def diffs(film: str, t0: float = 0.0, t1: float = 1e9):
    w, h = 320, 180
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0), "-i", film, "-t", str(max(0.1, t1 - t0)), "-vf", f"fps=30,scale={w}:{h},format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    return [(t0 + (i + 1) / 30, float(v)) for i, v in enumerate(d)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("film"); ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=1e9)
    ap.add_argument("--skip-head", type=float, default=0.15, help="片头横版封面那 0.1 秒切进正片，不算")
    a = ap.parse_args()
    d = [(t, v) for t, v in diffs(a.film, a.t0, a.t1) if t > a.skip_head]
    bad = [(t, v) for t, v in d if v > JUMP_MAX]
    for t, v in bad:
        print(f"✗ {t:7.2f}s  相邻帧差 {v:.1f} > {JUMP_MAX}")
    top = sorted(d, key=lambda x: -x[1])[:5]
    print("最大的 5 处：" + "  ".join(f"{t:.2f}s={v:.1f}" for t, v in top))
    print(f"硬切／跳变 {len(bad)} 处")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
