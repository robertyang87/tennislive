#!/usr/bin/env python3
"""猜一猜记分条大概在哪——给 `--scorebox` 省一次人工量坐标。

## 为什么要有它

`find_point_ends.py`（判死球时刻）要一个精确到像素的 `--scorebox x0,y0,x1,y1`，
而这个位置**每家转播不一样**，一直是人盯着 probe 那份「记分条缩略图墙」自己量。
`cmd_probe` 里那份缩略图墙本身也只是拿一个粗糙的经验框裁的
（左边 42%、底部往上 20%——`box = f"{w*42//100}:{h*20//100}:0:{h*78//100}"`），
不是量出来的精确框，够肉眼确认但不够喂给 `find_point_ends`。

## 怎么猜

记分条这类广播叠加层有一个和场上任何东西都不一样的签名：**它是一块几何位置
锁死的实底深色矩形**，只在比分变化时局部刷新（文字、高亮条），球场/看台/球员
这些才是持续在动的。所以：

1. 采样一批帧（跳过开头结尾各 10%，避免片头字卡）
2. 对每个像素算「在采样里有多少比例落在暗色（灰度 < 90，和 `find_point_ends.py`
   的 `DARK_SHARE` 同一个口径）」——**不是看方差**。第一版用「暗 且 稳定（低方差）」
   两个条件相与，结果记分条自己被挡在外面：比分数字、高亮条一直在变，
   区域内方差并不低（实测均值 21.4，而「稳定」门槛给的是 12）。换成
   「频繁暗」之后，占多数面积的纯色底板即使文字/高亮在闪，依然稳稳地
   落在「多数时候是暗的」里
3. 频繁暗的像素连通成块，按**填充率**（连通域面积 ÷ 外接矩形面积）筛：
   记分条是**实心矩形**，填充率能到 0.9 以上；树荫、看台暗色衣服这类
   暗色区域是**散的**，填充率明显更低。填充率是这一步真正的判据，
   不是面积——第一版光按面积排序，真正的记分条只排第二，第一名是把
   一整片看台阴影闭运算粘成一坨的假阳性（面积 158390 vs 记分条的 22491，
   但填充率 0.41 vs 0.93，一眼分得开）

## 验证过的结果，和它的局限

2026-08-07 用 `zhang-putintseva`（张帅 vs 普汀塞娃，1280×720 WTA 转播源片，
188.7 秒）这条**真实广播源片**验过：肉眼在源帧上量出的真值是
`(61,579)-(359,653)`，这个脚本猜出 `(61,579)-(382,654)`——左/上/下三边
完全对齐，右边多出 23px（多半是某些采样帧比分位数更宽，比如抢七的两位数，
把连通域的外接矩形略微撑宽了）。多出来的 23px 对下游没有坏处：
`find_point_ends.py` 判的是框内暗像素占比，多几列场地颜色的边界像素
稀释不到 `DARK_SHARE=0.45` 那道线。

⚠️ **只在这一条真实源片上验过。** 这台沙箱里能找到的两份缓存源片
（`~/.cache/tennislive-sources/*.mp4`）内容完全相同（md5 一致，只是被两个
不同的 URL 哈希各缓存了一份），**实际只有一个真实样本**。CLAUDE.md 里记过
不同转播商的记分条位置和样式差很大（ATP/Tennis TV、WTA 官方频道、赛事自办
频道各不相同），这个脚本**没有跨转播商验证过**，不能默认它对下一条源片
也一猜就中。

## 它不做什么

- **不自动喂给 `find_point_ends.py`**。猜出来的只是候选，`cmd_probe` 只把它
  当**打印出来的建议**（连同一张裁出来的预览图），人确认过再手动把
  `--scorebox` 填进下一轮 probe——和这条线上所有「候选 vs 判据」的分工一样
  （`scene_cuts` 是候选、`point_ends` 本身也是候选，都要拿缩略图墙对一眼）。
  没有静默改变任何已有行为
- **给不出高置信候选就说明白，不硬猜**。填充率不够、或者压根没有稳定的暗色
  矩形（记分条被换成了半透明水印、或者这段源片记分条一直没露出来），
  会返回空列表并把「查过但没有」的理由打出来——不给一个看着确定其实是赌的框

## 用法

    python3 tools/detect_scorebox.py --video source.mp4
    python3 tools/detect_scorebox.py --video source.mp4 --save-crop preview.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

#: 灰度门槛：低于这个值算「暗」——和 `find_point_ends.py` 的 `DARK_SHARE`
#: 判据同一个口径（那边判的是「这一帧记分条在不在」，这边判的是「这个像素
#: 常年是不是记分条底板」）。
DARK = 90.0
#: 一个像素要在至少这么多比例的采样帧里落在「暗」，才算记分条候选像素。
#: 量出来的：真记分条底板在整条源片里 79% 的采样帧暗，留出余量定在 0.65。
DARK_FREQ = 0.65
#: 连通域的填充率下限（面积 ÷ 外接矩形面积）。记分条是实心矩形，填充率
#: 能到 0.9+；散布的暗色区域（阴影、树荫、看台深色衣服闭运算粘连之后）
#: 填充率明显更低，实测那次是 0.41。
MIN_FILL = 0.70
#: 连通域面积下限，滤掉噪点和小图标（比如台标）。
MIN_AREA = 2500
#: 连通域面积上限：超过这个比例说明不是一块记分条，是背景大片被闭运算粘连了。
MAX_AREA_FRAC = 0.25
#: 闭运算核大小：记分条上的文字/数字/高亮条是亮色，会在暗色底板上抠出细缝，
#: 闭运算把这些细缝填回去，不然一块记分条会被文字切成好几个小连通域。
CLOSE_KERNEL = 9
#: 最多采样这么多帧——源片可能是几十分钟的整场录像，不能无限采样。
MAX_SAMPLES = 90


def sample_gray_frames(video: Path, max_samples: int = MAX_SAMPLES,
                        start_frac: float = 0.1, stop_frac: float = 0.9,
                        step_seconds: float = 2.0) -> np.ndarray:
    """跳过片头片尾各一截，按秒数等距采样灰度帧，摞成一个 (N,H,W) 数组。"""
    import cv2  # noqa: PLC0415

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        raise SystemExit(f"读不出帧数：{video}")
    lo, hi = int(total * start_frac), int(total * stop_frac)
    if hi <= lo:
        lo, hi = 0, total
    step = max(1, int(fps * step_seconds))
    idxs = list(range(lo, hi, step))[:max_samples]

    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            continue
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    cap.release()
    if not frames:
        raise SystemExit(f"一帧都读不出来：{video}")
    return np.stack(frames, axis=0).astype(np.float32)


def candidates_from_stack(stack: np.ndarray, *, dark: float = DARK,
                           dark_freq: float = DARK_FREQ, min_fill: float = MIN_FILL,
                           min_area: int = MIN_AREA,
                           max_area_frac: float = MAX_AREA_FRAC,
                           close_kernel: int = CLOSE_KERNEL) -> list[dict]:
    """纯数组函数，不碰视频——这样测试不用现造 mp4 就能验算法本身。

    返回按面积从大到小排的候选，每条是 `{"box": (x0,y0,x1,y1), "area": int,
    "fill": float}`。`fill` 是矩形填充率，**它才是判据**，不是面积。
    """
    import cv2  # noqa: PLC0415

    h, w = stack.shape[1:]
    freq = (stack < dark).mean(axis=0)
    mask = (freq > dark_freq).astype(np.uint8) * 255
    if close_kernel > 1:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                np.ones((close_kernel, close_kernel), np.uint8))
    n, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

    out = []
    for lbl in range(1, n):
        x, y, cw, ch, area = stats[lbl]
        if area < min_area or area > max_area_frac * h * w:
            continue
        fill = area / (cw * ch)
        if fill < min_fill:
            continue
        out.append({"box": (int(x), int(y), int(x + cw), int(y + ch)),
                    "area": int(area), "fill": round(float(fill), 3)})
    out.sort(key=lambda c: -c["area"])
    return out


def detect(video: Path, **kwargs) -> list[dict]:
    stack = sample_gray_frames(video)
    return candidates_from_stack(stack, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--save-crop", type=Path, default=None,
                    help="把最佳候选裁出来存一张预览图（还是要拿眼睛看一眼）")
    args = ap.parse_args()

    if not args.video.is_file():
        raise SystemExit(f"源片不存在：{args.video}")

    try:
        import cv2  # noqa: PLC0415, F401
    except ImportError:
        raise SystemExit("要 opencv：pip install -e '.[visualqa]'")

    stack = sample_gray_frames(args.video)
    cands = candidates_from_stack(stack)
    if not cands:
        print(f"[记分条] 采样 {stack.shape[0]} 帧，没有找到「频繁暗 + 高填充率」"
              f"的矩形（门槛 dark_freq>{DARK_FREQ} fill>{MIN_FILL}）——"
              "这条源片可能没有常驻记分条，或者门槛卡得太严，要人自己量。")
        return 1

    print(f"[记分条] 采样 {stack.shape[0]} 帧，{len(cands)} 个候选："
          "（填充率才是判据，不是面积）")
    for c in cands[:5]:
        x0, y0, x1, y1 = c["box"]
        print(f"  box={x0},{y0},{x1},{y1}  面积={c['area']:6d}  填充率={c['fill']:.2f}")

    best = cands[0]
    x0, y0, x1, y1 = best["box"]
    print(f"\n建议 --scorebox {x0},{y0},{x1},{y1}"
          "  （只是候选，还要拿缩略图墙对一眼再填进下一轮 probe）")

    if args.save_crop:
        from PIL import Image  # noqa: PLC0415
        import cv2  # noqa: PLC0415

        cap = cv2.VideoCapture(str(args.video))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) * 0.3))
        ok, frame = cap.read()
        cap.release()
        if ok:
            crop = frame[max(0, y0):y1, max(0, x0):x1]
            Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).save(args.save_crop)
            print(f"预览图存到 {args.save_crop}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
