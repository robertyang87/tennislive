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

from pathlib import Path

from tennislive.render.webcards import _font_css
from tennislive.video.explainer import _data_uri

# 仓库根：src/tennislive/video/outro_page.py → parents[3]
ROOT = Path(__file__).resolve().parents[3]

# 片尾卡的画幅：**3:4，和几条线的卡是同一个尺寸**。
#
# 它同时要等于 `versus_poster.VIDEO_W/VIDEO_H`（剪辑片的整幅画布）和
# `explainer.VIDEO_W` × `explainer.CARD_H`（解说片那张 3:4 的卡，再 pad 到
# 9:16）。三处必须一致，否则片尾接进去要么变形要么留黑边。
#
# ⚠️ **这儿另写了一份，不是从那两处 import 的**——`explainer` 稍后要反过来
# 用这个模块，import 回去就成环；而 `versus_poster` 在 `tools/` 里，
# `src` 不该依赖它。所以一致性交给判据钉
# （`test_片尾卡的画幅要和几条线的卡对得上`），不靠 import 保证。
VIDEO_W, VIDEO_H = 1080, 1440

# 片尾母版。**在的话每条片子从它转码（1.9s），不在就现渲（14.4s）。**
# 生成：`PYTHONPATH=src python3 tools/build_outro_master.py`
#
# 放 `assets/` 不放 `output/`：它是**资产**不是某一天的产物，而且 CI 的稀疏
# 检出把 output 挡在外面（「测试不许拿 output 当判据的主语」那条）。
MASTER = ROOT / "assets/brand/outro_master.mp4"

BRAND = "#c6f65a"      # 品牌绿（台标球身那个黄绿）
INK = "#04120d"        # 深底
TEXT = "#f4fbf7"
SUB = "#a9bcb2"        # 次级灰绿（文字最多两级）
ICON = ROOT / "assets/logo/brand/icon-512.png"

# 屏幕上印的那句。**口播比它多一句「关注网球时差」**，而那六个字正是屏幕上
# 最大的那四个字加动作——所以 outro 不另排字幕，见 `build_match_reel` 那头。
TAGLINE = "你睡着的那些球，我替你看完"

# 片尾那句口播。**全站只有这一个出处**（剪辑片、解说片、采访片共用）。
#
# 写进每条 spec 或者让每条生产线各写一份的话，几条线之间迟早分叉——而
# 「强化记忆」最怕的正是这个：记忆靠的是每条片子结尾**一模一样**的那一下。
#
# ⚠️ 屏幕上印的是它的后半截（`TAGLINE`），前面多出来的「关注网球时差」正是
# 屏幕最大那四个字加一个动作——所以片尾不另排字幕。改这句就要同时看一眼那张
# 页面还盖不盖得住，判据在 `test_片尾口播说的话画面上要印得全`。
NARRATION = "关注网球时差，你睡着的那些球，我替你看完。"

# 口播说完之后留的那口气。片尾是整条片子的最后一帧，贴着最后一个字切会像
# 被掐断，所以比封面那档（0.25s）留得多一点。
TAIL = 0.45
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

    # ⚠️ **要 `resolve()`。** `Path.as_uri()` 对相对路径直接抛
    # `ValueError: relative path can't be expressed as a file URI`。生产里
    # outdir 是工作流传进来的绝对路径，所以这条路踩不到——本地跑一次就炸了。
    # 和「`~` 不展开：两趟绿的 run，一个字节都没缓存」是同一族：**路径从外面
    # 传进来的，就要在自己这头兜住**。
    outdir = outdir.resolve()
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


def render_clip(
    outdir: Path,
    seconds: float,
    *,
    fps_expr: str,
    fps: float,
    chromium: str,
    dest: Path,
    audio_rate: str,
    preset: str,
    crf: str,
    audio_bitrate: str = "160k",
    audio_channels: int = 1,
    tail: float = 0.0,
    voice: Path | None = None,
    layers: dict[str, Path] | None = None,
    runner=None,
) -> Path:
    """渲片尾页 + 合动效，出一个 mp4 片段。**两条生产线共用这一份。**

    `voice` 给了就把口播混进去（解说片那条要自带音轨，它是一次编码直接出片，
    没有后续的混音步骤）；不给就铺一路静音占位（剪辑片那条要，口播在
    `duck_filtergraph` 那一步统一 `adelay` 叠上去）。

    ⚠️ **编码参数由调用方传，不在这儿定死。** 两条线的成片参数不一样
    （剪辑片的分段是 `ultrafast`/`crf 12` 的中间产物，解说片按静图调），
    而片尾必须和它要拼进去的那条流**完全一致**——`concat` 只认第一个文件的
    流参数，差一项就拼出坏流，**而它不报错**。

    ⚠️ `setsar` 已经写在 `motion_filter` 里了（不能在外面加 `-vf`，
    `-vf` 和 `-filter_complex` 同时给 ffmpeg 会拒绝）。

    `layers` 是给**判据**留的口子：喂几张现成的 PNG 进来，这个函数就不碰
    Chromium，于是「ffmpeg 参数拼对没有」能在 CI 上真跑一次。
    ⚠️ 这不是可有可无的方便——第一版的判据只测 `motion_filter`（滤镜图），
    而 `-framerate` 那个 bug 在**这个函数**里，测试自己拼命令行、自己带了
    `-framerate`，于是把生产代码里的两处全拿掉它照样绿。
    **查的东西和跑的东西不是一回事。**
    """
    import subprocess  # noqa: PLC0415

    run = runner or subprocess.run
    total = seconds + tail
    if layers is None:
        layers = render_layers(outdir, chromium)

    # ⚠️ **每个静图输入都要 `-framerate`。** 不给的话 ffmpeg 按 **25fps** 解
    # `-loop 1`，而 `zoompan` 的输出标的是目标帧率——帧数不够，成片时长就缩成
    # `total × 25/fps`。实测：目标 4.29s、fps=30，出来的画面只有 **3.57s**，
    # 音轨却是整 4.29s，**画面比音轨短 0.72 秒**。
    #
    # 它照例不报错，只出一段短的；而且**只在 fps ≠ 25 时发作**——剪辑片那条
    # 线的源片正好多是 25fps，所以它一直是对的，换一条 30 或 60fps 的源片就中。
    # 判据在 `test_片尾的动效每一层都要按时出现`（那条特意按 30fps 跑）。
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(fps_expr),
            "-loop", "1", "-t", f"{total:.3f}", "-i", str(layers["base"])]
    for key, *_ in LAYERS:
        args += ["-framerate", str(fps_expr),
                 "-loop", "1", "-t", f"{total:.3f}", "-i", str(layers[key])]

    graph = motion_filter(total, fps_expr, fps)
    audio_idx = len(LAYERS) + 1
    if voice is not None:
        # 口播比画面短时要补静音到整段长——否则 `-shortest` 之外的那一截没有
        # 音频，concat 到成片里就是一段无声（「补位的静音盖住真音轨」的镜像：
        # 这次是**没有**补位，画面走完了音轨先断）。
        args += ["-i", str(voice)]
        graph += f";[{audio_idx}:a]apad,atrim=0:{total:.3f},asetpts=PTS-STARTPTS[aout]"
    else:
        layout = "stereo" if audio_channels == 2 else "mono"
        args += ["-f", "lavfi", "-i",
                 f"anullsrc=channel_layout={layout}:sample_rate={audio_rate}"]
        graph += f";[{audio_idx}:a]atrim=0:{total:.3f}[aout]"

    args += ["-filter_complex", graph,
             "-map", "[vout]", "-map", "[aout]",
             "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", preset, "-crf", crf,
             # 2026-08-22：`-pix_fmt yuv420p` 不保证 `color_range=tv`——
             # 详见采访片 `_still_segment` 那份注释（那次是 JPEG 封面漏出
             # 满量程标记，视频号读不出封面帧）。这一屏同样是静图渲出来的，
             # 显式钉死，别指望 ffmpeg 自己推断对。
             "-pix_fmt", "yuv420p", "-color_range", "tv",
             # ⚠️ **声道数也要跟调用方一致。** 采访片走 `concat` demuxer +
             # `-c copy`，那条路对流参数最挑：帧率、采样率、**声道数**差一项
             # 就静默丢流，成片从某一秒起没声音，而 ffmpeg 不报错。
             "-c:a", "aac", "-b:a", audio_bitrate, "-ar", audio_rate,
             "-ac", str(audio_channels),
             "-r", str(fps_expr),
             str(dest)]
    run(args, check=True)
    return dest


def build_with_voice(
    outdir: Path,
    *,
    chromium: str,
    dest: Path,
    fps: float,
    audio_rate: str,
    preset: str,
    crf: str,
    audio_bitrate: str,
    fps_expr: str | None = None,
    audio_channels: int = 1,
    voice: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
) -> Path:
    """合口播 → 渲页 → 出片尾片段。**三条生产线共用这一份。**

    片尾停多久由**口播**决定，但不短于动效自己要的下限（`min_length`）——
    换嗓子或改动效节奏时两头都不会被截断。

    ⚠️ **编码参数一项都不能省，而且要和调用方的成片逐项一致。** 解说片是
    `concat` filter、采访片是 `concat` demuxer + `-c copy`，后者尤其严格：
    帧率、采样率、声道数差一项就静默丢流，成片从某一秒起没声音，**而它不报错**
    （采访片那条注释里已经为封面记过一次这个坑）。

    ⚠️ **合到单独的子目录。** `synthesize_narration` 按索引命名
    （`voice_00.mp3`），和正片同一个目录会**盖掉第一屏的旁白**——盖掉之后成片
    照样出得来，只是第一屏说了片尾的话。
    """
    import subprocess  # noqa: PLC0415

    from .explainer import (  # noqa: PLC0415
        DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE, ExplainerSegment,
        _audio_seconds, synthesize_narration,
    )

    # **母版在的话就从它转码，不重渲。** 账号所有者 2026-08-05：「就做好一个
    # 带口播的视频段，每次都拼接到最后不行么？」——实测每条片子渲一遍要
    # 14.38 秒（渲页 7.58 ＋ 编码 5.88 ＋ TTS 0.92），转码只要 1.9 秒。
    #
    # 比省时间更硬的理由是**一致性**：每次重新跑 edge-tts，服务端合成的输出
    # 可能有微小差异，而「强化记忆」靠的正是每条片子结尾一模一样的那一下。
    #
    # ⚠️ 中间这一步转码**省不掉**：三条线的帧率/采样率/声道数不一样，
    # `concat` 差一项就静默丢流。母版按上界存（60fps / 48000 stereo / crf 12），
    # 往下转无损失，往上补不出信息。
    if MASTER.is_file():
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(MASTER),
             "-r", str(fps_expr or int(fps)),
             "-c:v", "libx264", "-preset", preset, "-crf", crf,
             "-pix_fmt", "yuv420p", "-color_range", "tv",
             "-c:a", "aac", "-b:a", audio_bitrate, "-ar", audio_rate,
             "-ac", str(audio_channels), str(dest)],
            check=True)
        return dest

    # 母版不在就现渲一份（第一次生成母版本身走的就是这条路）。
    # ⚠️ **要出声**：默默多花 12 秒和正常出片长得一模一样。
    print("[片尾] 没有母版，这条片子现渲一份（约 14 秒）；"
          "跑一次 tools/build_outro_master.py 就不用每次渲了")
    spoken = synthesize_narration(
        [ExplainerSegment(kind="outro", label="片尾", title="", narration=NARRATION)],
        outdir / "_outro_voice",
        voice=voice or DEFAULT_VOICE,
        rate=rate or DEFAULT_RATE,
        pitch=pitch or DEFAULT_PITCH,
    )[0]
    secs = max(_audio_seconds(spoken, "ffprobe", subprocess.run) + TAIL, min_length())
    return render_clip(
        outdir, secs,
        fps_expr=fps_expr or str(int(fps)), fps=fps, chromium=chromium, dest=dest,
        audio_rate=audio_rate, preset=preset, crf=crf,
        audio_bitrate=audio_bitrate, audio_channels=audio_channels, voice=spoken,
    )
