#!/usr/bin/env python3
"""验一件事：**观众声抬起来能不能标出一分的结束。**

这是「比分板滞后」那套修法的核心判据。记分条的数值可靠、翻牌的时刻不可靠
（赛点那一分实测差十秒），所以真实落点要在两次翻牌夹出来的区间里另找，
而声音是最不受机位切换影响的信号。

**为什么要另找一条片子来验。** 黄泽林那条源片是网页播放器的录屏、播放器
静音，aac 音轨解出来 9402 帧全是 0——`bit_rate=2067` 就是信号。在哑源上
「检测不到观众声」和「这个方法不成立」长得一模一样，验不出任何东西。
账号所有者：「音频以后肯定是有的，这次是意外」。

跑法（YouTube 要 cookie / PO token，所以在 runner 上跑）：

    python tools/check_crowd_rise.py --url https://youtu.be/XXXX

它只报**候选**和它们的间隔，不下结论。判断「这些时刻是不是真的死球」仍然
要人打开听/看——工具报出来的数只是让人能对着看。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def ffmpeg_exe() -> str:
    """ffmpeg 的可执行文件。**别假设 runner 自带**——我假设过一次，预检当场
    打脸。`imageio-ffmpeg` 会带一个便携版，仓库里其他几条线也是这么解的。"""
    try:
        import imageio_ffmpeg  # noqa: PLC0415
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return "ffmpeg"


def preflight() -> None:
    """**开跑前先验依赖，别下完 100 MB 再报 ImportError。**

    让失败发生在第 5 秒，不是第 90 秒；而且报错要说出路，不能只说不行。
    """
    missing = []
    try:
        import numpy  # noqa: F401, PLC0415
    except ImportError:
        missing.append("numpy（pip install numpy）")
    try:
        subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, check=True)
    except Exception:  # noqa: BLE001
        missing.append("ffmpeg（pip install imageio-ffmpeg，或 apt-get install ffmpeg）")
    if missing:
        raise SystemExit("缺依赖，这条验不了（不是片子的问题）：\n  "
                         + "\n  ".join(missing))


def envelope(media: Path, sr: int = 8000, hop: float = 0.02):
    """短时能量包络。解成单声道 PCM 自己算，不引第三方音频库。"""
    import numpy as np  # noqa: PLC0415

    out = subprocess.run(
        [ffmpeg_exe(), "-v", "error", "-i", str(media), "-f", "s16le",
         "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True).stdout
    a = np.frombuffer(out, dtype="<i2").astype("float32") / 32768.0
    n = int(sr * hop)
    if a.size < n * 10:
        raise SystemExit("音轨太短或解不出来")
    a = a[: a.size // n * n].reshape(-1, n)
    return np.sqrt((a ** 2).mean(axis=1)), hop


def rises(env, hop: float, rise: float, hold: float, gap: float) -> list[float]:
    """整条片子里「声音抬起来并维持」的时刻。

    基线用**全局中位**：一分打完观众声起来，但回合中也有球声，中位数落在
    两者之间。门槛的数必须在同一个口径下量——这条线上已经栽过两次
    （人脸清晰度、记分条翻牌），所以这里把量出来的分布一起打出来。
    """
    import numpy as np  # noqa: PLC0415

    base = float(np.median(env))
    if base <= 0:
        raise SystemExit(
            "整条音轨的中位能量是 0 —— 这条片子是哑的（录屏静音？），"
            "换一条有声的再验，别在哑源上判断方法成不成立")
    need = int(hold / hop)
    loud = env > base * rise
    out, run = [], 0
    for k, v in enumerate(loud):
        run = run + 1 if v else 0
        if run == need:
            t = round((k - run + 1) * hop, 2)
            if not out or t - out[-1] >= gap:
                out.append(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default="", help="YouTube 链接（要 cookie/PO token）")
    ap.add_argument("--file", default="", help="本地文件，和 --url 二选一")
    ap.add_argument("--cookies", default="", help="cookies.txt")
    ap.add_argument("--rise", type=float, default=2.2, help="抬到基线的几倍")
    ap.add_argument("--hold", type=float, default=0.30, help="要维持多久")
    ap.add_argument("--gap", type=float, default=3.0, help="两次之间至少隔多久")
    args = ap.parse_args()

    preflight()

    import numpy as np  # noqa: PLC0415

    if args.url:
        dest = Path("crowd_test.m4a")
        cmd = ["yt-dlp", "--no-warnings", "-f", "bestaudio/best",
               "-o", str(dest), args.url]
        if args.cookies:
            cmd[2:2] = ["--cookies", args.cookies]
        print("→ 下载音轨…")
        subprocess.run(cmd, check=True)
        media = next(Path(".").glob("crowd_test.*"))
    else:
        media = Path(args.file)
    print(f"素材：{media}（{media.stat().st_size/1e6:.1f} MB）")

    env, hop = envelope(media)
    dur = env.size * hop
    base = float(np.median(env))
    print(f"音轨 {dur:.1f}s · 中位能量 {base:.4f} · 九成位 "
          f"{float(np.percentile(env, 90)):.4f} · 最大 {float(env.max()):.4f}")
    if base <= 0:
        print("**哑的**：中位是 0，这条验不了")
        return 1
    print(f"九成位/中位 = {float(np.percentile(env, 90))/base:.2f}x"
          f"  ← 门槛 {args.rise}x 要落在这个量级里才有意义")

    hits = rises(env, hop, args.rise, args.hold, args.gap)
    print(f"\n检出 {len(hits)} 个「声音抬起来」的时刻"
          f"（{args.rise}x 维持 {args.hold}s，间隔≥{args.gap}s）")
    if not hits:
        print("一个都没有——先怀疑门槛，别怀疑片子。上面那行分布就是量出来的口径")
        return 1
    gaps = np.diff(hits) if len(hits) > 1 else np.array([0.0])
    print(f"间隔：中位 {float(np.median(gaps)):.1f}s · "
          f"最短 {float(gaps.min()):.1f}s · 最长 {float(gaps.max()):.1f}s")
    print("  （网球一分之间通常 20–35 秒；集锦剪过，会短很多）")
    print("\n前 30 个：")
    for i, t in enumerate(hits[:30]):
        print(f"  {i+1:3d}  {t:7.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
