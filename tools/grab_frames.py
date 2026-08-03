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


def sample(video: Path, outdir: Path, every: float, width: int) -> list[Path]:
    if not shutil.which("ffmpeg"):
        raise SystemExit("没装 ffmpeg。")
    pat = str(outdir / "frame_%04d.jpg")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-vf", f"fps=1/{every},scale={width}:-2", "-q:v", "2", pat],
        check=True)
    frames = sorted(outdir.glob("frame_*.jpg"))
    # 按秒数重命名，肉眼一看就知道这一帧在片子的哪儿
    out: list[Path] = []
    for i, p in enumerate(frames):
        dest = p.with_name(f"frame_{int(i * every):04d}s.jpg")
        p.rename(dest)
        out.append(dest)
    print(f"[抽帧] {len(out)} 张，每 {every} 秒一张，宽 {width}")
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
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    video = download(args.url, outdir)
    frames = sample(video, outdir, args.every, args.width)
    contact_sheet(frames, outdir / "contact.jpg")
    # 源片不进仓库——几十上百 MB，而帧才是产物
    video.unlink(missing_ok=True)
    print(f"[清理] 删掉源片 {video.name}；留下 {len(frames)} 帧 + 联系表")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
