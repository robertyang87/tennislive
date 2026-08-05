#!/usr/bin/env python3
"""片尾品牌页（outro）：版式 + 动效滤镜图。

账号所有者 2026-08-05：「每个视频最后都加一页并配上关注的口播」
「**要突出「网球时差」**」「**给大家强化记忆**」「最后最好有一个动效出来这一屏」。

### 为什么是「名字 + 一句解释」，不是「点关注」三个字

记忆强化靠的是**名字有解释**，不是把名字念两遍。「网球时差」这个名字自带钩子
——比赛在国外的深夜打完，你睡着的时候它就结束了——底下那句把这层说破，
名字才挂得住。所以这一页的主语是品牌名（158px，整屏最大），
「时差」两个字给品牌绿：**整屏唯一的强调色**，正好点在名字的钩子上
（CLAUDE.md「一屏只留一个强调色」）。

### 为什么是分层 PNG + ffmpeg，不是逐帧截 Chromium

1. 逐帧要 ~110 张 1080×1440 截图（≈30 秒），而这条线正在压 render 时间
   （CLAUDE.md 一整节都在算这个账）。分层只截 4 张，合成 1 秒出头。
2. **帧率必须跟源片走**（这条线上 25/30/60 都有）。`concat` 只认第一个文件的
   流参数，outro 的帧率和分段对不上就会拼出坏流。分层 PNG 能按目标帧率现合，
   预先存一个固定 mp4 做不到。

每层都渲成**整幅画布的透明 PNG**（元素在它该在的位置，其余透明），所以
overlay 的 x 恒为 0、只有 y 随时间动——位置由 CSS 布局说了算，不用在 Python
里另算一遍坐标（**一个数写两处必分叉**）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "tools"):
    # `tools` 也要进来：`versus_poster` 是同目录的兄弟模块，而这个文件被
    # 当模块 import 时（测试里）脚本目录不会自动进 sys.path。
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tennislive.render.webcards import _font_css  # noqa: E402
from tennislive.video.explainer import _data_uri  # noqa: E402

# 画幅跟成片同一个：3:4。**从 versus_poster 引，不另写一份**——海报、成片、
# 片尾三处画幅必须一致，写三遍必分叉。
from versus_poster import VIDEO_H, VIDEO_W  # noqa: E402

BRAND = "#c6f65a"      # 品牌绿（台标球身那个黄绿）
INK = "#04120d"        # 深底
TEXT = "#f4fbf7"
SUB = "#a9bcb2"        # 次级灰绿（文字最多两级）
ICON = ROOT / "assets/logo/brand/icon-512.png"

# 屏幕上印的那句。**口播比它多一句「关注网球时差」**，而那六个字正是屏幕上
# 最大的那四个字加动作——所以 outro 不另排字幕，见 `build_match_reel` 那头。
TAGLINE = "你睡着的那些球，我替你看完"
HANDLE = "@网球时差 · TENNIS JETLAG"

# 每层的入场时刻、淡入时长、上浮量。**顺序就是口播的节奏**：
# 球落下来 → 名字 → 那句解释。
LAYERS: list[tuple[str, float, float, int]] = [
    ("logo", 0.15, 0.50, 46),
    ("name", 0.70, 0.50, 34),
    ("tag", 1.50, 0.55, 26),
]
# 最后一层淡完之后至少还要停这么久，否则字刚出来就切走了。
# outro 总长跟着口播走（见 `outro_length`），这个数只是**下限**。
MIN_HOLD = 0.9
PUSH = 1.030           # 整屏极缓推的终点倍率


def _page(visible: str | None) -> str:
    """`visible=None` 渲底层；否则只让那一层可见。

    ⚠️ 用 `opacity` 不用 `display:none`——后者会改变 flex 布局，每一层就会落在
    不同的位置上，overlay 再怎么对也对不齐，而且**它不报错**。
    """
    def op(key: str) -> str:
        return "1" if visible == key else "0"

    base = "1" if visible is None else "0"
    return f"""<!doctype html><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{VIDEO_W}px;height:{VIDEO_H}px;overflow:hidden;
 background:{'transparent' if visible else INK};
 position:relative;font-family:'TL Sans SC',sans-serif;color:{TEXT}}}
.bar{{position:absolute;top:0;left:0;right:0;height:12px;z-index:9;opacity:{base};
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%)}}
.glow{{position:absolute;inset:0;opacity:{base};background:
 radial-gradient(120% 80% at 50% 38%,rgba(198,246,90,.13) 0%,rgba(4,18,13,0) 62%)}}
.wrap{{position:absolute;inset:0;display:flex;flex-direction:column;
 align-items:center;justify-content:center;z-index:5}}
.ico{{width:200px;height:200px;margin-bottom:48px;opacity:{op('logo')};
 filter:drop-shadow(0 18px 52px rgba(0,0,0,.55))}}
.name{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-weight:400;
 font-size:158px;letter-spacing:6px;line-height:1;opacity:{op('name')}}}
.name em{{font-style:normal;color:{BRAND}}}
.tag{{font-family:'TL Sans SC',sans-serif;font-weight:700;color:{SUB};
 font-size:42px;letter-spacing:2px;margin-top:56px;line-height:1.4;
 text-align:center;opacity:{op('tag')}}}
.handle{{position:absolute;bottom:78px;left:0;right:0;text-align:center;
 font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:30px;
 letter-spacing:4px;color:{SUB};opacity:{'.72' if visible is None else '0'};z-index:6}}
</style><div class="bar"></div><div class="glow"></div>
<div class="wrap"><img class="ico" src="{_data_uri(ICON)}">
<div class="name">网球<em>时差</em></div>
<div class="tag">{TAGLINE}</div></div>
<div class="handle">{HANDLE}</div>"""


def render_layers(outdir: Path, chromium: str) -> dict[str, Path]:
    """渲 4 张 PNG：底层不透明，其余三层抠背景。

    `chromium` 由调用方给——`build_match_reel._chromium()` 已经把「沙箱和 CI
    路径不一样」那件事解决过一次了，别在这儿再写一份 glob。
    """
    from playwright.sync_api import sync_playwright

    outdir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=chromium, args=["--no-sandbox"])
        pg = br.new_page(viewport={"width": VIDEO_W, "height": VIDEO_H})
        for key in [None] + [k for k, *_ in LAYERS]:
            name = key or "base"
            html = outdir / f"_outro_{name}.html"
            html.write_text(_page(key), encoding="utf-8")
            pg.goto(html.as_uri())
            pg.wait_for_timeout(260)
            dest = outdir / f"_outro_{name}.png"
            pg.screenshot(path=str(dest), omit_background=key is not None)
            paths[name] = dest
        br.close()
    return paths


def min_length() -> float:
    """动效自己要求的最短时长——最后一层淡完再停 `MIN_HOLD`。"""
    _, st, dur, _ = LAYERS[-1]
    return round(st + dur + MIN_HOLD, 3)


def motion_filter(secs: float, fps_expr: str, fps: float) -> str:
    """动效滤镜图：每层「淡入 + 上浮」，最后整屏极缓推。

    上浮写成 `y = -rise·(1-p)³`，p 是这一层入场的进度——三次方是 **ease-out**：
    一上来快、末尾贴着停住。线性上浮看着像匀速滑进来，机械感很重。

    ⚠️ `fade` 认 alpha 要先 `format=rgba`，不然它去改亮度，透明层会被填黑。

    ⚠️ **帧率要两个参数**：`fps_expr` 是给 `zoompan` 的（可能是 `30000/1001`
    这种分数，成片帧率跟着源片走），`fps` 是算缓推步长用的数值。拿分数字符串
    去做除法会 `TypeError`，拿 round 过的整数去写滤镜又会把 29.97 变成 30——
    那正是「硬定 30 而源片是 25，每 5 帧补一帧」那条踩过的坑。
    """
    parts, prev = [], "[0:v]"
    for i, (_key, st, dur, rise) in enumerate(LAYERS, start=1):
        p = f"clip((t-{st})/{dur},0,1)"
        parts.append(f"[{i}:v]format=rgba,fade=t=in:st={st}:d={dur}:alpha=1[l{i}]")
        out = f"[m{i}]"
        parts.append(f"{prev}[l{i}]overlay=x=0:"
                     f"y='-({rise})*pow(1-{p},3)':format=auto{out}")
        prev = out
    # `zoompan` 的 z 按输出帧号 `on` 算，比按 t 算稳（t 在 zoompan 里是输入帧的
    # 时间，一张静图上它不走）。
    frames = max(2, int(secs * fps))
    # ⚠️ `setsar` 要写在**滤镜图里**，不能在外面加 `-vf`——`-vf` 和
    # `-filter_complex` 同时给，ffmpeg 会拒绝（而 `concat` 那一步要求所有
    # part 的 SAR 一致，漏掉它就是拼出坏流）。
    parts.append(f"{prev}zoompan=z='1+({PUSH}-1)*on/{frames}':"
                 f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                 f"s={VIDEO_W}x{VIDEO_H}:fps={fps_expr},setsar=1[vout]")
    return ";".join(parts)
