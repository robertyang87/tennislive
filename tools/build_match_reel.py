#!/usr/bin/env python3
"""把一条官方集锦剪成 9:16 的竖版短片：只留高光、中文解说、字幕、封面。

两段式，因为**选段必须靠眼睛**：

    probe   下载源片 → 出场景切点 + 一张缩略图墙（带时间码）→ 提交进仓库
            人（或我）看着这张图挑出要哪几段、每段横向裁在哪儿
    render  按 spec.json 剪 → 裁 9:16 → 合成中文解说 → 烧字幕 → 加封面 → 成片

## 为什么必须在 GitHub Actions 上跑

**沙箱的 IP 被 YouTube 挡了**：yt-dlp 拿得到清单和格式表（走 android_vr 的
player API），一取媒体就 403；用真 Chromium 打开播放页，页面直接是
「Our systems have detected unusual traffic from your computer network」，
`playabilityStatus` = `UNPLAYABLE`。这不是「视频不存在」，是**这台机器不让下**
——又一次「空结果先自证是真空」。edge-tts 同理，本地取不到。

## 裁剪：横向裁到 9:16，不是加模糊边

1920×1080 裁成 9:16 就是 **608×1080**，再放大到 1080×1920。网球转播的主机位
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
    VIDEO_H,
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
# 1080 高的源，9:16 的宽 = 1080*9/16 = 607.5。裁剪宽度必须是偶数，取 608。
CROP_H = 1080
CROP_W = 608
COVER_SECONDS = 2.6
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
    selector = (
        "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/"
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    )
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
        print(f"[cookies] 用 {jar}")

    failures: list[str] = []
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, "--js-runtimes", "node", "--no-warnings", "-f", selector,
             *cookies, *extra, "--merge-output-format", "mp4",
             "-o", str(dest), url],
            capture_output=True, text=True,
        )
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            print(f"[ok] {label} 下到了 {dest.stat().st_size / 1e6:.1f} MB")
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
# **不出画就不摇。** 窗口只有 608 宽（源片的 32%），原来是 40px 死区跟着质心走，
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


def auto_center(source: Path, seg: "Segment", source_w: int) -> float:
    """不摇的那些段，固定中心取**整段运动质心的中位数**。

    钉死画面不等于钉在正中：庆祝那一屏人偏左，钉在 0.5 就把他挤到边上。
    中位数比均值稳——中间一两次大幅挥拍带不动它。
    """
    coarse = track_run(source, seg.start, seg.end, source_w, quiet=True)
    if not coarse:
        return 0.5
    import numpy as np

    return float(np.median([x for _, x in coarse])) / source_w


def track_shots(source: Path, segments: list["Segment"],
                source_w: int) -> dict[int, list[tuple[float, int]]]:
    """把在源片里连着的段合成一个镜头跟一次，再切回各段。

    「连着」的判据是**上一段的 end 就是这一段的 start**。spec 里之所以要断开，
    是为了给不同的旁白和不同的画面文字配时间，源片那边并没有剪；镜头一断，
    跟踪就重新起步，交界处窗口瞬移（实测 222 / 448 / 399 px）。

    顺带把不摇的那些段的固定中心也定了（`auto_center`）。
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
    for index, seg in enumerate(segments):
        if seg.track or seg.fit == "contain" or seg.cx is not None:
            continue
        with stage("定心抽帧"):
            seg.cx = auto_center(source, seg, source_w)
        print(f"    [fixed] 第 {index} 段不摇，固定中心 cx={seg.cx:.3f}")
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
    """切一段、裁成 9:16、放大到 1080×1920。

    `-ss` 放在 `-i` **前面**是关键帧级的快速定位，落点可能偏几百毫秒；放在
    后面才是精确定位。高光片段一秒都不能偏，所以用精确定位（慢一点无所谓）。
    """
    # 两种取景。**默认 crop，铺满全屏——回合镜头也一样。**
    #
    #   crop    真·9:16 裁切，铺满全屏。窗口只有 32% 宽（608/1920），球飞到
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
            chain = (f"crop={CROP_W}:{CROP_H}:{x}:0,"
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
    """封面：从片子里抓一帧当底，压暗，写台头 / 大标题 / 赛果 / 落款。

    **走和知识帖、开球之前同一套字**——`webcards._font_css()` 里那几张脸：
    标题用 TL Display SC（得意黑），正文用 TL Sans SC（思源黑），比分用
    TL Numeral（Montserrat）。所以这里不再用 PIL 画字，改成渲 HTML 再截图：
    PIL 那条路拿的是系统里随便一个 CJK 字体，和卡片上的标题根本不是一家。
    """
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from tennislive.render.webcards import _font_css  # noqa: PLC0415
    from tennislive.video.explainer import _data_uri  # noqa: PLC0415

    cover = spec["cover"]
    grab = dest.parent / "_cover_frame.jpg"
    at = float(cover.get("frame_at", 3.0))
    # 封面的固定中心和分段一样可以自己定：**源片在本地看不到时更需要它**
    # （YouTube 对沙箱一律 403，cx 只能靠猜，猜错就是把人裁到边上）。
    # 取抓帧前后两秒的运动质心中位数——握手、庆祝这类镜头人不在正中。
    if cover.get("cx") is None:
        probe = Segment(max(0.0, at - 1.2), at + 1.2, None, "")
        cx = auto_center(source, probe, source_w)
        print(f"    [cover] 没给 cx，自动定心 cx={cx:.3f}")
    else:
        cx = float(cover["cx"])
    # 底图两种铺法：
    #
    #   cover（默认）  真·竖版大图，9:16 裁切铺满整屏。1080p 里裁 608 宽再拉到
    #                 1080，是放大 1.78 倍，本来会糊——所以走 lanczos 再补一道
    #                 轻 unsharp，把放大吃掉的边缘找回来一点。**人要在框里**，
    #                 cx 按握手那两个人的位置量。
    #   contain       整幅缩到 1080 宽（是缩小，最清晰），两侧用同一帧放大模糊
    #                 垫满。清楚，但画面只占屏高一半多，冲击力折一半。
    #
    # 先用过 contain，反馈是"要竖版大图"——封面这一屏首要是**砸下来**，
    # 清晰度排第二，何况上面还压着渐变和大标题。
    if str(cover.get("fill", "cover")) == "contain":
        chain = (f"[0:v]split=2[bg][fg];"
                 f"[bg]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                 f"crop={VIDEO_W}:{VIDEO_H},boxblur=46:2,eq=brightness=-0.22[bgb];"
                 f"[fg]scale={VIDEO_W}:-2:flags=lanczos[fgs];"
                 f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2[out]")
    else:
        x = max(0, min(int(round(cx * source_w - CROP_W / 2)), source_w - CROP_W))
        chain = (f"[0:v]crop={CROP_W}:{CROP_H}:{x}:0,"
                 f"scale={VIDEO_W}:{VIDEO_H}:flags=lanczos,"
                 f"unsharp=5:5:0.7:5:5:0.0[out]")
    with stage("封面抓帧"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{at:.2f}", "-i", str(source), "-frames:v", "1",
            "-filter_complex", chain, "-map", "[out]",
            "-q:v", "2", str(grab))

    lines = "".join(
        f"<div>{line.strip()}</div>"
        for line in str(cover.get("hook", "")).split("\n") if line.strip()
    )
    html = f"""<!doctype html><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{VIDEO_W}px;height:{VIDEO_H}px;overflow:hidden;background:#04120d}}
.f{{position:absolute;inset:0;background-image:url('{_data_uri(grab)}');
   background-size:cover;background-position:center}}
/* 渐变从 44% 高处才起，到文字那一带接近全黑——压暗要按文字落在哪一段算，
   不是整张按比例推。上半张几乎不动，糊了就看不出是哪一场。 */
.s{{position:absolute;inset:0;background:linear-gradient(
   180deg,rgba(4,18,13,0) 44%,rgba(4,18,13,.72) 62%,rgba(4,18,13,.94) 78%)}}
.c{{position:absolute;left:78px;right:78px;bottom:250px;z-index:3;
   display:flex;flex-direction:column;align-items:flex-start;gap:26px}}
.k{{background:#c6f65a;color:#062018;font-family:'TL Sans SC',sans-serif;
   font-size:30px;font-weight:800;letter-spacing:4px;padding:11px 26px;
   border-radius:999px}}
.t{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-weight:400;
   font-size:104px;line-height:1.16;color:#f4fbf7;letter-spacing:1px;
   text-shadow:0 4px 30px rgba(0,0,0,.55)}}
.n{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:600;
   font-size:52px;color:#c6f65a;letter-spacing:1px}}
.b{{font-family:'TL Sans SC',sans-serif;font-weight:400;font-size:34px;
   color:#9fb4aa;letter-spacing:2px}}
</style><div class="f"></div><div class="s"></div><div class="c">
<div class="k">{cover.get('eyebrow','')}</div>
<div class="t">{lines}</div>
<div class="n">{cover.get('score','')}</div>
<div class="b">{cover.get('sub','')}</div></div>"""

    page_file = dest.parent / "_cover.html"
    page_file.write_text(html, encoding="utf-8")
    still = dest.parent / "_cover.jpg"
    with stage("封面截图"), sync_playwright() as pw:
        # 先让 playwright 自己找（CI 上装在它的默认位置）；找不到再回退到
        # 显式路径（沙箱里 PLAYWRIGHT_BROWSERS_PATH 指的目录带版本号，
        # playwright 自己对不上）。反过来写就会像这次一样：CI 上直接
        # 「找不到 chromium」，而它其实装好了，只是不在我猜的那两个路径里。
        try:
            browser = pw.chromium.launch(args=["--no-sandbox"])
        except Exception:  # noqa: BLE001
            browser = pw.chromium.launch(
                executable_path=_chromium(), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": VIDEO_W, "height": VIDEO_H},
                                device_scale_factor=1)
        page.goto(page_file.resolve().as_uri())
        page.wait_for_timeout(700)
        page.screenshot(path=str(still), type="jpeg", quality=95)
        browser.close()

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


def render(spec: dict, outdir: Path, *, voice: str, rate: str,
           source_override: Path | None = None) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
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
    if source_h != CROP_H:
        print(f"[注意] 源片不是 1080 高，裁剪按等比换算")

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

    # 每段解说落在它那一段的**开头**，字幕跟着同一个偏移
    cues: list[tuple[float, float, str]] = []
    mix_inputs: list[str] = []
    filters: list[str] = []
    offset = COVER_SECONDS
    for index, (seg, (path, marks)) in enumerate(zip(segments, voices)):
        if seg.narration.strip():
            spoken = probe_duration(path)
            if spoken > seg.length + 0.35:
                print(f"[注意] 第 {index + 1} 段解说 {spoken:.1f}s 比画面 "
                      f"{seg.length:.1f}s 长，字幕会压到下一段")
            mix_inputs.extend(["-i", str(path)])
            filters.append(
                f"[{len(mix_inputs)//2}:a]adelay={int(offset*1000)}|"
                f"{int(offset*1000)}[v{index}]")
            cues.extend(subtitle_cues(readable(seg.narration), spoken,
                                      boundaries=marks, offset=offset))
        offset += seg.length

    ass = write_subtitles(cues, outdir / "subtitles.ass")
    print(f"字幕 {len(cues)} 行 → {ass.name}（上锚 MarginV={_ASS_MARGIN_V}，"
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
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
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
