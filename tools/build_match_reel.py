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

FPS = 30
# 1080 高的源，9:16 的宽 = 1080*9/16 = 607.5。裁剪宽度必须是偶数，取 608。
CROP_H = 1080
CROP_W = 608
COVER_SECONDS = 2.6
# contain 模式横向保留多少。0.62 → 窗口 1190px，球员落在画面 19%~81% 之间都还在，
# 缩到 1080 宽后有 980 高，占屏高一半——比整幅铺进来的 608 高大了六成。
CONTAIN_KEEP = 0.62
# 原声压到多少。留一点现场声（球声、观众），但不能盖过中文解说。
ORIGINAL_GAIN = 0.34


class ReelError(RuntimeError):
    pass


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
    cx: float
    narration: str
    fit: str = "crop"

    @property
    def length(self) -> float:
        return round(self.end - self.start, 3)


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("segments", "cover"):
        if key not in spec:
            raise ReelError(f"spec 缺少 {key}")
    return spec


def cut_segment(source: Path, seg: Segment, dest: Path, source_w: int) -> Path:
    """切一段、裁成 9:16、放大到 1080×1920。

    `-ss` 放在 `-i` **前面**是关键帧级的快速定位，落点可能偏几百毫秒；放在
    后面才是精确定位。高光片段一秒都不能偏，所以用精确定位（慢一点无所谓）。
    """
    # 两种取景，按这一段的内容选，不能一刀切：
    #
    #   crop    真·9:16 裁切，铺满全屏。**只用于特写**——球员脸、庆祝、握手、
    #           看台。主体本来就在正中，裁掉的是空白。
    #   contain 整幅 16:9 缩到卡宽放在卡中央。**回合镜头必须用这个**。
    #           这场转播的主机位里，球员经常跑到画面 20% / 80% 的位置，而
    #           9:16 的窗口只有 32% 宽（608/1920）——硬裁会把人切掉半个。
    #           照片那条「横幅走 contain」的规矩，动态画面同样成立。
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
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,fps={FPS},setsar=1"
        )
    else:
        x = int(round(seg.cx * source_w - CROP_W / 2))
        x = max(0, min(x, source_w - CROP_W))
        chain = (f"crop={CROP_W}:{CROP_H}:{x}:0,"
                 f"scale={VIDEO_W}:{VIDEO_H}:flags=lanczos,fps={FPS},setsar=1")
    # 所有 -i 必须排在滤镜/输出选项前面，否则 ffmpeg 会把 -vf 当成下一个输入的
    # 选项直接报错。源片是纯视频轨（人从网盘传来的那份就是），所以补一条静音轨
    # 进去——后面混音那步要求每段都有音频流。
    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-ss", f"{seg.start:.3f}", "-to", f"{seg.end:.3f}",
        "-filter_complex", chain if seg.fit == "contain" else f"[0:v]{chain}",
        "-shortest", "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
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
    cx = float(cover.get("cx", 0.5))
    x = max(0, min(int(round(cx * source_w - CROP_W / 2)), source_w - CROP_W))
    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{at:.2f}", "-i", str(source), "-frames:v", "1",
        "-vf", f"crop={CROP_W}:{CROP_H}:{x}:0,scale={VIDEO_W}:{VIDEO_H}:flags=lanczos",
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
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=_chromium(), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": VIDEO_W, "height": VIDEO_H},
                                device_scale_factor=1)
        page.goto(page_file.resolve().as_uri())
        page.wait_for_timeout(700)
        page.screenshot(path=str(still), type="jpeg", quality=95)
        browser.close()

    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(still), "-f", "lavfi",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t", f"{COVER_SECONDS}", "-vf", f"fps={FPS},setsar=1",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(dest))
    return dest


def _chromium() -> str:
    """沙箱里 PLAYWRIGHT_BROWSERS_PATH 指的路径带版本号，playwright 自己找不到，
    得显式给。CI 上装的那份在默认位置，glob 一下两边都覆盖。"""
    import glob as _glob
    for pattern in ("/opt/pw-browsers/chromium*/chrome-linux/chrome",
                    str(Path.home() / ".cache/ms-playwright/chromium*/chrome-linux/chrome")):
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
        source = download(spec["source_url"], source)
    # 网盘那份常常只有视频轨（DASH 的自适应流是分开的）。人另外传了 m4a 就在这儿
    # 合上——没有原声的成片只剩解说，球声和观众声全没了，片子会很平。
    audio = spec.get("source_audio")
    if audio and not _has_audio(source):
        merged = outdir / "source_av.mp4"
        if not merged.is_file():
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(source), "-i", str(Path(audio)),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-shortest", str(merged))
        print(f"[audio] 合上原声 {audio}")
        source = merged

    source_w, source_h = probe_size(source)
    print(f"源片 {source_w}×{source_h}，{probe_duration(source):.1f}s")
    if source_h != CROP_H:
        print(f"[注意] 源片不是 1080 高，裁剪按等比换算")

    segments = [Segment(float(s["start"]), float(s["end"]),
                        float(s.get("cx", 0.5)), s.get("narration", "").strip(),
                        str(s.get("fit", "crop")))
                for s in spec["segments"]]
    total = sum(s.length for s in segments) + COVER_SECONDS
    print(f"{len(segments)} 段，画面共 {total:.1f}s")
    if total > 120:
        print(f"[注意] 超过两分钟（{total:.1f}s），按要求应当再砍")

    parts: list[Path] = [build_cover(source, spec, outdir / "part_cover.mp4", source_w)]
    for index, seg in enumerate(segments):
        parts.append(cut_segment(source, seg, outdir / f"part_{index:02d}.mp4",
                                 source_w))

    listing = outdir / "_concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts),
                       encoding="utf-8")
    silent = outdir / "_video.mp4"
    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", str(silent))

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
    if filters:
        chain = ";".join(filters)
        names = "".join(f"[v{i}]" for i, seg in enumerate(segments)
                        if seg.narration.strip())
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(silent), *mix_inputs,
            "-filter_complex",
            f"[0:a]volume={ORIGINAL_GAIN}[bed];{chain};"
            f"[bed]{names}amix=inputs={len(filters)+1}:normalize=0:"
            f"dropout_transition=0[out]",
            "-map", "[out]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            str(mixed))
    else:
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(silent), "-vn", "-c:a", "aac", "-b:a", "192k", str(mixed))

    final = outdir / f"{spec.get('slug', 'reel')}.mp4"
    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(silent), "-i", str(mixed),
        "-vf", f"subtitles={_escape(ass)}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(final))

    for junk in list(outdir.glob("part_*.mp4")) + [listing, silent, mixed,
                                                   outdir / "_cover_frame.jpg"]:
        junk.unlink(missing_ok=True)
    print(f"成片 {final}（{probe_duration(final):.1f}s，"
          f"{final.stat().st_size / 1e6:.1f} MB）")
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
