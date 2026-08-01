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


# ---------------------------------------------------------------- 滞后校正
#
# **记分条的数值可靠，翻牌的时刻不可靠。** 赛点那一分实测：球在 ~172.7 秒结束、
# 庆祝在 173.3 秒，记分条 183.0 秒才翻——差十秒，因为转播切了近景、记分条整块
# 冻住。按翻牌那一帧排旁白，收尾会压在人已经庆祝完的画面上。
#
# 修法不是猜一个常数，是**夹逼 + 回溯**：
#
#   前一次翻牌 t0 ──────────── 这一分 ──────────── 这次翻牌 t1
#                              ↑ 真实落点一定在 (t0, t1] 里
#
# 区间是硬边界（两次翻牌之间正好打了一分）。在里面找落点靠**声音**——观众声
# 抬起来那一下比像素稳得多，不受机位切换影响。滞后于是从「要猜的常数」变成
# 「每一分都能测的量」。

CROWD_RISE = 2.2      # 观众声抬到基线的几倍算「这一分结束了」
CROWD_HOLD = 0.30     # 抬起来要维持多久，才不是一次拍击的尖峰
HOP = 0.02            # 音频包络的步长


def audio_envelope(video: Path, hop: float = HOP) -> tuple[object, float]:
    """整条音轨的短时能量包络。用 ffmpeg 解成单声道 8kHz PCM 再自己算，
    不引第三方音频库——这条线已经因为「加能力没同时改依赖」栽过三次。"""
    import subprocess  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    sr = 8000
    try:
        import imageio_ffmpeg  # noqa: PLC0415
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        exe = "ffmpeg"
    out = subprocess.run(
        [exe, "-v", "error", "-i", str(video), "-f", "s16le", "-ac", "1",
         "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(out, dtype="<i2").astype("float32") / 32768.0
    n = int(sr * hop)
    if n <= 0 or a.size < n:
        raise SystemExit("音轨太短或解不出来——先确认这条片子有原声")
    a = a[: a.size // n * n].reshape(-1, n)
    return np.sqrt((a ** 2).mean(axis=1)), hop


def true_end(env, hop: float, t0: float, t1: float,
             rise: float = CROWD_RISE, hold: float = CROWD_HOLD) -> float | None:
    """在 (t0, t1] 里找这一分真正结束的时刻：观众声抬起来那一下。

    返回 None 就是**没找到**——宁可说不知道，也不给一个看着合理的秒数。
    """
    import numpy as np  # noqa: PLC0415

    i0, i1 = int(t0 / hop), int(t1 / hop)
    seg = env[max(0, i0):max(1, i1)]
    if seg.size < 5:
        return None
    base = float(np.median(seg))
    if base <= 0:
        return None
    need = int(hold / hop)
    loud = seg > base * rise
    # 找第一段**连续维持**的抬升。区间里正好一分，所以只该有一段；
    # 一次拍击的尖峰维持不到 CROWD_HOLD，会被滤掉。
    run = 0
    for k, v in enumerate(loud):
        run = run + 1 if v else 0
        if run >= need:
            return round((max(0, i0) + k - run + 1) * hop, 2)
    return None


# **源片可能是哑的。** 黄泽林那条是 Tennis TV 网页播放器的录屏，播放器当时静音，
# 音轨在（aac 44.1kHz）但解出来 9402 帧全是 0——`bit_rate=2067` 就是信号。
# 所以音频回溯要有兜底：转播在一分结束之后**必切反应镜头**，那次剪辑点就是
# 落点的好代理。两条都试，并且**报出用的是哪一条**——兜底不吭声是这个仓库
# 反复踩的坑。

# **量出来的，不是拍的。** 第一版写 0.35，比剪辑点本身还高，于是一次都没命中
# ——而「全都没找到」和「这段片子没剪过」长得一模一样。实测 170–176s：
# 真实剪辑点 0.1829，普通帧中位 0.0163、九成位 0.0343。0.10 落在中间。
CUT_SCENE = 0.10      # 帧间整幅差到多少算一次剪辑


def shot_cuts(video: Path, t0: float, t1: float,
              thresh: float = CUT_SCENE) -> list[tuple[float, float]]:
    """(t0, t1] 里的镜头切换时刻。整幅缩到 160×90 再比，够用且快。"""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t0 * fps))
    prev, out, idx = None, [], int(t0 * fps)
    while idx <= int(t1 * fps):
        ok, fr = cap.read()
        if not ok:
            break
        small = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (160, 90))
        if prev is not None:
            d = float(np.abs(small.astype(np.int16) - prev).mean()) / 255.0
            if d >= thresh:
                out.append((round(idx / fps, 2), round(d, 4)))
        prev = small.astype(np.int16)
        idx += 1
    cap.release()
    return out


def unlag(video: Path, t0: float, t1: float, env=None, hop: float = HOP) -> dict:
    """把「翻牌时刻」换成「这一分真正结束的时刻」。

    区间 (t0, t1] 是硬边界——两次翻牌之间正好打了一分。返回里带 `how`，
    说清用的是哪条判据；两条都失败就是 `None`，**不给一个看着合理的数**。
    """
    if env is not None:
        got = true_end(env, hop, t0, t1)
        if got is not None:
            return {"t": got, "how": "crowd", "lag": round(t1 - got, 2)}
    # **镜头切换这条兜底不成立，别把它当答案。** 在赛点那一分上验过两种取法，
    # 都不对：取区间里最后一次切是 180.79s，取差值最大的一次是 177.35s，
    # 而真实落点是 173.25s——庆祝段里的切换比「球场全景→人脸特写」那一下还
    # 剧烈（0.2004 > 0.1829）。所以它只列候选，**不给结论**：给一个看着合理
    # 的秒数比说「不知道」糟得多。
    cuts = shot_cuts(video, t0, t1)
    return {"t": None, "how": "候选（要人看）", "lag": None,
            "cuts": cuts, "bracket": (t0, t1)}
