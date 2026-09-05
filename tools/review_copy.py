#!/usr/bin/env python3
"""把成片压成一个能发给账号所有者看的**审片版**（默认 ≤28 MiB）。

来路：账号所有者 2026-08-05「**那以后你要单独发出来我看一下呀，你不发出来我
怎么在这里看呀？**」。而 `SendUserFile` 的上限是 **30 MiB**，这条线的成片按
实测 5700 kb/s 算 **90 秒就 63 MiB**——**基本每一条都超**，不是边角情况。
`wang-kasatkina` 那次 37.7 MiB 被退回，我当场临时切片段，属于现搓；写成脚本
是为了别再搓第二次。

⚠️ **审片版只用来看，不许当成片。** 发微信的永远是 `output/` 里那份原码率的。
所以输出文件名硬性带 `-审片版`，肉眼就能分出来——这条线为「两个地址两条片子，
谁也没说哪个是哪个」栽过（见 CLAUDE.md 里 Release 那节）。

⚠️ **2026-09-05 起这是一条常规动作，不是应急手段**：账号所有者点开微信里那个
▶ 按钮「视频也下不下来」——它指向 `release-assets.githubusercontent.com`
（GitHub 的 Release CDN，响应头写着 `attachment` + `octet-stream`），而他在国内。
量出来的对照很干净：同一条推送里**海报走 gcore.jsdelivr 是好的**，而复制页
（github.io）和成片（Release）**两个 GitHub 域名的都打不开**。他定的处置是
「对话里发审片版」，所以**每条片子渲完就跑一趟这个脚本，把审片版发进对话**。

用法：
    python3 tools/review_copy.py --slug shang-rublev          # 常规路，自己去 Release 拉
    python3 tools/review_copy.py <成片路径>                    # 成片已经在手上时
    python3 tools/review_copy.py --slug <slug> --mib 20 --width 640
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

MIB = 1024 * 1024
# 30 MiB 是硬上限，留 2 MiB 给容器开销和码率控制的抖动
DEFAULT_TARGET_MIB = 28
# 音轨给足：审片最要紧的一维是配音（断句、气口、音色），不能为了省体积压糊
AUDIO_KBPS = 96


def probe_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"ffprobe 读不出 {path}：{out.stderr.strip()[:200]}")
    return float(json.loads(out.stdout)["format"]["duration"])


def fetch_released_film(slug: str) -> Path:
    """按 slug 反查产物目录，把 Release 上那份成片拉到**专用临时目录**。

    来路：2026-09-05 账号所有者「视频也下不下来」——微信里那个 ▶ 按钮指向
    `release-assets.githubusercontent.com`（GitHub 的 Release CDN，`attachment`
    + `octet-stream`），他在国内点不开。定下来的处置是**渲完在对话里发一份
    审片版**，而在这之前要三步手工（curl → review_copy → mv），所以收成一条命令
    ——「只有一个说得通的下一步时，让它便宜到不会被跳过」。

    ⚠️ **拉回来那份 64 MB 的原片一律落在临时目录，绝不落 `output/`。**
    这条线为它栽过：`check_reel_landed` 按产物目录找成片，图省事把 Release
    那份下到了它要找的位置，验完顺手 `git add -A`，差 30 秒就把一个 41.8 MB
    的 mp4 提交进历史（`git show --stat` 第一行才看见）。「一个躺在被跟踪目录里
    的未跟踪大文件」是个盲区：`test_成片一律走Release不进git` 查的是
    `git ls-files`，那一刻它还没被跟踪，三道闸一道都不响。

    ⚠️ **链接从 `render.json` 读，不自己拼**——出处只有一处
    （`push_reel.released_video_url`）。自己拼一份必然分叉，而分叉的样子是
    「拉回来的是另一条片子」或者一个 404，两种都不吭声。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import push_reel  # noqa: PLC0415  # 只为复用那一处出处，不在模块顶层拖依赖

    root = Path(__file__).resolve().parent.parent
    # 日期目录按上海时间分而沙箱跑在 UTC，别去算「今天」——排序取最新的那一天，
    # 两种时区下都对（和 `render_cover_local.find_outdir` 同一个理由）。
    hits = sorted(root.glob(f"output/*/reel/{slug}"), reverse=True)
    if not hits:
        raise SystemExit(
            f"output/ 里找不到 {slug} 的产物目录。\n"
            "  slug 写错了？还是这条片子的产物没在这个工作区里（先 git fetch/checkout）？")
    outdir = hits[0]

    url = push_reel.released_video_url(outdir)
    if not url:
        # 走过 Release 之前的老片子，成片就在产物目录里
        local = outdir / f"{slug}.mp4"
        if local.is_file():
            print(f"[审片版] {outdir} 里就有成片，不用下载")
            return local
        raise SystemExit(
            f"{outdir}/render.json 里没有 video_url，{local} 也不在。\n"
            "  这条片子还没渲完？先看一眼那份 render.json。")

    import urllib.request

    tmp = Path(tempfile.mkdtemp(prefix="review-copy-"))
    dest = tmp / f"{slug}.mp4"
    print(f"[审片版] 从 Release 拉成片：{url}")
    try:
        urllib.request.urlretrieve(url, dest)  # noqa: S310  # 只认 render.json 里的链接
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"成片下不下来（{exc}）——Release 链接过期或者网络不通？") from exc
    print(f"[审片版] 拿到 {dest.stat().st_size / MIB:.1f} MiB → {dest}")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    # ⚠️ 两条入口二选一：`--slug` 是常规路（自己去 Release 拉），给路径那条
    # 留给「成片已经在手上」的情形。**都不给或者都给都要当场报错**——
    # 静默挑一条的话，「拉的是哪一条片子」就没人说得清了。
    ap.add_argument("film", type=Path, nargs="?",
                    help="成片路径。和 --slug 二选一")
    ap.add_argument("--slug", help="按 slug 反查产物目录，从 render.json 的 "
                                   "Release 链接把成片拉回来（常规路）")
    ap.add_argument("--mib", type=float, default=DEFAULT_TARGET_MIB)
    ap.add_argument("--width", type=int, default=720,
                    help="缩到这个宽度；审片看的是内容和节奏，不是画质")
    # ⚠️ **默认不写进 `output/`。** 第一版写在成片旁边，当场发现它会被
    # `git add` 吃进仓库——一个 27 MiB 的、谁也说不清是不是成片的文件。
    # 这条线为「两个地址两条片子，谁也没说哪个是哪个」栽过一次，不再来第二次。
    ap.add_argument("--out-dir", type=Path, default=Path(tempfile.gettempdir()),
                    help="审片版落在哪，默认临时目录（**不进仓库**）")
    args = ap.parse_args()

    if bool(args.film) == bool(args.slug):
        raise SystemExit("要么给成片路径，要么给 --slug，二选一。\n"
                         "  常规路：python3 tools/review_copy.py --slug <slug>")

    film = fetch_released_film(args.slug) if args.slug else args.film
    if not film.is_file():
        raise SystemExit(f"成片不在：{film}")
    src_mib = film.stat().st_size / MIB
    secs = probe_seconds(film)

    if src_mib <= args.mib:
        print(f"[审片版] 原片 {src_mib:.1f} MiB 已经在 {args.mib} MiB 以内，"
              "直接发原片就行，不用压")
        print(film)
        return 0

    # 反算视频码率：目标体积扣掉音轨，再留 3% 给封装
    budget_kbit = args.mib * MIB * 8 / 1000
    video_kbps = int((budget_kbit / secs - AUDIO_KBPS) * 0.97)
    if video_kbps < 200:
        raise SystemExit(
            f"{secs:.0f} 秒要压进 {args.mib} MiB，视频只剩 {video_kbps} kbps，"
            "压出来没法看。\n改发**片段 + 全片音轨**："
            "音轨 1.5 MB 上下，而配音和断句正是最需要耳朵的那一维。")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{film.stem}-审片版.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(film),
           "-vf", f"scale={args.width}:-2",
           "-c:v", "libx264", "-preset", "medium",
           "-b:v", f"{video_kbps}k", "-maxrate", f"{int(video_kbps*1.3)}k",
           "-bufsize", f"{video_kbps*2}k",
           "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k",
           "-movflags", "+faststart", str(out)]
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit("ffmpeg 压制失败")

    got = out.stat().st_size / MIB
    print(f"[审片版] {src_mib:.1f} → {got:.1f} MiB"
          f"（{secs:.0f}s，{args.width}px 宽，视频 {video_kbps}k + 音频 {AUDIO_KBPS}k）")
    if got > 30:
        raise SystemExit(f"⚠️ 压完还是 {got:.1f} MiB，超过 30 MiB 上限——"
                         "调小 --mib 或 --width 再来一次")
    print(f"⚠️ 这是**审片版**，只用来看。发微信的仍然是 {film.name}")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
