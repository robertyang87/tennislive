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
# 封面停多久。**2.6 秒太长**——账号所有者：「好多人以为是图片不是视频」。
# 封面同时是信息流里的缩略图，点进来的人已经看过它了；画面迟迟不动，
# 第一反应是「这是张图」，划走。1.2 秒够读完两行钩子加一行比分，
# 又能让第一个回合立刻接上。
COVER_SECONDS = 1.2
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
    selector = "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"
    sort = ["-S", "res:1080,fps,vcodec:h264,acodec:m4a"]
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
        print(f"[cookies] 用 {jar}")

    failures: list[str] = []
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, "--js-runtimes", "node", "--no-warnings", "-f", selector,
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
                  columns: int = 6, tile_w: int = 360) -> list[Path]:
    """每 `every` 秒抓一帧，烧上时间码，拼成几张缩略图墙。

    时间码必须烧进画面里——不然看图挑完段，还得数第几格再乘回去，数错一次
    整段就切偏了。
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
            "-vf", (f"scale={tile_w}:-2,"
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
        sheet = outdir / f"contact_{n // per_sheet:02d}.jpg"
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

    @property
    def length(self) -> float:
        return round(self.end - self.start, 3)


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("segments", "cover"):
        if key not in spec:
            raise ReelError(f"spec 缺少 {key}")
    return spec


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


def track_shots(source: Path, segments: list["Segment"],
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
        joins = (runs and trackable
                 and abs(seg.start - segments[runs[-1][-1]].end) < 1e-3
                 and segments[runs[-1][-1]].fit != "contain"
                 and segments[runs[-1][-1]].track)
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
            coarse = track_run(source, start, end, source_w)
        if len(members) > 1:
            print(f"    [track] 上面这条是 {len(members)} 段连着的同一个镜头")
        for index in members:
            tracks[index] = sample_track(coarse, segments[index])
    return tracks


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
            "-ss", f"{seg.start:.3f}", "-i", str(source), *extra_in,
            # 时长而不是 `-to`：`-ss` 变成输入选项之后输出时间轴从 0 起算，
            # 再写 `-to seg.end` 会把整段截没。
            "-t", f"{seg.length:.3f}",
            # 输出必须打标签并显式 map：`-map 0:v:0` 取的是**原始流**，
            # 会把整个滤镜图绕过去——裁切、缩放、跟踪全不生效，成片直接是 16:9。
            "-filter_complex",
            (chain + "[vout]") if seg.fit == "contain" else f"[0:v]{chain}[vout]",
            "-shortest", "-map", "[vout]",
            "-map", "0:a:0" if has_audio else "1:a:0",
            # 分段是**中间产物**：最后整片还要以 crf 18 重编一次，这里编到
            # crf 17/preset slow 是把画质编进一个马上被重编的文件里，白花时间。
            # medium/crf 20 在同一段上 6.2s → 4.0s，重编后的成片肉眼无差。
            # 成片那一步的参数没有动。
            "-c:v", "libx264", "-preset", PART_PRESET, "-crf", PART_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", AUDIO_RATE,
            str(dest))
    return dest


def build_cover(source: Path, spec: dict, dest: Path, source_w: int) -> Path:
    """封面：**一律走「赛场之上」的固定海报模板**（`tools/versus_poster.py`）。

    账号所有者定的：「以后『赛场之上』封面海报都用新的模板方案。」所以这里
    **没有第二条路**——抓一帧当封面那条分支已经删掉了，不是留着当兜底。
    留着兜底的后果是可预见的：哪条片子一时找不到照片，就悄悄退回抽帧，
    栏目的封面从此有两副面孔，而且退回去的那次没人会注意到。

    抽帧本来就不该当默认：1920×1080 的一帧裁成竖版要放大一倍多，比一张官方
    原图软一大截，而封面是唯一决定人点不点的那一屏。

    缺图就报错，并把出路写在报错里——**去扩检索源**（赛事官方图库 → 协会/赛事
    新闻页 → 新闻站与图片社 → Commons/Flickr），不是退回抽帧。
    """
    cover = spec["cover"]
    if not cover.get("versus"):
        raise ReelError(
            "封面缺 `cover.versus`：赛场之上的封面一律走固定海报模板，"
            "要两个人各一张**本场**的真实照片。\n"
            "找不到就去扩检索源（赛事官方图库 → 协会/赛事新闻页 → 新闻站/图片社 "
            "→ Commons/Flickr），别退回从视频里抽帧——那条路已经删了。\n"
            "格式：cover.versus = {split, names: [上, 下], "
            "top: {image, focus, focus_y, zoom, fit}, bottom: {…}}")
    return build_versus_poster(source, cover, dest)


def build_versus_poster(source: Path, cover: dict, dest: Path) -> Path:
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

    versus = dict(cover["versus"])
    layout = str(cover.get("layout", "cutout"))

    def _grab(spot: dict, tag: str) -> str:
        """`image` 直接用，`frame_at` 从源片抓一帧。抓出来的不进仓库。"""
        if spot.get("image"):
            if not Path(spot["image"]).is_file():
                raise ReelError(f"VS 拼接的 {tag} 找不到图：{spot['image']}")
            return str(spot["image"])
        grab = dest.parent / f"_versus_{tag}.jpg"
        with stage(f"VS 抓帧 {tag}"):
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{float(spot['frame_at']):.2f}", "-i", str(source),
                "-frames:v", "1", "-q:v", "2", str(grab))
        return str(grab)

    if layout == "cutout":
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
                panel["cutout"] = _cut_person(source, panel, key, dest.parent)
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
    with stage("封面海报"):
        build_poster({**cover, "versus": versus}, poster, layout=layout)
    poster.with_suffix(".html").unlink(missing_ok=True)   # 内嵌 data URI，十几 MB
    print(f"    [封面] 赛场之上海报 {layout} → {poster.name}")
    return _still_to_clip(poster, dest)


#: 抠图模型。三个都试过并把 alpha 摊在棋盘格上看边：u2net 和 u2net_human_seg
#: 把锦织圭的发梢切平了一条，isnet 保住了。
CUT_MODEL = "isnet-general-use"


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
        cut = cut.crop(bbox)
        cut.save(out)
    print(f"    [封面] {tag} 抽帧抠图 {panel['frame_at']}s → {cut.size[0]}×{cut.size[1]}")
    raw.unlink(missing_ok=True)
    return str(out)


def _still_to_clip(still: Path, dest: Path) -> Path:
    """封面静图 → 一小段带静音轨的视频，接进片头。"""
    with stage("封面编码"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(still), "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}",
            "-t", f"{COVER_SECONDS}", "-vf", f"fps={FPS_EXPR},setsar=1",
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


def synthesize(segments: list[Segment], outdir: Path, voice: str, rate: str
               ) -> list[tuple[Path, list[dict]]]:
    # 一段解说都没有就别碰 edge-tts——沙箱里根本装不上，而"没有解说的片子"
    # 是个合法的形态（先看画面剪得对不对，再配音）
    if not any(seg.narration.strip() for seg in segments):
        return [(outdir / f"voice_{i:02d}.mp3", []) for i in range(len(segments))]

    import asyncio

    import edge_tts

    async def one(text: str, path: Path) -> list[dict]:
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

    out: list[tuple[Path, list[dict]]] = []
    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        if not seg.narration.strip():
            out.append((path, []))
            continue
        marks = asyncio.run(one(seg.narration, path))
        if not path.is_file() or path.stat().st_size == 0:
            raise ReelError(f"第 {index + 1} 段 TTS 没出音频")
        path.with_suffix(".words.json").write_text(
            json.dumps(marks, ensure_ascii=False), encoding="utf-8")
        out.append((path, marks))
    return out


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


def render(spec: dict, outdir: Path, *, voice: str, rate: str,
           source_override: Path | None = None) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    _preflight_cutout(spec)
    source = source_override or (outdir / "source.mp4")
    if not source.is_file():
        with stage("下载源片"):
            source = download(spec["source_url"], source)
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

    source_w, source_h = probe_size(source)
    # 成片帧率跟着源片走。硬定 30 而源片是 25，就是每 5 帧补一帧，一秒卡五次。
    global FPS, FPS_EXPR
    FPS_EXPR, FPS = resolve_fps(source)
    print(f"源片 {source_w}×{source_h}，{probe_duration(source):.1f}s")
    resolve_crop(source_w, source_h, spec.get("crop_y"))
    portrait = source_w * 4 < source_h * 3

    # **默认不摇。** 窗口只有源片的 32% 宽，一横摇，画面里本该静止的底线、球网、
    # 广告板、看台全跟着滑；源片是 25 fps，滑动的静止物最容易看出一格一格。
    # 真人看下来的结论就是「固定中心的感觉更好」，所以横摇改成**按段显式打开**
    # （`"track": true`），只留给主机位的宽景回合。
    segments = [Segment(float(s["start"]), float(s["end"]),
                        None if s.get("cx") is None else float(s["cx"]),
                        s.get("narration", "").strip(),
                        str(s.get("fit", "crop")), bool(s.get("track", False)))
                for s in spec["segments"]]
    total = sum(s.length for s in segments) + COVER_SECONDS
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
    tracks = track_shots(source, segments, source_w)

    parts: list[Path] = [build_cover(source, spec, outdir / "part_cover.mp4", source_w)]
    for index, seg in enumerate(segments):
        parts.append(cut_segment(source, seg, outdir / f"part_{index:02d}.mp4",
                                 source_w, tracks.get(index)))

    listing = outdir / "_concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts),
                       encoding="utf-8")
    silent = outdir / "_video.mp4"
    with stage("拼接"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", str(silent))

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
    offset = COVER_SECONDS
    for index, (seg, (path, marks)) in enumerate(zip(segments, voices)):
        if seg.narration.strip():
            spoken = spoken_of[index]
            mix_inputs.extend(["-i", str(path)])
            filters.append(
                f"[{len(mix_inputs)//2}:a]adelay={int(offset*1000)}|"
                f"{int(offset*1000)}[v{index}]")
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
            names = "".join(f"[v{i}]" for i, seg in enumerate(segments)
                            if seg.narration.strip())
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(silent), *mix_inputs,
                "-filter_complex",
                f"[0:a]volume={BED_LOUD}[bed];{chain};"
                f"{names}amix=inputs={len(filters)}:normalize=0[voice];"
                f"[voice]asplit=2[vk][vm];"
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

    for junk in list(outdir.glob("part_*.mp4")) + [listing, silent, mixed,
                                                   outdir / "_cover_frame.jpg"]:
        junk.unlink(missing_ok=True)
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
        cuts = scene_changes(source)
        print(f"源片 {w}×{h}，{duration:.1f}s，检出 {len(cuts)} 个切点")
        sheets = contact_sheet(source, outdir, every=args.every)
        (outdir / "probe.json").write_text(json.dumps({
            "url": args.url, "width": w, "height": h, "duration": duration,
            "scene_cuts": cuts, "sheets": [s.name for s in sheets],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("缩略图墙:", ", ".join(s.name for s in sheets))
        return 0

    render(load_spec(Path(args.spec)), outdir,
           voice=args.voice, rate=args.rate,
           source_override=Path(args.source) if args.source else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
