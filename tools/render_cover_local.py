#!/usr/bin/env python3
"""本地渲一张「赛场之上」的封面海报出来**亲眼看**，不碰源片、不上 runner。

## 为什么要有它

量出来的账（shang-rublev，2026-08-05，从 probe 到成片 98 分钟）：

| | |
|---|---|
| 7 趟 GitHub Actions 的机器时间 | 19 分钟（19%） |
| 两趟之间（等 run、拉产物、改 spec、等 CI） | **79 分钟（81%）** |
| 其中 01:34→02:05 那一段**全花在封面上** | **31 分钟** |

那 31 分钟是两趟 `mode=cover` 加一趟因为封面改了而重跑的 `render`，而三趟里
真正改的只有**钩子文案、暗角开关和一次换帧**——渲出来的 HTML 变了，
帧本身没变。

封面之所以非上 runner 不可，只有一个原因：`cover.portrait.frame_at` 要从
`source.mp4` 抓一帧，而源片在沙箱里下不动（IP 被 YouTube 挡）、在 runner 上
渲完就删。**把抓下来的那一帧留住，这条链就断了**——见 `build_match_reel.py`
的 `COVER_SRC_DIR`。

实测：本地渲一张 **6.9 秒**，对比一趟 `mode=cover` 的 2 分 03 秒 run
外加大约 8 分钟往返。

## 用法

    # 素材已经在仓库里（跑过一趟 mode=cover 或 render 之后）
    PYTHONPATH=src python3 tools/render_cover_local.py --slug shang-rublev

    # 一次渲几版摆一起比：改 spec → 重跑 → 换个 --out
    PYTHONPATH=src python3 tools/render_cover_local.py --slug shang-rublev \
        --out /tmp/hook-v3.jpg

改完 spec 直接重跑，看着对了再上 runner 跑 `mode=render` 出成片——
那一趟会**复用同一批素材**，所以你看到的这张就是成片里的那一张。

## 它管不了什么

- **换 `frame_at`**：那是要一帧新的，仓库里没有。得上 runner 跑一趟
  `mode=cover`（它会把新素材连同 `cover_src/` 一起提交），之后又能本地迭代了
- **成片**：这儿只出海报。字幕、配音、分段全在 render 里
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_match_reel import (  # noqa: E402
    COVER_SRC_DIR,
    ReelError,
    load_spec,
    render_poster,
    resolve_cover_payload,
)

ROOT = Path(__file__).resolve().parent.parent


def cover_needs_frames(cover: dict) -> bool:
    """这张封面要不要从源片抓帧。

    ⚠️ **不要帧的封面不该被 `cover_src/` 挡在门外。** solo 版式的
    `portrait.image` 和 VS 版式的 `cutout` 指的都是**仓库里的文件**——
    素材本来就在手上，一帧源片都不用碰，可这个工具原来一律要求产物目录里
    有 `cover_src/`，于是「本地 7 秒渲一版」这条路对这类封面是关着的，
    人得先去跑一趟两分钟的 `mode=cover`——正是「能力写出来了，能用的那台
    机器上没有开关」那个形状。

    判据是**有没有 `frame_at`**：抓帧这件事只由它触发（`portrait.frame_at`、
    `versus.top/bottom.frame_at`、`versus.background.frame_at`）。
    """
    def any_frame_at(node: object) -> bool:
        if isinstance(node, dict):
            return "frame_at" in node or any(any_frame_at(v) for v in node.values())
        if isinstance(node, list):
            return any(any_frame_at(v) for v in node)
        return False

    return any_frame_at(cover)


def find_outdir(slug: str, explicit: str | None,
                needs_frames: bool = True) -> Path:
    """找这条片子的产物目录。**给了就用给的，没给就挑最新的那一天。**

    ⚠️ 日期目录按**上海时间**分（工作流里是 `TZ=Asia/Shanghai date +%F`），
    而沙箱跑在 UTC——每天 16:00 UTC 之后两者差一天。所以这儿不去算「今天」，
    直接按目录名排序取最新的那个**真的有素材**的：算出来的日期会在半夜错一天，
    而「排序取最新」在两种时区下都对。
    """
    if explicit:
        out = Path(explicit)
        if not out.is_dir():
            raise SystemExit(f"给的 --outdir 不存在：{out}")
        return out
    hits = sorted(ROOT.glob(f"output/*/reel/{slug}"), reverse=True)
    if not hits and needs_frames is False:
        # 封面素材全在仓库里（`portrait.image` 之类）时，连产物目录都不需要——
        # 见下面 `needs_frames` 那段注释
        return ROOT
    if not hits:
        raise SystemExit(
            f"output/ 里找不到 {slug} 的产物目录。\n"
            "这条片子还没在 runner 上跑过——先跑一趟 "
            "`match-reel mode=cover slug=" + slug + "`，"
            "它会把封面素材（cover_src/）连同产物一起提交。")
    with_src = [h for h in hits if (h / COVER_SRC_DIR).is_dir()]
    if not with_src and needs_frames is False:
        return hits[0]
    if not with_src:
        raise SystemExit(
            f"{slug} 有产物目录，但没有一个带 {COVER_SRC_DIR}/：\n  "
            + "\n  ".join(str(h.relative_to(ROOT)) for h in hits)
            + f"\n\n这几趟是在「封面素材落库」之前跑的。跑一趟 "
              f"`match-reel mode=cover slug={slug}` 把素材抓下来，之后就能本地渲。")
    if with_src[0] != hits[0]:
        # **不吭声地退到旧目录是最坏的**：你会对着上一版的素材调半天。
        print(f"[注意] 最新的 {hits[0].relative_to(ROOT)} 里没有 {COVER_SRC_DIR}/，"
              f"退回 {with_src[0].relative_to(ROOT)}")
    return with_src[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True, help="片子 slug（spec 文件名）")
    ap.add_argument("--outdir", default="",
                    help="产物目录；不给就挑 output/ 里最新一个带素材的")
    ap.add_argument("--out", default="",
                    help="海报存哪儿；不给就写进产物目录旁边的 poster_local.jpg")
    args = ap.parse_args()

    spec_path = ROOT / "specs" / "reels" / f"{args.slug}.json"
    if not spec_path.is_file():
        raise SystemExit(f"找不到 spec：{spec_path}")
    spec = load_spec(spec_path)
    cover = spec.get("cover")
    if not cover:
        raise SystemExit(f"{spec_path.name} 里没有 cover 段")

    needs_frames = cover_needs_frames(cover)
    outdir = find_outdir(args.slug, args.outdir or None, needs_frames)
    src = outdir / COVER_SRC_DIR
    if needs_frames:
        print(f"[素材] {src.relative_to(ROOT) if src.is_relative_to(ROOT) else src}")
    else:
        # 出声说走的是哪条路：「这张封面不用抓帧」和「素材没找着但它没吭声」
        # 长得一模一样
        print("[素材] 这张封面没有 frame_at，素材全在仓库里，不用 cover_src/")

    # `sources=None` ＝ **只认缓存**：一个源片字节都不碰。缺素材要报错，
    # 不许悄悄退回抓帧——那条路在沙箱里必然失败，而失败的样子会是一句
    # 看不懂的 ffmpeg 报错，不是「你要的是一帧新的」。
    # ⚠️ `primary` 不能省：素材键里的 `source` 是 `spot.get("source", primary)`
    # 算的，不传就恒为 `""`，而 runner 写进 manifest 的是真源名（多源 spec 里是
    # `"olympics"` 这种）。两边对不上 → 每次都判成「缓存里没有这一版」，
    # 而报出来的话是「先跑一趟 mode=cover 把素材抓下来」——**指着一个已经做过
    # 的动作**，于是多源片子的本地迭代这条路等于关着，且没人看得出为什么。
    # 判据 test_本地渲封面要按spec的主源算素材键。
    try:
        payload, layout = resolve_cover_payload(
            cover, outdir, sources=None, primary=str(spec.get("primary", "")))
    except ReelError as exc:
        raise SystemExit(str(exc)) from exc

    out = Path(args.out) if args.out else outdir / "poster_local.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_poster(payload, out, layout)
    size = out.stat().st_size / 1024
    print(f"[海报] {layout} → {out}（{size:.0f} KB）")
    print("  用 Read 打开看。改 spec 之后直接重跑这条命令，几秒钟一版。")
    # 素材清单一并打出来：**海报对不对，一半取决于用的是哪一帧**，
    # 而那个数只在 manifest 里。不打的话「改了 frame_at 没生效」看不出来。
    man = src / "manifest.json"
    if man.is_file():
        for tag, key in json.loads(man.read_text(encoding="utf-8")).items():
            print(f"  {tag}: {key.get('frame_at')}s"
                  f"（{key.get('kind')}，源 {key.get('source') or '主'}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
