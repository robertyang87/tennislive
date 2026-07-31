#!/usr/bin/env python3
"""从烧死的记分条里找「死球」的时刻，给剪辑定切点。

**为什么需要它**：第一版成片里好几段在球还在飞的时候就切走了，观众不知道这分
谁赢了。账号所有者的原话：「很多球没有播放完成就切到下一个了，建议死球后再切
换下一个，不然让人看的不明不白的」。

「死球」不用靠看球——**记分条在死球那一刻才会变**，它就是判据。所以量记分条
那一小块的帧间差：跳变的时刻就是一分结束的时刻。

两个坑，都在实现里挡掉了：

- **镜头切走时记分条会整块消失**（近景、慢镜、看台），那也是一次大跳变，
  但不是死球。所以只认「变化之后记分条还在」的那些跳变（用暗色块占比判断
  它在不在）。
- **比分数字是小面积**，整块平均差会把它淹掉。所以用「有多少像素变了」而不是
  「平均变了多少」。

    python tools/find_point_ends.py --video src.mp4 --box 0,1743,580,1915

产物是一串秒数，**还要拿缩略图墙对一眼**：这一段是不是真在这儿结束。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: 记分条那一小块里，有多少比例的像素变了才算一次跳变。
#: **框要只框比分那一列**，这是「门槛的数要在同一个口径下量」的又一例：
#: 同一条片子、同一个门槛 0.06，框整条记分条只报 26 次，只框比分列报 39 次——
#: 名字那半边从不变，把翻牌的占比稀释掉一个量级（90 分位 0.030 对 0.114）。
CHANGE = 0.06
#: 判「记分条还在不在」：它是一块深色实底，暗像素占比很高。
DARK_SHARE = 0.45
#: 两次跳变挨得太近就并成一次（翻牌有动画，会连着报好几帧）。
MERGE = 0.8


def scan(video: Path, box: tuple[int, int, int, int], step: float) -> list[dict]:
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    x0, y0, x1, y1 = box
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, int(round(fps * step)))
    prev = None
    idx = 0
    out: list[dict] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % stride == 0:
            roi = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            dark = float((roi < 90).mean())
            if prev is not None:
                moved = float((np.abs(roi.astype(np.int16)
                                      - prev.astype(np.int16)) > 40).mean())
                out.append({"t": round(idx / fps, 2), "moved": round(moved, 4),
                            "dark": round(dark, 3)})
            prev = roi
        idx += 1
    cap.release()
    return out


def point_ends(rows: list[dict], change: float, dark: float,
               merge: float) -> list[float]:
    hits = [r["t"] for r in rows if r["moved"] >= change and r["dark"] >= dark]
    merged: list[float] = []
    for t in hits:
        if not merged or t - merged[-1] > merge:
            merged.append(t)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--box", required=True,
                    help="记分条位置 x0,y0,x1,y1（源片像素）")
    ap.add_argument("--step", type=float, default=0.1)
    ap.add_argument("--change", type=float, default=CHANGE)
    ap.add_argument("--dark", type=float, default=DARK_SHARE)
    ap.add_argument("--merge", type=float, default=MERGE)
    ap.add_argument("--ends", default="", help="逗号分隔的段尾秒数，逐个吸附到死球后")
    ap.add_argument("--tail", type=float, default=1.2,
                    help="死球之后再留多久（看得到结果和反应）")
    args = ap.parse_args()

    try:
        import cv2  # noqa: PLC0415, F401
    except ImportError:
        print("要 opencv：pip install -e '.[visualqa]'", file=sys.stderr)
        return 2

    box = tuple(int(v) for v in args.box.split(","))
    rows = scan(args.video, box, args.step)
    ends = point_ends(rows, args.change, args.dark, args.merge)
    print(f"采样 {len(rows)} 点，记分条跳变 {len(ends)} 次")
    print("  " + " ".join(f"{t:.1f}" for t in ends))

    # **不合格的也报出来**：跳变了但记分条不在（镜头切走）的那些单列，
    # 否则看不出这个门槛到底筛掉了什么。
    gone = [r["t"] for r in rows if r["moved"] >= args.change and r["dark"] < args.dark]
    print(f"  丢弃 {len(gone)} 次「变了但记分条不在」（镜头切走，不是死球）")

    for raw in [s for s in args.ends.split(",") if s.strip()]:
        want = float(raw)
        after = [t for t in ends if t >= want - 0.4]
        if not after:
            print(f"  段尾 {want:>6.1f}s → 之后没有死球，保持原样")
            continue
        print(f"  段尾 {want:>6.1f}s → 死球 {after[0]:.1f}s，建议切到 "
              f"{after[0] + args.tail:.1f}s（+{after[0] + args.tail - want:.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
