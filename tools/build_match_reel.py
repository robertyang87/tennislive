#!/usr/bin/env python3
"""把一条官方集锦剪成 3:4 的竖版短片：只留高光、中文解说、字幕、封面。

两段式，因为**选段必须靠眼睛**：

    probe   下载源片 → 出场景切点 + 一张缩略图墙（带时间码）→ 提交进仓库
            人（或我）看着这张图挑出要哪几段、每段横向裁在哪儿
    render  按 spec.json 剪 → 裁 3:4 → 合成中文解说 → 烧字幕 → 加封面 → 成片

## 为什么必须在 GitHub Actions 上跑

**沙箱的 IP 被 YouTube 挡了**：yt-dlp 拿得到清单和格式表（走 android_vr 的
player API），一取媒体就 403；用真 Chromium 打开播放页，页面直接是
「Our systems have detected unusual traffic from your computer network」，
`playabilityStatus` = `UNPLAYABLE`。这不是「视频不存在」，是**这台机器不让下**
——又一次「空结果先自证是真空」。edge-tts 同理，本地取不到。

## 裁剪：横向裁到 3:4，不是加模糊边

1920×1080 裁成 3:4 就是 **810×1080**，再放大到 1080×1440。网球转播的主机位
在底线后方架高，球场是个左右对称的梯形，两个人大部分时间都在画面中间三分之一
里——所以中间裁得住。裁掉的是两侧的双打边线外沿和看台。

**每一段的横向中心单独给**（`cx`，0~1 的比例）。防的是那种一方跑到边线外
接球的镜头：整段用一个中心会把人裁掉半个身子。挑段的时候看着缩略图墙定。

## 慢在哪，要量出来

render 每一步都记时间，末尾按耗时排一张表（`report_timings()`）。这条流水线
一度在 runner 上跑七分半，我照着直觉猜是 `-preset slow` 太狠——量出来第一名
是**每段都从第 0 秒解码整条源片**（`-ss` 放在 `-i` 后面）。同一段 19.2s → 6.2s，
而且那个写法还让跟踪的 `sendcmd` 全部空放（见 `cut_segment`）。

四核沙箱上、67 秒素材、十一段（无旁白，本地取不到 TTS）：

    改前 318.2s                      改后 142.4s
      分段编码 184.1s  57.9%           烧字幕+成片 71.7s  50.3%
      烧字幕+成片 69.8s 21.9%          分段编码   59.5s  41.8%
      跟踪抽帧  53.1s  16.7%           跟踪抽帧    5.5s   3.8%

外加混音那一步（要有旁白才走到，单独量的）20.3s → 1.35s：它产出的是个 m4a，
却在默认参数下把整条画面重编了一遍。

**成片那一步（preset slow / crf 18）一个字没动**——省时间要从中间产物和重复
解码上省，不能从最后交出去的那一份上省。

## 字幕位置沿用解说片那一套

`explainer.py` 里那组常量（上锚、`MarginV=1524`、左右各 150px、字号 68）是
量真成片量出来的：躲开小红书/抖音底部的文案区与 home 条，也躲开右侧那列
点赞收藏评论。这里直接 import 过来，不重新拍一组数字。

用法：

    # 第一步：下载 + 出缩略图墙（在 Actions 上）
    python tools/build_match_reel.py probe --url "https://www.youtube.com/watch?v=..." \\
        --outdir output/2026-07-28/reel/nishikori-shang

    # 第二步：按 spec 出成片
    python tools/build_match_reel.py render --spec specs/nishikori-shang.json \\
        --outdir output/2026-07-28/reel/nishikori-shang
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.video.explainer import (  # noqa: E402
    CARD_H,
    CARD_TOP,
    VIDEO_H as _EXPLAINER_H,
    VIDEO_W,
    _BAND_COLOR,
    _ASS_MARGIN_H,
    _ASS_MARGIN_V,
    readable,
    subtitle_cues,
    write_subtitles,
)
from tennislive.video.subtitle_text import drop_punctuation  # noqa: E402
from tennislive.video.audio import (  # noqa: E402
    AVSegment,
    ConcatFiltergraph,
    audio_qa_for_graph,
    concat_av_filter,
)

# **成片帧率跟着源片走，不要硬定 30。** 这份华盛顿的官方集锦是 25 fps，
# 而滤镜链里写死 `fps=30`：25 和 30 的比是 5:6，于是每 5 帧就复制一帧，
# 一秒卡五次。更糟的是它和横摇**不同频**——画面内容 25 Hz 前进，裁切窗口
# 30 Hz 平移，同一帧里两种节奏，看着就是"顿一下、飘一下"。
# 复制出来的帧还查不出来：裁切位置每帧都在变，两帧的**像素**并不相同
# （2099 帧里逐帧比对，完全相同的 0 帧），只有比源片和成片的帧率才看得出。
# 这是「兜底和默认值出事的时候不吭声」的又一例：`fps=` 从不报错，只是默默补帧。
FPS = 30            # 兜底值；render 开跑时按源片改写（见 resolve_fps）
FPS_EXPR = "30"     # 传给 ffmpeg 的那份，保留分数形式（29.97 是 30000/1001）
# 3:4 的裁切窗口。**按源片实际高度算，不是写死 1080**——`resolve_crop()` 在
# render 开跑时改写这两个值。原来这里写死 1080，而源片有时只下到 360p，
# `crop=810:1080` 直接被 ffmpeg 拒掉；那句「源片不是 1080 高，裁剪按等比换算」
# 的提示只打印，从来没真的换算过（注释和行为对不上，跑起来才炸）。
CROP_H = 1080
CROP_W = 810
# 裁切窗口在源片里的纵向落点。横幅源片恒为 0（窗口高度就是源片高度，没得挪）；
# **竖版源片才用得上**——那种源片宽度顶满、要在高度上取一段，见 `resolve_crop`。
CROP_Y = 0
# **成片是 3:4（1080×1440），不是 9:16。** 定这个画幅的理由是「尽可能多保住主体」：
#
# - 小红书的视频**静态展示就是 3:4**。9:16 的成片在信息流里会被裁掉上下两条，
#   海报的台头、比分、赛事行首当其冲——而那几行正是让人看懂这是哪一场的东西
# - 从 1920×1080 的源片里取窗口，9:16 只有 **608px 宽**，3:4 有 **810px 宽**，
#   多 33% 的球场。球飞到两边出画、窗口中心偏一点就丢半个场，这两件事同时缓解
#
# 代价是抖音/视频号播放时不铺满，上下留黑边——两边权衡下来，
# 主体完整比铺满更要紧。解说片那条线仍是 9:16 画布 + 3:4 卡（`_EXPLAINER_H`），
# 两条线的画幅是分开的，别互相牵动。
VIDEO_H = CARD_H                    # 1080 宽下 3:4 的高 = 1440
# 字幕的上锚要跟着画布重算，不能沿用解说片那个 1524：那是在 1920 画布里、
# 卡底（1680）往上 156px。这里整幅画布就是那张卡，所以同样是「卡底往上 156」，
# 换算过来是 1440-156=1284。**保的是同一个物理位置**——量出来的那组数没变。
_REEL_MARGIN_V = VIDEO_H - (CARD_TOP + CARD_H - _ASS_MARGIN_V)
# **源片自己烧了记分条时，字幕要让开它。**
#
# 以前没撞过是因为运气：16:9 的转播源片把记分条放在左下，而 3:4 的窗口只取中间
# 42% 宽，整块被裁掉了。Tennis TV 的**竖版**短片不一样——画幅本来就是竖的，
# 记分条烧在左下，量出来占 y 1281~1439，而字幕上锚正好是 1284：两层白字叠在
# 一起，四帧抽出来帧帧都中。
#
# 这个数是**源片的属性**，不是画幅的属性，所以放在 spec 里（`subtitle_top`），
# 默认沿用 `_REEL_MARGIN_V`。给了就把字幕整体抬到记分条上沿之上。
# **别改成自动检测**：记分条的位置、颜色、是否存在都随播出方变，检测不到时
# 会悄悄退回原位——又是「兜底出事的时候不吭声」。让写 spec 的人量一次、写死。
#
# **这是特例，不是新默认**（账号所有者定的）：只有自带记分条的源片才写这个
# 字段，版式本身照旧。判据在 `test_源片自己烧了记分条时字幕要让开` 里两头钉着
# ——默认值不许改，别的 spec 不许跟着写。
# 低于这个高度的源片不值得做成片：裁成 3:4 再放到 1080 宽是放大好几倍。
MIN_SOURCE_H = 700
# 封面**没有配音时**停多久——「赛场之上」走的就是这一档（它不给封面配音）。
# **2.6 秒太长**：账号所有者「好多人以为是图片不是视频」。封面同时是信息流里的
# 缩略图，点进来的人已经看过它了；画面迟迟不动，第一反应是「这是张图」，划走。
# 1.2 秒够读完两行钩子加一行比分，又能让第一个回合立刻接上。
#
# 「网球有故事」那条线不一样：它给封面配音，封面停多久跟着配音走（`cover_length`），
# 这个数用不上。**两条线别互相牵动**——判据见 `test_封面跟着配音走只给网球有故事`。
COVER_SECONDS = 1.2
# 说完之后留的那口气。贴着最后一个字切，末尾辅音会被 concat 的边界削掉。
COVER_TAIL = 0.25
# 封面海报**要进仓库**：推送正文的第一屏就是它（布局照着知识解说那条推送来），
# 微信里要能直接看到这是谁打谁、几比几。以前它叫 `_cover.jpg`、下划线开头，
# 被"丢掉中间物"那步删掉了——于是推送里一张图都没有，只有两个按钮。
POSTER_NAME = "poster.jpg"
# contain 模式横向保留多少。0.62 → 窗口 1190px，球员落在画面 19%~81% 之间都还在，
# 缩到 1080 宽后有 980 高，占屏高一半——比整幅铺进来的 608 高大了六成。
CONTAIN_KEEP = 0.62
# 原声压到多少。留一点现场声（球声、观众），但不能盖过中文解说。
BED_LOUD = 0.72   # 没人说话时的现场声
# **每一段的音轨都要压到同一个采样率**。`concat` + `-c copy` 只认第一个文件的
# 流参数：封面那段的 anullsrc 是 48k，而各分段跟着源片走 44.1k，于是 44.1k 的
# AAC 帧被当成 48k 播——整条现场声快 8.8%，音轨在画面还剩 5.7 秒时就播完了
# （69.9s 的画面配 64.3s 的音轨，64.3/69.9 = 0.9196 ≈ 44100/48000）。
# 它不报错，ffprobe 也只写着「48000」，只有把两个时长摆在一起才看得出来。
AUDIO_RATE = "48000"
# **交付片要看独立的视频/音频流，不看容器总时长。** MP4 的 format.duration
# 正常不代表两条流一样长：旁白钥匙提前 EOF 时，容器照样跟着视频写到最后，
# 音轨却已经没了。最终字幕、sidechain 和 amix 全封装完之后再过这道闸。
FINAL_AV_MAX_DELTA_SECONDS = 0.05
# 分段和封面都是**中间产物**：拼完之后整片还要以 crf 18 重编一次。在这里编到
# crf 17/preset slow，等于把画质编进一个马上要被重编的文件里。成片那一步的参数
# 没有跟着降。
PART_PRESET = "medium"
PART_CRF = "20"

# 成片那一步的参数。**不要为了压体积动它们。**
#
# 账号所有者 2026-07-29 定的：「不要舍弃画质，没有硬性要求 20mb」。
#
# 20 MB 是 jsDelivr 的单文件上限，超了就退回 raw。那**不是一条要满足的指标**——
# 这条线从来没有一条片子进得去：按实测码率（3315 / 3517 / 3779 kb/s 三条几乎
# 一样）算，20 MB 只够 44 秒，而已发的 69 秒和 83 秒那两条是 28.8 和 32.9 MB。
# 要真挤进去得把 crf 推到 23 上下，那是拿画质换一条通道，方向反了。
#
# 片长可以商量（大威那条从 2 分 38 秒剪到 1 分 35 秒，59 → 42.6 MB），
# **画质不商量**。判据落在 test_成片的编码参数不许为了压体积往下调。
FINAL_PRESET = "slow"
FINAL_CRF = "18"


class ReelError(RuntimeError):
    pass


# 计时 ---------------------------------------------------------------------
# 「慢在哪」和「做完了」是同一类问题：**要量，不要猜**。之前这条 render 在
# runner 上跑七分半，我以为瓶颈在 `-preset slow`；量出来第一名是别的（每段都
# 从头解码整条源片）。所以每一步都记时间，最后按耗时排序打一张表——下次谁再
# 想优化，先看这张表，别照着直觉改。
_TIMINGS: list[tuple[str, float]] = []


@contextmanager
def stage(name: str):
    started = time.perf_counter()
    try:
        yield
    finally:
        spent = time.perf_counter() - started
        _TIMINGS.append((name, spent))
        print(f"    [耗时] {name} {spent:.2f}s", flush=True)


def report_timings() -> None:
    if not _TIMINGS:
        return
    total = sum(s for _, s in _TIMINGS)
    # 同名的步骤（每段切片、每段跟踪）合起来看，不然十一行淹掉重点
    buckets: dict[str, tuple[int, float]] = {}
    for name, spent in _TIMINGS:
        key = name.split("#")[0].strip()
        count, acc = buckets.get(key, (0, 0.0))
        buckets[key] = (count + 1, acc + spent)
    print(f"\n=== 耗时明细（合计 {total:.1f}s，{os.cpu_count()} 核）===")
    for key, (count, acc) in sorted(buckets.items(), key=lambda kv: -kv[1][1]):
        share = acc / total * 100 if total else 0
        times = f" ×{count}" if count > 1 else ""
        print(f"  {acc:7.1f}s  {share:5.1f}%  {key}{times}")


def run(*args: str, quiet: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-2500:]
        raise ReelError(f"命令失败 {args[0]}：\n{' '.join(args)[:400]}\n{tail}")
    if not quiet:
        print(proc.stdout)
    return proc


def probe_duration(path: Path) -> float:
    out = run("ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", str(path)).stdout.strip()
    return float(out)


def _has_audio(path: Path) -> bool:
    out = run("ffprobe", "-v", "error", "-select_streams", "a",
              "-show_entries", "stream=index", "-of", "csv=p=0", str(path)).stdout
    return bool(out.strip())


def _probe_av_stream_timing(path: Path) -> dict[str, float]:
    """Read coherent start/duration/end metrics for both final streams."""
    raw = run(
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,start_time,duration", "-of", "json", str(path),
    ).stdout
    streams = json.loads(raw).get("streams") or []
    timing: dict[str, float] = {}
    for stream in streams:
        kind = stream.get("codec_type")
        start = stream.get("start_time")
        duration = stream.get("duration")
        if (kind in {"video", "audio"}
                and start not in {None, "N/A"}
                and duration not in {None, "N/A"}):
            start_number = float(start)
            duration_number = float(duration)
            if not math.isfinite(start_number) or not math.isfinite(duration_number):
                continue
            timing[f"{kind}_start_seconds"] = start_number
            timing[f"{kind}_duration_seconds"] = duration_number
            timing[f"{kind}_end_seconds"] = start_number + duration_number
    required = {
        f"{kind}_{field}_seconds"
        for kind in ("video", "audio")
        for field in ("start", "duration", "end")
    }
    missing = sorted(required - timing.keys())
    if missing:
        raise ReelError(
            f"最终成片 {path.name} 读不到独立的起点、时长和终点："
            + ", ".join(missing)
        )
    return timing


def _audit_final_delivery(final: Path, *, declared_duration: float) -> Path:
    """Promote the join plan QA to a measurement of the delivered MP4.

    ``_join_parts`` can prove that its prepared intermediate kept the declared
    timeline.  It cannot prove that the later TTS/sidechain/amix/subtitle mux
    kept the audio alive.  This gate therefore runs only after the final MP4
    exists, retains the original join rows, and measures the two delivered
    streams rather than ``format.duration``.
    """
    if not math.isfinite(declared_duration) or declared_duration <= 0:
        raise ReelError(f"最终成片声明时长不合法：{declared_duration!r}")
    qa_path = final.parent / "audio-qa.json"
    if not qa_path.exists():
        raise ReelError("最终成片审计前缺 audio-qa.json，转场计划没有落盘")
    try:
        report = json.loads(qa_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReelError(f"读不到转场计划 {qa_path}：{exc}") from exc
    if not isinstance(report.get("joins"), list):
        raise ReelError("audio-qa.json 缺 joins，不能丢掉转场计划只写最终时长")

    timing = _probe_av_stream_timing(final)
    video_start = timing["video_start_seconds"]
    audio_start = timing["audio_start_seconds"]
    video_duration = timing["video_duration_seconds"]
    audio_duration = timing["audio_duration_seconds"]
    video_end = timing["video_end_seconds"]
    audio_end = timing["audio_end_seconds"]
    start_delta = abs(video_start - audio_start)
    av_delta = abs(video_duration - audio_duration)
    end_delta = abs(video_end - audio_end)
    programme_duration = max(video_duration, audio_duration)
    declared_delta = abs(programme_duration - declared_duration)
    problems: list[str] = []
    if start_delta > FINAL_AV_MAX_DELTA_SECONDS:
        problems.append(
            f"最终 A/V 起点时差 {start_delta:.3f}s > "
            f"{FINAL_AV_MAX_DELTA_SECONDS:.3f}s"
        )
    if end_delta > FINAL_AV_MAX_DELTA_SECONDS:
        problems.append(
            f"最终 A/V 终点时差 {end_delta:.3f}s > "
            f"{FINAL_AV_MAX_DELTA_SECONDS:.3f}s"
        )
    if av_delta > FINAL_AV_MAX_DELTA_SECONDS:
        problems.append(
            f"最终 A/V 时长差 {av_delta:.3f}s > "
            f"{FINAL_AV_MAX_DELTA_SECONDS:.3f}s"
        )
    if declared_delta > FINAL_AV_MAX_DELTA_SECONDS:
        problems.append(
            f"最终总时长相对声明偏差 {declared_delta:.3f}s > "
            f"{FINAL_AV_MAX_DELTA_SECONDS:.3f}s"
        )

    report.update({
        "stage": "final_delivery",
        "status": "fail" if problems else "pass",
        "final_declared_duration_seconds": round(declared_duration, 6),
        "final_video_start_seconds": round(video_start, 6),
        "final_audio_start_seconds": round(audio_start, 6),
        "final_video_duration_seconds": round(video_duration, 6),
        "final_audio_duration_seconds": round(audio_duration, 6),
        "final_video_end_seconds": round(video_end, 6),
        "final_audio_end_seconds": round(audio_end, 6),
        "final_programme_duration_seconds": round(programme_duration, 6),
        "av_start_delta_seconds": round(start_delta, 6),
        "av_duration_delta_seconds": round(av_delta, 6),
        "av_end_delta_seconds": round(end_delta, 6),
        # Backward-compatible alias used by older QA consumers.
        "av_delta_seconds": round(av_delta, 6),
        "final_declared_delta_seconds": round(declared_delta, 6),
        "max_av_delta_seconds": FINAL_AV_MAX_DELTA_SECONDS,
        "final_delivery_problems": problems,
    })
    qa_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if problems:
        raise ReelError("最终成片音频审计失败：" + "；".join(problems))
    return qa_path


def resolve_crop(source_w: int, source_h: int, crop_y: int | None = None) -> None:
    """在源片里取**最大的 3:4 窗口**，太小的源片直接拒掉。

    **下到 360p 也算「下载成功」**——yt-dlp 退到低画质那一档时不会报错，
    看起来一切正常，直到 `crop=810:1080` 撞上 640×360 的源片才炸在第一段切片上
    （run 30412173035）。所以这里既换算、也把不合格的源片挡在开跑前，
    别等渲了一半才发现。

    **两种朝向都要认。** 原来只按高度算，隐含「源片一定比 3:4 宽」——
    转播集锦确实都是 16:9。但 Tennis TV 的**竖版短片**是 1180×2114，
    照旧算出来 `CROP_W = 1584 > 1180`，`crop` 直接被 ffmpeg 拒掉。
    竖版源片要反过来：宽度顶满，在高度上取一段。

    `crop_y` 是竖版源片的纵向落点，spec 里给。**不给就居中，而居中往往是错的**
    ——手机录屏的顶上压着进度条、标题、关闭叉和台标，底下压着上滑箭头，
    居中会把台标留在画面里。黄泽林那条量出来是 345（渲了 310/345/380 三档比
    出来的：310 台标还在、记分条被切掉一行，380 白丢 35px）。
    """
    global CROP_H, CROP_W, CROP_Y
    if source_h < MIN_SOURCE_H:
        raise ReelError(
            f"源片只有 {source_w}×{source_h}，太小了（要求高 ≥ {MIN_SOURCE_H}）。"
            "裁成 3:4 再放到 1080 宽是放大好几倍，成片糊得没法看。"
            "多半是 yt-dlp 退到了低画质那一档——换 player client 重下，"
            "或者换一个能拿到 720p 以上的源。"
        )
    if source_w * 4 >= source_h * 3:          # 比 3:4 宽：高度顶满
        CROP_H = source_h // 2 * 2
        CROP_W = int(round(CROP_H * 3 / 4)) // 2 * 2
        CROP_Y = 0
        shape = "横幅"
    else:                                      # 比 3:4 竖：宽度顶满
        CROP_W = source_w // 2 * 2
        CROP_H = int(round(CROP_W * 4 / 3)) // 2 * 2
        default_y = (source_h - CROP_H) // 2 // 2 * 2
        CROP_Y = default_y if crop_y is None else int(crop_y) // 2 * 2
        if CROP_Y < 0 or CROP_Y + CROP_H > source_h:
            raise ReelError(
                f"crop_y={crop_y} 超出源片：窗口 {CROP_W}×{CROP_H} 放在 y={CROP_Y}，"
                f"下沿 {CROP_Y + CROP_H} 超过源片高度 {source_h}。")
        shape = f"竖版，纵向落点 y={CROP_Y}" + (
            "（居中，spec 没给 crop_y）" if crop_y is None else "")
    print(f"[裁切] 源片 {source_w}×{source_h} → 3:4 窗口 {CROP_W}×{CROP_H}（{shape}）")


def resolve_fps(path: Path) -> tuple[str, float]:
    """成片帧率 = 源片帧率。返回 (给 ffmpeg 的分数式, 浮点值)。

    分数式要原样传给 `fps=`：29.97 写成 `30000/1001` 才是准的，写 `29.97`
    会一点点漂。离谱的值（<10 或 >60）不认，退回 30 并说出来。
    """
    raw = run("ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=r_frame_rate",
              "-of", "default=nw=1:nk=1", str(path)).stdout.strip()
    try:
        num, den = (raw.split("/") + ["1"])[:2]
        value = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        value = 0.0
    if not 10.0 <= value <= 60.0:
        print(f"[fps] 源片报的帧率是 {raw!r}，不合常理，退回 30")
        return "30", 30.0
    print(f"[fps] 成片跟着源片走：{raw} = {value:.3f}")
    return raw, value


def fetch_captions(url: str, outdir: Path) -> Path | None:
    """把自动字幕连时间码拉下来，写成 `captions.txt`（`秒数<TAB>这一句`）。

    **为什么要它**：采访素材靠缩略图墙是选不了段的——一整条五分钟的访谈，
    每一帧都是一个人在说话，画面上分不出他这一秒在讲什么。要用他的原声，
    就得知道那句话落在第几秒。

    沙箱拿不到（timedtext 对这台机器返回 **0 字节的 200**，看起来和「这条片子
    没有字幕」一模一样——又一次「空结果先自证是真空」：播放页里明明列着
    `asr` 轨）。runner 的 IP 拿得到，所以收在 probe 里。

    拿不到就返回 None，**不影响 probe 的其余产物**：字幕是锦上添花，
    缩略图墙和切点才是这一步的主产物。
    """
    binary = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    if not binary or ("youtube.com" not in url and "youtu.be" not in url):
        return None
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
    # **`-o` 要带 `%(ext)s`。** 写成一个没有扩展名的裸前缀时，yt-dlp 落盘的
    # 名字由它自己拼，我这边靠 glob 去猜——猜错就是「拿不到字幕」，
    # 和「这条片子没有字幕」长得一模一样。用惯例写法，名字就不用猜了。
    tmpl = str(outdir / "_subs.%(ext)s")
    notes: list[str] = []
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, *YTDLP_BASE, "--skip-download",
             "--write-auto-subs", "--write-subs",
             "--sub-langs", "en.*,en", "--sub-format", "json3/vtt/best",
             "-o", tmpl, url, *cookies, *extra],
            capture_output=True, text=True)
        got = sorted(outdir.glob("_subs*.json3")) + sorted(outdir.glob("_subs*.vtt"))
        if got:
            print(f"[字幕] {label} 拿到 {got[0].name}")
            break
        why = (proc.stderr or proc.stdout or "").strip()
        notes.append(f"### {label}\n{why[-1200:]}")
        print(f"[字幕] {label} 没拿到：{why[-160:]}")
    else:
        # **把失败原因落进产物里。** 「所有 client 都没拿到」有好几种成因
        # （这条片子真没字幕 / 这台机器被挡 / 我的参数写错），只印在日志里
        # 就得翻 run 才看得见，而 run 的日志翻起来很贵。写成文件跟着提交，
        # 下次一眼就知道该改参数还是该换路子。
        (outdir / "captions_debug.txt").write_text(
            "拿不到自动字幕，各 client 的原因如下：\n\n" + "\n\n".join(notes),
            encoding="utf-8")
        print("[字幕] 所有 client 都没拿到自动字幕 → captions_debug.txt")
        return None
    lines = _caption_lines(got[0])
    if not lines:
        return None
    dest = outdir / "captions.txt"
    dest.write_text("".join(f"{t:.2f}\t{s}\n" for t, s in lines), encoding="utf-8")
    for f in got:
        f.unlink(missing_ok=True)
    print(f"[字幕] {len(lines)} 句 → {dest.name}")
    return dest


def _caption_lines(path: Path) -> list[tuple[float, str]]:
    """json3 或 vtt → [(起始秒, 这一句)]。两种都认，因为 yt-dlp 给哪种看运气。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json3":
        out = []
        for event in json.loads(text).get("events", []):
            body = "".join(s.get("utf8", "") for s in event.get("segs") or ())
            body = " ".join(body.split())
            if body:
                out.append((event.get("tStartMs", 0) / 1000, body))
        return out
    out, stamp = [], None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"(\d+):(\d+):(\d+)[.,](\d+)\s*-->", line)
        if m:
            h, mi, s, ms = (int(g) for g in m.groups())
            stamp = h * 3600 + mi * 60 + s + ms / 1000
        elif line and stamp is not None and "-->" not in line:
            body = " ".join(re.sub(r"<[^>]+>", "", line).split())
            if body and (not out or out[-1][1] != body):
                out.append((stamp, body))
    return out


def probe_size(path: Path) -> tuple[int, int]:
    out = run("ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=width,height",
              "-of", "csv=p=0:s=x", str(path)).stdout.strip()
    w, h = out.split("x")[:2]
    return int(w), int(h)


# --------------------------------------------------------------------------
# probe：下载 + 缩略图墙
# --------------------------------------------------------------------------

# YouTube 对机房 IP 一律「Sign in to confirm you're not a bot」——沙箱和
# GitHub 托管 runner 都中招（2026-07-28 实测两边都是这句）。不同的 player
# client 走的是不同的接口，被挡的程度不一样，所以按梯子一档档试，**每一档的
# 报错都打出来**：一句笼统的「下载失败」没法区分「这条视频不存在」「这台机器
# 被挡了」「格式选错了」。
#
# `web` / `mweb` / `tv` 这几档要 GVS PO token 才放行，装了 bgutil 的
# provider 之后 yt-dlp 会自己去取——所以有 provider 的时候把它们排在前面，
# 没有的话它们会最先失败、白等一轮，就排到后面去。
_POT_FIRST = [
    ("web(+POT)", ["--extractor-args", "youtube:player_client=web"]),
    ("mweb(+POT)", ["--extractor-args", "youtube:player_client=mweb"]),
    ("tv(+POT)", ["--extractor-args", "youtube:player_client=tv"]),
]
_PLAIN = [
    ("默认", []),
    ("android_vr", ["--extractor-args", "youtube:player_client=android_vr"]),
    ("tv_simply", ["--extractor-args", "youtube:player_client=tv_simply"]),
    ("web_embedded", ["--extractor-args", "youtube:player_client=web_embedded"]),
    ("android+ios", ["--extractor-args", "youtube:player_client=android,ios"]),
]


# **编码是偏好，不是硬条件。** 抽成常量是为了能测：判据原来靠在源码里
# 「从 `selector = ` 切到 `cookies: list[str]`」取一段字符串，而这两个记号
# 在文件里都不是唯一的——后来 `fetch_captions` 里也有一句 `cookies: list[str]`，
# 而且排在前面，那一刀切出来是**空串**，于是「不含 avc1」自动成立、
# 「含 h264」自动失败。**判据不该依赖它在文件里的位置。**
FMT_SELECTOR = "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"
FMT_SORT = "res:1080,fps,vcodec:h264,acodec:m4a"

# **每一次 yt-dlp 调用都要带上这几个**，所以抽出来共用。
# `--js-runtimes node` 是解 n challenge 的那一环：没有它，YouTube 的格式表
# 只剩故事板，报出来是「Only images are available」+「Requested format is
# not available」——看起来像「这条片子取不到」，其实是**这一次调用少带了一个
# 参数**。我给 `fetch_captions` 新写 yt-dlp 调用时正是这么漏的：同一个 job 里
# `download()` 明明下得动整条 294 秒的片子，字幕那条八个 client 全红。
# 这就是「加新能力就要同时改三处」的又一个变种——新调用没继承旧调用的前提。
YTDLP_BASE = ["--js-runtimes", "node"]


def _ladder() -> list[tuple[str, list[str]]]:
    if os.environ.get("YT_POT_PROVIDER", "").strip():
        return _POT_FIRST + _PLAIN
    return _PLAIN + _POT_FIRST


def download(url: str, dest: Path) -> Path:
    """取**最高清晰度**：先试 1080p 的 avc1（码率最高的那档），退到 bestvideo。

    `YT_COOKIES` 指向一个 cookies.txt 就带上——机房 IP 被挡的时候，
    一份登录过的 cookie 是唯一稳定的解。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"[skip] 已有 {dest}")
        return dest

    # 不是 YouTube 就是一个普通直链（网盘、赛事站…），curl 一下就完了。
    # 这条路是被逼出来的：YouTube 对这台机器和 runner 都封着，人只能自己下好
    # 传到网盘，再把直链给我们。
    if "youtube.com" not in url and "youtu.be" not in url:
        proc = subprocess.run(
            ["curl", "-sSL", "--fail", "-o", str(dest), url],
            capture_output=True, text=True)
        if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise ReelError(f"直链下载失败（{url[:90]}）：{(proc.stderr or '')[-300:]}")
        head = dest.read_bytes()[:64]
        if head[:15].lower().startswith(b"<!doctype html") or b"<html" in head.lower():
            dest.unlink(missing_ok=True)
            raise ReelError(
                "直链回的是 HTML 不是视频——网盘多半还是「仅限受邀者」，"
                "改成「知道链接的任何人」再试")
        print(f"[ok] 直链下到 {dest.stat().st_size / 1e6:.1f} MB")
        return dest

    binary = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    if not binary:
        raise ReelError("找不到 yt-dlp")
    # **编码是偏好，不是硬条件。** 原来第一档写死 `vcodec^=avc1` + `ext=m4a`：
    # YouTube 的高清一律是分离流，而 1080p 那几档常常是 VP9/AV1(webm)。某个
    # player client 列出来的格式表不全时（PO token / n challenge 那一环没打通
    # 就会这样），前两档全匹配不上，一路掉到 `best`——**YouTube 唯一预合成好的
    # 格式是 itag 18，正好 640×360**。于是「下载成功」和「只拿到 360p」成了同一
    # 件事，中间没有一步会报错，直到裁切那步才炸（run 30412173035）。
    #
    # 现在 `-f` 只管分辨率上限，编码偏好交给 `-S`：h264 排在前面（下游 ffmpeg
    # 处理最省事），但拿不到就用 VP9/AV1，而不是掉回 360p。
    selector, sort = FMT_SELECTOR, ["-S", FMT_SORT]
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
        print(f"[cookies] 用 {jar}")

    failures: list[str] = []
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, *YTDLP_BASE, "--no-warnings", "-f", selector,
             *sort, *cookies, *extra, "--merge-output-format", "mp4",
             "-o", str(dest), url],
            capture_output=True, text=True,
        )
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            # **下到了不等于下对了。** 某些 player client 只放得出 360p，
            # yt-dlp 照样 returncode 0、照样有文件——直到裁切那一步才炸
            # （run 30412173035：640×360 的源撞上 crop=810:1080）。
            # 所以在这儿量一次高度，不够就换下一档 client 接着试。
            width, height = probe_size(dest)
            if height < MIN_SOURCE_H:
                print(f"[低画质] {label} 只有 {width}×{height}，换下一档再试")
                failures.append(f"{label}: 只拿到 {width}×{height}")
                dest.unlink(missing_ok=True)
                continue
            print(f"[ok] {label} 下到了 {width}×{height}，"
                  f"{dest.stat().st_size / 1e6:.1f} MB")
            return dest
        reason = " | ".join(
            line.strip() for line in (proc.stderr or "").splitlines()
            if line.startswith("ERROR") or "403" in line
        )[:300] or (proc.stderr or "")[-300:]
        print(f"[fail] {label}: {reason}")
        failures.append(f"{label}: {reason}")
        dest.unlink(missing_ok=True)

    raise ReelError(
        f"{len(failures)} 种 player client 都下不下来（{url}）。逐条原因：\n  "
        + "\n  ".join(failures)
        + "\n\n如果全是 “Sign in to confirm you’re not a bot”，那是**这台机器的 IP "
        "被 YouTube 挡了**，不是视频的问题：把一份登录过的 cookies.txt 存成仓库 "
        "Secret（YT_COOKIES_TXT），工作流会写到文件并通过 YT_COOKIES 传进来。"
    )


def scene_changes(path: Path, threshold: float = 0.35) -> list[float]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path),
         "-filter:v", f"select='gt(scene,{threshold})',showinfo",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [round(float(m), 2)
            for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr or "")]


def contact_sheet(path: Path, outdir: Path, *, every: float = 2.0,
                  columns: int = 6, tile_w: int = 360, crop: str = "",
                  prefix: str = "contact") -> list[Path]:
    """每 `every` 秒抓一帧，烧上时间码，拼成几张缩略图墙。

    时间码必须烧进画面里——不然看图挑完段，还得数第几格再乘回去，数错一次
    整段就切偏了。

    `crop`（ffmpeg 的 `w:h:x:y`）先裁再缩。**整幅缩到 360 宽时记分条只有几个
    像素高，比分根本读不出来**——而定段落必须知道每一段是第几局第几分，
    否则「转折点在不在片子里」就只能靠猜。裁出记分条那一块单独拼一版，
    同样的机制，放大到能读。
    """
    outdir.mkdir(parents=True, exist_ok=True)
    frames = outdir / "frames"
    frames.mkdir(exist_ok=True)
    for old in frames.glob("*.jpg"):
        old.unlink()
    duration = probe_duration(path)
    stamps = [round(t, 2) for t in _frange(0.5, duration, every)]
    for index, t in enumerate(stamps):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
            "-vf", ((f"crop={crop}," if crop else "")
                    + f"scale={tile_w}:-2,"
                    f"drawtext=text='{t:.1f}s':x=8:y=8:fontsize=26:"
                    f"fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6"),
            "-q:v", "3", str(frames / f"f{index:03d}.jpg"))
    sheets: list[Path] = []
    per_sheet = columns * 5
    picked = sorted(frames.glob("*.jpg"))
    for n in range(0, len(picked), per_sheet):
        chunk = picked[n:n + per_sheet]
        listing = outdir / f"_sheet{n // per_sheet}.txt"
        listing.write_text("".join(f"file '{p.resolve()}'\n" for p in chunk),
                           encoding="utf-8")
        sheet = outdir / f"{prefix}_{n // per_sheet:02d}.jpg"
        rows = math.ceil(len(chunk) / columns)
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-filter_complex", f"tile={columns}x{rows}:padding=6:color=0x11221b",
            "-frames:v", "1", "-q:v", "3", str(sheet))
        listing.unlink()
        sheets.append(sheet)
    return sheets


def _frange(start: float, stop: float, step: float):
    value = start
    while value < stop:
        yield value
        value += step


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

@dataclass
class Segment:
    start: float
    end: float
    cx: float | None          # None = 没人量过，按整段运动质心的中位数自己定
    narration: str
    fit: str = "crop"
    track: bool = True
    # 这一段取自哪条源片（`spec["sources"]` 的键）。空＝主源。
    # 一条片子跨两场比赛时用得上：休伊特那条要「首胜吉隆」和「负于德米纳尔」
    # 两条官方集锦，故事才完整。
    source: str = ""
    # **这一段让当事人自己说**：现场采访的原声不配旁白，只上中文字幕。
    #
    # 为什么要单开一个字段而不是塞进 narration：narration 会合成一条中文语音
    # 压在原声上（而且 sidechaincompress 会把原声压下去），等于把他的话盖掉。
    # 而字幕那条线**只认 narration**——没有 narration 就没有字幕，于是
    # 「静音刷是默认状态」那条规矩下，这一段对多数人是彻底空白：
    # 听不懂英文的看不懂，静音的什么也没有。两头都丢。
    #
    # 所以 quote 是「不出声、只出字」的那一档：原声开到 BED_LOUD 不闪避
    # （这一段本来就没人配音），字幕按字数等比分配到整段时长上——拿不到
    # 词边界时本来就是这么退的，不完美，但绝不能因此整段没字幕。
    quote: str = ""
    # **角标**：一张 PNG 压在这一段的角上，画面不中断。
    #
    # 比整屏切一张静图好在**两件事同时在画面上**。休伊特那条讲的是儿子做了
    # 父亲的动作，而父亲那一下只有图没有影像（三条官方存档集锦都没拍到）。
    # 切成整屏静图要停三秒、把片子剪断；压在角上，儿子做那一下的同一帧里就
    # 有父亲做同一个动作——那句话本身就是这个画面，不用讲。
    # 账号所有者 2026-07-31：「把这个照片贴在他儿子做动作视频页面的角落里，
    # 这样就不用切画面了」。
    # 格式：`inset: {"image": 路径, "corner": "tl|tr|bl|br", "width": 0.34}`
    inset: dict | None = None

    @property
    def length(self) -> float:
        return round(self.end - self.start, 3)


def parse_segments(spec: dict, sources: dict, primary: str) -> list[Segment]:
    """spec 的 `segments` → `Segment` 列表，顺带把两条互斥/引用的规矩拦在这儿。

    **抽出来是为了能测。** 原来这段在 `render()` 里内联，而 `render()` 要先下
    源片、探 fps、渲封面才走到这儿——判据只能在 runner 上、六分钟之后才生效，
    等于没有。这两条都是「不吭声」型的错：

    - 引用了不存在的源 → 会静默从主源抓（另一场比赛的画面）
    - 同一段既有 narration 又有 quote → 两个人同时开口，而且闪避把原声压掉

    **默认不摇。** 窗口只有源片的 32% 宽，一横摇，画面里本该静止的底线、球网、
    广告板、看台全跟着滑；源片是 25 fps，滑动的静止物最容易看出一格一格。
    真人看下来的结论就是「固定中心的感觉更好」，所以横摇改成**按段显式打开**
    （`"track": true`），只留给主机位的宽景回合。
    """
    segments = [Segment(float(s["start"]), float(s["end"]),
                        None if s.get("cx") is None else float(s["cx"]),
                        s.get("narration", "").strip(),
                        str(s.get("fit", "crop")), bool(s.get("track", False)),
                        str(s.get("source", primary)),
                        s.get("quote", "").strip(),
                        s.get("inset") or None)
                for s in spec["segments"]]
    gone = [(i + 1, str((s.inset or {}).get("image", "")))
            for i, s in enumerate(segments) if s.inset]
    gone = [(i, f) for i, f in gone if not f or not Path(f).is_file()]
    if gone:
        raise ReelError(
            "这些段的图片找不到文件（写错路径时 ffmpeg 只会在切片那一步才炸，"
            "而那已经是下完所有源片之后了）：\n  "
            + "\n  ".join(f"第 {i} 段：{f or '(空)'}" for i, f in gone))
    bad_corner = [i + 1 for i, s in enumerate(segments) if s.inset
                  and str(s.inset.get("corner", "tl")) not in
                  {"tl", "tr", "bl", "br"}]
    if bad_corner:
        raise ReelError(f"第 {bad_corner} 段的 `inset.corner` 只能是 tl/tr/bl/br")
    unknown = sorted({s.source for s in segments} - set(sources))
    if unknown:
        raise ReelError(
            f"这些段引用了不存在的源：{unknown}；spec 里声明的是 {sorted(sources)}")
    both = [i + 1 for i, s in enumerate(segments) if s.narration and s.quote]
    if both:
        raise ReelError(
            f"第 {both} 段同时写了 narration 和 quote。\n"
            "两者是互斥的：quote 那一段要让当事人自己说，配上旁白就是"
            "**两个人同时开口**，而且闪避会把原声压下去——他的话就没了。\n"
            "要么把这句话改写成旁白（narration，我们替他讲），"
            "要么只留 quote（原声 + 中文字幕）。")
    return segments


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("segments", "cover"):
        if key not in spec:
            raise ReelError(f"spec 缺少 {key}")
    if not spec.get("sources") and not spec.get("source_url"):
        raise ReelError("spec 既没有 `sources` 也没有 `source_url`")
    # 多源的 spec：每一段都要说清自己从哪条源片剪。**不给默认值**——猜错了
    # 剪出来是另一场比赛的画面，而且画面本身不会报错，只会静静地对不上旁白。
    names = set(spec.get("sources") or {})
    if names:
        for index, seg in enumerate(spec["segments"]):
            got = seg.get("source")
            if got not in names:
                raise ReelError(
                    f"第 {index} 段的 source 是 {got!r}，不在 sources 里"
                    f"（有 {sorted(names)}）。多源 spec 的每一段都必须显式声明来源。")
    return spec


def segments_straddling_cuts(
    spec: dict, probes: list[dict],
) -> tuple[list[dict], list[str]]:
    """哪几段跨过了源片的场景切点，以及哪几条源片没查成。

    **跨切点＝这一段中途换镜头，而换过去的那个镜头里常常是另一个人。**
    郑钦文那条第一版踩了三处，一处都没报错：末屏「你定闹钟吗？」压在对手
    握拳庆祝的近景上（源片 148.2 有切点，窗口取的 144.3–150.0）；「往回爬」
    那句前两秒是对手的背影；巴黎那段「亚洲的第一枚奥运网球单打金牌」整句
    落在维基奇身上。画面和旁白对不上**不会让渲染失败**，只会静静地发出去。

    `probe.json` 里本来就记着 `scene_cuts` 和 `url`，按 url 认源片就能机检——
    挑段仍然要靠眼睛，这一条只负责拦住「窗口中途换了镜头而我没看见」。

    真要跨（两边都是同一个人时），在这一段写 `"crosses_cut": "<为什么>"`
    显式挂账，别默默跨过去。

    第二个返回值是**没查成的源片**：probe 没给全时，前一个返回值会是空的，
    而空的和「全都合格」长得一模一样（CLAUDE.md：空结果先自证是真空）。
    """
    by_url = {p.get("url"): list(p.get("scene_cuts") or []) for p in probes}
    urls = dict(spec.get("sources") or {})
    if not urls:
        urls = {"": spec.get("source_url", "")}
    straddling: list[dict] = []
    unchecked = sorted(
        name for name, url in urls.items() if url not in by_url)
    for index, seg in enumerate(spec["segments"]):
        name = seg.get("source", "")
        url = urls.get(name)
        if url not in by_url or seg.get("crosses_cut"):
            continue
        inside = [c for c in by_url[url]
                  if seg["start"] < c < seg["end"]]
        if inside:
            straddling.append({
                "index": index, "source": name,
                "start": seg["start"], "end": seg["end"],
                "cuts": inside, "narration": seg["narration"],
            })
    return straddling, unchecked


def resolve_sources(spec: dict, outdir: Path) -> dict[str, Path]:
    """把 spec 里的源片全下下来，返回 {名字: 路径}。

    单源 spec 走 `source_url`，键是空串——和 `Segment.source` 的默认值对上，
    老 spec 一个字都不用改。
    """
    urls = dict(spec.get("sources") or {})
    if not urls:
        urls = {"": spec["source_url"]}
    paths: dict[str, Path] = {}
    for name, url in urls.items():
        dest = outdir / (f"source_{name}.mp4" if name else "source.mp4")
        if not dest.is_file():
            with stage(f"下载源片 {name or '(单源)'}"):
                dest = download(url, dest)
        paths[name] = dest
    return paths


# 跟踪裁切 -----------------------------------------------------------------
TRACK_FPS = 5.0        # 抽帧频率：够跟上回合，又不至于让镜头抖
TRACK_SMOOTH = 13      # 平滑窗口（帧），越大越像摇臂
TRACK_MAX_SPEED = 150  # 每秒最多摇多少像素，防止镜头追着球甩
# **不出画就不摇。** 窗口只有 810 宽（源片的 42%），原来是 40px 死区跟着质心走，
# 等于一直在摇——而源片是 25 fps，一横摇，画面里本该静止的底线、球网、广告板、
# 看台全跟着滑，25 fps 下滑动的静止物最容易看出一格一格。窗口不动时只有人和球在动，
# 眼睛对这个宽容得多。所以改成**边缘触发**：回合中心在窗口中间这一段里随便晃都不动，
# 只有要顶出去了才补那一截，补完继续钉住。
TRACK_SLACK = 0.62     # 目标可以离窗口中心多远（占半宽），超了才动


def track_run(source: Path, start: float, end: float, source_w: int,
              *, quiet: bool = False) -> list[tuple[float, float]]:
    """按运动质心给出 [start, end) 这一整段镜头的裁切中心轨迹。

    返回的是**源片绝对秒 + 中心 x（浮点）**的粗轨迹（5 Hz），交给
    `sample_track` 去按段重采样。之所以分成两步：spec 里相邻的两段常常在源片里
    是**同一个没剪断的镜头**（66.0–74.2 接 74.2–79.28），一段一段各跟各的，
    交界处窗口会瞬间横移——实测跳了 222 / 448 / 399 像素，画面内容一模一样、
    位置突然平移一大截，看着就是"转场卡了一下"。整条镜头跟一次再切开，
    交界处才是连续的。

    网球转播的主机位是固定的：动的是球和两个人，静的是看台、场地线、广告板。
    所以**相邻帧差分的加权质心**天然落在回合上，不需要任何模型。

    三层处理缺一不可，少哪层都会晕：
      平滑   —— 质心逐帧跳，直接用就是抽搐
      死区   —— 球在画面中间小幅来回时不该动镜头
      限速   —— 镜头要像摇臂一样慢慢摇，不能追着球甩

    抽帧是**顺序解码 + 按帧号挑**，只在段首寻址一次。原来每个采样点都
    `cap.set(CAP_PROP_POS_MSEC)` 随机寻址，等于每次都回到关键帧重新解一遍：
    实测 55 帧要 9.12s，顺序解码 0.81s，**快十一倍**。跳过的帧照样要解码，
    但解码一帧比重新寻址一次便宜得多。
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(source))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    every = max(1, int(round(src_fps / TRACK_FPS)))   # 每隔几帧取一个样
    step = every / src_fps                            # 样点之间的真实间隔
    half = CROP_W / 2
    lo, hi = half, source_w - half

    # 寻址一次到段首，之后一路 grab()/retrieve()：grab 只解码不转格式，
    # 跳过的帧走 grab，要用的帧才 retrieve。
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)
    want = int(math.ceil((end - start) / step))

    prev = None
    raw: list[tuple[float, float]] = []
    for index in range(want):
        if index:
            for _ in range(every - 1):
                if not cap.grab():
                    break
        ok, frame = cap.read()
        if not ok:
            break
        t = start + index * step          # 绝对秒：切段的时候要按它对齐
        small = cv2.cvtColor(cv2.resize(frame, (480, 270)), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diff = cv2.absdiff(small, prev)
            _, mask = cv2.threshold(diff, 12, 255, cv2.THRESH_BINARY)
            col = mask.sum(axis=0).astype(np.float64)
            if col.sum() > 0:
                cx = float((col * np.arange(col.size)).sum() / col.sum())
                raw.append((t, cx / col.size * source_w))
        prev = small
    cap.release()

    if not raw:
        # 没抽到运动就退回固定中心——但要说出来，别让「没跟踪」和「跟踪了但没动」
        # 长得一样
        print(f"    [track] {start:.1f}–{end:.1f}s 没检出运动，退回 spec 里的 cx")
        return []

    xs = np.array([x for _, x in raw])
    kernel = np.ones(min(TRACK_SMOOTH, len(xs))) / min(TRACK_SMOOTH, len(xs))
    xs = np.convolve(xs, kernel, mode="same")

    coarse: list[tuple[float, float]] = []
    cur = float(np.clip(xs[0], lo, hi))
    slack = CROP_W / 2 * TRACK_SLACK       # 目标在这个范围内晃，窗口不动
    limit = TRACK_MAX_SPEED * step
    moved = 0
    for (t_abs, _), target in zip(raw, xs):
        target = float(np.clip(target, lo, hi))
        off = target - cur
        if abs(off) > slack:
            # 只补超出的那一截，补完目标正好回到边界上——不是把它拉回正中，
            # 那样每次都要多摇 slack 那么多，等于又变成一直在跟
            want = off - math.copysign(slack, off)
            cur = float(np.clip(cur + max(-limit, min(limit, want)), lo, hi))
            moved += 1
        coarse.append((t_abs, cur))
    if not quiet:
        span = max(x for _, x in coarse) - min(x for _, x in coarse)
        print(f"    [track] {start:.1f}–{end:.1f}s：{moved}/{len(coarse)} 个采样点需要摇，"
              f"总横移 {span:.0f}px")
    return coarse


def sample_track(coarse: list[tuple[float, float]],
                 seg: "Segment") -> list[tuple[float, int]]:
    """把整条镜头的粗轨迹按这一段重采样成 [(段内秒, 裁切左边界)]。

    **重采样到每一帧**。抽帧是 5 Hz，成片是二三十 fps——直接把 5 Hz 的命令发给
    sendcmd，x 就每 200 毫秒跳一次、一跳最多 TRACK_MAX_SPEED*step 像素，
    看上去就是一格一格的台阶，摇得越快越明显。中间线性插值补齐，
    镜头才是连续地摇。多出来的命令行数无所谓（67 秒约两千行）。
    """
    import numpy as np

    if not coarse:
        return []
    half = CROP_W / 2
    ct = np.array([t for t, _ in coarse])
    cx_arr = np.array([x for _, x in coarse])
    frames = np.arange(0.0, seg.length, 1.0 / FPS)
    smooth = np.interp(seg.start + frames, ct, cx_arr)   # 按绝对秒取值
    return [(round(float(t), 3), int(round(float(x) - half)))
            for t, x in zip(frames, smooth)]


def track_shots(sources: dict[str, Path], segments: list["Segment"],
                source_w: int) -> dict[int, list[tuple[float, int]]]:
    """把在源片里连着的段合成一个镜头跟一次，再切回各段。

    「连着」的判据是**上一段的 end 就是这一段的 start**。spec 里之所以要断开，
    是为了给不同的旁白和不同的画面文字配时间，源片那边并没有剪；镜头一断，
    跟踪就重新起步，交界处窗口瞬移（实测 222 / 448 / 399 px）。

    顺带把不摇的那些段的固定中心也定了：恒定取源片正中。
    """
    runs: list[list[int]] = []
    for index, seg in enumerate(segments):
        trackable = seg.fit != "contain" and seg.track
        prev = segments[runs[-1][-1]] if runs else None
        joins = (runs and trackable
                 and abs(seg.start - prev.end) < 1e-3
                 and prev.fit != "contain"
                 and prev.track
                 # **跨源不许合并镜头。** 「连着」的判据是时间码相接，而两条
                 # 源片的时间码会**偶然**相接——那样就把两场比赛的画面当成
                 # 一个连续镜头去跟，跟出来的质心横跨两个机位，毫无意义。
                 # 而且它不吭声：合出来的窗口照样能渲。
                 and prev.source == seg.source)
        if joins:
            runs[-1].append(index)
        elif trackable:
            runs.append([index])

    tracks: dict[int, list[tuple[float, int]]] = {}
    # **裁切窗口恒定取源片正中，向左右两边等量扩到 3:4。** 账号所有者定的。
    #
    # 自动定心走过三版，全删了：
    #
    # 1. 逐段取运动质心的中位数——一段几秒就一两个回合，谁球多中心就偏谁。
    #    实测九段 0.338~0.547，1920 宽里差 400px，而机位从头到尾没动过
    # 2. 池化到全片，稳了，但仍偏离正中（0.455，86px），**而且解释不了**：
    #    转播主机位本来就对着球场架，正中才是最合理的先验，质心只是个弱代理
    # 3. 按白线剖面找球场对称轴——合成画面误差 0.001，真实素材上 108 张源片帧
    #    估出来的轴从 0.0 散到 0.85（机位一偏离中轴，球场在画面里就不再对称，
    #    "找对称轴"找的不是球场中轴）
    #
    # 3:4 之后窗口占源片 41.3% 宽（9:16 时只有 32%），对中的余量本来就宽裕。
    # **可预期比「聪明」要紧**：读者的直觉就是等比裁切，行为得对得上。
    # 个别段要另定，spec 里显式给 `cx`——那是人看着缩略图墙定的，说了算。
    fixed = [s for s in segments
             if not s.track and s.fit != "contain" and s.cx is None]
    for seg in fixed:
        seg.cx = 0.5
    if fixed:
        print(f"    [fixed] {len(fixed)} 段不摇，窗口取源片正中 cx=0.500")
    for members in runs:
        start = segments[members[0]].start
        end = segments[members[-1]].end
        with stage("跟踪抽帧"):
            # 同一条 run 里的段来自同一条源（跨源不合并，见上面 joins 的判据）
            coarse = track_run(sources[segments[members[0]].source],
                               start, end, source_w)
        if len(members) > 1:
            print(f"    [track] 上面这条是 {len(members)} 段连着的同一个镜头")
        for index in members:
            tracks[index] = sample_track(coarse, segments[index])
    return tracks


def _overlay_chain(base: str, ins: dict) -> str:
    """把角标压上去。没有角标时只是把 `[base]` 改名成 `[vout]`。

    **位置和边距都按画幅算，不写死像素。** 角标宽度给的是占画幅宽的比例，
    1080 宽下 0.34 → 367px；边距 4.3% → 46px。改画幅时两个数一起跟着走。

    ⚠️ 角标要**避开字幕那一条**。字幕上锚在 y=1284（卡底往上 156px），
    所以底部两角实际只剩到 1284 为止——贴 `bl`/`br` 时自己算清楚，
    默认给 `tl`：这条线的成片顶部没有常驻角标，那儿是空的。
    """
    if not ins:
        return base.replace("[base]", "[vout]")
    width = int(round(float(ins.get("width", 0.34)) * VIDEO_W)) // 2 * 2
    pad = int(round(float(ins.get("pad", 0.043)) * VIDEO_W))
    corner = str(ins.get("corner", "tl"))
    x = f"{pad}" if corner in ("tl", "bl") else f"W-w-{pad}"
    y = f"{pad}" if corner in ("tl", "tr") else f"H-h-{pad}"
    return (f"{base};[1:v]scale={width}:-2[ins];"
            f"[base][ins]overlay={x}:{y}[vout]")


def cut_segment(source: Path, seg: Segment, dest: Path, source_w: int,
                path: list[tuple[float, int]] | None = None) -> Path:
    """切一段、裁成 3:4、放大到 1080×1440。

    `-ss` 放在 `-i` **前面**是关键帧级的快速定位，落点可能偏几百毫秒；放在
    后面才是精确定位。高光片段一秒都不能偏，所以用精确定位（慢一点无所谓）。
    """
    # 两种取景。**默认 crop，铺满全屏——回合镜头也一样。**
    #
    #   crop    真·3:4 裁切，铺满画布。窗口 42% 宽（810/1920），球飞到
    #           两边时确实会出画，但**铺满的观感赢过「不丢画面」**：竖版短片
    #           在手机上是整屏播的，上下留黑边等于把冲击力先折一半。
    #           这一条是人看过两版之后定的，不是推出来的。
    #   contain 整幅 16:9 缩到卡宽放中间，上下模糊垫底。**现在不用**——
    #           留着是给「一屏里必须同时看见两个人且他们分得很开」那种画面的
    #           后路（比如颁奖合影），要用就在 spec 里单独写 `"fit": "contain"`。
    if seg.fit == "contain":
        # 整幅铺进来会只占屏高的三成（1080 宽的 16:9 才 608 高），上下两条死黑，
        # 「冲击力先折一半」。所以两件事一起做：
        #   1. 先横向留 KEEP 的宽度再缩——画面大一圈，而球员仍在窗口内
        #   2. 上下不留纯色，用同一帧放大模糊垫底
        # 模糊垫底比纯色好在：屏幕是满的，眼睛跟着中间那条走，不会被两条黑边切断。
        keep = int(1920 * CONTAIN_KEEP) // 2 * 2
        x = (1920 - keep) // 2
        chain = (
            f"split=2[bg][fg];"
            f"[bg]crop={keep}:{CROP_H}:{x}:0,"
            f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},boxblur=42:2,eq=brightness=-0.20[bgb];"
            f"[fg]crop={keep}:{CROP_H}:{x}:0,"
            f"scale={VIDEO_W}:-2:flags=lanczos[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,fps={FPS_EXPR},setsar=1"
        )
    else:
        x = int(round(seg.cx * source_w - CROP_W / 2))
        x = max(0, min(x, source_w - CROP_W))
        if path:
            cmds = dest.with_suffix(".cmds")
            cmds.write_text("".join(f"{t:.3f} crop@c x {v};\n" for t, v in path),
                            encoding="utf-8")
            span = max(v for _, v in path) - min(v for _, v in path)
            print(f"    [track] {seg.start:.1f}s 段 {len(path)} 个点，横摇 {span}px")
            chain = (f"sendcmd=f={_escape(cmds)},"
                     f"crop@c={CROP_W}:{CROP_H}:{path[0][1]}:0,"
                     f"scale={VIDEO_W}:{VIDEO_H}:flags=lanczos,"
                     f"fps={FPS_EXPR},setsar=1")
        else:
            chain = (f"crop={CROP_W}:{CROP_H}:{x}:{CROP_Y},"
                     f"scale={VIDEO_W}:{VIDEO_H}:flags=lanczos,"
                     f"fps={FPS_EXPR},setsar=1")
    # 所有 -i 必须排在滤镜/输出选项前面，否则 ffmpeg 会把 -vf 当成下一个输入的
    # 选项直接报错。源片是纯视频轨（人从网盘传来的那份就是），所以补一条静音轨
    # 进去——后面混音那步要求每段都有音频流。
    # 源片有原声就用原声；**只有它真的没有音轨时**才补静音。之前这里是无条件
    # `-map 1:a:0`，把补位的静音当成音轨——原声合进来之后照样取静音，成片里
    # 没有解说的段落量出来是 -91 dB，纯数字静音。补位的东西一旦无条件生效，
    # 就会盖住真货，而且从波形上看不出来（有音轨、有码率、就是没声音）。
    has_audio = _has_audio(source)
    # **角标那张 PNG 排在源片后面当第 1 路输入**，补位静音顺延到第 2 路。
    # 顺序写死是为了让下面 `-map` 的音轨索引可算——原来 `1:a:0` 指的是静音，
    # 插进一路图之后它就变成第 2 路了；这种索引错**不报错**，只是取错流。
    ins = seg.inset or {}
    inset_in = ["-i", str(ins["image"])] if ins else []
    null_idx = 2 if ins else 1
    extra_in = ([] if has_audio else
                ["-f", "lavfi", "-i",
                 f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}"])
    with stage("分段编码"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            # `-ss` 放在 `-i` **前面**（输入寻址）。这里原来放在后面，理由写的是
            # 「放前面只能定位到关键帧，可能偏几百毫秒」——那是 ffmpeg 2.1 之前的
            # 老规矩了。现在输入寻址默认 accurate_seek：跳到前一个关键帧，再解码
            # 丢弃到精确时刻，**帧是同一帧**（两种写法出的首帧逐像素比对，平均差
            # 0.0）。差的是时间：放后面是从第 0 秒开始解码整条源片再把前面丢掉，
            # 183s 那一段光解码就白跑三分钟的画面。实测同一段 19.2s → 6.2s。
            # 十一段起点加起来一千多秒的 1080p 解码，这是本条流水线第一大头。
            #
            # **它顺带修好了跟踪**。`sendcmd` 的时刻走的是滤镜图上的时间；输出
            # 寻址时整条源片都要过滤镜图，于是 0.2~11.8s 这些命令在**被丢掉的
            # 那段画面里**就全部发完了，真正留下来的帧拿到的是最后一条命令。
            # 量过：142.5s 那一段，输出的每一帧裁切位置都卡在 x=802（末条命令
            # 是 803），从头到尾一动不动；改成输入寻址后逐帧模板匹配，实测位置
            # 和 sendcmd 对得上（稳定处误差 0~1px）。日志照样打「59 个点，
            # 横摇 977px」——**算了、打印了、没生效**，和「补位静音盖住真音轨」
            # 是同一种病：出事的时候不吭声。
            "-ss", f"{seg.start:.3f}", "-i", str(source), *inset_in, *extra_in,
            # 时长而不是 `-to`：`-ss` 变成输入选项之后输出时间轴从 0 起算，
            # 再写 `-to seg.end` 会把整段截没。
            "-t", f"{seg.length:.3f}",
            # 输出必须打标签并显式 map：`-map 0:v:0` 取的是**原始流**，
            # 会把整个滤镜图绕过去——裁切、缩放、跟踪全不生效，成片直接是 16:9。
            "-filter_complex",
            _overlay_chain(
                (chain + "[base]") if seg.fit == "contain"
                else f"[0:v]{chain}[base]", ins),
            "-shortest", "-map", "[vout]",
            "-map", "0:a:0" if has_audio else f"{null_idx}:a:0",
            # 分段是**中间产物**：最后整片还要以 crf 18 重编一次，这里编到
            # crf 17/preset slow 是把画质编进一个马上被重编的文件里，白花时间。
            # medium/crf 20 在同一段上 6.2s → 4.0s，重编后的成片肉眼无差。
            # 成片那一步的参数没有动。
            "-c:v", "libx264", "-preset", PART_PRESET, "-crf", PART_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", AUDIO_RATE,
            str(dest))
    return dest


def build_cover(sources: dict[str, Path], primary: str, spec: dict,
                dest: Path, source_w: int, seconds: float = COVER_SECONDS) -> Path:
    """封面：**一律走「赛场之上」的固定海报模板**（`tools/versus_poster.py`）。

    账号所有者定的：「以后『赛场之上』封面海报都用新的模板方案。」所以这里
    **没有第二条路**——抓一帧当封面那条分支已经删掉了，不是留着当兜底。
    留着兜底的后果是可预见的：哪条片子一时找不到照片，就悄悄退回抽帧，
    栏目的封面从此有两副面孔，而且退回去的那次没人会注意到。

    抽帧本来就不该当默认：1920×1080 的一帧裁成竖版要放大一倍多，比一张官方
    原图软一大截，而封面是唯一决定人点不点的那一屏。

    缺图就报错，并把出路写在报错里——**去扩检索源**（赛事官方图库 → 协会/赛事
    新闻页 → 新闻站与图片社 → Commons/Flickr），不是退回抽帧。

    **模板有两副，按栏目选，不按素材凑手选**：

    - `赛场之上`讲一场对决 → VS 模板（两格 + 中缝 + VS 圆牌 + 两个名字）
    - `网球有故事`讲一个人 → `layout: "solo"`，封面只有主角

    账号所有者 2026-07-31 定的：休伊特那条「是讲休伊特的儿子的话题，不是
    赛场之上的内容」「所以封面只有休伊特儿子照片」。反过来那条**没有松**：
    赛场之上仍然只能用 VS 模板，solo 不是它缺图时的兜底。
    """
    cover = spec["cover"]
    layout = str(cover.get("layout", "cutout"))
    eyebrow = str(cover.get("eyebrow", "")).strip()
    if layout == "solo":
        if eyebrow == "赛场之上":
            raise ReelError(
                "「赛场之上」的封面一律是 VS 模板：这个栏目讲的是一场对决，"
                "封面只放一个人就少了一半。\n"
                "solo 是给讲人的栏目（网球有故事）用的，不是缺图时的兜底——"
                "缺图去扩检索源，或从本场源片抓一帧。")
        if not (cover.get("portrait") or {}).get("image") and \
                (cover.get("portrait") or {}).get("frame_at") is None:
            raise ReelError(
                "solo 封面缺 `cover.portrait`：要主角的一张**本场**实拍。\n"
                "格式：cover.portrait = {image | frame_at, source, "
                "focus, focus_y, zoom, fit}\n"
                "四道闸门照旧；四类源都拿不到本场的，就从本场源片抓一帧。")
        return build_versus_poster(sources, primary, cover, dest, seconds)
    if not cover.get("versus"):
        raise ReelError(
            "封面缺 `cover.versus`：赛场之上的封面一律走固定海报模板，"
            "要两个人各一张**本场**的真实照片。\n"
            "先扩检索源（赛事官方图库 → 协会/赛事新闻页 → 新闻站/图片社 → "
            "Commons/Flickr）；**四类源都拿不到本场的实拍，就从本场源片抓一帧**"
            "（`frame_at`，账号所有者 2026-07-31 定：「或者从比赛中抠大图，"
            "要情绪饱满的」）。抓帧要挑情绪最满的那一格，别挑随便一个回合。\n"
            "格式：cover.versus = {split, names: [上, 下], "
            "top: {image, focus, focus_y, zoom, fit}, bottom: {…}}\n"
            "讲一个人的栏目（网球有故事）用 `layout: \"solo\"` + cover.portrait。")
    return build_versus_poster(sources, primary, cover, dest, seconds)


def build_versus_poster(sources: dict[str, Path], primary: str,
                        cover: dict, dest: Path, seconds: float = COVER_SECONDS) -> Path:
    """「赛场之上」的固定海报，版式在 `tools/versus_poster.py` 里定死。

    **这是栏目的固定封面，不是这一条片子的一次性设计。** 以前是在这儿现拼一张
    上下两格的底图再盖字，每条片子的比例、压暗、名字位置都得重调；现在只换素材
    和文字。改版式要改那个模块，改完三条片子一起重渲比一眼。

    照片版每一格给 `image`（本地静态图）或 `frame_at`（从源片抓一帧）。
    cutout 版式则更严格：人物用官方抠图，背景必须给
    `frame_at + shot: "wide_court"`，从**本场比赛视频**截取底线全场机位；
    场馆资料图、别场比赛和通用球场图都不能代替。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from versus_poster import build_poster  # noqa: PLC0415

    layout = str(cover.get("layout", "cutout"))
    versus = dict(cover.get("versus") or {})

    def _grab(spot: dict, tag: str) -> str:
        """`image` 直接用，`frame_at` 从源片抓一帧。抓出来的不进仓库。

        多源之后 `frame_at` 要说清楚**抓哪条源**（`"source": "键"`，默认主源）。
        不说清楚就会从主源的同一时刻抓——那是另一场比赛的画面，而且**不报错**。
        """
        if spot.get("image"):
            if not Path(spot["image"]).is_file():
                raise ReelError(f"VS 拼接的 {tag} 找不到图：{spot['image']}")
            return str(spot["image"])
        key = str(spot.get("source", primary))
        if key not in sources:
            raise ReelError(
                f"VS 的 {tag} 要从源 {key!r} 抓帧，但 spec 里声明的是 {sorted(sources)}")
        grab = dest.parent / f"_versus_{tag}.jpg"
        with stage(f"VS 抓帧 {tag}（源 {key or '主'}）"):
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{float(spot['frame_at']):.2f}", "-i", str(sources[key]),
                "-frames:v", "1", "-q:v", "2", str(grab))
        return str(grab)

    if layout == "solo":
        art = dict(cover["portrait"])
        art["image"] = _grab(art, "portrait")
        cover = {**cover, "portrait": art}
    elif layout == "cutout":
        # 人物是官方抠图（本地 PNG），只有背景那张要抓帧。
        bg = dict(versus.get("background") or {})
        if bg.get("frame_at") is None:
            raise ReelError(
                "cutout 版式的背景必须用本场比赛视频："
                "versus.background.frame_at = <底线全场机位秒数>；"
                "不能用场馆资料图、别场比赛或通用球场图。")
        if bg.get("shot") != "wide_court":
            raise ReelError(
                'cutout 版式的背景景别必须写 shot: "wide_court"：'
                "选能看清整片球场的底线全场机位，不用人物近景。")
        bg["image"] = _grab(bg, "bg")
        versus["background"] = bg
        for key in ("top", "bottom"):
            panel = dict(versus[key] or {})
            if panel.get("frame_at") is not None:
                # **抓哪条源要按 panel 自己写的算**，和 `_grab` 同一套。原来这儿
                # 写的是 `source`，而这个函数的作用域里根本没有这个名字——
                # 「首选本场抽帧」这条路一次都没跑起来过，第一次用必 NameError。
                # `ruff --select F821` 一秒就能指出来，判据落在
                # test_没有名字是凭空来的。
                skey = str(panel.get("source", primary))
                if skey not in sources:
                    raise ReelError(
                        f"VS 的 {key} 要从源 {skey!r} 抽帧抠图，"
                        f"但 spec 里声明的是 {sorted(sources)}")
                panel["cutout"] = _cut_person(sources[skey], panel, key,
                                              dest.parent)
                panel.pop("crop", None)   # box 已经在抠之前裁过了，别再裁一次
                versus[key] = panel
                continue
            cut = panel.get("cutout")
            if not cut or not Path(cut).is_file():
                raise ReelError(
                    f"cutout 版式的 {key} 格既没给 frame_at 也找不到抠图：{cut}\n"
                    "首选 `frame_at`：从**本场源片**抓一帧抠出来，衣服、光、球场"
                    "都是这场的；官方棚拍图退居兜底。\n"
                    "WTA：photoresources 的 <Name>-Torso_<wta_id>.png?width=3000；"
                    "ATP：赛事域名的 /-/media/alias/player-gladiator-image/<atp_id>。\n"
                    "**这个球员根本没有官方抠图、源片里也挑不出近景，就退回 "
                    "`layout: diagonal` 的照片版**（账号所有者定的兜底）——"
                    "别拿头像凑，见 versus_poster.py 里同一处的说明。")
    else:
        for key in ("top", "bottom"):
            side = dict(versus[key])
            side["image"] = _grab(side, key)
            versus[key] = side
    poster = dest.parent / POSTER_NAME
    payload = dict(cover) if layout == "solo" else {**cover, "versus": versus}
    with stage("封面海报"):
        build_poster(payload, poster, layout=layout)
    poster.with_suffix(".html").unlink(missing_ok=True)   # 内嵌 data URI，十几 MB
    column = str(cover.get("eyebrow", "")).strip() or "赛场之上"
    print(f"    [封面] {column}海报 {layout} → {poster.name}")
    return _still_to_clip(poster, dest, seconds)


#: 抠图模型。三个都试过并把 alpha 摊在棋盘格上看边：u2net 和 u2net_human_seg
#: 把锦织圭的发梢切平了一条，isnet 保住了。
CUT_MODEL = "isnet-general-use"
#: 抠出来的东西至少要占裁切框这么大，否则当成「没抠到人」。
#: 6% 是从已知好素材倒推的：官方半身抠图占 65%，本场人物近景同一量级，
#: 而抠到一条球拍残影只有百分之几——两者隔着一个数量级，门槛落在中间。
CUT_MIN_SHARE = 0.06


def _cut_person(source: Path, panel: dict, tag: str, workdir: Path) -> str:
    """从本场源片抓一帧、裁出人、抠掉背景 —— 封面人物的首选来源。

    **为什么不用官方棚拍图**：棚拍的衣服、光、背景都跟这场球没关系，压在本场
    画面上像两张贴纸。账号所有者的原话：「因为更贴近比赛的服装，感觉会更好，
    用之前资料就有点脱节」。

    顺带还赢在分辨率，这个能量（模板槽位 634px）：

        ATP 官方棚拍 裁到胯   265×410   → 1.55× **放大**
        本场抽帧              660×1040  → 0.61× 缩小

    看着"正规"的棚拍图其实是全套素材里最软的一档。

    挑哪一帧交给 `tools/pick_cover_frames.py`（判据：正脸或稍微侧脸、上半身
    直立、表情读得出），**挑完要打开看**——谁是谁、表情对不对题机器判不了。

    `box` 是 0~1 的裁切框，作用在**源帧**上，抠之前裁。它有两件事要做：
    少给模型无关像素（alpha 干净得多），以及把转播叠加物排除掉——记分条在
    左下、台标在右上，它们不是人，但离人近的时候会被一起圈进来。
    """
    from PIL import Image  # noqa: PLC0415

    raw = workdir / f"_versus_raw_{tag}.png"
    out = workdir / f"_versus_cut_{tag}.png"
    with stage(f"VS 抠帧 {tag}"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{float(panel['frame_at']):.2f}", "-i", str(source),
            "-frames:v", "1", str(raw))
        im = Image.open(raw).convert("RGB")
        box = panel.get("box")
        if box:
            if len(box) != 4:
                raise ReelError(f"VS {tag} 的 box 要四个数 [x0,y0,x1,y1]（0~1）：{box}")
            w, h = im.size
            im = im.crop((round(box[0] * w), round(box[1] * h),
                          round(box[2] * w), round(box[3] * h)))
        from rembg import new_session, remove  # noqa: PLC0415

        # **`post_process_mask=True` 不能省。** 不加的时候深色球衣压在深色背景墙上
        # （锦织圭那格）会留**一整块方底**，渲到海报上是一个看得见的矩形边。
        # 加上之后三个模型的 alpha 全干净——那不是模型不行，是后处理没开。
        cut = remove(im, session=new_session(CUT_MODEL), post_process_mask=True)
        bbox = cut.getbbox()
        if not bbox:
            raise ReelError(
                f"VS {tag} 抠出来是空的：{panel['frame_at']}s 那一帧里没找到人。"
                "换一帧，或者用 tools/pick_cover_frames.py 重挑。")
        # **「抠出来是空的」有两种，`getbbox()` 只拦得住一种。** 完全透明它拦得住；
        # 抠到一条球拍残影、一道边线，bbox 非空，于是**一路绿到底**——render
        # success、`check_reel_landed` 0 项不合格、海报上人没了。2026-08-01 黄泽林
        # 那张就是这么出去的（138.14s 那一帧，左格只剩背景和一道白线）。
        # 又一次「兜底出事的时候不吭声」。
        #
        # 判据用**不透明像素占裁切框的比例**：人物近景是一大块，残影是一条线。
        # 门槛 6% 是从已知好素材倒推的——官方半身抠图 65%，本场近景同一量级，
        # 中间隔着一个数量级。比例照常打进日志，这样下次调门槛有数可依
        # （「检查工具要把不合格的也列出来」）。
        alpha = cut.getchannel("A")
        opaque = sum(n for v, n in zip(range(256), alpha.histogram()) if v > 16)
        share = opaque / float(im.size[0] * im.size[1])
        if share < CUT_MIN_SHARE:
            raise ReelError(
                f"VS {tag} 抠出来只有裁切框的 {share:.1%}（要 ≥{CUT_MIN_SHARE:.0%}）"
                f"——{panel['frame_at']}s 那一帧多半抠到了球拍或边线，不是人。\n"
                "换一帧（挑**头部和背后背景对比强**的那种），或者退回官方抠图："
                'top/bottom 写 {"cutout": "assets/players/<...>.png"}。')
        cut = cut.crop(bbox)
        cut.save(out)
    print(f"    [封面] {tag} 抽帧抠图 {panel['frame_at']}s → {cut.size[0]}×{cut.size[1]}"
          f"，占裁切框 {share:.1%}")
    raw.unlink(missing_ok=True)
    return str(out)


def _still_to_clip(still: Path, dest: Path, seconds: float = COVER_SECONDS) -> Path:
    """封面静图 → 一小段带静音轨的视频，接进片头。

    静音轨是**占位**：封面那句旁白和其他段一样，在最后混音那一步按 `adelay=0`
    叠上去。这儿要是也塞一路音频，就成了「补位的静音盖住真音轨」那个老毛病。
    """
    with stage("封面编码"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(still), "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}",
            "-t", f"{seconds:.3f}",
            "-vf", f"fps={FPS_EXPR},setsar=1",
            "-c:v", "libx264", "-preset", PART_PRESET, "-crf", PART_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", AUDIO_RATE,
            "-shortest", str(dest))
    return dest


def _chromium() -> str:
    """沙箱里 PLAYWRIGHT_BROWSERS_PATH 指的路径带版本号，playwright 自己找不到，
    得显式给。CI 上装的那份在默认位置，glob 一下两边都覆盖。"""
    import glob as _glob
    roots = ["/opt/pw-browsers", str(Path.home() / ".cache/ms-playwright")]
    for pattern in [f"{r}/chromium*/chrome-linux*/{exe}"
                    for r in roots for exe in ("chrome", "headless_shell")]:
        hits = sorted(_glob.glob(pattern))
        if hits:
            return hits[-1]
    raise ReelError("找不到 chromium")


def tts_one(text: str, path: Path, voice: str, rate: str) -> list[dict]:
    """合一条语音，落盘并返回词边界。

    抽出来是因为**封面也要配音**了：封面那句得在渲封面之前就合出来——封面停多久
    由它的长度决定（见 `cover_length`），不能等到 `synthesize()` 那一步。
    """
    import asyncio

    import edge_tts

    async def one() -> list[dict]:
        marks: list[dict] = []
        with path.open("wb") as fh:
            stream = edge_tts.Communicate(
                text, voice, rate=rate, boundary="WordBoundary").stream()
            async for chunk in stream:
                if chunk.get("type") == "audio" and chunk.get("data"):
                    fh.write(chunk["data"])
                elif chunk.get("type") in ("WordBoundary", "SentenceBoundary"):
                    marks.append({"offset": chunk.get("offset", 0),
                                  "duration": chunk.get("duration", 0),
                                  "text": chunk.get("text", "")})
        return marks

    marks = asyncio.run(one())
    if not path.is_file() or path.stat().st_size == 0:
        raise ReelError(f"TTS 没出音频：{path.name}　「{text[:24]}…」")
    path.with_suffix(".words.json").write_text(
        json.dumps(marks, ensure_ascii=False), encoding="utf-8")
    return marks


def synth_cover(spec: dict, outdir: Path, voice: str, rate: str
                ) -> tuple[Path | None, list[dict]]:
    """封面那句旁白。没写就返回 `(None, [])`——封面退回定长静止。

    **封面配音是「网球有故事」那条线的做法**（账号所有者定的）：那个栏目讲一个人，
    封面念的就是海报上那句钩子，封面停多久跟着它走。

    「赛场之上」不走这条：它是一场对决的赛报，封面是定长 1.2 秒的短亮相，
    立刻切进第一个回合——**停久了会被当成图片**。所以在这儿拦住，别让两条线
    互相牵动：赛场之上写了 `cover.narration` 直接报错，而不是默默把封面拉长。
    """
    text = str((spec.get("cover") or {}).get("narration") or "").strip()
    if not text:
        return None, []
    column = str(spec.get("column") or (spec.get("cover") or {}).get("eyebrow") or "")
    if "赛场之上" in column:
        raise ReelError(
            "「赛场之上」的封面不配音：它是定长 1.2 秒的短亮相，立刻切进第一个"
            "回合——停久了会被当成图片而不是视频。封面跟着配音走是「网球有故事」"
            "那条线的做法（那个栏目讲一个人，念的就是海报上那句钩子）。\n"
            "把 cover.narration 删掉；那句话要留，就放进第一段的 narration。")
    path = outdir / "voice_cover.mp3"
    with stage("封面配音"):
        marks = tts_one(text, path, voice, rate)
    return path, marks


def cover_length(voice_path: Path | None) -> float:
    """封面停多久。

    **有配音就跟着配音走，没有才用定长。** 账号所有者定的：「这个栏目不要求
    〔固定几秒〕，随着配音切换吧」——封面那句话说完就切，不多停，也不半路截断。

    `COVER_TAIL` 是说完之后留的那口气：切得贴着最后一个字，末尾的辅音会被
    concat 的边界削掉，听着像卡了一下。0.25s 是「说完了」和「停顿」之间那一档。

    没有配音的片子（存量的赛场之上都是）退回 `COVER_SECONDS`，并且**要出声说
    走的是哪条路**——两条路的产物长得不一样，日志里不写就只能靠猜。
    """
    if voice_path is None:
        print(f"[封面] 没有配音，定长停 {COVER_SECONDS}s")
        return COVER_SECONDS
    spoken = probe_duration(voice_path)
    length = round(spoken + COVER_TAIL, 3)
    print(f"[封面] 跟着配音走：旁白 {spoken:.2f}s + 尾 {COVER_TAIL}s = {length:.2f}s")
    return length


def synthesize(segments: list[Segment], outdir: Path, voice: str, rate: str
               ) -> list[tuple[Path, list[dict]]]:
    # 一段解说都没有就别碰 edge-tts——沙箱里根本装不上，而"没有解说的片子"
    # 是个合法的形态（先看画面剪得对不对，再配音）
    if not any(seg.narration.strip() for seg in segments):
        return [(outdir / f"voice_{i:02d}.mp3", []) for i in range(len(segments))]

    out: list[tuple[Path, list[dict]]] = []
    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        if not seg.narration.strip():
            out.append((path, []))
            continue
        out.append((path, tts_one(seg.narration, path, voice, rate)))
    return out


def spec_sources(spec: dict) -> dict[str, str]:
    """spec 声明的源片：`{键: url}`。

    单源写 `source_url`（历史写法，全部存量都是它），键是 `""`。
    跨场次的片子写 `sources`，段里用 `"source": "<键>"` 指定取自哪条。

    休伊特那条就是跨两场：17 岁的克鲁兹从资格赛打进正赛、首轮赢下生涯第一场
    ATP 正赛（一条集锦），下一轮遇上他父亲带出来的德米纳尔（另一条集锦）。
    只用后一场，故事少了前半截；只用前一场，没有那个拥抱。
    """
    # **按键在不在判断，不按真假**：`"sources": []` 或 `{}` 是假值，用 `if multi:`
    # 会静静绕过校验、掉进 `spec["source_url"]` 的 KeyError——报错完全不说人话。
    # 自己的冒烟测试抓到的。
    if "sources" in spec:
        multi = spec["sources"]
        if "source_url" in spec:
            raise ReelError("`sources` 和 `source_url` 只能有一个，别两处各写一遍")
        if not isinstance(multi, dict) or not multi:
            raise ReelError(
                f'`sources` 要写成非空的 {{"键": "url"}}，段里用 "source": "键" 引用；'
                f"现在是 {multi!r}")
        return {str(k): str(v) for k, v in multi.items()}
    if "source_url" not in spec:
        raise ReelError('spec 里要有 `source_url`（单源）或 `sources`（多源）')
    return {"": spec["source_url"]}


def check_sources_match(paths: dict[str, Path], spec: dict | None = None) -> None:
    """多源要对得上，不一致就在这儿报，别渲到一半。**两样的严重程度不同：**

    - **尺寸**：裁切窗口按源片宽高算（`resolve_crop`），对不上就是**裁错**。
      没有出路，一律红
    - **帧率**：成片跟**主源**走（`FPS`），别的源会被 `fps=` 重采样。这有代价，
      但代价随内容差得很远：50 → 25 是整齐地隔帧丢，看不出来；30 → 25 是
      六帧丢一帧，**静态说话头几乎无感，回合镜头一眼能看出一顿一顿**

    所以帧率不一致**要在 spec 里显式认领**（`mixed_fps: {源键: 为什么可以}`），
    不认领就红。原来是一律红——那会把「让当事人自己说」这类素材整个挡在门外
    （采访多是 30，赛事集锦多是 25/50）；一律放行又回到「兜底出事的时候不吭声」。
    认领这一步的作用就是**让这个取舍留下判据**，而不是让它悄悄发生。
    """
    if len(paths) < 2:
        return
    seen = {k: (*probe_size(p), resolve_fps(p)[0]) for k, p in paths.items()}
    ref_key = next(iter(seen))
    rw, rh, rf = seen[ref_key]
    rows = "\n  ".join(f"{k or '(主源)'}: {w}×{h} @ {f}"
                       for k, (w, h, f) in seen.items())
    bad_size = [k for k, (w, h, _) in seen.items() if (w, h) != (rw, rh)]
    if bad_size:
        raise ReelError(
            f"这些源片和主源 {ref_key or '(主源)'} 的尺寸对不上，裁切会静默裁错："
            f"{bad_size}\n  " + rows +
            "\n尺寸没有出路——换一条同尺寸的源片。")
    declared = (spec or {}).get("mixed_fps") or {}
    bad_fps = [k for k, (_, _, f) in seen.items() if f != rf and k not in declared]
    if bad_fps:
        raise ReelError(
            f"这些源片的帧率和主源 {ref_key or '(主源)'}（{rf}）不一样：{bad_fps}\n  "
            + rows +
            f"\n成片跟主源走，它们会被重采样到 {rf}——**静态画面（采访、定镜）"
            "几乎无感，回合镜头会一顿一顿**。\n"
            "确实可以接受就在 spec 里认领，并写清为什么：\n"
            '  "mixed_fps": {"' + bad_fps[0] + '": "30 fps；这条只用来放采访的'
            '说话头，重采样看不出来"}')
    for key, why in declared.items():
        if key in seen and seen[key][2] != rf:
            print(f"[fps] {key} 是 {seen[key][2]}，重采样到主源的 {rf}——{why}")


def _preflight_cutout(spec: dict) -> None:
    """封面要抽帧抠图就先验一次 rembg —— **在下源片之前**。

    「加新能力要同时改三处」那条已经踩过三次（playwright、Chromium、cv2），
    每次都是下完 64MB 源片、合完原声之后才死在 import 上，白跑一分半。
    这里是第四次，提前收在第 5 秒。
    """
    versus = (spec.get("cover") or {}).get("versus") or {}
    if not any((versus.get(k) or {}).get("frame_at") is not None
               for k in ("top", "bottom")):
        return
    try:
        import rembg  # noqa: F401,PLC0415
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise ReelError(
            "封面要从源片抽帧抠图（versus.top/bottom 里写了 frame_at），"
            "但这台机器没有 rembg。\n"
            '装：pip install "rembg[cpu]"；'
            "或者把那一格换回官方棚拍抠图（`cutout`: 本地透明 PNG）。"
        ) from exc


def _join_parts(
    parts: list[Path],
    durations: list[float],
    source_ids: list[str],
    dest: Path,
) -> ConcatFiltergraph:
    """拼接画面，同时让音轨走全工程统一的定长转场。

    这里不能再让 concat demuxer 同时带着音轨走：不同剪辑段的环境声、解说声和
    音乐底一旦在边界直接换轨，听感就是一次硬切。视频仍然可以 ``-c:v copy``
    无损拼接；音频则由 :mod:`tennislive.video.audio` 在每段自己的时间窗内淡出、
    淡入，随后再回封装。这样输出时长仍是各段时长之和，已经按这个时间轴排好的
    旁白和字幕不用重算。

    ``source_ids`` 描述的是一个**连续剪辑窗口**，不是底层文件名。同一条官方
    集锦里相隔几十秒的两个片段也不是采样连续的，必须给不同 ID，不能因为文件名
    相同就退化成 20ms 的同源去爆音处理。
    """
    if not parts or not (len(parts) == len(durations) == len(source_ids)):
        raise ReelError("拼接输入、时长和来源标识必须非空且一一对应")

    graph = concat_av_filter(
        [
            AVSegment(duration, source_id=source_id)
            for duration, source_id in zip(durations, source_ids)
        ],
        audio_role="mixed",
    )
    expected = graph.output_duration
    listing = dest.with_name("_concat_video.txt")
    video_only = dest.with_name("_concat_video.mp4")
    joined_audio = dest.with_name("_concat_audio.m4a")
    listing.write_text(
        "ffconcat version 1.0\n"
        + "".join(
            f"file '{part.resolve()}'\nduration {duration:.6f}\n"
            for part, duration in zip(parts, durations)
        ),
        encoding="utf-8",
    )
    try:
        # concat demuxer 只准处理画面。`-an` 是一道显式闸门：哪怕以后 part 又多了
        # 一条音轨，也不能悄悄绕过下面的全局音频转场策略。
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-map", "0:v:0", "-an", "-c:v", "copy",
            "-t", f"{expected:.6f}", str(video_only),
        )

        audio_inputs = [item for part in parts for item in ("-i", str(part))]
        # concat_av_filter 同时声明 A/V 时间线。这里只有音频需要写文件，所以把
        # 生成的画面输出接到 nullsink；仍由同一个图裁齐每段时长，防 AAC padding
        # 把下一段（以及后面的旁白 offset）一点点往后推。
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *audio_inputs,
            "-filter_complex", f"{graph.filtergraph};{graph.video_label}nullsink",
            "-map", graph.audio_label, "-vn",
            "-c:a", "aac", "-b:a", "192k", "-ar", AUDIO_RATE,
            "-t", f"{expected:.6f}", str(joined_audio),
        )
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_only), "-i", str(joined_audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c", "copy",
            "-t", f"{expected:.6f}", str(dest),
        )

        actual = probe_duration(dest)
        # 视频只能落在帧边界，给一帧加 20ms 的封装余量；超过就是时轴真漂了。
        tolerance = max(0.05, 1.0 / FPS + 0.02)
        if abs(actual - expected) > tolerance:
            raise ReelError(
                f"音频转场后时轴漂移：应为 {expected:.3f}s，"
                f"实为 {actual:.3f}s（容差 {tolerance:.3f}s）"
            )
        audio_qa = audio_qa_for_graph(
            graph,
            audio_role="mixed",
            reason="non_contiguous_official_highlight_windows",
        )
        audio_qa["declared_output_duration_seconds"] = round(expected, 6)
        audio_qa["measured_output_duration_seconds"] = round(actual, 6)
        audio_qa["timeline_delta_seconds"] = round(actual - expected, 6)
        (dest.parent / "audio-qa.json").write_text(
            json.dumps(audio_qa, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return graph
    finally:
        for intermediate in (listing, video_only, joined_audio):
            intermediate.unlink(missing_ok=True)


def render(spec: dict, outdir: Path, *, voice: str, rate: str,
           source_override: Path | None = None) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    _preflight_cutout(spec)
    urls = spec_sources(spec)
    sources: dict[str, Path] = {}
    for key, url in urls.items():
        path = outdir / (f"source_{key}.mp4" if key else "source.mp4")
        if key == "" and source_override:
            path = source_override
        if not path.is_file():
            with stage(f"下载源片 {key or '(主源)'}"):
                path = download(url, path)
        sources[key] = path
    check_sources_match(sources, spec)
    primary = next(iter(sources))
    source = sources[primary]
    # 网盘那份常常只有视频轨（DASH 的自适应流是分开的）。人另外传了 m4a 就在这儿
    # 合上——没有原声的成片只剩解说，球声和观众声全没了，片子会很平。
    audio = spec.get("source_audio")
    if audio and not _has_audio(source):
        merged = outdir / "source_av.mp4"
        if not merged.is_file():
            with stage("合原声"):
                run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(source), "-i", str(Path(audio)),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(merged))
        print(f"[audio] 合上原声 {audio}")
        source = merged

    # 多源：几何必须一致，否则一套裁切窗口套在两种画幅上，剪出来一段满一段不满。
    # 这里**宁可报错也不自动缩放**——自动缩放会把「素材选错了」变成一个看不见的
    # 画质问题，而报错能让人当场发现。
    sizes = {name: probe_size(path) for name, path in sources.items()}
    if len(set(sizes.values())) > 1:
        raise ReelError(
            "多条源片的画幅不一致，裁切几何没法共用：\n  "
            + "\n  ".join(f"{n or '(单源)'}: {w}×{h}" for n, (w, h) in sizes.items())
            + "\n换一条同画幅的源片，或者把不一致的那条单独出片。")
    source_w, source_h = sizes[next(iter(sources))]

    # 成片帧率跟着源片走。硬定 30 而源片是 25，就是每 5 帧补一帧，一秒卡五次。
    # 多源时只能有一个输出帧率，取主源的；**别的源和它不一样就要打出来**——
    # 那意味着那几段在重采样，不打出来没人知道画面为什么发涩。
    global FPS, FPS_EXPR
    FPS_EXPR, FPS = resolve_fps(source)
    print(f"源片 {source_w}×{source_h}，{probe_duration(source):.1f}s")
    resolve_crop(source_w, source_h, spec.get("crop_y"))
    portrait = source_w * 4 < source_h * 3

    segments = parse_segments(spec, sources, primary)
    # 封面那句先合出来——**封面停多久由它决定**，所以排在渲封面之前。
    cover_voice, cover_marks = synth_cover(spec, outdir, voice, rate)
    cover_secs = cover_length(cover_voice)
    total = sum(s.length for s in segments) + cover_secs
    print(f"{len(segments)} 段，画面共 {total:.1f}s")
    if total > 120:
        print(f"[注意] 超过两分钟（{total:.1f}s），按要求应当再砍")

    # 竖版源片的窗口就是整幅宽度，横向一个像素都挪不动——`track` 和 `cx` 在
    # 这里没有意义。**不吭声地忽略掉是最坏的做法**（spec 里写着 track，成片
    # 却纹丝不动，看起来像跟踪失效），所以直接报错，让人去删掉那两个字段。
    if portrait:
        bad = [i for i, seg in enumerate(segments) if seg.track or seg.cx is not None]
        if bad:
            raise ReelError(
                f"源片是竖版（{source_w}×{source_h}），裁切窗口就是整幅宽度，"
                f"横摇和 cx 都无处可摇。请删掉第 {[i + 1 for i in bad]} 段的 "
                "`track` / `cx`；要挪画面只能用 spec 顶层的 `crop_y`（纵向）。")

    # 缺 cv2 要**在这儿**报，不要等到第一段切片。跟踪合进来的那次 render 就是
    # 下完 64MB 源片、合完原声、渲完封面之后才死在 `import cv2` 上——和当初
    # playwright 那次一模一样的浪费。用到跟踪就先验一下。
    if any(seg.track for seg in segments):
        try:
            import cv2  # noqa: F401,PLC0415
        except ImportError as exc:  # pragma: no cover - 环境问题
            raise ReelError(
                "spec 里有段要跟踪裁切，但这台机器没有 cv2。"
                '装：pip install -e ".[visualqa]"；'
                "或者把这些段的 track 置为 false（画面退回固定中心）。"
            ) from exc

    # 跟踪要**先整条镜头跟完再切**，所以排在切片之前统一算（见 track_shots）
    tracks = track_shots(sources, segments, source_w)

    parts: list[Path] = [build_cover(sources, primary, spec,
                                 outdir / "part_cover.mp4", source_w,
                                 cover_secs)]
    for index, seg in enumerate(segments):
        parts.append(cut_segment(sources[seg.source], seg,
                                 outdir / f"part_{index:02d}.mp4",
                                 source_w, tracks.get(index)))

    silent = outdir / "_video.mp4"
    with stage("拼接"):
        # 封面和每个剪辑窗口都不是采样连续的音源。窗口级 ID 保证即使它们来自
        # 同一个 source.mp4，也执行全局的定长淡出/淡入，而不是直接换轨。
        join_graph = _join_parts(
            parts,
            [cover_secs, *(seg.length for seg in segments)],
            [
                f"cover:{spec.get('slug', 'reel')}",
                *(
                    f"{sources[seg.source].resolve()}#"
                    f"{seg.start:.6f}-{seg.end:.6f}"
                    for seg in segments
                ),
            ],
            silent,
        )

    with stage("TTS 合成"):
        voices = synthesize(segments, outdir, voice, rate)

    # **旁白比画面长，就不是「注意」，是错的。**
    #
    # 每段的语音都按自己那一段的开头 `adelay`，所以上一段一旦超出边界，
    # 下一段的语音**从边界那一刻照常开始**——两个人同时在说话。字幕同理：
    # 两条 Dialogue 在时间轴上重叠，libass 会把它们**一起画出来**，屏幕上
    # 叠着两行。
    #
    # 这儿原来只 `print` 一句「[注意] …字幕会压到下一段」，而且容差是 0.35s。
    # 伊埃拉那条第 10 段只超了 **0.29s**——够不着容差，一声不吭，成片里却是
    # 实实在在的两行字幕加两个声音（88.7 秒那一帧上看得清清楚楚）。
    # **只要超出一点点就会重叠**，因为下一段是卡着边界起的，所以容差要小；
    # 而且要**一次把所有超出的段都列出来**，别改一段跑一次六分钟。
    over = []
    spoken_of: dict[int, float] = {}
    for index, (seg, (path, _marks)) in enumerate(zip(segments, voices)):
        if not seg.narration.strip():
            continue
        spoken_of[index] = probe_duration(path)
        if spoken_of[index] > seg.length + 0.12:
            over.append(f"  第 {index + 1} 段：画面 {seg.length:.1f}s，"
                        f"旁白 {spoken_of[index]:.2f}s，超出 "
                        f"{spoken_of[index] - seg.length:.2f}s"
                        f"　「{seg.narration[:24]}…」")
    if over:
        raise ReelError(
            "有旁白比它那一段的画面长，会和下一段的语音、字幕叠在一起：\n"
            + "\n".join(over)
            + "\n\n两条出路，选一条：把这几段的旁白删短，或者把画面拉长"
              "（`end` 往后挪，但别越过下一段的 `start`）。")

    # 每段解说落在它那一段的**开头**，字幕跟着同一个偏移
    cues: list[tuple[float, float, str]] = []
    mix_inputs: list[str] = []
    filters: list[str] = []
    # 标签跟着 filters 一起攒，**别在下面另拿一个条件重算一遍**：加封面配音那次
    # 就是这么差点漏的——`names` 原来是从 segments 里重新筛一遍，封面那一路
    # 定义了却没人接。这类「两处各写一遍同一个条件」迟早会分叉。
    voice_labels: list[str] = []
    # 封面这一句从第 0 秒起。**它也要出字幕**——「静音刷是默认状态」，
    # 只给耳朵不给眼睛，等于开场那句话对一半人不存在。
    if cover_voice is not None:
        mix_inputs.extend(["-i", str(cover_voice)])
        filters.append(f"[{len(mix_inputs)//2}:a]adelay=0|0[vcover]")
        voice_labels.append("[vcover]")
        cover_text = str(spec["cover"]["narration"]).strip()
        # **念的就是海报上印的那句，就别再排一行字幕。** 钩子在海报上是几十号的
        # 大字，字幕把同样的话在同一帧里再写一遍，只是把画面弄脏。
        # 判据是「一不一样」，不是「封面一律不出字幕」：封面那句要是**另说了
        # 一件事**（存量里没有，但迟早会有），它照样要有字幕——静音刷是默认状态。
        printed = drop_punctuation(
            str(spec["cover"].get("hook", "")).replace("\n", " "))
        if drop_punctuation(cover_text) == printed:
            print("[封面] 旁白就是海报上那句钩子，不另排字幕")
        else:
            cues.extend(subtitle_cues(readable(cover_text),
                                      probe_duration(cover_voice),
                                      boundaries=cover_marks, offset=0.0))
    offset = cover_secs
    for index, (seg, (path, marks)) in enumerate(zip(segments, voices)):
        if seg.quote:
            # 原声段：没有语音可对齐，按字数等比铺满整段。**行数不能太多**，
            # 否则每行只剩一瞬——一段 12 秒的采访塞 60 字就是这样。
            cues.extend(subtitle_cues(readable(seg.quote), seg.length,
                                      offset=offset))
        elif seg.narration.strip():
            spoken = spoken_of[index]
            mix_inputs.extend(["-i", str(path)])
            filters.append(
                f"[{len(mix_inputs)//2}:a]adelay={int(offset*1000)}|"
                f"{int(offset*1000)}[v{index}]")
            voice_labels.append(f"[v{index}]")
            # 上面已经拦掉了超长的段，这儿再把字幕**收进本段的窗口**——
            # 边界事件的时刻是按语音插值出来的，末尾那一条可以比语音本身还长
            # 几分之一秒（伊埃拉那条超出 0.29s 的段，字幕尾巴甩出去 1.02s）。
            # 兜底和它拦的那件事分开写，坏的方式要选能兜住的那种。
            limit = offset + seg.length
            cues.extend(
                (a, min(b, limit), text)
                for a, b, text in subtitle_cues(
                    readable(seg.narration), spoken,
                    boundaries=marks, offset=offset)
                if a < limit)
        offset += seg.length

    margin_v = int(spec.get("subtitle_top", _REEL_MARGIN_V))
    ass = write_subtitles(cues, outdir / "subtitles.ass",
                          height=VIDEO_H, margin_v=margin_v)
    moved = "" if margin_v == _REEL_MARGIN_V else (
        f"，比默认抬高 {_REEL_MARGIN_V - margin_v}px 让开源片自己的记分条")
    print(f"字幕 {len(cues)} 行 → {ass.name}（画布 {VIDEO_W}×{VIDEO_H}，"
          f"上锚 MarginV={margin_v}{moved}，"
          f"左右 {_ASS_MARGIN_H}）")

    mixed = outdir / "_audio.m4a"
    with stage("混音"):
        if filters:
            # 闪避，不是一路压死：没人说话的时候现场声开到 BED_LOUD，解说一进来
            # sidechaincompress 把它压下去，说完再放开。之前是全程一个固定音量——
            # 要么盖住解说，要么整条片子的球声都听不见，两头不讨好。
            chain = ";".join(filters)
            names = "".join(voice_labels)
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(silent), *mix_inputs,
                "-filter_complex",
                f"[0:a]volume={BED_LOUD}[bed];{chain};"
                f"{names}amix=inputs={len(filters)}:normalize=0[voice];"
                f"[voice]asplit=2[vk0][vm];"
                # **`apad` 不能省。** `sidechaincompress` 两路里**任一路 EOF
                # 就整个结束**——旁白在最后一段里往往说不满（伊埃拉那条末段
                # 画面 11.5s、旁白 8.8s），于是钥匙那一路先断，现场声跟着被
                # 一起掐掉：成片最后 2.74 秒**一点声音都没有**，正好是拥抱教练
                # 那一下。它不报错，画面照旧，只有把音轨长度和画面长度摆在一起
                # 才看得见（`check_reel_landed.py` 那条「音轨比画面短」）。
                # 补成无限长之后，这一路由 `[bed]` 定长度，闪避行为一点没变：
                # 合成信号实测有旁白时 -38.1 dB、旁白说完 -24.0 dB。
                f"[vk0]apad[vk];"
                f"[bed][vk]sidechaincompress=threshold=0.02:ratio=12:"
                f"attack=15:release=450:makeup=1[duck];"
                f"[duck][vm]amix=inputs=2:normalize=0:dropout_transition=0[out]",
                # 这一步只是把解说混进现场声，产物是个 m4a——画面在这儿是
                # 拿来给 `-shortest` 定长度的，**必须 copy**。原来没写 `-c:v`，
                # 默认动作是把整条 1080×1920 重新 x264 编一遍，编完写进 m4a、
                # 下一步再整个丢掉。（改前/改后的实测见提交说明。）
                "-map", "0:v:0", "-map", "[out]", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", AUDIO_RATE,
                "-shortest", str(mixed))
        else:
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(silent), "-vn", "-c:a", "aac", "-b:a", "192k",
                "-ar", AUDIO_RATE, str(mixed))

    final = outdir / f"{spec.get('slug', 'reel')}.mp4"
    # 成片这一步的画质**不降**：preset slow / crf 18 原样保留。省时间要从
    # 中间产物和重复解码上省，不能从最后交出去的这一份上省。
    with stage("烧字幕+成片"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(silent), "-i", str(mixed),
            "-vf", f"subtitles={_escape(ass)}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", FINAL_PRESET, "-crf", FINAL_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", str(final))

    # **不能只审计 `_video.mp4` 中间片。** TTS、sidechaincompress、amix 和
    # 字幕封装都发生在它之后；过去片尾现场声被截断，正是中间片完全正常而最终
    # 音轨提前结束。这里量交付 MP4 的两条独立 stream，失败就不进入清理/提交。
    _audit_final_delivery(final, declared_duration=join_graph.output_duration)

    for junk in list(outdir.glob("part_*.mp4")) + [silent, mixed,
                                                   outdir / "_cover_frame.jpg"]:
        junk.unlink(missing_ok=True)
    # **封面停多久要记下来。** 它现在跟着配音走，光看 spec 算不出来——
    # `check_reel_landed.py` 拿它对片长，没有这份就只能拿常量猜，而猜错的样子
    # 是「片长对不上」，和真出问题长得一模一样。
    (outdir / "render.json").write_text(json.dumps({
        "cover_seconds": round(cover_secs, 3),
        "cover_narrated": cover_voice is not None,
        "segments_seconds": round(sum(s.length for s in segments), 3),
        "film_seconds": round(probe_duration(final), 3),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"成片 {final}（{probe_duration(final):.1f}s，"
          f"{final.stat().st_size / 1e6:.1f} MB）")
    report_timings()
    return final


def _escape(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("probe", help="下载源片并出缩略图墙")
    p.add_argument("--url", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--every", type=float, default=2.0)

    r = sub.add_parser("render", help="按 spec 出成片")
    r.add_argument("--spec", required=True)
    r.add_argument("--outdir", required=True)
    r.add_argument("--source", help="已经下好的源片（跳过下载）")
    r.add_argument("--voice", default="zh-CN-YunxiNeural")
    r.add_argument("--rate", default="+6%")

    args = parser.parse_args()
    outdir = Path(args.outdir)

    if args.mode == "probe":
        outdir.mkdir(parents=True, exist_ok=True)
        source = download(args.url, outdir / "source.mp4")
        w, h = probe_size(source)
        duration = probe_duration(source)
        # **帧率要记进 probe.json。** 多源那条线上，`check_sources_match` 拿
        # 尺寸和帧率一起判，对不上就红——而 probe 之前只报尺寸，于是「这条源
        # 能不能和已有的那条一起剪」要等到 render 跑六分钟之后才知道。
        # 探测的作用就是把这种问题提前，别让它藏到最后一步。
        fps_expr, fps = resolve_fps(source)
        cuts = scene_changes(source)
        print(f"源片 {w}×{h} @ {fps_expr}，{duration:.1f}s，检出 {len(cuts)} 个切点")
        sheets = contact_sheet(source, outdir, every=args.every)
        # 记分条单独拼一版，否则整幅缩完读不出比分。位置按源片分辨率推：
        # 转播把记分条烧在左下，取左边 42%、底部往上 20% 那一块。
        w, h = probe_size(source)
        box = f"{w * 42 // 100}:{h * 20 // 100}:0:{h * 78 // 100}"
        sheets += contact_sheet(source, outdir, every=args.every,
                                crop=box, prefix="score", columns=4,
                                tile_w=520)
        print(f"记分条缩略图墙：crop={box}（源片 {w}x{h}）")
        captions = fetch_captions(args.url, outdir)
        (outdir / "probe.json").write_text(json.dumps({
            "url": args.url, "width": w, "height": h, "duration": duration,
            "fps": fps_expr, "fps_value": round(fps, 3),
            "scene_cuts": cuts, "sheets": [s.name for s in sheets],
            "captions": captions.name if captions else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("缩略图墙:", ", ".join(s.name for s in sheets))
        return 0

    render(load_spec(Path(args.spec)), outdir,
           voice=args.voice, rate=args.rate,
           source_override=Path(args.source) if args.source else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
