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

体积 1.4 MB 上下（2026-09-27 重出后 1.37 MB），进仓库无压力。

用法（改了版式或口播之后重跑一次，把产物提交上去）：

    PYTHONPATH=src python3 tools/build_outro_master.py

### 只改画面、不改口播：`--keep-voice`

    PYTHONPATH=src python3 tools/build_outro_master.py --keep-voice

画面照样**现渲**（Chromium 渲四层 ＋ 动效滤镜，不从旧母版转码），口播那一轨
**原样搬**现有母版的（`-c copy`，逐字节不动），帧数也按旧母版对齐、对不上就报错。

为什么要这一档：上面那条「一致性」说的是**每条片子结尾一模一样的那一下**。
改的只是动效（2026-09-27 修推镜抖动，UI/VI 评审 WP7）时重合一遍 edge-tts，
等于为了画面去赌服务端这次合出来的声音和上次一样——没必要赌。
⚠️ **改了 `NARRATION` / `TAGLINE` 就不许用它**：那时旧母版里的口播本身就是
过期的，必须走默认那条（现合口播）。
"""
from __future__ import annotations

import argparse
import shutil
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


def _probe(path: Path, entry: str) -> str:
    """一个流字段（`r_frame_rate` / `nb_read_packets` ……），逐个问，不靠 csv 列序。"""
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", f"stream={entry}", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()


def rebuild_picture_keep_voice(master: Path, work: Path) -> Path:
    """`--keep-voice`：画面现渲，口播轨从现有母版 `-c copy` 搬过来。

    ⚠️ 画面**不许**从旧母版转码（模块文档「必须现渲」那条）——`render_clip` 不给
    `layers` 就会现起 Chromium 渲四层，这儿正是这么调的。
    ⚠️ 片长按旧母版的**帧数**对齐：`render_clip` 拿秒数算帧（`-t` 三位小数），
    重渲出来的帧数和旧母版对不上就报错，不静默出一份长短不同的母版。
    """
    if not master.is_file():
        raise SystemExit(f"--keep-voice 要沿用现有母版的口播，而 {master} 不存在")
    old = work / "_old_master.mp4"
    shutil.copy2(master, old)                # --out 就是旧母版本身：先挪开再写
    rate, frames = _probe(old, "r_frame_rate"), _probe(old, "nb_read_packets")
    num, den = (rate.split("/") + ["1"])[:2]
    fps = float(num) / float(den)
    if round(fps) != MASTER_FPS:
        raise SystemExit(f"旧母版是 {rate} fps，不是 {MASTER_FPS}——别沿用它，走默认那条现渲")
    picture = work / "_picture.mp4"
    # +1e-6：247/60 在浮点里是 4.11666…，`motion_filter` 拿 `int(秒数×帧率)` 算推镜走完
    # 的帧数，不垫这一下会算成 246（推镜比老母版早一帧走满）；`-t` 照旧印成 4.117
    outro_page.render_clip(
        work, int(frames) / fps + 1e-6, fps_expr=str(MASTER_FPS), fps=float(MASTER_FPS),
        chromium=_chromium_executable(), dest=picture,
        audio_rate=MASTER_AUDIO_RATE, preset="slow", crf=MASTER_CRF,
        audio_bitrate="192k", audio_channels=2)
    got = _probe(picture, "nb_read_packets")
    if got != frames:
        raise SystemExit(f"重渲的画面 {got} 帧，旧母版 {frames} 帧——片长对不上，没写母版")
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(picture), "-i", str(old),
         "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", str(master)],
        check=True)
    return master


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=MASTER)
    ap.add_argument("--keep-voice", action="store_true",
                    help="只重渲画面，口播原样沿用 --out 那份现有母版的音轨"
                         "（改动效/版式、没改口播时用）")
    args = ap.parse_args()

    localca.trust_local_proxy_ca(verbose=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    work = args.out.parent / "_outro_master_work"
    work.mkdir(parents=True, exist_ok=True)

    # ⚠️ 工作目录**失败了也要清**：它就在 `assets/brand/` 底下，`--keep-voice` 帧数对不上
    # 报错时里面躺着 `_old_master.mp4`（旧母版的一份 1.4 MB 拷贝）和 `_picture.mp4`，
    # 下一次 `git add -A` 会把它们一起提交上去。
    try:
        if args.keep_voice:
            clip = rebuild_picture_keep_voice(args.out, work)
        else:
            clip = outro_page.build_with_voice(
                work, chromium=_chromium_executable(), dest=args.out,
                fps=float(MASTER_FPS), audio_rate=MASTER_AUDIO_RATE,
                preset="slow", crf=MASTER_CRF, audio_bitrate="192k", audio_channels=2,
                # **必须现渲。** 不带它的话母版在时会从旧母版转码——改了口播重跑这个
                # 工具，出来的还是旧文案，而且不报错（`--out` 指到别处时）。
                fresh=True,
            )
    finally:
        shutil.rmtree(work, ignore_errors=True)

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=duration,r_frame_rate,width,height", "-of", "csv=p=0", str(clip)],
        check=True, capture_output=True, text=True).stdout.strip()
    size = clip.stat().st_size / 1048576
    # `--out` 指到仓库外时 `relative_to` 会抛 ValueError（母版已经写好了，却在打印这一行炸掉）。
    # ⚠️ 两边都要 `resolve()`：在仓库根下跑 `--out assets/brand/outro_master.mp4`（相对路径）时
    # `clip.resolve()` 在 ROOT 底下，而 `clip` 本身是相对的，`clip.relative_to(ROOT)` 照样抛。
    shown = clip.resolve().relative_to(ROOT) if clip.resolve().is_relative_to(ROOT) else clip
    print(f"[母版] {shown}  {dur}  {size:.2f} MB")
    print("[母版] 提交上去，之后每条片子从它转码（约 1.9 秒），不再各渲一遍")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
