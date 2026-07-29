#!/usr/bin/env python3
"""竖版成片的窗口有没有钉在球场中轴上——**查产物，不查日志**。

日志里那句 `固定中心 cx=0.487（球场中轴）` 只说明代码走了那条分支，不说明它算对了。
真正的判据在成片里：窗口如果正落在中轴上，**画面里看得见的那部分球场就是左右对称
于成片中心的**，把中轴检测器再跑一遍应该报 0.5。偏多少，就是窗口偏了多少。

所以这条检查是自证的——同一个函数，先在源片上定位，再在成片上验收。

    python tools/check_reel_centering.py output/2026-07-29/reel/eala-zheng/eala-zheng.mp4

**不合格的也要列出来**：只在通过时出声的检查，没法证明它真的看过。没有球场的那些
帧（封面、特写、看台、庆祝）单独归一类报出来，它们本来就不参与这条判据。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_match_reel import _court_axis  # noqa: E402

TOLERANCE = 0.06        # 成片宽 1080，0.06 约 65px；再多就看得出来右半场出画了


def sample(video: Path, every: float) -> list[tuple[float, float | None]]:
    import cv2  # noqa: PLC0415

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    out: list[tuple[float, float | None]] = []
    at = 0.0
    while at * fps < total:
        cap.set(cv2.CAP_PROP_POS_MSEC, at * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        out.append((at, _court_axis(frame)))
        at += every
    cap.release()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--every", type=float, default=2.0, help="每几秒取一帧")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    args = ap.parse_args()

    rows = sample(Path(args.video), args.every)
    court = [(t, a) for t, a in rows if a is not None]
    blind = [t for t, a in rows if a is None]
    if not court:
        print("[检查] 一帧球场都没认出来——这条片子全是特写？先打开看一眼")
        return 1

    bad = [(t, a) for t, a in court if abs(a - 0.5) > args.tolerance]
    print(f"[检查] {Path(args.video).name}：{len(rows)} 帧，"
          f"{len(court)} 帧有球场，{len(blind)} 帧没有（封面/特写/看台，不参与判据）")
    for t, a in court:
        off = (a - 0.5) * 1080
        flag = "  ← 偏了" if abs(a - 0.5) > args.tolerance else ""
        print(f"    {t:6.1f}s  中轴 {a:.3f}  偏离中心 {off:+6.0f}px{flag}")
    worst = max(abs(a - 0.5) for _, a in court)
    print(f"[检查] 最大偏离 {worst * 1080:.0f}px（容差 {args.tolerance * 1080:.0f}px）"
          f"，不合格 {len(bad)}/{len(court)} 帧")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
