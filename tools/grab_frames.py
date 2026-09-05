#!/usr/bin/env python3
"""从一条 YouTube 视频里抽候选帧，用来给某一屏配图。

**为什么要在 runner 上跑**：YouTube 对机房 IP 一律「Sign in to confirm you're
not a bot」，沙箱里 yt-dlp 拿到 403 或 DRM 报错。runner 上有整套解法
（bgutil PO token provider 起在 4416 + `YT_COOKIES_TXT`），match-reel 那条线
一直在用——这个脚本复用它的 client 梯子和 cookie 约定，不另写一套。

**为什么产物要提交进仓库**：这个沙箱下不动 artifact（`api.github.com` 是 403），
所以帧只能进仓库我才看得到。见 CLAUDE.md「这台沙箱的两条硬限制」。

    python3 tools/grab_frames.py <youtube-url> -o <目录> [--every 2.0] [--width 1600]

产物：`frame_<秒数>.jpg` 一批，外加一张 `contact.jpg` 联系表——
**先看联系表**，一眼扫完再决定打开哪几张，比逐张点开省事得多
（`tools/build_grand_slam_v2` 那条线上一直是这么干的）。

⚠️ 抽出来的帧**仍然要过四道闸门**，尤其是第一道：这一屏讲的事，画面对不对得上。
帧来自哪条视频要写进 credits，视频本身的四要素（谁、哪一站、哪一天）由频道和
标题自证——所以**只用赛事官方或球员官方频道的片子**，不用二创和集锦搬运。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _ytdlp_ladder():
    """复用 match-reel 那套 client 梯子，别另写一份会分叉的。"""
    try:
        from build_match_reel import YTDLP_BASE, _ladder  # noqa: PLC0415
        return YTDLP_BASE, _ladder()
    except Exception as exc:  # 导入失败要出声，别悄悄退回一个更弱的梯子
        print(f"[警告] 取不到 match-reel 的 client 梯子（{exc}），退回单档 web")
        return ["--js-runtimes", "node"], [
            ("web", ["--extractor-args", "youtube:player_client=web"])
        ]


def download(url: str, outdir: Path) -> Path:
    binary = shutil.which("yt-dlp")
    if not binary:
        raise SystemExit("没装 yt-dlp。工作流里要 `pip install yt-dlp`。")
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
        print(f"[下载] 带 cookie（{jar}）")
    else:
        print("[下载] 没有 cookie，只靠 PO token + client 梯子")

    base, ladder = _ytdlp_ladder()
    dest = outdir / "source.mp4"
    tried: list[str] = []
    for label, extra in ladder:
        proc = subprocess.run(
            [binary, *base, "-f", "bv*[height>=720]+ba/bv*+ba/b*/b/worst",
             "--merge-output-format", "mp4",
             "-o", str(outdir / "source.%(ext)s"), url, *cookies, *extra],
            capture_output=True, text=True)
        # `-o` 是模板不是保证：合流编码装不进 mp4 时 yt-dlp 会自己改后缀
        got = sorted(outdir.glob("source.*"))
        got = [p for p in got if p.suffix.lower() in (".mp4", ".mkv", ".webm")]
        if got:
            print(f"[下载] {label} 拿到 {got[0].name}（{got[0].stat().st_size} 字节）")
            return got[0]
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["(无输出)"]
        tried.append(f"  {label}: {tail[0][:110]}")
    # 空结果要自证是真空：把每一档失败的原因都列出来，别只说「下不动」。
    # 而 `Requested format is not available` 这一支尤其要**把实际有哪些格式打出来**——
    # 「片子只有 DRM 格式」和「我的选择器写错了」报出来一模一样，不列格式分不出。
    print("所有 client 都没下动：\n" + "\n".join(tried), file=sys.stderr)
    print("\n[诊断] 服务端到底给了哪些格式：", file=sys.stderr)
    subprocess.run([binary, *base, "--list-formats", url, *cookies],
                   check=False)
    raise SystemExit(1)


def frame_stamp(seconds: float) -> str:
    """一帧的文件名。**名字里那个数必须是片子里的绝对秒数。**

    挑封面时 `cover.frame_at` 直接照抄这个数，所以它错多少、封面就偏多少。
    2026-09-04 挑孟菲尔斯告别仪式的封面时，我拿缩略图墙的格号乘了个 4.9
    （真步长是 storyboard 自报的 1/fps = 4.8947），39 格下来偏了 0.2 秒——
    正好跨过一个镜头切点，渲出来是另一个画面，而闸只会说「没检出正面人脸」。
    所以截了一段之后，名字要按 `start + i*every` 算，不是按 `i*every`。

    整秒仍然是老的四位补零写法（既有产物一个字节不变、也还排得了序）；
    只有 `--every`/`--start` 带小数时才多一位。
    """
    if float(seconds).is_integer():
        return f"frame_{int(seconds):04d}s.jpg"
    return f"frame_{seconds:07.1f}s.jpg"


def probe_size(video: Path) -> tuple[int, int]:
    """源片的像素尺寸。读不出来回 `(0, 0)`，**不抛**——这是诊断信息，
    不该让一次抽帧因为 ffprobe 缺席或者流里没写尺寸而整个失败。
    """
    if not shutil.which("ffprobe"):
        return (0, 0)
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
             str(video)],
            check=True, capture_output=True, text=True).stdout.strip()
        w, h = out.split("x")[:2]
        return (int(w), int(h))
    except Exception:
        return (0, 0)


def sample(video: Path, outdir: Path, every: float, width: int,
           start: float = 0.0, end: float = 0.0) -> list[Path]:
    """抽帧。`start`/`end` 给的是**片子里的秒数**，不给就是整条。

    ⚠️ 截一段不是为了省时间，是为了**别把整条片子的帧都塞进仓库**：
    这个工具的产物是提交进 git 的（沙箱下不动 artifact），372 秒的片子
    按 1 秒一帧就是 372 张、上百 MB，而想看的往往只有其中十几秒。
    """
    if not shutil.which("ffmpeg"):
        raise SystemExit("没装 ffmpeg。")
    if end and end <= start:
        raise SystemExit(f"--end {end:g} 要大于 --start {start:g}。")
    # **先报源片是多大，再抽。** `scale={width}:-2` 只往一个方向走：给的宽
    # 比源片窄就是静默降采样，比源片宽就是静默放大——两种都不报错，画面看着
    # 都挺好，只有把两版并排才看得出亏了（CLAUDE.md 记过一次：源片 1920 写了
    # 1600）。把源片的真实尺寸打进日志，这一类就不再是「事后才发现」。
    #
    # 顺带它是这条线上**唯一**能在 runner 上量到源片分辨率的地方：沙箱的
    # YouTube 格式表被 n challenge / 429 挡着，`--print height` 恒空，而
    # 「片头必须是 1080p 官方集锦」那道闸要的正是这个数。
    src_w, src_h = probe_size(video)
    if src_w and src_h:
        how = "原样" if width == src_w else ("放大" if width > src_w else "降采样")
        print(f"[源片] {src_w}x{src_h}　→ 抽帧宽 {width}（{how}）")
    else:
        print(f"[源片] ⚠️ ffprobe 读不出尺寸，抽帧宽 {width} 是降是放不知道")
    pat = str(outdir / "frame_%04d.jpg")
    # `-ss` 放在 `-i` 前面走快速定位；时长用 `-t` 给（`-to` 在这个位置的
    # 语义随 ffmpeg 版本变过，`-t` 没有这个歧义）。
    seek = ["-ss", f"{start:g}"] if start else []
    span = ["-t", f"{end - start:g}"] if end else []
    subprocess.run(
        ["ffmpeg", "-v", "error", *seek, "-i", str(video), *span,
         "-vf", f"fps=1/{every},scale={width}:-2", "-q:v", "2", pat],
        check=True)
    frames = sorted(outdir.glob("frame_[0-9][0-9][0-9][0-9].jpg"))
    # 按秒数重命名，肉眼一看就知道这一帧在片子的哪儿
    out: list[Path] = []
    for i, p in enumerate(frames):
        dest = p.with_name(frame_stamp(start + i * every))
        p.rename(dest)
        out.append(dest)
    span_text = f"（{start:g}s~{end:g}s）" if (start or end) else ""
    print(f"[抽帧] {len(out)} 张，每 {every} 秒一张，宽 {width}{span_text}")
    return out


def contact_sheet(frames: list[Path], dest: Path, cols: int = 6) -> None:
    from PIL import Image, ImageDraw
    if not frames:
        print("[联系表] 一帧都没有，跳过")
        return
    tw = 320
    thumbs = []
    for p in frames:
        im = Image.open(p).convert("RGB")
        thumbs.append((p.stem, im.resize((tw, round(tw * im.height / im.width)))))
    th = max(t.height for _, t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (18, 24, 20))
    draw = ImageDraw.Draw(sheet)
    for i, (name, t) in enumerate(thumbs):
        x, y = (i % cols) * tw, (i // cols) * (th + 22)
        sheet.paste(t, (x, y))
        draw.text((x + 6, y + th + 4), name, fill=(200, 220, 205))
    sheet.save(dest, quality=88)
    print(f"[联系表] {dest.name}  {sheet.size[0]}x{sheet.size[1]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--every", type=float, default=2.0, help="每几秒抽一帧")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--start", type=float, default=0.0,
                    help="从片子的第几秒开始抽（默认从头）")
    ap.add_argument("--end", type=float, default=0.0,
                    help="抽到第几秒为止（默认到尾）")
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    video = download(args.url, outdir)
    frames = sample(video, outdir, args.every, args.width,
                    args.start, args.end)
    contact_sheet(frames, outdir / "contact.jpg")
    # 源片不进仓库——几十上百 MB，而帧才是产物。
    #
    # ⚠️ **要按 `source.*` 扫，不能只删 `video` 那一个文件名。** 2026-08-03
    # 抽 `u2DJ5-OhJaY` 时 yt-dlp 留下了一个 `source.f137.mp4.part`（DASH 分流
    # 下载的残留），而 `video` 指的是合流之后的 `source.mp4`——于是那 9.6 MB
    # 的残片被 `git add --sparse` 一起提交进了仓库。**帧一张不少、日志一句
    # 不响**，是 `test_下载残留不进仓库` 事后才把它抓出来的，而那时它已经
    # 推上去了。又一次「兜底出事的时候不吭声」。
    #
    # 删了什么要**列出来**：只说「删掉源片」的话，多删少删长得一模一样。
    leftovers = sorted(p for p in outdir.glob("source.*") if p.is_file())
    for path in leftovers:
        size = path.stat().st_size
        path.unlink()
        print(f"[清理] 删掉 {path.name}（{size / 1048576:.1f} MB）")
    if not leftovers:
        print("[清理] 没有要删的源片——⚠️ 这不正常，下载那一步应该留下 source.*")
    print(f"[清理] 留下 {len(frames)} 帧 + 联系表")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
