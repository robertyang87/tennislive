#!/usr/bin/env python3
"""在**一组已经过了闸门的候选帧**里，挑清晰度最高的那张。

账号所有者 2026-08-03：「走动也可以，击球中是第一选择（如果文案内容是击球中），
其次时间地点人物事件都能对上就 ok」「**但在同等级别里选清晰度高的**」。

所以这个脚本**不判对不对题**——对不对题是人看缩略图墙定的（四道闸门的前三道）。
它只回答最后一道：这几张里哪张最锐。

    python3 tools/rank_frame_sharpness.py frames/frame_0100s.jpg frames/frame_0104s.jpg ...
    python3 tools/rank_frame_sharpness.py --dir frames --range 100 112

⚠️ **两个口径上的坑，都是这个仓库栽过的：**

1. **要在同一个尺寸下量。** `pick_cover_frames` 那条注释记着：直接在原尺寸 ROI 上
   求 Laplacian 方差，得数和放大倍率成反比——371px 的近景 17.6，198px 的中景 123.9，
   于是门槛把**所有近景**都判成「糊」。这里统一缩到 `NORM_W` 再算。
2. **烧死的记分条和台标是永远最锐的**，整帧一起量会被它们拉平——两张帧的差别
   被一块不变的图形淹掉。所以默认把**下三分之一**（记分条）和**右上角**（台标）
   排除掉再量；`--whole` 可以关掉这个排除来对照。

判据里报的是**每一档的绝对值**，不是只报第一名：只报赢家的排序没法自证它有没有
真的看过（「检查工具要把不合格的也列出来」）。

⚠️ **它量的是高频能量，不纯是「锐不锐」——所以只能在同一个镜头里比。**
实测踩到过：蒙特利尔那张背后是一整片看台观众（边缘极多）得 320.9，
华盛顿那张背后是一大块平的深蓝广告布，只有 73.3——**两张一样清楚**，
差的是背景有多少纹理，不是清晰度。跨镜头拿这个数排序会把「背景热闹」
读成「更清楚」。

所以正确的用法是**在同一个镜头的相邻几帧里挑**（`--dir` 配 `--range`）：
同样的构图、同样的背景，差别才真的只剩运动模糊。跨镜头的取舍仍然靠眼睛，
这一步机器判不了。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: 一律缩到这个宽度再算，否则「大图」天然占便宜。
NORM_W = 960
#: 记分条压在底部这一段里，台标压在右上角这一块——两者都是矢量图形，永远最锐。
_SCORE_BAR_BOTTOM = 0.30
_LOGO_TOP = 0.12
_LOGO_LEFT = 0.78


def sharpness(path: Path, *, whole: bool = False) -> float:
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit(f"读不出来：{path}")
    h = round(img.shape[0] * NORM_W / img.shape[1])
    img = cv2.resize(img, (NORM_W, h), interpolation=cv2.INTER_AREA)
    lap = cv2.Laplacian(img, cv2.CV_64F)
    if whole:
        return float(lap.var())
    mask = np.ones(lap.shape, dtype=bool)
    mask[round(h * (1 - _SCORE_BAR_BOTTOM)):, :] = False       # 记分条
    mask[:round(h * _LOGO_TOP), round(NORM_W * _LOGO_LEFT):] = False  # 台标
    return float(lap[mask].var())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frames", nargs="*", type=Path)
    ap.add_argument("--dir", type=Path, help="从这个目录里按 frame_NNNNs.jpg 取")
    ap.add_argument("--range", nargs=2, type=int, metavar=("起", "止"),
                    help="配合 --dir，按秒数闭区间取")
    ap.add_argument("--whole", action="store_true",
                    help="连记分条和台标一起量（对照用）")
    args = ap.parse_args(argv)

    frames = list(args.frames)
    if args.dir:
        lo, hi = args.range if args.range else (0, 10**9)
        frames += [p for p in sorted(args.dir.glob("frame_*s.jpg"))
                   if lo <= int(p.stem[6:-1]) <= hi]
    if not frames:
        raise SystemExit("一张候选帧都没给——空结果先自证是真空：--dir 写对了吗？")

    scored = [(sharpness(p, whole=args.whole), p) for p in frames]
    scored.sort(reverse=True)
    best = scored[0][0]
    print(f"{len(scored)} 张，缩到 {NORM_W}px 同口径量"
          f"{'（整帧）' if args.whole else '（已排除记分条和台标）'}：")
    for v, p in scored:
        mark = " ← 最锐" if v == best else ""
        print(f"  {v:8.1f}  {v / best * 100:5.1f}%  {p.name}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
