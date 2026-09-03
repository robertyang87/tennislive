#!/usr/bin/env python3
"""渲一份片尾母版，提交进仓库。**每条片子从它转码，不再各渲一遍。**

账号所有者 2026-08-05：「就做好一个带口播的视频段，每次都拼接到最后不行么？」

对的，而且账算出来很硬（沙箱实测，一条片子付一遍）：

    TTS                0.92s
    渲页（Chromium）   7.58s   ← 大头
    编码               5.88s
    ────────────────────────
    合计              14.38s

母版方案只剩**按目标参数转一次码：1.9 秒**，省 87%。

⚠️ **但不能存一个 mp4 直接 `-c copy` 拼**——三条线的流参数不一样：

    剪辑片   帧率跟源片走（25/30/60 都有）  48000 stereo
    解说片   30fps                          24000 mono
    采访片   25fps                          48000 stereo

`concat` 差一项就静默丢流（成片从某一秒起没声音，而 ffmpeg 不报错）。
所以中间那一步转码省不掉——它换来的是**帧率能跟着源片走**。

### 比省时间更硬的理由：一致性

现在每条片子都重新跑一次 edge-tts，而**服务端合成的输出可能有微小差异**。
「强化记忆」靠的正是每条片子结尾**一模一样**的那一下——母版把这件事从
「每次重新合成，希望它一样」变成「就是同一份文件」。

### 母版的参数为什么这么定

按**上界**取，因为转码只能往下走不能往上补：

- **60fps**：三条线里最高的那档（剪辑片的 60fps 源片）。母版低于目标帧率的话
  转上去是插帧，动效会顿
- **48000 stereo**：音频同理，降采样无损失，升采样补不出信息
- **crf 12**：母版是中间产物，画质要留够余量给下游那次转码

体积 0.5 MB，进仓库无压力。

用法（改了版式或口播之后重跑一次，把产物提交上去）：

    PYTHONPATH=src python3 tools/build_outro_master.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennislive import localca  # noqa: E402
from tennislive.render.webcards import _chromium_executable  # noqa: E402
from tennislive.video import outro_page  # noqa: E402

# 母版落在 assets 里，跟着仓库走。**不放 output/**——那儿是按日期分的产物，
# 而母版是**资产**：它不属于哪一天，而且 CI 的稀疏检出把 output 挡在外面。
MASTER = ROOT / "assets/brand/outro_master.mp4"

# 按上界取，见模块文档。
MASTER_FPS = 60
MASTER_AUDIO_RATE = "48000"
MASTER_CRF = "12"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=MASTER)
    args = ap.parse_args()

    localca.trust_local_proxy_ca(verbose=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    work = args.out.parent / "_outro_master_work"
    work.mkdir(parents=True, exist_ok=True)

    clip = outro_page.build_with_voice(
        work, chromium=_chromium_executable(), dest=args.out,
        fps=float(MASTER_FPS), audio_rate=MASTER_AUDIO_RATE,
        preset="slow", crf=MASTER_CRF, audio_bitrate="192k", audio_channels=2,
        # **必须现渲。** 不带它的话母版在时会从旧母版转码——改了口播重跑这个
        # 工具，出来的还是旧文案，而且不报错（`--out` 指到别处时）。
        fresh=True,
    )

    for junk in work.glob("*"):
        if junk.is_file():
            junk.unlink()
        else:
            for f in junk.glob("*"):
                f.unlink()
            junk.rmdir()
    work.rmdir()

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=duration,r_frame_rate,width,height", "-of", "csv=p=0", str(clip)],
        check=True, capture_output=True, text=True).stdout.strip()
    size = clip.stat().st_size / 1048576
    print(f"[母版] {clip.relative_to(ROOT)}  {dur}  {size:.2f} MB")
    print("[母版] 提交上去，之后每条片子从它转码（约 1.9 秒），不再各渲一遍")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
