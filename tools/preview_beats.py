#!/usr/bin/env python3
"""开球之前纯视频的 **beat / 角标辅助函数**——属于一条**独立的开球之前管线**。

⚠️ 本文件**不是**完整的构建入口（还没有 `main`/`assemble_preview_reel`），只提供
开球之前比「赛场之上」多出来的那几样 segment 编码器：多源素材 beat、压在画面
上的信息条角标、海报 beat。

⚠️ **开球之前要独立，不和 match-reel 混。** 账号所有者 08-08 定的是「单独走
一条管线」——既不走 explainer（卡片视频），也不复用 match-reel（赛场之上那条）。
当前存量 spec 还躺在 `specs/reels/` 下、由 match-reel.yml 渲，那是**历史遗留的
混线状态**，正是接下来要拆开的；`assemble_preview_reel` + 自己的 CLI + 自己的
workflow 补齐之后，开球之前就彻底独立。文件名从 `build_preview_reel.py` 改成
`preview_beats.py`，是为了不让人误以为它已经是个能独立出片的构建入口。

## 为什么单独一个文件

账号所有者 2026-08-08：「开球之前之后建议单独走一个管线，不和知识解说一起，
因为后续我希望都走纯视频路线，少走卡片视频路线了」——本条线的产物从「整屏
文字卡 + TTS」换成「真实画面 + 压在画面上的信息条」，和 explainer.py 那套
Chromium 截图幻灯片是两种做法。放进同一个文件会让以后改 explainer.py 的任何
一处都要担心会不会波及这条线；分开之后两条线各自独立发展。

## 为什么不能照抄 build_match_reel.py

match-reel 的前提是**有一条连续的官方比赛集锦源片**，所有 segment 都是从这
一条源片上切时间窗。开球之前恰恰没有这个——比赛还没打，能剪的只有：

- 双方各自上一轮的集锦（两条互不相干的源片）
- 有交手史的话，上次交手的集锦（第三条源片）
- 现场气氛 B-roll（`intro_toronto_crowd.mp4` 那条路）

这是「N 组互不相干的源片，每组各取几段」，不是「一条源片切几段」。好在这件
事 match-reel 本来就支持——`sources` 字典 + `mixed_fps` 显式认领那一套是给
多源准备的，直接照搬。真正没有的是「按选手/H2H/气氛分组」这一层组织，而这
只是 spec 结构的事，不是新能力。

## 复用清单（原样从 build_match_reel.py 导入，不重写）

- `dissolve_filtergraph` / `duck_filtergraph`：溶解转场、闪避混音
- `_still_to_clip`：把一张海报变成一段带静音轨的视频，接进溶解链
- `-ss` 放在 `-i` 前面 + `-t`（不是 `-to`）：精确输入寻址，`cut_segment` 那条
  注释已经验证过这是现代 ffmpeg 的 accurate_seek，不是老式关键帧对齐
- crop+cx 居中公式：和 explainer.py 的 `intro_cx` 同一条公式，这条线上直接
  叫 `cx`，和 match-reel 逐段的 `cx` 是同一个形状

## 真正新写的东西

`_render_stat_overlay`——排名/H2H 这类数据不会凭空消失，只是从占满一屏的
卡片，收成压在真实回合镜头上的下三分之一角标（就是电视转播赛前包的做法）。
目前只实现 `player_card` 一种（选手名条：国旗+中文名+即时排名，直接复用
`versus_poster._name_html`）——先出一条真片子看效果，再决定要不要加
H2H 战绩条、连胜角标那几种。没量过的样式写多了，下一个人会拿它们当判据，
而它们可能一次都没被真实数据验证过。

## 还没做的（设计过，没写，因为没有真实素材可测）

- narration/字幕/闪避混音接进 `assemble_preview_reel`——机制上就是原样调用
  `duck_filtergraph` 和 explainer.py 的 `write_subtitles`，match-reel 已经
  证明这套能工作；没有真实 beats spec 之前写这段等于「写了没跑过」
- 完整的 spec 加载/校验（`load_spec` 等价物）和 CLI 入口（probe/render 分档）
- H2H 没打过时怎么办：账号所有者「信息有效且能吸引观众」——「首次交手」本身
  就是钩子，该用一句台词带过，不是静默跳过那个 beat；落地时要在 `beats` 里
  给一个 `h2h_none` 类型的说法，而不是让缺 H2H 的片子比有 H2H 的片子少一拍
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_match_reel import (  # noqa: E402
    ReelError,
    load_spec,  # noqa: F401
    render as render_reel,  # noqa: F401
    validate_spec,  # noqa: F401
    dissolve_filtergraph,  # noqa: F401  (导出给装配函数用，见下)
    duck_filtergraph,  # noqa: F401
    _still_to_clip,  # noqa: F401
)
from versus_poster import _name_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# 这条线唯一的画布：3:4，没有 9:16 分支——不像 explainer.py 要兼顾
# 「网球有故事」的老画布，这里从第一天起就是竖版视频的标准比例。
VIDEO_W = 1080
VIDEO_H = 1440


def footage_crop_chain(canvas_w: int, canvas_h: int, cx: float,
                        fps: str = "30") -> str:
    """铺满裁切 + 显式居中，和 explainer.py 的 `intro_cx` 同一条公式。

    `force_original_aspect_ratio=increase` 把源片放大到两边都盖过目标画布，
    `crop` 再切一块出来；`x` 不给缺省居中的是源片画幅的几何中心，不是画面
    里的人——`cx` 是显式给的水平中心（源片宽度的比例，0.5＝几何居中）。
    """
    return (
        f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
        f"crop={canvas_w}:{canvas_h}:"
        f"x='clip(iw*{cx}-ow/2\\,0\\,iw-ow)':y=0,setsar=1,fps={fps}"
    )


def _run(*args: str) -> None:
    proc = subprocess.run(list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-2500:]
        raise ReelError(f"命令失败 {args[0]}：\n{' '.join(args)[:400]}\n{tail}")


def cut_footage_beat(
    source: Path, start: float, end: float, cx: float, dest: Path,
    *, canvas_w: int = VIDEO_W, canvas_h: int = VIDEO_H,
    tail: float = 0.0, overlay: Path | None = None,
) -> Path:
    """切一段真实素材、裁成 3:4、可选压一条信息角标上去。

    `tail` 留给下一个接缝的溶解料，和 `cut_segment` 同一个账——这一段在
    成片里占的仍然是 `end - start`，不是 `end - start + tail`。

    `overlay` 不给 `-loop 1`：静态图当 ffmpeg 输入默认只有一帧，配合
    `overlay` 滤镜默认的 `eof_action=repeat`，它会把这一帧一直保持到主输入
    （真实素材那一路）结束——这个行为已经拿合成素材验证过（8 秒主片段，
    0.2/4.0/7.8 秒三个采样点角标都在），不需要像 `_render_intro_badge` 当年
    那样猜一个够长的 `-t`。
    """
    length = end - start
    chain = footage_crop_chain(canvas_w, canvas_h, cx)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-i", str(source)]
    if overlay is not None:
        cmd += ["-i", str(overlay)]
        filt = (
            f"[0:v]{chain}[base];"
            f"[base][1:v]overlay=0:{canvas_h - _overlay_png_height(overlay)}[vout]"
        )
    else:
        filt = f"[0:v]{chain}[vout]"
    cmd += ["-t", f"{length + tail:.3f}",
            "-filter_complex", filt, "-shortest",
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000",
            str(dest)]
    _run(*cmd)
    return dest


def _overlay_png_height(path: Path) -> int:
    from PIL import Image  # noqa: PLC0415
    with Image.open(path) as im:
        return im.size[1]


_OVERLAY_BAR_H = 160


def _render_stat_overlay(kind: str, data: dict, outdir: Path,
                          canvas_w: int = VIDEO_W) -> Path | None:
    """渲染一条压在真实画面上的信息条（下三分之一角标），透明背景。

    只实现 `player_card`：国旗 + 中文名 +（即时世界排名），直接复用
    `versus_poster._name_html`——数据要求（`country`/`rank` 必填、允许显式
    `null`）和海报上那一条完全一样，不重新发明一套校验。

    位置压在画布底部（`bottom:0`），不是贴着画面正中——这是给回合镜头用的
    角标，不能挡住球员本人。字号/边距是**没有真实渲染对比过的初版**，不是
    量出来的数字；接第一条真片子时要按渲出来的样子调，别当成定案。

    渲不出来（缺 Chromium）返回 None，退回没有角标的样子——和
    `_render_intro_badge` 同一个态度：这是锦上添花，不该拖垮整条片子。
    """
    if kind != "player_card":
        raise ValueError(f"还没实现的角标类型：{kind!r}，目前只有 player_card")

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    from tennislive.render.webcards import _chromium_executable, _font_css  # noqa: PLC0415

    who = _name_html(str(data["name"]).strip(), data, "overlay.player_card")
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:{canvas_w}px;height:{_OVERLAY_BAR_H}px;background:transparent;}}
body{{font-family:'TL Sans SC','Noto Sans CJK SC','Noto Sans SC',sans-serif;}}
.card{{position:absolute;left:70px;bottom:24px;display:inline-flex;
 align-items:center;padding:18px 32px;border-radius:16px;
 background:rgba(6,28,20,.72);box-shadow:0 8px 28px rgba(0,0,0,.35);
 font-size:42px;}}
.who{{display:inline-flex;align-items:baseline;white-space:nowrap;
 font-weight:700;color:#f4fbf7;text-shadow:0 2px 10px rgba(0,0,0,.6);}}
.who b{{font-weight:400;margin-right:.22em;}}
.who em{{font-style:normal;font-size:.55em;opacity:.85;margin-left:.08em;
 color:#c6f65a;}}
</style></head><body>
<div class="card">{who}</div>
</body></html>"""

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"_overlay_{kind}_{abs(hash(data['name']))}.png"
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            exe = _chromium_executable()
            if not exe:
                return None
            browser = p.chromium.launch(executable_path=exe)
        try:
            page = browser.new_page(
                viewport={"width": canvas_w, "height": _OVERLAY_BAR_H},
                device_scale_factor=1,
            )
            try:
                page.set_content(doc)
                page.wait_for_function(
                    "document.fonts.status === 'loaded'", timeout=15000
                )
                page.screenshot(path=str(out), type="png", omit_background=True)
            finally:
                page.close()
        finally:
            browser.close()
    return out


def poster_beat(poster: Path, dest: Path, seconds: float,
                 tail: float = 0.0) -> Path:
    """把一张（1080×1440 渲好的）海报变成一段视频 beat，接进溶解链。

    直接调用 `_still_to_clip`——它按海报自己的分辨率出片，不重新缩放，所以
    海报必须已经渲在这条线的画布尺寸上（`versus_poster.build_versus_poster`
    出的图本来就是）。`tail` 同 `cut_footage_beat`：多出的时长是留给下一个
    接缝的溶解料，`dissolve_filtergraph` 会正好把它吃掉。
    """
    return _still_to_clip(poster, dest, seconds + tail)


# 独立管线的 spec 目录。存量 4 条开球之前 spec 还躺在 specs/reels/ 下（历史混线），
# 新 spec 一律写进这里；load_preview_spec 对老 slug 退回 reels 只为了老片子还能渲。
PREVIEW_SPEC_DIR = ROOT / "specs" / "previews"
PREVIEW_OUTDIR = ROOT / "output" / "preview"


def load_preview_spec(slug: str) -> dict:
    """从 specs/previews/<slug>.json 读，读不到再退回 specs/reels/<slug>.json。

    回退是**只读兼容**（4 条存量老片还在 reels 下），不是「允许新 spec 继续混线」。
    判据：specs/previews/ 下出现的 slug 优先，读到了就 print 一句「独立目录」。
    """
    p = PREVIEW_SPEC_DIR / f"{slug}.json"
    if p.is_file():
        print(f"[spec] {p}（独立目录）")
        return load_spec(p)
    legacy = ROOT / "specs" / "reels" / f"{slug}.json"
    if legacy.is_file():
        print(f"[spec] {legacy}（历史混线，存量老片）")
        return load_spec(legacy)
    raise ReelError(
        f"找不到开球之前 spec：{slug}——specs/previews/ 和 specs/reels/ 都找过")


def assemble_preview_reel(spec: dict, outdir: Path, *,
                          voice: str, rate: str) -> Path:
    """开球之前独立管线的装配入口——现阶段委托给 `build_match_reel.render()`。

    ⚠️ 这是**入口独立**，不是渲染独立：预览 spec 用的就是 match-reel 的
    `segments + sources + mixed_fps` schema，`render()` 已经验证能渲。真正独立的
    beat 类型（footage_beat / poster_beat / stat_overlay，本文件上半部分那几样）
    是下一步——等有真实素材，再往 render 前插一层「按 beat 类型分派」，而不是
    现在写一段「写了没跑过」的装配。
    """
    return render_reel(spec, outdir, voice=voice, rate=rate)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="只验 spec 形状，不下载不渲染")
    ap.add_argument("--voice", default="zh-CN-YunjianNeural")
    ap.add_argument("--rate", default="+6%")
    args = ap.parse_args()

    spec = load_preview_spec(args.slug)

    if args.dry_run:
        validate_spec(spec)
        print(f"[dry-run] 开球之前 spec {args.slug} 形状 OK："
              f"源片 {len(spec.get('sources') or {})} 组，"
              f"段落 {len(spec.get('segments') or [])} 段")
        return 0

    outdir = PREVIEW_OUTDIR / args.slug
    film = assemble_preview_reel(spec, outdir,
                                 voice=args.voice, rate=args.rate)
    print(f"成片 {film}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
