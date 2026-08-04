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
import hashlib
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.video import azure_tts  # noqa: E402
from tennislive.video.explainer import (  # noqa: E402
    CARD_H,
    CARD_TOP,
    VIDEO_H as _EXPLAINER_H,
    VIDEO_W,
    _BAND_COLOR,
    _ASS_MARGIN_H,
    _ASS_MARGIN_V,
    readable,
    speakable,
    all_single_char_segments,
    word_split_report,
    subtitle_cues,
    write_subtitles,
)
from tennislive.video.subtitle_text import drop_punctuation  # noqa: E402

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
# 封面**没有配音时**停多久——「赛场之上」走的就是这一档（它不给封面配音）。
# **2.6 秒太长**：账号所有者「好多人以为是图片不是视频」。封面同时是信息流里的
# 缩略图，点进来的人已经看过它了；画面迟迟不动，第一反应是「这是张图」，划走。
# 1.2 秒够读完两行钩子加一行比分，又能让第一个回合立刻接上。
#
# 「网球有故事」那条线不一样：它给封面配音，封面停多久跟着配音走（`cover_length`），
# 这个数用不上。**两条线别互相牵动**——判据见 `test_封面跟着配音走只给网球有故事`。
COVER_SECONDS = 1.2
# 说完之后留的那口气。贴着最后一个字切，末尾辅音会被 concat 的边界削掉。
COVER_TAIL = 0.25
# 封面海报**要进仓库**：推送正文的第一屏就是它（布局照着知识解说那条推送来），
# 微信里要能直接看到这是谁打谁、几比几。以前它叫 `_cover.jpg`、下划线开头，
# 被"丢掉中间物"那步删掉了——于是推送里一张图都没有，只有两个按钮。
POSTER_NAME = "poster.jpg"
# 2026-08-04 之前发出去的「赛场之上」封面，走的是 VS 版式（cutout / diagonal）。
# 那天账号所有者把这个栏目的封面改成一律 solo，**这些不重渲**：微信那条消息
# 发出去收不回来，为版式重跑一遍六分钟的 render 换不到任何东西。
#
# ⚠️ **只许减不许加。** 加一个名字进来就等于让一条新片子绕过新规矩，而它
# 不会报错——正是这张表要防的事。判据在
# `test_赛场之上的封面一律用solo`（这张表里的每个 slug 都必须真的是老片子，
# 而且必须真的是非 solo——写错一个名字，豁免就成了一盏恒真的绿灯）。
_LEGACY_VS_COVERS = frozenset({
    "eala-fernandez", "eala-osaka", "eala-svitolina", "potapova-venus",
    "wang-pareja", "wang-samsonova", "wong-brooksby", "wong-gea",
    "wong-lehecka",
})
# contain 模式横向保留多少。0.62 → 窗口 1190px，球员落在画面 19%~81% 之间都还在，
# 缩到 1080 宽后有 980 高，占屏高一半——比整幅铺进来的 608 高大了六成。
CONTAIN_KEEP = 0.62
# 原声压到多少。留一点现场声（球声、观众），但不能盖过中文解说。
BED_LOUD = 0.72   # 没人说话时的现场声
# **段与段之间要淡入淡出，不能硬切。** 账号所有者：「音频和视频切换或转场的时候，
# 要有淡入淡出，而不是要突然一下从这里切过来，就是感觉给人的观感不好，或者听感
# 不好。」画面和**现场声**都要——现场声硬切时球场的底噪会「啪」地换一个，
# 比画面跳更刺耳。
#
# ⚠️ **第一版把它做成了「每段各自淡到黑再淡回来」，于是每个接缝中间都有一帧
# 全黑**——账号所有者的原话：「接缝画面的时候有轻微的闪烁」。量出来一点都不含糊，
# jodar-fritz 18 个接缝挨个采样，最黑的五个平均亮度 `0.0`（62.191s 那一帧是
# 整幅纯黑），谷值平均 8.3。**淡入淡出不等于淡到黑**：两段之间要的是**溶解**
# （前一段直接化进后一段），中间一帧黑都不许有。
#
# 现在的做法：每个 part 都比它在成片里占的时间**多切 `SEG_FADE` 秒**（多出来的
# 是源片的自然延续，从来没单独播过），拼接那一步用 `xfade`/`acrossfade` 把这
# 多出来的一段吃掉。于是**每一段在成片里仍然正好是 `seg.length` 秒**，旁白和
# 字幕的偏移一个字都不用改——这一条是故意的，见 `dissolve_filtergraph` 的
# 长度账。**最后一段不留尾巴**，所以总长仍然是 Σ seg.length，`check_reel_landed`
# 那句「画面总长 − 段落总长 ＝ 封面」照旧成立。
#
# 0.18 秒是「化开了」和「拖沓」之间那一档：段长最短的一段 4.0 秒，占 4.5%，
# 看得出是转场而不是变慢。旁白**不参与**——它是拼接之后另混上去的，每句话自己
# 有起止，淡它等于把开头几个字吞掉。
SEG_FADE = 0.18
# **每一段的音轨都要压到同一个采样率**。`concat` + `-c copy` 只认第一个文件的
# 流参数：封面那段的 anullsrc 是 48k，而各分段跟着源片走 44.1k，于是 44.1k 的
# AAC 帧被当成 48k 播——整条现场声快 8.8%，音轨在画面还剩 5.7 秒时就播完了
# （69.9s 的画面配 64.3s 的音轨，64.3/69.9 = 0.9196 ≈ 44100/48000）。
# 它不报错，ffprobe 也只写着「48000」，只有把两个时长摆在一起才看得出来。
AUDIO_RATE = "48000"


def dissolve_filtergraph(lengths: list[float], fade: float) -> str:
    """把各段**溶解**着接起来的滤镜图（画面 `xfade`，现场声 `acrossfade`）。

    ### 长度账——这是这个函数存在的全部理由

    每个 part 文件都比它在成片里占的时间多 `fade` 秒（`cut_segment` 的 `tail`），
    **最后一段除外**。`xfade` 的输出长度是 `A + B - fade`，所以：

        acc₁ = (L₀+f) + (L₁+f) − f = L₀ + L₁ + f
        acc₂ = acc₁   + (L₂+f) − f = L₀ + L₁ + L₂ + f
        …
        accₙ = acc    +  Lₙ    − f = Σ Lᵢ          ← 末段没尾巴，那个 f 正好被吃掉

    也就是**总长和硬切时一模一样**，每一段的起点也一模一样。旁白的 `adelay`、
    字幕的 cue、`render.json` 里「画面总长 − 段落总长 ＝ 封面」那条恒等式，
    因此一处都不用改。要是给末段也留尾巴，总长会多出 `fade` 秒——那就得在
    别处补一刀 `-t`，而**一个数写两处必分叉**。

    `offset` 是溶解在**当前累积流**上开始的时刻，累积流的时间轴就是成片时间轴，
    所以它正是这一段的起点 Σ_{j<k} Lⱼ。

    `acrossfade` 没有 offset——它一律咬住前一路的**末尾**，而前一路的末尾正好
    是同一个窗口（accₖ 末尾 = Σ Lⱼ + f），两边对得上。
    """
    n = len(lengths)
    if n == 1:
        return "[0:v]null[vout];[0:a]anull[aout]"
    vparts, aparts = [], []
    vprev, aprev, offset = "[0:v]", "[0:a]", 0.0
    for i in range(1, n):
        offset += lengths[i - 1]
        vout = "[vout]" if i == n - 1 else f"[vx{i}]"
        aout = "[aout]" if i == n - 1 else f"[ax{i}]"
        vparts.append(f"{vprev}[{i}:v]xfade=transition=fade:"
                      f"duration={fade}:offset={offset:.3f}{vout}")
        # `c1`/`c2` 都用三角曲线：默认那组是等功率的，两条现场声（球场底噪）
        # 叠在一起会在中间鼓一下——底噪不相干，等功率补的那一块是白给的。
        aparts.append(f"{aprev}[{i}:a]acrossfade=d={fade}:c1=tri:c2=tri{aout}")
        vprev, aprev = vout, aout
    return ";".join(vparts + aparts)


def duck_filtergraph(filters: list[str], voice_labels: list[str]) -> str:
    """闪避的滤镜图：没人说话时现场声开到 `BED_LOUD`，解说一进来就压下去。

    **`[vk0]apad[vk]` 那一段不能省，而且不能只当它是个细节。**
    `sidechaincompress` **两路里任一路 EOF 就整个结束**，于是 `[duck]`
    只活到最后一句旁白说完，下游 `amix` 跟着收口——**整条现场声在那儿断掉**。

    九条已发的成片里**七条**结尾 1.95~4.50 秒完全没有声音：

        eala-fernandez −4.50s   wang-pareja −2.98s   hewitt-washington −2.97s
        wang-samsonova −2.66s   potapova-venus −2.64s
        wong-brooksby  −1.98s   eala-zheng     −1.95s

    被削掉的正是握手、庆祝、观众声那几秒——CLAUDE.md 里「收尾那句要提前起，
    从上一段就开始说、跨进末屏」保的就是这几秒，也就是整条片子的情绪落点。
    **而 ffmpeg 不报错**，成片时长看着也完全正常（画面是全长的），只有把
    视频流和音频流的时长摆在一起才看得见。又一次「兜底出事的时候不吭声」。

    `apad` 把 sidechain 补静音到无限长，压缩器就跟着 `[bed]` 走完。
    只补 `[vk0]`（喂给压缩器的那一路），`[vm]`（真正听见的那一路）不动。
    闪避行为一点没变：合成信号实测有旁白时 −38.1 dB、旁白说完 −24.0 dB。

    ⚠️ **这个 bug 被独立发现过两次**（main 上是「伊埃拉那条末段画面 11.5s、
    旁白 8.8s，成片最后 2.74 秒一点声音都没有，正好是拥抱教练那一下」）。
    两次的判据完全一样：**把音轨长度和画面长度摆在一起**。抽成函数是为了让
    判据能真跑一次混音——查源码里有没有 `apad` 防不住「它从来没工作过」。

    抽成函数是为了让判据能**真跑一次混音**：查源码文本的断言只能防「有人把它
    删了」，防不住「它从来没工作过」。
    """
    return (
        f"[0:a]volume={BED_LOUD}[bed];{';'.join(filters)};"
        f"{''.join(voice_labels)}amix=inputs={len(filters)}:normalize=0[voice];"
        f"[voice]asplit=2[vk0][vm];"
        f"[vk0]apad[vk];"
        f"[bed][vk]sidechaincompress=threshold=0.02:ratio=12:"
        f"attack=15:release=450:makeup=1[duck];"
        f"[duck][vm]amix=inputs=2:normalize=0:dropout_transition=0[out]"
    )


# 分段和封面都是**中间产物**：拼完之后整片还要以 crf 18 重编一次。在这里编到
# crf 17/preset slow，等于把画质编进一个马上要被重编的文件里。成片那一步的参数
# 没有跟着降。
#
# **中间产物要花的是比特，不是时间。** 这一版从 medium/crf 20 换成
# ultrafast/crf 12，方向看着反直觉（preset 更快、crf 更低），但两件事各管各的：
# preset 决定编码器**花多少时间**去找省比特的编法，crf 决定**留多少画质**。
# 中间段马上要被重编，省下来的比特一点用都没有——它唯一的作用是别把画质
# 提前丢掉。所以把 preset 推到最快、crf 压到很低：又快又更保真。
#
# 量出来的（10 秒 1080×1440/60fps 素材，四核，和沙箱同规格）：
#
#     中间段 preset/crf   中间编码   最终成片 SSIM   最终 PSNR
#     medium   / 20        14.73s      0.993110      47.09   ← 改前
#     veryfast / 18         7.33s      0.992667      46.43
#     ultrafast/ 16         2.76s      0.992025      47.22
#     ultrafast/ 12         2.92s      0.993212      48.01   ← 改后，又快又更像
#     （上界：不经中间段直接 slow/crf18   0.995223      49.52）
#
# **5 倍快，而且最终成片比改前更接近源片**。runner 上分段编码那一栏是
# 176.7s（run 30624808733），按同样的比例落到 47s 上下。
#
# 解码 + 滤镜的地板是 2.10s/10s，也就是说改完之后编码本身只再加 2.4s——
# 再往这个方向推没有多少可省的了，下一个大头是成片那一步，而那一步不许动。
#
# 代价是中间段变大：同样 10 秒从 6.3 MB 涨到 38.5 MB。90 秒的片子于是多占
# ~700 MB（分段 ~350 MB，`-c copy` 拼出来的 `_video.mp4` 又是同样一份），
# 加上 392 MB 的源片，峰值 1.2 GB 上下——runner 有十几 GB 空余，吃得下。
# 它们在 `render` 末尾全被删掉（`part_*.mp4` / `_video.mp4` 那一行），
# 一个都不会进仓库；工作流那道「超过 8 MB 又不是成片就报错」的兜底也照旧
# 拦得住，真有一天忘了删，它会红。
#
# ⚠️ **两个调用点必须用同一组参数**（分段和封面），否则 `concat` + `-c copy`
# 会把两种流参数拼在一起。所以这两个常量在 `cut_segment` 和 `build_cover`
# 里都用，别只改一处。
PART_PRESET = "ultrafast"
PART_CRF = "12"

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

# **成片有两条落脚点，按体积自己选。**
#
# 账号所有者 2026-08-02 定的：「我的基础要求是保证内容和画面质量，文件多大都
# 没关系」「不要砍片长」「我怕故事讲解不完整」。所以**片长不设上限**。
#
# git 那条路确实有个 100 MiB 的服务端硬拒（那条 3 分 04 秒的片子渲出来 104 MiB，
# push 被拒，五分钟白跑，run 30725160625）——但答案不是砍片长，是换一条路：
# 超过 95 MiB 的成片改传 **GitHub Release 附件**（单个 2 GB，公开仓库下载不计
# 流量额度），链接写进 `render.json`，`push_reel` 优先读它。
# 比过的另外两条：Git LFS 免费额度只有 1 GB 存储 + **1 GB/月流量**，一条片子
# 一百多 MB，一次推送就能把月流量打光，而且 `raw.githubusercontent.com` 对 LFS
# 文件返回的是**指针文本不是视频**；外部对象存储要另一套密钥和账单。
#
# 实测码率（3:4 画幅、crf 18、真实比赛画面，都是从成片量的）：
#   eala-svitolina    81.9 MiB / 158.0s = 4348 kb/s   源片 25 fps
#   wong-gea          80.2 MiB / 155.8s = 4318 kb/s   源片 25 fps
#   eala-osaka 3 分版 104.0 MiB / 185.2s = 4712 kb/s   源片 25 fps
#   eala-osaka 2 分半版 94.5 MiB / 158.8s = 4990 kb/s   源片 25 fps
#   gea-shapovalov   168.4 MiB / 247.9s = **5698 kb/s** 源片 **59.94 fps**
#
# ⚠️ **剪短之后码率反而更高**：砍掉的是全片最静的那一段，留下的全是高动量的
# 关键分。所以「按当前码率线性外推」会低估——常量取**实测最高**的那一条。
#
# ⚠️ 而 4990 那一版是**按 25 fps 那批量的**：60 fps 的源片每秒多一倍帧要编，
# 同样的 crf 自然多花比特。gea-shapovalov 按 4990 估出来 147 MiB，实际
# 168 MiB——**低估 14%，而且低估的方向正是危险的那一头**：贴着 95 MiB 的片子
# 会被估成「进仓库」，然后在 `git push` 那一刻才炸（run 30725160625 就是这么
# 白跑五分钟的）。所以这个常量只许往上调，判据在
# `test_估体积的码率只许按实测往上调`。
#
# 这个估算现在只用来**报走哪条路**，不再拦人。它仍然有用：知道要走 Release
# 就知道这一版的链接不是 raw 而是 releases/download。
GITHUB_FILE_LIMIT_MIB = 100
MEASURED_REEL_KBPS = 5700
# 超过这个就走 Release。95 而不是 100，留 5 MiB 给「估得不准」。
REPO_INLINE_MIB = 95


def reel_length_verdict(spec: dict) -> tuple[float, float]:
    """(这条 spec 的成片时长, 估出来的 MiB)。不判断，只算——调用方决定怎么办。"""
    seconds = sum(float(s["end"]) - float(s["start"])
                  for s in spec.get("segments") or ())
    seconds += COVER_SECONDS
    return seconds, seconds * MEASURED_REEL_KBPS * 1000 / 8 / 1024 / 1024


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


# 峰值低于这个数就当成「没有现场声」。真实的比赛音轨峰值贴近 0 dBFS，
# 数字静音是 −91；−60 落在两者中间很远的地方，不会误伤录得轻的源片。
SILENT_PEAK_DB = -60.0


def audio_peak_db(path: Path) -> float | None:
    """源片音轨的峰值响度（dBFS）。**没有音频流返回 None。**

    `_has_audio` 只查**流存不存在**，查不出「有流但是数字静音」——而这两件事
    在日志上、在 ffprobe 里、在成片的码率上完全一样。wong-brooksby 就栽在这儿：
    spec 的 `_source` 白纸黑字写着「带原声」，成片里**没有旁白的段落全是数字
    静音**（按 3 秒一格采样，29 个窗里 12 个低于 −70 dB；其余八条片子
    0/23~0/39），整套 `sidechaincompress` 闪避对它是空转。

    这和 1051 行那条注释记的坑是**同一个形状**——「补位的静音盖住真音轨」，
    只是这次补位的不是我们，是源片自己。所以判据要量**信号**，不是量**流**。

    124 秒的片子实测 0.81 秒（只解音频），值这个钱。
    """
    if not _has_audio(path):
        return None
    out = run("ffmpeg", "-hide_banner", "-i", str(path), "-vn",
              "-af", "volumedetect", "-f", "null", os.devnull).stderr
    found = re.search(r"max_volume:\s*(-?[\d.]+) dB", out)
    # 量不出来**不能当成静音**（那会把一个探测失败变成一次硬报错），
    # 但也不能当成正常——返回 None 走「没有音轨」那条路，它自己会出声。
    return float(found.group(1)) if found else None


def point_end_candidates(source: Path, scorebox: str) -> list[float]:
    """量一遍死球时刻，写进 `probe.json`——**趁源片还在**。

    `find_point_ends.py` 一直是**零调用方**：它的 `--video` 指的是源片，而源片
    渲完就被清理那一步删掉，于是想用它得自己另下一份 400 MB。结果是段尾切错
    只能靠人在 2 秒一格的缩略图墙上看出来，而账号所有者点名过这件事
    （「很多球没有播放完成就切到下一个了……让人看的不明不白的」）。
    wong-brooksby 那三处修正每一处都先付了一趟渲染才发现。

    记分条的位置**没法自动认**（每家转播不一样），所以要人给；不给就跳过，
    **而且要说为什么**——「没量」和「量出来一个都没有」长得一模一样，
    这正是「空结果先自证是真空」。

    量出来的数**也要打印分布**：检测不到和方法不成立是两回事，只有把数摆出来
    才分得清（成片那条「找球场对称轴」的教训就是这么来的）。
    """
    if not str(scorebox).strip():
        print("[死球] 没给 --scorebox（记分条位置每家转播不一样，认不出来），"
              "这一项跳过。段尾就只能靠缩略图墙用眼睛定。")
        return []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import find_point_ends as fpe  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 依赖缺失才会走到
        print(f"[死球] 取不到 find_point_ends（{exc}），跳过")
        return []
    try:
        box = tuple(int(v) for v in str(scorebox).split(","))
        if len(box) != 4:
            raise ValueError(box)
    except ValueError:
        raise ReelError(
            f"--scorebox 要写成 x0,y0,x1,y1（源片像素），给的是「{scorebox}」")
    with stage("量死球"):
        rows = fpe.scan(source, box, 0.1)
        ends = fpe.point_ends(rows, fpe.CHANGE, fpe.DARK_SHARE, fpe.MERGE)
    print(f"[死球] 采样 {len(rows)} 点，记分条跳变 {len(ends)} 次")
    if ends:
        print("  " + " ".join(f"{t:.1f}" for t in ends[:40])
              + (" …" if len(ends) > 40 else ""))
    else:
        # 零命中要能自证：把量到的分布打出来，别让「门槛卡错」和「真的没有」
        # 长得一样。
        moved = sorted((r["moved"] for r in rows), reverse=True)[:5]
        print(f"  一个都没有。门槛 change={fpe.CHANGE} dark={fpe.DARK_SHARE}，"
              f"实测 moved 最大的几个：{moved}"
              "——要是这些数都远低于门槛，多半是 box 框错了，不是没有死球")
    return [round(t, 2) for t in ends]


def require_live_sound(source: Path, spec: dict) -> float | None:
    """源片是哑的就报错并给出路，认领过的放行——**两种情况都打印**。

    照 `mixed_fps` 那套做**显式认领**。一律放行等于继续出哑片；一律拒绝会把
    纯视频轨的源片整个挡在门外（网盘那份常常只有视频轨）。认领这一步是让这个
    取舍**留下判据**，而不是让它悄悄发生。

    原来这两条分支**一句 print 都没有**，于是「源片是哑的」和「源片正常」在
    日志上完全一样——wong-brooksby 那条整片没有现场声的片子就是这么发出去的。
    """
    peak = audio_peak_db(source)
    if peak is None:
        print(f"[原声] {source.name} 没有可用音频流")
    else:
        print(f"[原声] {source.name} 音轨峰值 {peak:.1f} dBFS")
    if peak is None or peak < SILENT_PEAK_DB:
        claimed = str(spec.get("silent_source", "")).strip()
        if not claimed:
            raise ReelError(
                f"{source.name} 没有可用的现场声"
                + ("（没有音频流）" if peak is None
                   else f"（峰值 {peak:.1f} dBFS，低于 {SILENT_PEAK_DB:g}，"
                        "整条轨是数字静音）") + "。\n"
                "整片会只剩解说，球声和观众声全没有，而闪避那一套会空转。\n"
                "三条出路：① spec 里写 `source_audio` 指一份单独的音轨合上；"
                "② 换一个带声音的源片；"
                "③ 确实只能这样，就在 spec 顶层写 "
                '`"silent_source": "为什么可以"` 认领下来。')
        print(f"[原声] 认领哑源片：{claimed}")
    return peak


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


def fetch_captions(url: str, outdir: Path) -> Path | None:
    """把自动字幕连时间码拉下来，写成 `captions.txt`（`秒数<TAB>这一句`）。

    **为什么要它**：采访素材靠缩略图墙是选不了段的——一整条五分钟的访谈，
    每一帧都是一个人在说话，画面上分不出他这一秒在讲什么。要用他的原声，
    就得知道那句话落在第几秒。

    沙箱拿不到（timedtext 对这台机器返回 **0 字节的 200**，看起来和「这条片子
    没有字幕」一模一样——又一次「空结果先自证是真空」：播放页里明明列着
    `asr` 轨）。runner 的 IP 拿得到，所以收在 probe 里。

    拿不到就返回 None，**不影响 probe 的其余产物**：字幕是锦上添花，
    缩略图墙和切点才是这一步的主产物。
    """
    binary = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    if not binary or ("youtube.com" not in url and "youtu.be" not in url):
        return None
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
    # **`-o` 要带 `%(ext)s`。** 写成一个没有扩展名的裸前缀时，yt-dlp 落盘的
    # 名字由它自己拼，我这边靠 glob 去猜——猜错就是「拿不到字幕」，
    # 和「这条片子没有字幕」长得一模一样。用惯例写法，名字就不用猜了。
    tmpl = str(outdir / "_subs.%(ext)s")
    notes: list[str] = []
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, *YTDLP_BASE, "--skip-download",
             "--write-auto-subs", "--write-subs",
             "--sub-langs", "en.*,en", "--sub-format", "json3/vtt/best",
             "-o", tmpl, url, *cookies, *extra],
            capture_output=True, text=True)
        got = sorted(outdir.glob("_subs*.json3")) + sorted(outdir.glob("_subs*.vtt"))
        if got:
            print(f"[字幕] {label} 拿到 {got[0].name}")
            break
        why = (proc.stderr or proc.stdout or "").strip()
        notes.append(f"### {label}\n{why[-1200:]}")
        print(f"[字幕] {label} 没拿到：{why[-160:]}")
    else:
        # **把失败原因落进产物里。** 「所有 client 都没拿到」有好几种成因
        # （这条片子真没字幕 / 这台机器被挡 / 我的参数写错），只印在日志里
        # 就得翻 run 才看得见，而 run 的日志翻起来很贵。写成文件跟着提交，
        # 下次一眼就知道该改参数还是该换路子。
        (outdir / "captions_debug.txt").write_text(
            "拿不到自动字幕，各 client 的原因如下：\n\n" + "\n\n".join(notes),
            encoding="utf-8")
        print("[字幕] 所有 client 都没拿到自动字幕 → captions_debug.txt")
        return None
    lines = _caption_lines(got[0])
    if not lines:
        return None
    dest = outdir / "captions.txt"
    dest.write_text("".join(f"{t:.2f}\t{s}\n" for t, s in lines), encoding="utf-8")
    for f in got:
        f.unlink(missing_ok=True)
    print(f"[字幕] {len(lines)} 句 → {dest.name}")
    return dest


def _caption_lines(path: Path) -> list[tuple[float, str]]:
    """json3 或 vtt → [(起始秒, 这一句)]。两种都认，因为 yt-dlp 给哪种看运气。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json3":
        out = []
        for event in json.loads(text).get("events", []):
            body = "".join(s.get("utf8", "") for s in event.get("segs") or ())
            body = " ".join(body.split())
            if body:
                out.append((event.get("tStartMs", 0) / 1000, body))
        return out
    out, stamp = [], None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"(\d+):(\d+):(\d+)[.,](\d+)\s*-->", line)
        if m:
            h, mi, s, ms = (int(g) for g in m.groups())
            stamp = h * 3600 + mi * 60 + s + ms / 1000
        elif line and stamp is not None and "-->" not in line:
            body = " ".join(re.sub(r"<[^>]+>", "", line).split())
            if body and (not out or out[-1][1] != body):
                out.append((stamp, body))
    return out


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


# **编码是偏好，不是硬条件。** 抽成常量是为了能测：判据原来靠在源码里
# 「从 `selector = ` 切到 `cookies: list[str]`」取一段字符串，而这两个记号
# 在文件里都不是唯一的——后来 `fetch_captions` 里也有一句 `cookies: list[str]`，
# 而且排在前面，那一刀切出来是**空串**，于是「不含 avc1」自动成立、
# 「含 h264」自动失败。**判据不该依赖它在文件里的位置。**
FMT_SELECTOR = "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"
FMT_SORT = "res:1080,fps,vcodec:h264,acodec:m4a"

# **每一次 yt-dlp 调用都要带上这几个**，所以抽出来共用。
# `--js-runtimes node` 是解 n challenge 的那一环：没有它，YouTube 的格式表
# 只剩故事板，报出来是「Only images are available」+「Requested format is
# not available」——看起来像「这条片子取不到」，其实是**这一次调用少带了一个
# 参数**。我给 `fetch_captions` 新写 yt-dlp 调用时正是这么漏的：同一个 job 里
# `download()` 明明下得动整条 294 秒的片子，字幕那条八个 client 全红。
# 这就是「加新能力就要同时改三处」的又一个变种——新调用没继承旧调用的前提。
YTDLP_BASE = ["--js-runtimes", "node"]


def _ladder() -> list[tuple[str, list[str]]]:
    if os.environ.get("YT_POT_PROVIDER", "").strip():
        return _POT_FIRST + _PLAIN
    return _PLAIN + _POT_FIRST


# 下过的源片存哪儿。**空着就是旧行为**（每次都重下），工作流把它指到一个
# `actions/cache` 的目录上。
_SOURCE_CACHE_ENV = "TENNISLIVE_SOURCE_CACHE"


def _cached_source(url: str, suffix: str) -> Path | None:
    """这条 URL 在缓存里的位置。没配缓存目录就返回 None（走旧行为）。

    **同一条源片会被下两到三次**：probe 一次、cover 一次、render 一次——中间
    「丢掉不进仓库的中间物」那一步把它删了，而它本来就不进仓库。实测一个
    70 MB 的源片要下 **100.86 秒**（YouTube 限速，不是带宽问题），而 render
    整步才 198 秒——**一半的时间花在重下同一个文件上**。

    键取 URL 的哈希：YouTube 的同一条 URL 内容不会变，所以缓存永远是对的；
    换了 URL 自然是另一个键。缓存目录在 `~` 底下，清理那一步只碰 `outdir`，
    碰不到它。
    """
    root = os.environ.get(_SOURCE_CACHE_ENV, "").strip()
    if not root:
        return None
    # ⚠️ **`~` 要自己展开。** 工作流里写的是 `~/.cache/tennislive-sources`，
    # 而 Python **不展开波浪号**——`Path("~/…")` 是一个**名叫 `~` 的相对目录**，
    # 落在仓库工作区里。`actions/cache` 找的是真的 `$HOME/.cache/…`，于是
    # 每趟都报 `Path Validation Error: ... do(es) not exist`，**一个字节都没存过**，
    # 而两趟 run 全是绿的（run 156/158）。
    # 单元测试当时也是绿的——它喂的是绝对路径 `tmp_path`，正好绕过这一半。
    return (Path(root).expanduser()
            / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}{suffix}")


def _keep_source(url: str, src: Path) -> None:
    """把刚下好的源片留一份进缓存，下一趟就不用再等一百秒。

    **存不进去不算失败**（磁盘满、目录没建起来）——它只是个加速，
    不该让一趟已经下载成功的 run 因为缓存写失败而红。但**要出声**，
    否则「缓存没生效」和「缓存生效了」在日志上一样。
    """
    cached = _cached_source(url, src.suffix or ".mp4")
    if cached is None or cached.is_file():
        return
    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, cached)
        print(f"[缓存] 存了一份，下一趟不用重下（{cached.name}）")
    except OSError as exc:
        print(f"[缓存] 存不进去，下一趟还要重下：{exc}")


def download(url: str, dest: Path) -> Path:
    """取**最高清晰度**：先试 1080p 的 avc1（码率最高的那档），退到 bestvideo。

    `YT_COOKIES` 指向一个 cookies.txt 就带上——机房 IP 被挡的时候，
    一份登录过的 cookie 是唯一稳定的解。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"[skip] 已有 {dest}")
        return dest

    cached = _cached_source(url, dest.suffix or ".mp4")
    if cached is not None and cached.is_file() and cached.stat().st_size > 0:
        shutil.copy2(cached, dest)
        print(f"[缓存] 命中，没有重下（{dest.stat().st_size / 1e6:.1f} MB）")
        return dest

    # 不是 YouTube 就是一个普通直链（网盘、赛事站…），curl 一下就完了。
    # 这条路是被逼出来的：YouTube 对这台机器和 runner 都封着，人只能自己下好
    # 传到网盘，再把直链给我们。
    direct_failed = ""
    if "youtube.com" not in url and "youtu.be" not in url:
        proc = subprocess.run(
            ["curl", "-sSL", "--fail", "-o", str(dest), url],
            capture_output=True, text=True)
        if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise ReelError(f"直链下载失败（{url[:90]}）：{(proc.stderr or '')[-300:]}")
        # **「下到了」不等于「下到的是视频」**，而这条路原来只看**前 64 字节**
        # 里有没有 `<!doctype html` / `<html`。Brightcove 的播放页
        # （`players.brightcove.net/<账号>/<player>/index.html?videoId=…`）
        # 正是这么溜过去的：0.3 MB 的网页被当成源片收下，`_keep_source` 还把它
        # **存进了缓存**，ffprobe 到下一步才报 `Invalid data found`
        # （run 30838371382）。缓存把这个坏结果固化了——同一条 URL 再跑一趟会
        # 直接命中它，于是「换个参数重试」永远重现同一个错。
        #
        # 判据换成「ffprobe 读不读得出一路视频流」。**yt-dlp 那条路早就在用
        # `probe_size` 把关了**（它甚至还量高度防 360p），只有直链这条没有。
        size_mb = dest.stat().st_size / 1e6
        try:
            width, height = probe_size(dest)
        except (ReelError, ValueError):
            head = dest.read_bytes()[:400].lower()
            looks_html = b"<html" in head or b"<!doctype" in head
            dest.unlink(missing_ok=True)
            # ⚠️ **这里原来直接抛错，而错误正文写着「这类要交给 yt-dlp」**——
            # 也就是说出路已经写出来了，只是**让人去走，代码自己不走**。
            # 张帅那条就撞在这儿：`players.brightcove.net/…/index.html?videoId=…`
            # 不含 youtube，于是走 curl 拿回 0.3 MB 网页，render 第 12 秒就红
            # （run 30875896980）——而同一条 URL 交给 yt-dlp 一次就下来了。
            #
            # **按结果分路，不按域名分路。** 维护一张「哪些站是播放页」的名单
            # 会过期，而过期的名单和一条常年红的检查是同一个毛病；
            # 「curl 下到的东西 ffprobe 读不出视频流」这个判据永远新鲜。
            direct_failed = (
                f"直链下到 {size_mb:.1f} MB，但 ffprobe 读不出视频流"
                f"{'（内容是 HTML）' if looks_html else ''}")
            print(f"[直链] {direct_failed}，改交给 yt-dlp 再试一次")
        else:
            print(f"[ok] 直链下到 {size_mb:.1f} MB，{width}×{height}")
            _keep_source(url, dest)
            return dest

    binary = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    if not binary:
        raise ReelError(
            f"{direct_failed}，而且找不到 yt-dlp" if direct_failed
            else "找不到 yt-dlp")
    # **编码是偏好，不是硬条件。** 原来第一档写死 `vcodec^=avc1` + `ext=m4a`：
    # YouTube 的高清一律是分离流，而 1080p 那几档常常是 VP9/AV1(webm)。某个
    # player client 列出来的格式表不全时（PO token / n challenge 那一环没打通
    # 就会这样），前两档全匹配不上，一路掉到 `best`——**YouTube 唯一预合成好的
    # 格式是 itag 18，正好 640×360**。于是「下载成功」和「只拿到 360p」成了同一
    # 件事，中间没有一步会报错，直到裁切那步才炸（run 30412173035）。
    #
    # 现在 `-f` 只管分辨率上限，编码偏好交给 `-S`：h264 排在前面（下游 ffmpeg
    # 处理最省事），但拿不到就用 VP9/AV1，而不是掉回 360p。
    selector, sort = FMT_SELECTOR, ["-S", FMT_SORT]
    cookies: list[str] = []
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        cookies = ["--cookies", jar]
        print(f"[cookies] 用 {jar}")

    failures: list[str] = []
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, *YTDLP_BASE, "--no-warnings", "-f", selector,
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
            _keep_source(url, dest)
            return dest
        reason = " | ".join(
            line.strip() for line in (proc.stderr or "").splitlines()
            if line.startswith("ERROR") or "403" in line
        )[:300] or (proc.stderr or "")[-300:]
        print(f"[fail] {label}: {reason}")
        failures.append(f"{label}: {reason}")
        dest.unlink(missing_ok=True)

    raise ReelError(
        (f"{direct_failed}；退回 yt-dlp 之后，" if direct_failed else "")
        + f"{len(failures)} 种 player client 都下不下来（{url}）。逐条原因：\n  "
        + "\n  ".join(failures)
        + "\n\n如果全是 “Sign in to confirm you’re not a bot”，那是**这台机器的 IP "
        "被 YouTube 挡了**，不是视频的问题：把一份登录过的 cookies.txt 存成仓库 "
        "Secret（YT_COOKIES_TXT），工作流会写到文件并通过 YT_COOKIES 传进来。"
    )


# `scene_cuts` 用的门槛。**不许动这个数**：存量 spec 的 `crosses_cut` 是照着
# 它挂的账，改了等于把一批已经想清楚的声明变成噪音。
CUT_THRESHOLD = 0.35
# 「疑似切点」用的门槛。0.35 认不出「宽景回合 → 同一场地的中景」这一类，
# gea-shapovalov 那次更直白：474.5 秒他还穿着白 polo 在场上，476.5 秒已经换上
# 蓝外套在捧杯——**中间必然有一刀**，而 `scene_cuts` 只报了 473.07 和 482.67。
# 同一块场地、同一个机位、同样的灯光，帧间差就是过不了 0.35。
#
# 所以另出一份低门槛的候选，**不并进 `scene_cuts`**（那是判据，这是线索）：
# 挑段的时候扫一眼，落在窗口里的那几个自己去缩略图墙上看一眼是不是真换了。
LOOSE_CUT_THRESHOLD = 0.12


def scene_changes(path: Path, threshold: float = CUT_THRESHOLD, *,
                  start: float = 0.0, stop: float | None = None) -> list[float]:
    """切点。`start`/`stop` 给了就**只在那一段里找**，返回值仍是源片的绝对秒数。

    为什么要能只看一段：WTA 的单场集锦不是每场都发，**Day N 合集才是全覆盖的**
    （王欣瑜对卡萨金娜那场就只在 61 分钟的 Day 2 合集里，章节
    `2371–2553  X. Wang Vs. D. Kasatkina`）。整片扫一遍要几分钟，
    而且缩略图墙会出七十多张、全是别人的比赛。

    ⚠️ **`-ss` 放在 `-i` 前面是输入寻址，`pts_time` 会从 0 重新起算**，
    所以要把 `start` 加回去——不加的话切点全部偏移，而它**不会报错**，
    只会让每一段都切在错的地方。
    """
    seek = []
    if start:
        seek += ["-ss", f"{start:.2f}"]
    if stop is not None:
        seek += ["-t", f"{max(0.0, stop - start):.2f}"]
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", *seek, "-i", str(path),
         "-filter:v", f"select='gt(scene,{threshold})',showinfo",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [round(float(m) + start, 2)
            for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr or "")]


def contact_sheet(path: Path, outdir: Path, *, every: float = 2.0,
                  columns: int = 6, tile_w: int = 360, crop: str = "",
                  prefix: str = "contact", start: float = 0.0,
                  stop: float | None = None) -> list[Path]:
    """每 `every` 秒抓一帧，烧上时间码，拼成几张缩略图墙。

    时间码必须烧进画面里——不然看图挑完段，还得数第几格再乘回去，数错一次
    整段就切偏了。

    `crop`（ffmpeg 的 `w:h:x:y`）先裁再缩。**整幅缩到 360 宽时记分条只有几个
    像素高，比分根本读不出来**——而定段落必须知道每一段是第几局第几分，
    否则「转折点在不在片子里」就只能靠猜。裁出记分条那一块单独拼一版，
    同样的机制，放大到能读。
    """
    outdir.mkdir(parents=True, exist_ok=True)
    frames = outdir / "frames"
    frames.mkdir(exist_ok=True)
    for old in frames.glob("*.jpg"):
        old.unlink()
    duration = probe_duration(path)
    # 只看一段时，缩略图仍然烧**源片的绝对秒数**——挑段的人照着它写 spec，
    # 换算一次就是一次切偏的机会。
    lo = start + 0.5
    hi = duration if stop is None else min(stop, duration)
    stamps = [round(t, 2) for t in _frange(lo, hi, every)]
    for index, t in enumerate(stamps):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
            "-vf", ((f"crop={crop}," if crop else "")
                    + f"scale={tile_w}:-2,"
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
        sheet = outdir / f"{prefix}_{n // per_sheet:02d}.jpg"
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
    # 这一段取自哪条源片（`spec["sources"]` 的键）。空＝主源。
    # 一条片子跨两场比赛时用得上：休伊特那条要「首胜吉隆」和「负于德米纳尔」
    # 两条官方集锦，故事才完整。
    source: str = ""
    # **这一段让当事人自己说**：现场采访的原声不配旁白，只上中文字幕。
    #
    # 为什么要单开一个字段而不是塞进 narration：narration 会合成一条中文语音
    # 压在原声上（而且 sidechaincompress 会把原声压下去），等于把他的话盖掉。
    # 而字幕那条线**只认 narration**——没有 narration 就没有字幕，于是
    # 「静音刷是默认状态」那条规矩下，这一段对多数人是彻底空白：
    # 听不懂英文的看不懂，静音的什么也没有。两头都丢。
    #
    # 所以 quote 是「不出声、只出字」的那一档：原声开到 BED_LOUD 不闪避
    # （这一段本来就没人配音），字幕按字数等比分配到整段时长上——拿不到
    # 词边界时本来就是这么退的，不完美，但绝不能因此整段没字幕。
    quote: str = ""
    # **`quote` 写成列表时，每一条就是一条字幕**，断句权交回写 spec 的人；
    # 元素里的换行渲成两行（上英下中）。
    #
    # 为什么要这一档：原声段拿不到词边界，退路是「按字数等比铺满整段」，
    # 断句靠标点自动切。中英双语过不了这一关——自动切会把英文句子劈开，
    # 也不知道哪一行该和哪一行配成一对。
    # 账号所有者 2026-08-03：「前面夺冠庆祝的部分全用英文原声配中英文字幕」。
    quote_cues: tuple[str, ...] = ()
    # **这一段的语速 / 音高**，空＝跟全片的默认值走。
    #
    # 为什么只有这两个旋钮：2026-08-04 在 runner 上实测过一遍这条免费端点
    # （`tools/probe_tts_ssml.py`，run 30884267406）——`<break/>` 和
    # `<mstts:express-as style=...>`（sad / sports-commentary-excited /
    # narration-relaxed / cheerful 四个都试了）**服务端一律拒绝**，
    # 情绪风格那条路要付费的 Azure Speech 才有。**认的只剩 prosody**：
    # 同一句话 −20%/−8Hz 是 8.59 秒、+6% 是 6.50 秒、+25%/+12Hz 是 5.52 秒。
    #
    # 所以「多渲染情绪」在这条线上唯一能拧的就是它，而原来**全片只有一个值**。
    voice_rate: str = ""
    voice_pitch: str = ""
    # 下面三样**只有 Azure 那条路认**（`AZURE_SPEECH_KEY` 配了才走）。
    # 2026-08-04 在 runner 上实测：Edge 免费端点对 `mstts:express-as` 和
    # `<break/>` 一律拒绝，Azure F0 十个风格全过、break 也生效
    # （run 30884267406 / 30892017944）。
    # ⚠️ **写了这几样却没配 key 要报错，不许悄悄退回** ——那等于发一条和
    # spec 说的不一样的片子，而且不吭声。
    voice_style: str = ""
    voice_styledegree: str = ""
    voice_lead_pause: float = 0.0
    # **角标**：一张 PNG 压在这一段的角上，画面不中断。
    #
    # 比整屏切一张静图好在**两件事同时在画面上**。休伊特那条讲的是儿子做了
    # 父亲的动作，而父亲那一下只有图没有影像（三条官方存档集锦都没拍到）。
    # 切成整屏静图要停三秒、把片子剪断；压在角上，儿子做那一下的同一帧里就
    # 有父亲做同一个动作——那句话本身就是这个画面，不用讲。
    # 账号所有者 2026-07-31：「把这个照片贴在他儿子做动作视频页面的角落里，
    # 这样就不用切画面了」。
    # 格式：`inset: {"image": 路径, "corner": "tl|tr|bl|br", "width": 0.34}`
    inset: dict | None = None

    @property
    def length(self) -> float:
        return round(self.end - self.start, 3)


def _quote_cues(raw: object) -> tuple[str, ...]:
    """`quote` 写成列表时，**每一条就是一条字幕**（元素里的换行渲成两行）。

    写成字符串时返回空元组 —— 走原来那条「按标点自动切、按字数等比铺满」的路，
    存量 spec 一个字都不用改。
    """
    if not isinstance(raw, list):
        return ()
    out = []
    for x in raw:
        if isinstance(x, dict):
            out.append({"at": float(x["at"]), "text": str(x["text"]).strip()})
        elif str(x).strip():
            out.append(str(x).strip())
    return tuple(out)


def _quote_text(raw: object) -> str:
    """互斥判断和「这一段有没有原声字幕」都只看真假，所以列表拼成一段就够。"""
    if isinstance(raw, list):
        return " ".join(x["text"] if isinstance(x, dict) else x
                        for x in _quote_cues(raw))
    return str(raw).strip()


def explicit_quote_cues(lines: tuple, span: float,
                        offset: float) -> list[tuple[float, float, str]]:
    """按条声明的原声字幕。两种写法，可以混着用：

    - `"上英\\n下中"` —— 时长按各条的字数摊到整段上（短段够用）
    - `{"at": 段内秒数, "text": "上英\\n下中"}` —— **钉在真实时刻上**

    ⚠️ **一整段几十秒的原声必须用 `at`。** 按字数摊的前提是「说话密度均匀」，
    而真实解说有停顿、有留白：夺冠那一段 67 秒里十几条，摊出来能差好几秒，
    字幕比人先开口或者慢半拍——比不同步更糟的是**它看起来像同步**。
    `at` 直接从 `probe.json` 旁边那份 `captions.txt` 的时间戳减去段起点。

    末条的结束时间收在段尾；中间每条收在下一条的开头（解说是连着说的，
    留空档反而会闪）。

    ⚠️ 元素里的换行是「这一条排两行」——`explainer.write_subtitles` 按行分别
    过 `_ass_text` 再用 ASS 换行符拼。上锚保证多一行是**往下**长。
    """
    stamped = [t for t in lines if isinstance(t, dict)]
    if stamped and len(stamped) != len(lines):
        raise ReelError(
            "同一段的 quote 里不许一半写 `at` 一半不写：混着用的话，没写的那些"
            "要按字数摊，摊的范围又被写了 `at` 的那些切碎，出来的时刻没人能预料。")
    out: list[tuple[float, float, str]] = []
    if stamped:
        at_list = [float(t["at"]) for t in stamped]
        bad = [a for a in at_list if not 0 <= a < span]
        if bad:
            raise ReelError(f"quote 的 `at` 超出这一段（0–{span:.2f}s）：{bad}")
        for index, item in enumerate(stamped):
            start = offset + at_list[index]
            end = (offset + at_list[index + 1]) if index + 1 < len(stamped) \
                else offset + span
            out.append((start, end, readable(str(item["text"]))))
        return out
    weights = [max(1, len(str(t).replace("\n", ""))) for t in lines]
    total = sum(weights)
    at = offset
    for text, weight in zip(lines, weights):
        dur = span * weight / total
        out.append((at, at + dur, readable(str(text))))
        at += dur
    return out


_RATE_RE = re.compile(r"^[+-]\d{1,3}%$")
_PITCH_RE = re.compile(r"^[+-]\d{1,3}Hz$")


def _seg_voice(raw: dict, index: int) -> tuple[str, str, str, str, float]:
    """一段自己的语速 / 音高。没写就返回两个空串（跟全片默认值走）。

    写法：`"voice": {"rate": "-8%", "pitch": "-6Hz", "_why": "这一段是崩盘"}`

    **`_why` 是必填的**，和 `mixed_fps` / `silent_source` / `cover._layout_why`
    一个形状：**认领这一步把「想清楚了」和「凑合一下」分开**。语速这东西改一个
    数就能改，最容易被用来「让这段刚好装得下」——而那是剪窗口该干的事，
    不是配音该干的事。逼着写一句为什么，就能在下一个人读 spec 的时候看出来
    这是编辑决定还是凑数。

    ⚠️ **格式要卡死**：`rate` 是 `+12%` / `-8%`，`pitch` 是 `+6Hz` / `-6Hz`。
    写成 `-8`（漏了百分号）edge-tts 会抛 `Invalid rate`，而那一刻已经在
    render 里跑了几分钟——`mode=narration` 才 90 秒，让它死在这儿。
    """
    voice = raw.get("voice")
    if voice is None:
        return "", "", "", "", 0.0
    if not isinstance(voice, dict):
        raise ReelError(f"第 {index + 1} 段的 `voice` 要写成对象，"
                        '例如 {"rate": "-8%", "pitch": "-6Hz", "_why": "..."}')
    allowed = {"rate", "pitch", "style", "styledegree", "lead_pause", "_why"}
    extra = sorted(set(voice) - allowed)
    if extra:
        raise ReelError(f"第 {index + 1} 段的 `voice` 只认 "
                        f"{' / '.join(sorted(allowed))}，多了 {extra}")
    rate = str(voice.get("rate", "") or "").strip()
    pitch = str(voice.get("pitch", "") or "").strip()
    style = str(voice.get("style", "") or "").strip()
    degree = str(voice.get("styledegree", "") or "").strip()
    lead = float(voice.get("lead_pause", 0) or 0)
    if not any((rate, pitch, style, lead)):
        raise ReelError(f"第 {index + 1} 段写了 `voice` 却一项都没给")
    bad_style = azure_tts.check_styles([style])
    if bad_style:
        raise ReelError(
            f"第 {index + 1} 段的 `voice.style` 是 `{style}`，不在实测通过的表里。\n"
            "⚠️ **拼错的风格名 Azure 是静默忽略的**——合成照样成功，只是没有情绪，"
            "而「拼错了」和「这个风格本来就平」在成片上一模一样。\n"
            f"认的十个：{' / '.join(azure_tts.KNOWN_STYLES)}")
    if lead and not 0 < lead <= 2.0:
        raise ReelError(f"第 {index + 1} 段的 `voice.lead_pause` 要在 0~2 秒之间，"
                        f"现在是 {lead}")
    if rate and not _RATE_RE.match(rate):
        raise ReelError(f"第 {index + 1} 段的 `voice.rate` 要写成 `+12%` / `-8%`，"
                        f"现在是 `{rate}`")
    if pitch and not _PITCH_RE.match(pitch):
        raise ReelError(f"第 {index + 1} 段的 `voice.pitch` 要写成 `+6Hz` / "
                        f"`-6Hz`，现在是 `{pitch}`")
    if not str(voice.get("_why", "") or "").strip():
        raise ReelError(
            f"第 {index + 1} 段改了语速/音高却没写 `voice._why`。\n"
            "这一步要认领：语速改一个数就能让一段「刚好装得下」，而那是剪窗口\n"
            "该干的事。写一句为什么（「这一段是崩盘，降速降调」），下一个人才\n"
            "分得出这是编辑决定还是凑数。")
    return rate, pitch, style, degree, lead


def parse_segments(spec: dict, sources: dict, primary: str) -> list[Segment]:
    """spec 的 `segments` → `Segment` 列表，顺带把两条互斥/引用的规矩拦在这儿。

    **抽出来是为了能测。** 原来这段在 `render()` 里内联，而 `render()` 要先下
    源片、探 fps、渲封面才走到这儿——判据只能在 runner 上、六分钟之后才生效，
    等于没有。这两条都是「不吭声」型的错：

    - 引用了不存在的源 → 会静默从主源抓（另一场比赛的画面）
    - 同一段既有 narration 又有 quote → 两个人同时开口，而且闪避把原声压掉

    **默认不摇。** 窗口只有源片的 32% 宽，一横摇，画面里本该静止的底线、球网、
    广告板、看台全跟着滑；源片是 25 fps，滑动的静止物最容易看出一格一格。
    真人看下来的结论就是「固定中心的感觉更好」，所以横摇改成**按段显式打开**
    （`"track": true`），只留给主机位的宽景回合。
    """
    segments = [Segment(float(s["start"]), float(s["end"]),
                        None if s.get("cx") is None else float(s["cx"]),
                        s.get("narration", "").strip(),
                        str(s.get("fit", "crop")), bool(s.get("track", False)),
                        str(s.get("source", primary)),
                        _quote_text(s.get("quote", "")),
                        _quote_cues(s.get("quote", "")),
                        *_seg_voice(s, i),
                        s.get("inset") or None)
                for i, s in enumerate(spec["segments"])]
    gone = [(i + 1, str((s.inset or {}).get("image", "")))
            for i, s in enumerate(segments) if s.inset]
    gone = [(i, f) for i, f in gone if not f or not Path(f).is_file()]
    if gone:
        raise ReelError(
            "这些段的图片找不到文件（写错路径时 ffmpeg 只会在切片那一步才炸，"
            "而那已经是下完所有源片之后了）：\n  "
            + "\n  ".join(f"第 {i} 段：{f or '(空)'}" for i, f in gone))
    bad_corner = [i + 1 for i, s in enumerate(segments) if s.inset
                  and str(s.inset.get("corner", "tl")) not in
                  {"tl", "tr", "bl", "br"}]
    if bad_corner:
        raise ReelError(f"第 {bad_corner} 段的 `inset.corner` 只能是 tl/tr/bl/br")
    unknown = sorted({s.source for s in segments} - set(sources))
    if unknown:
        raise ReelError(
            f"这些段引用了不存在的源：{unknown}；spec 里声明的是 {sorted(sources)}")
    both = [i + 1 for i, s in enumerate(segments) if s.narration and s.quote]
    if both:
        raise ReelError(
            f"第 {both} 段同时写了 narration 和 quote。\n"
            "两者是互斥的：quote 那一段要让当事人自己说，配上旁白就是"
            "**两个人同时开口**，而且闪避会把原声压下去——他的话就没了。\n"
            "要么把这句话改写成旁白（narration，我们替他讲），"
            "要么只留 quote（原声 + 中文字幕）。")
    return segments


# 这一级上「拿掉下划线正好是个真字段」的键名。判据不靠人维护这张表：
# `test_真字段表要盖住每条spec里出现过的字段` 拿 `specs/reels/*.json` 里实际
# 出现过的字段名去对，少一个就红。
_REAL_FIELDS: dict[str, tuple[str, ...]] = {
    "spec": ("cover", "crop_y", "crop_zoom", "mixed_fps", "push", "segments",
             "silent_source", "slug", "source_audio", "source_url", "sources",
             "subtitle_top"),
    "cover": ("event_badge", "eyebrow", "hook", "layout", "matchup", "meta",
              "narration", "portrait", "portrait_above", "result", "round",
              "score", "scrim", "split", "sub", "subject", "tier", "topic",
              "versus", "winner"),
    "segment": ("crosses_cut", "crop_zoom", "cx", "end", "fit", "inset",
                "narration", "quote", "source", "start", "track", "voice"),
}


def _reject_underscored_fields(spec: dict) -> None:
    """`_push` 这种键等于没写——而它整整对了一个月都没人发现。

    `push_meta` 读的是 `push`；仓库里 `_` 开头一律是写给下一个人的注解
    （`_why` / `_source` / `_match`）。写成 `_push` 之后整块**静静地不生效**，
    标题退回「对阵 + 比分」——而那一句看起来完全正常，复制页、微信标题、
    守卫测试全绿。是后来换成单人封面、退路一空，标题当场变成
    `8.2 赛场之上 | ` 才把它抖出来：**这个 bug 只有在另一件不相干的事改变了
    退路的时候才现形。**

    ⚠️ 判据要窄。`_inset` 在 `hewitt-washington` 第 3 段是**真的注解**——
    它就贴在真的 `inset` 旁边，写的是「为什么把角标压在左上角」。所以只认
    **值是一个结构（dict）**的那种：注解是写给人看的话（字符串或字符串列表），
    一个 `_` 开头、值却是个对象、拿掉下划线又正好是真字段的键，几乎一定是
    手滑。反过来验过：`_inset` 那条字符串注解不许被判红。
    """
    def check(where: str, level: str, obj: dict) -> None:
        for key, value in obj.items():
            if not key.startswith("_") or not isinstance(value, dict):
                continue
            if key.lstrip("_") in _REAL_FIELDS[level]:
                raise ReelError(
                    f"{where} 里的 `{key}` 拿掉下划线正好是真字段 "
                    f"`{key.lstrip('_')}`，而 `_` 开头的一律当注解**读都不读**"
                    f"——这一块现在是静静地不生效。\n"
                    f"要它生效就改名叫 `{key.lstrip('_')}`；"
                    f"确实只是注解，就把值写成一句话（字符串），别写成对象。")

    check("spec 顶层", "spec", spec)
    check("cover", "cover", spec.get("cover") or {})
    for index, seg in enumerate(spec.get("segments") or ()):
        if isinstance(seg, dict):
            check(f"第 {index + 1} 段", "segment", seg)


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("segments", "cover"):
        if key not in spec:
            raise ReelError(f"spec 缺少 {key}")
    _reject_underscored_fields(spec)
    if not spec.get("sources") and not spec.get("source_url"):
        raise ReelError("spec 既没有 `sources` 也没有 `source_url`")
    # 多源的 spec：每一段都要说清自己从哪条源片剪。**不给默认值**——猜错了
    # 剪出来是另一场比赛的画面，而且画面本身不会报错，只会静静地对不上旁白。
    names = set(spec.get("sources") or {})
    if names:
        for index, seg in enumerate(spec["segments"]):
            got = seg.get("source")
            if got not in names:
                raise ReelError(
                    f"第 {index} 段的 source 是 {got!r}，不在 sources 里"
                    f"（有 {sorted(names)}）。多源 spec 的每一段都必须显式声明来源。")
    # **只报走哪条路，不拦。** 片长是编辑决定的（账号所有者：「不要砍片长」），
    # 而超过 git 上限的片子自有 Release 那条路接着。**但要出声**——两条路的
    # 链接长得完全不一样，日志里不写就只能靠猜。
    seconds, mib = reel_length_verdict(spec)
    where = ("走 Release 附件（超过 git 的 100 MiB 硬上限）"
             if mib > REPO_INLINE_MIB else "进仓库")
    print(f"[片长] {seconds:.1f}s = {int(seconds // 60)} 分 {int(seconds % 60)} 秒，"
          f"按实测 {MEASURED_REEL_KBPS} kb/s 估 {mib:.0f} MiB —— {where}")
    return spec


def segments_straddling_cuts(
    spec: dict, probes: list[dict],
) -> tuple[list[dict], list[str], list[dict]]:
    """哪几段跨过了源片的场景切点、哪几条源片没查成、哪几段的溶解底料跨了切点。

    **跨切点＝这一段中途换镜头，而换过去的那个镜头里常常是另一个人。**
    郑钦文那条第一版踩了三处，一处都没报错：末屏「你定闹钟吗？」压在对手
    握拳庆祝的近景上（源片 148.2 有切点，窗口取的 144.3–150.0）；「往回爬」
    那句前两秒是对手的背影；巴黎那段「亚洲的第一枚奥运网球单打金牌」整句
    落在维基奇身上。画面和旁白对不上**不会让渲染失败**，只会静静地发出去。

    `probe.json` 里本来就记着 `scene_cuts` 和 `url`，按 url 认源片就能机检——
    挑段仍然要靠眼睛，这一条只负责拦住「窗口中途换了镜头而我没看见」。

    真要跨（两边都是同一个人时），在这一段写 `"crosses_cut": "<为什么>"`
    显式挂账，别默默跨过去。

    第二个返回值是**没查成的源片**：probe 没给全时，前一个返回值会是空的，
    而空的和「全都合格」长得一模一样（CLAUDE.md：空结果先自证是真空）。
    """
    by_url = {p.get("url"): list(p.get("scene_cuts") or []) for p in probes}
    urls = dict(spec.get("sources") or {})
    if not urls:
        urls = {"": spec.get("source_url", "")}
    straddling: list[dict] = []
    tail_cuts: list[dict] = []
    unchecked = sorted(
        name for name, url in urls.items() if url not in by_url)
    last = len(spec["segments"]) - 1
    for index, seg in enumerate(spec["segments"]):
        name = seg.get("source", "")
        url = urls.get(name)
        if url not in by_url or seg.get("crosses_cut"):
            continue
        # **溶解的底料也要查，但它和「段中途换镜头」不是一回事，别混成一档。**
        # 除末段外，每一段还要多切 `SEG_FADE` 秒当下一个接缝的底
        # （见 `dissolve_filtergraph`）。那几秒跨了切点，溶解里会**多叠进一个
        # 镜头**——而它是半透明、只有一两帧，和「整句旁白压在另一个人身上」
        # 差着量级。
        #
        # 分开报是因为**合成一档会把强的那条判据弄钝**：段体跨切点的出路是
        # 写 `crosses_cut` 认领，而尾巴跨切点在实拍素材上很常见（窗口本来就
        # 该切在源片自己的镜头边界上，于是切点就落在末尾一两帧之后）。
        # 一档的话，人会为了压掉尾巴那条噪音去写 `crosses_cut`，顺手把段体
        # 那条真检查一起关掉。
        inside = [c for c in by_url[url] if seg["start"] < c < seg["end"]]
        if inside:
            straddling.append({
                "index": index, "source": name,
                "start": seg["start"], "end": seg["end"],
                "cuts": inside, "narration": seg["narration"],
            })
        elif index != last:
            ghost = [c for c in by_url[url]
                     if seg["end"] <= c < seg["end"] + SEG_FADE]
            if ghost:
                tail_cuts.append({
                    "index": index, "source": name, "end": seg["end"],
                    "cuts": ghost,
                    # 切点落在溶解的哪个位置：越靠后，叠进来的那一层越淡
                    "opacity": max(0.0, 1 - (min(ghost) - seg["end"]) / SEG_FADE),
                })
    return straddling, unchecked, tail_cuts


def resolve_sources(spec: dict, outdir: Path) -> dict[str, Path]:
    """把 spec 里的源片全下下来，返回 {名字: 路径}。

    单源 spec 走 `source_url`，键是空串——和 `Segment.source` 的默认值对上，
    老 spec 一个字都不用改。
    """
    urls = dict(spec.get("sources") or {})
    if not urls:
        urls = {"": spec["source_url"]}
    paths: dict[str, Path] = {}
    for name, url in urls.items():
        dest = outdir / (f"source_{name}.mp4" if name else "source.mp4")
        if not dest.is_file():
            with stage(f"下载源片 {name or '(单源)'}"):
                dest = download(url, dest)
        paths[name] = dest
    return paths


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


def track_shots(sources: dict[str, Path], segments: list["Segment"],
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
        prev = segments[runs[-1][-1]] if runs else None
        joins = (runs and trackable
                 and abs(seg.start - prev.end) < 1e-3
                 and prev.fit != "contain"
                 and prev.track
                 # **跨源不许合并镜头。** 「连着」的判据是时间码相接，而两条
                 # 源片的时间码会**偶然**相接——那样就把两场比赛的画面当成
                 # 一个连续镜头去跟，跟出来的质心横跨两个机位，毫无意义。
                 # 而且它不吭声：合出来的窗口照样能渲。
                 and prev.source == seg.source)
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
    # ⚠️ **摇的段也要填 `cx`。** 这里原来写着 `not s.track`——只给不摇的段填，
    # 于是 `track: true` 的段 `cx` 留着 `None`，而 `cut_segment` **无条件先算**
    # 一个兜底的 `x = seg.cx * source_w - CROP_W/2`，当场
    # `TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'`
    # （run 30877075310，分段编码到第 11 段才炸，前面十段全白编）。
    #
    # **存量九条 spec 一条都没用过 `track`**，所以这条路从「自动定心改成固定
    # 中心」那天起就是坏的，一直没人踩到——又一次「写了不等于跑过」：
    # 那次改动只保证了它走的那条路，另一条路的前提被顺手拿掉了。
    #
    # 摇的段有 `path` 时用不上这个值；**拿不到 path 时它就是兜底**，见下面。
    fixed = [s for s in segments if s.fit != "contain" and s.cx is None]
    for seg in fixed:
        seg.cx = 0.5
    still = [s for s in fixed if not s.track]
    if still:
        print(f"    [fixed] {len(still)} 段不摇，窗口取源片正中 cx=0.500")
    for members in runs:
        start = segments[members[0]].start
        end = segments[members[-1]].end
        with stage("跟踪抽帧"):
            # 同一条 run 里的段来自同一条源（跨源不合并，见上面 joins 的判据）
            coarse = track_run(sources[segments[members[0]].source],
                               start, end, source_w)
        if len(members) > 1:
            print(f"    [track] 上面这条是 {len(members)} 段连着的同一个镜头")
        for index in members:
            tracks[index] = sample_track(coarse, segments[index])
    return tracks


def _overlay_chain(base: str, ins: dict) -> str:
    """把角标压上去。没有角标时只是把 `[base]` 改名成 `[vout]`。

    **位置和边距都按画幅算，不写死像素。** 角标宽度给的是占画幅宽的比例，
    1080 宽下 0.34 → 367px；边距 4.3% → 46px。改画幅时两个数一起跟着走。

    ⚠️ 角标要**避开字幕那一条**。字幕上锚在 y=1284（卡底往上 156px），
    所以底部两角实际只剩到 1284 为止——贴 `bl`/`br` 时自己算清楚，
    默认给 `tl`：这条线的成片顶部没有常驻角标，那儿是空的。
    """
    if not ins:
        return base.replace("[base]", "[vout]")
    width = int(round(float(ins.get("width", 0.34)) * VIDEO_W)) // 2 * 2
    pad = int(round(float(ins.get("pad", 0.043)) * VIDEO_W))
    corner = str(ins.get("corner", "tl"))
    x = f"{pad}" if corner in ("tl", "bl") else f"W-w-{pad}"
    y = f"{pad}" if corner in ("tl", "tr") else f"H-h-{pad}"
    return (f"{base};[1:v]scale={width}:-2[ins];"
            f"[base][ins]overlay={x}:{y}[vout]")


def cut_segment(source: Path, seg: Segment, dest: Path, source_w: int,
                path: list[tuple[float, int]] | None = None,
                tail: float = 0.0) -> Path:
    """切一段、裁成 3:4、放大到 1080×1440。

    `tail` 是留给**下一个接缝**的溶解料：多切这么几秒源片的自然延续，
    拼接那一步的 `xfade` 正好把它吃掉（见 `dissolve_filtergraph`）。
    所以这一段在成片里占的仍然是 `seg.length`，不是 `seg.length + tail`。

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
            # **声明了要摇却没拿到路径**，是退回固定中心——但要出声。
            # 不吭声的话，「跟踪抽帧失败」和「本来就不摇」在日志上一模一样，
            # 而这一段之所以写 `track: true`，正是因为固定中心装不下主体。
            if seg.track:
                print(f"    [track] ⚠️ {seg.start:.1f}s 段声明了 track 但没跟出"
                      f"路径，退回固定中心 cx={seg.cx:.3f}——"
                      "主体如果在横向移动，这一段的构图要自己看一眼")
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
    # **角标那张 PNG 排在源片后面当第 1 路输入**，补位静音顺延到第 2 路。
    # 顺序写死是为了让下面 `-map` 的音轨索引可算——原来 `1:a:0` 指的是静音，
    # 插进一路图之后它就变成第 2 路了；这种索引错**不报错**，只是取错流。
    ins = seg.inset or {}
    inset_in = ["-i", str(ins["image"])] if ins else []
    null_idx = 2 if ins else 1
    extra_in = ([] if has_audio else
                ["-f", "lavfi", "-i",
                 f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}"])
    # ⚠️ **这儿不许再出现 `fade=`。** 淡入淡出收在拼接那一步的 `xfade`：
    # 在这儿淡是「各自淡到黑」，接缝中间必然有一帧全黑（量过，见 SEG_FADE）。
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
            "-ss", f"{seg.start:.3f}", "-i", str(source), *inset_in, *extra_in,
            # 时长而不是 `-to`：`-ss` 变成输入选项之后输出时间轴从 0 起算，
            # 再写 `-to seg.end` 会把整段截没。
            "-t", f"{seg.length + tail:.3f}",
            # 输出必须打标签并显式 map：`-map 0:v:0` 取的是**原始流**，
            # 会把整个滤镜图绕过去——裁切、缩放、跟踪全不生效，成片直接是 16:9。
            "-filter_complex",
            _overlay_chain(
                (chain + "[base]") if seg.fit == "contain"
                else f"[0:v]{chain}[base]", ins),
            "-shortest", "-map", "[vout]",
            "-map", "0:a:0" if has_audio else f"{null_idx}:a:0",
            # 分段是**中间产物**：最后整片还要以 crf 18 重编一次，这里编到
            # crf 17/preset slow 是把画质编进一个马上被重编的文件里，白花时间。
            # medium/crf 20 在同一段上 6.2s → 4.0s，重编后的成片肉眼无差。
            # 成片那一步的参数没有动。
            "-c:v", "libx264", "-preset", PART_PRESET, "-crf", PART_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", AUDIO_RATE,
            str(dest))
    return dest


def build_cover(sources: dict[str, Path], primary: str, spec: dict,
                dest: Path, source_w: int, seconds: float = COVER_SECONDS,
                *, tail: float = 0.0) -> Path:
    """封面：**一律走「赛场之上」的固定海报模板**（`tools/versus_poster.py`）。

    账号所有者定的：「以后『赛场之上』封面海报都用新的模板方案。」所以这里
    **没有第二条路**——抓一帧当封面那条分支已经删掉了，不是留着当兜底。
    留着兜底的后果是可预见的：哪条片子一时找不到照片，就悄悄退回抽帧，
    栏目的封面从此有两副面孔，而且退回去的那次没人会注意到。

    抽帧本来就不该当默认：1920×1080 的一帧裁成竖版要放大一倍多，比一张官方
    原图软一大截，而封面是唯一决定人点不点的那一屏。

    缺图就报错，并把出路写在报错里——**去扩检索源**（赛事官方图库 → 协会/赛事
    新闻页 → 新闻站与图片社 → Commons/Flickr），不是退回抽帧。

    **模板有两副，按栏目选，不按素材凑手选**：

    - `赛场之上`讲一场对决 → VS 模板（两格 + 中缝 + VS 圆牌 + 两个名字）
    - `网球有故事`讲一个人 → `layout: "solo"`，封面只有主角

    账号所有者 2026-07-31 定的：休伊特那条「是讲休伊特的儿子的话题，不是
    赛场之上的内容」「所以封面只有休伊特儿子照片」。反过来那条**没有松**：
    ⚠️ **2026-08-04 又翻了回来**：账号所有者「以后都用 solo 版做「赛场之上」
    封面」，于是 solo 成了默认，**退回 VS 才要写 `_layout_why`**。下面那段
    注释记着这次翻面的完整理由。
    """
    cover = spec["cover"]
    layout = str(cover.get("layout", "cutout"))
    eyebrow = str(cover.get("eyebrow", "")).strip()
    # ⚠️ **闸在 2026-08-04 整个反过来了。**
    #
    # 账号所有者：「**以后都用 solo 版做「赛场之上」封面**」「中间标题下面
    # 写上比分（带双方国旗）」。所以 solo 成了这个栏目的默认，VS 反过来成了
    # 需要认领的那一支。
    #
    # 老规矩（「赛场之上一律 VS，solo 要写 `_layout_why`」）要防的是**滑坡**：
    # 单人海报一旦能渲，下次哪条对决片子凑不齐两张照片，就会「先用 solo
    # 顶一下」。**那个滑坡现在不存在了**——solo 本来就是默认，没什么可省的。
    # 而反方向的滑坡出现了：有人手头正好有两张抠图，就顺手退回 VS，栏目的
    # 封面于是又变成两种样子。所以闸原样翻个面：**非 solo 要写 `_layout_why`**。
    #
    # 已发的十几条 VS 封面不动（`_LEGACY_VS_COVERS`，只许减不许加）——
    # 微信那条消息发出去收不回来，为版式重渲没有意义。
    if layout != "solo" and eyebrow == "赛场之上" \
            and str(spec.get("slug", "")) not in _LEGACY_VS_COVERS \
            and not str(cover.get("_layout_why", "")).strip():
        raise ReelError(
            "「赛场之上」的封面从 2026-08-04 起一律用 solo："
            "账号所有者「以后都用 solo 版做『赛场之上』封面」。\n"
            f"这条 spec 写的是 layout={layout!r}。\n"
            "改成 `\"layout\": \"solo\"` + `cover.portrait`（本场源片抓一帧就行），"
            "赛果写在 `cover.result` + `cover.matchup`，"
            "会渲成标题底下那一行「🇨🇳 张帅（57） 6-4 6-1 🇰🇿 普汀塞娃（81）」。\n"
            "**确实要退回 VS 版式，就写一句 `cover._layout_why` 说清楚为什么**"
            "——一句话就行，但必须写；不写就是手滑，不是决定。")
    if layout == "solo":
        if not (cover.get("portrait") or {}).get("image") and \
                (cover.get("portrait") or {}).get("frame_at") is None:
            raise ReelError(
                "solo 封面缺 `cover.portrait`：要主角的一张**本场**实拍。\n"
                "格式：cover.portrait = {image | frame_at, source, "
                "focus, focus_y, zoom, fit}\n"
                "四道闸门照旧；四类源都拿不到本场的，就从本场源片抓一帧。")
        return build_versus_poster(sources, primary, cover, dest, seconds,
                                   tail=tail)
    if not cover.get("versus"):
        raise ReelError(
            "封面缺 `cover.versus`：赛场之上的封面一律走固定海报模板，"
            "要两个人各一张**本场**的真实照片。\n"
            "先扩检索源（赛事官方图库 → 协会/赛事新闻页 → 新闻站/图片社 → "
            "Commons/Flickr）；**四类源都拿不到本场的实拍，就从本场源片抓一帧**"
            "（`frame_at`，账号所有者 2026-07-31 定：「或者从比赛中抠大图，"
            "要情绪饱满的」）。抓帧要挑情绪最满的那一格，别挑随便一个回合。\n"
            "格式：cover.versus = {split, names: [上, 下], "
            "top: {image, focus, focus_y, zoom, fit}, bottom: {…}}\n"
            "讲一个人的栏目（网球有故事）用 `layout: \"solo\"` + cover.portrait。")
    # ⚠️ **`tail` 两条出路都要带上。** `build_cover` 有两个 return，上面那个是
    # solo、这个是 VS——而「赛场之上」「开球之前」走的都是这一个。第一版只改了
    # 上面那个，于是封面片段没有多切 0.18s，`xfade` 的 offset 正好落在它的末尾，
    # 整条溶解链塌掉：成片 12.44s，段落加起来 114.46s（run 30752134514）。
    # 同一对函数（build_cover → build_versus_poster）栽的第三次。
    return build_versus_poster(sources, primary, cover, dest, seconds,
                               tail=tail)


def build_versus_poster(sources: dict[str, Path], primary: str,
                        cover: dict, dest: Path, seconds: float = COVER_SECONDS,
                        *, tail: float = 0.0) -> Path:
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

    layout = str(cover.get("layout", "cutout"))
    versus = dict(cover.get("versus") or {})

    def _grab(spot: dict, tag: str) -> str:
        """`image` 直接用，`frame_at` 从源片抓一帧。抓出来的不进仓库。

        多源之后 `frame_at` 要说清楚**抓哪条源**（`"source": "键"`，默认主源）。
        不说清楚就会从主源的同一时刻抓——那是另一场比赛的画面，而且**不报错**。
        """
        if spot.get("image"):
            if not Path(spot["image"]).is_file():
                raise ReelError(f"VS 拼接的 {tag} 找不到图：{spot['image']}")
            return str(spot["image"])
        key = str(spot.get("source", primary))
        if key not in sources:
            raise ReelError(
                f"VS 的 {tag} 要从源 {key!r} 抓帧，但 spec 里声明的是 {sorted(sources)}")
        grab = dest.parent / f"_versus_{tag}.jpg"
        with stage(f"VS 抓帧 {tag}（源 {key or '主'}）"):
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{float(spot['frame_at']):.2f}", "-i", str(sources[key]),
                "-frames:v", "1", "-q:v", "2", str(grab))
        return str(grab)

    if layout == "solo":
        art = dict(cover["portrait"])
        art["image"] = _grab(art, "portrait")
        cover = {**cover, "portrait": art}
    elif layout == "cutout":
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
                # **抓哪条源要按 panel 自己写的算**，和 `_grab` 同一套。原来这儿
                # 写的是 `source`，而这个函数的作用域里根本没有这个名字——
                # 「首选本场抽帧」这条路一次都没跑起来过，第一次用必 NameError。
                # `ruff --select F821` 一秒就能指出来，判据落在
                # test_没有名字是凭空来的。
                skey = str(panel.get("source", primary))
                if skey not in sources:
                    raise ReelError(
                        f"VS 的 {key} 要从源 {skey!r} 抽帧抠图，"
                        f"但 spec 里声明的是 {sorted(sources)}")
                panel["cutout"] = _cut_person(sources[skey], panel, key,
                                              dest.parent)
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
    payload = dict(cover) if layout == "solo" else {**cover, "versus": versus}
    with stage("封面海报"):
        build_poster(payload, poster, layout=layout)
    poster.with_suffix(".html").unlink(missing_ok=True)   # 内嵌 data URI，十几 MB
    column = str(cover.get("eyebrow", "")).strip() or "赛场之上"
    print(f"    [封面] {column}海报 {layout} → {poster.name}")
    return _still_to_clip(poster, dest, seconds + tail)


#: 抠图模型。三个都试过并把 alpha 摊在棋盘格上看边：u2net 和 u2net_human_seg
#: 把锦织圭的发梢切平了一条，isnet 保住了。
CUT_MODEL = "isnet-general-use"
#: 抠出来的东西至少要占裁切框这么大，否则当成「没抠到人」。
#: 6% 是从已知好素材倒推的：官方半身抠图占 65%，本场人物近景同一量级，
#: 而抠到一条球拍残影只有百分之几——两者隔着一个数量级，门槛落在中间。
CUT_MIN_SHARE = 0.06


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
        # **「抠出来是空的」有两种，`getbbox()` 只拦得住一种。** 完全透明它拦得住；
        # 抠到一条球拍残影、一道边线，bbox 非空，于是**一路绿到底**——render
        # success、`check_reel_landed` 0 项不合格、海报上人没了。2026-08-01 黄泽林
        # 那张就是这么出去的（138.14s 那一帧，左格只剩背景和一道白线）。
        # 又一次「兜底出事的时候不吭声」。
        #
        # 判据用**不透明像素占裁切框的比例**：人物近景是一大块，残影是一条线。
        # 门槛 6% 是从已知好素材倒推的——官方半身抠图 65%，本场近景同一量级，
        # 中间隔着一个数量级。比例照常打进日志，这样下次调门槛有数可依
        # （「检查工具要把不合格的也列出来」）。
        alpha = cut.getchannel("A")
        opaque = sum(n for v, n in zip(range(256), alpha.histogram()) if v > 16)
        share = opaque / float(im.size[0] * im.size[1])
        if share < CUT_MIN_SHARE:
            raise ReelError(
                f"VS {tag} 抠出来只有裁切框的 {share:.1%}（要 ≥{CUT_MIN_SHARE:.0%}）"
                f"——{panel['frame_at']}s 那一帧多半抠到了球拍或边线，不是人。\n"
                "换一帧（挑**头部和背后背景对比强**的那种），或者退回官方抠图："
                'top/bottom 写 {"cutout": "assets/players/<...>.png"}。')
        cut = cut.crop(bbox)
        cut.save(out)
    print(f"    [封面] {tag} 抽帧抠图 {panel['frame_at']}s → {cut.size[0]}×{cut.size[1]}"
          f"，占裁切框 {share:.1%}")
    raw.unlink(missing_ok=True)
    return str(out)


def _still_to_clip(still: Path, dest: Path, seconds: float = COVER_SECONDS) -> Path:
    """封面静图 → 一小段带静音轨的视频，接进片头。

    静音轨是**占位**：封面那句旁白和其他段一样，在最后混音那一步按 `adelay=0`
    叠上去。这儿要是也塞一路音频，就成了「补位的静音盖住真音轨」那个老毛病。
    """
    with stage("封面编码"):
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(still), "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}",
            "-t", f"{seconds:.3f}",
            "-vf", f"fps={FPS_EXPR},setsar=1",
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


def tts_one(text: str, path: Path, voice: str, rate: str,
             pitch: str = "+0Hz", style: str = "", styledegree: str = "",
             lead_pause: float = 0.0) -> list[dict]:
    """合一条语音，落盘并返回词边界。

    抽出来是因为**封面也要配音**了：封面那句得在渲封面之前就合出来——封面停多久
    由它的长度决定（见 `cover_length`），不能等到 `synthesize()` 那一步。
    """
    # **配了 Azure 就走 Azure。** 同一把嗓子（`zh-CN-YunjianNeural`），多出
    # 十个情绪风格和真 `<break>`——两条路 2026-08-04 在 runner 上并排探过
    # （run 30884267406 / 30892017944）。词边界单位已经在 `azure_tts` 里对齐到
    # 100ns，字幕那条线一个字不用改。
    if azure_tts.available():
        print(f"[TTS] Azure（风格 {style or '无'}）")
        return azure_tts.synthesize(
            text, path, voice=voice, rate=rate, pitch=pitch, style=style,
            styledegree=styledegree, lead_pause=lead_pause)
    # ⚠️ **spec 明确要了情绪风格却没有 Azure，必须报错**：悄悄退回 edge-tts
    # 等于发一条和 spec 说的不一样的片子，而且不吭声——这个仓库最常见的那种坏。
    if style or lead_pause:
        raise ReelError(
            f"这一段要 `voice.style={style or '—'}` / `lead_pause="
            f"{lead_pause or '—'}`，而它们**只有 Azure 那条路有**"
            f"（Edge 免费端点对 express-as 和 break 一律拒绝，实测 run "
            f"30884267406）。\n当前不可用：{azure_tts.why_unavailable()}\n"
            "两条出路：把这两个键从 spec 里去掉（退回只调语速音高），"
            "或者配好 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION 再渲。")

    import asyncio

    import edge_tts

    async def one() -> list[dict]:
        marks: list[dict] = []
        with path.open("wb") as fh:
            stream = edge_tts.Communicate(
                text, voice, rate=rate, pitch=pitch,
                boundary="WordBoundary").stream()
            async for chunk in stream:
                if chunk.get("type") == "audio" and chunk.get("data"):
                    fh.write(chunk["data"])
                elif chunk.get("type") in ("WordBoundary", "SentenceBoundary"):
                    marks.append({"offset": chunk.get("offset", 0),
                                  "duration": chunk.get("duration", 0),
                                  "text": chunk.get("text", "")})
        return marks

    marks = asyncio.run(one())
    if not path.is_file() or path.stat().st_size == 0:
        raise ReelError(f"TTS 没出音频：{path.name}　「{text[:24]}…」")
    path.with_suffix(".words.json").write_text(
        json.dumps(marks, ensure_ascii=False), encoding="utf-8")
    return marks


def synth_cover(spec: dict, outdir: Path, voice: str, rate: str
                ) -> tuple[Path | None, list[dict]]:
    """封面那句旁白。没写就返回 `(None, [])`——封面退回定长静止。

    **封面配音是「网球有故事」那条线的做法**（账号所有者定的）：那个栏目讲一个人，
    封面念的就是海报上那句钩子，封面停多久跟着它走。

    「赛场之上」不走这条：它是一场对决的赛报，封面是定长 1.2 秒的短亮相，
    立刻切进第一个回合——**停久了会被当成图片**。所以在这儿拦住，别让两条线
    互相牵动：赛场之上写了 `cover.narration` 直接报错，而不是默默把封面拉长。
    """
    text = str((spec.get("cover") or {}).get("narration") or "").strip()
    if not text:
        return None, []
    column = str(spec.get("column") or (spec.get("cover") or {}).get("eyebrow") or "")
    if "赛场之上" in column:
        raise ReelError(
            "「赛场之上」的封面不配音：它是定长 1.2 秒的短亮相，立刻切进第一个"
            "回合——停久了会被当成图片而不是视频。封面跟着配音走是「网球有故事」"
            "那条线的做法（那个栏目讲一个人，念的就是海报上那句钩子）。\n"
            "把 cover.narration 删掉；那句话要留，就放进第一段的 narration。")
    path = outdir / "voice_cover.mp3"
    with stage("封面配音"):
        marks = tts_one(text, path, voice, rate)
    return path, marks


def cover_length(voice_path: Path | None) -> float:
    """封面停多久。

    **有配音就跟着配音走，没有才用定长。** 账号所有者定的：「这个栏目不要求
    〔固定几秒〕，随着配音切换吧」——封面那句话说完就切，不多停，也不半路截断。

    `COVER_TAIL` 是说完之后留的那口气：切得贴着最后一个字，末尾的辅音会被
    concat 的边界削掉，听着像卡了一下。0.25s 是「说完了」和「停顿」之间那一档。

    没有配音的片子（存量的赛场之上都是）退回 `COVER_SECONDS`，并且**要出声说
    走的是哪条路**——两条路的产物长得不一样，日志里不写就只能靠猜。
    """
    if voice_path is None:
        print(f"[封面] 没有配音，定长停 {COVER_SECONDS}s")
        return COVER_SECONDS
    spoken = probe_duration(voice_path)
    length = round(spoken + COVER_TAIL, 3)
    print(f"[封面] 跟着配音走：旁白 {spoken:.2f}s + 尾 {COVER_TAIL}s = {length:.2f}s")
    return length


# 一段画面里最多允许多少秒没人在说话。
#
# 账号所有者 2026-08-02：「不是补全的问题，我是说有些没有字幕了，给漏掉了」
# 「利用完整区域，整个里面去读一下」。按时间轴通读，jodar-fritz **68.7s /
# 185.4s（37%）屏幕上没有字**——不是字幕丢了，是那几秒没人在说话，集中在每段
# 后半截（短句配了长窗口）。
#
# **门槛卡「最长的一段空白」，不卡总占比。** 1~3 秒的空是句子之间正常的换气，
# 填满反而赶；难受的是一段连着 5~6 秒什么都没有。量出来的分布很干净：
#
#     补之前 jodar   最长一段 6.44s，>4s 的有 5 段
#     补之后 jodar   最长一段 2.89s，>3s 的 0 段
#     eala-pegula    最长一段 2.99s，>3s 的 0 段
#
# 4.0s 落在 2.99 和 5.03 之间，两头都不贴边。
MAX_SILENT_GAP = 4.0


def _protected_names(spec: dict) -> list[str]:
    """这条片子里不许被切开的专名：封面上印的那两个中文名 + 主角。

    出处只有 spec 一处（`cover.matchup` / `cover.subject`），**不另维护名单**——
    一个要靠人记着更新的名单，和一条常年红的检查是同一个毛病。
    """
    cover = spec.get("cover") or {}
    names = [str(p.get("name", "")).strip()
             for p in (cover.get("matchup") or []) if isinstance(p, dict)]
    names.append(str(cover.get("subject", "")).strip())
    for side in ("top", "bottom"):
        who = (cover.get("versus") or {}).get(side) or {}
        if isinstance(who, dict):
            names.append(str(who.get("name", "")).strip())
    # 两个字的名字太容易撞上普通词（「王」「张」），跟译名表那条一个道理
    return [n for n in dict.fromkeys(names) if len(n) >= 3]


def _word_splits(spec, segments, voices) -> list[tuple[int, str, list, list, str, list]]:
    """每段问一次合成器「你把这句话切成了哪些词」。

    ⚠️ **喂进去的必须是 `speakable()` 之后那份**——合成器念的是它，不是 spec 里
    写的那份。拿原文去 find token，「硬地」那种替换过的字一个都对不上。
    """
    out = []
    names = _protected_names(spec)
    for index, seg in enumerate(segments):
        text = (seg.narration or "").strip()
        if not text or index >= len(voices):
            continue
        marks = voices[index][1]
        if not marks:
            continue
        spoken = speakable(text)
        line, crossing, inside = word_split_report(spoken, marks, names)
        tokens = [t for t in (str(m.get("text", "")).strip() for m in marks) if t]
        out.append((index, line, crossing, inside, spoken, tokens))
    return out


def _print_word_splits(splits) -> None:
    """把切词摊开印进日志。**不拦，只报。**

    为什么不做成闸：跨边界这一类确实该改，但改法是重写句子（加逗号、换句式），
    是个编辑判断；而「专名内部切开」压根改不了。做成硬闸的下场是有人为了让它
    变绿去改一句本来很好的台词——和「判据宁可窄，不可宽」是同一条。
    """
    if not splits:
        print("\n[查切词] 这条 spec 没有拿到词边界（合成器没报，或者没有旁白）。"
              "\n  ⚠️ 空不等于没问题——拿一段已知有旁白的 spec 对一次再下结论。")
        return
    crossing = [(i, c) for i, _, c, _, _, _ in splits if c]
    inside = [(i, x) for i, _, _, x, _, _ in splits if x]
    singles = all_single_char_segments(
        [(i, text, toks) for i, _, _, _, text, toks in splits])
    print(f"\n[查切词] 合成器自己报的切词，{len(splits)} 段：")
    for index, line, _, _, _, _ in splits:
        print(f"  第 {index + 1:>2d} 段  {line}")
    if singles:
        print("\n⚠️ 整段每个 token 都是一个字，说明切词器没拿到上下文，"
              "这几段读音风险最高：")
        for item in singles:
            print(f"  {item}")
    if crossing:
        print("\n⚠️ 有 token 骑在人名的边界上——念出来会把名字和邻字连读成一个"
              "不存在的词：")
        for index, items in crossing:
            for item in items:
                print(f"  第 {index + 1:>2d} 段  {item}")
        print("  改法：名字前后加逗号，或者动词后面加「了」把它撑开"
              "（「赢斯特鲁夫」→「赢了斯特鲁夫」）。")
    if inside:
        print("\n（下面这些是人名内部被切开，每个字的读音不变，一般不用管）")
        for index, items in inside:
            for item in items:
                print(f"  第 {index + 1:>2d} 段  {item}")
    if not crossing:
        print("\n[查切词] 没有 token 骑在人名边界上。"
              "其余的切法要自己扫一眼上面那几行 `｜`。")


def narration_overruns(segments, voices) -> tuple[dict, list[str]]:
    """量每段旁白的真实时长，把**超出自己那一段**的全列出来。

    抽出来是为了让它能**脱离 render 单独跑**（`--check-narration`）：这道闸
    比的是「TTS 时长 vs spec 里的段长」，**两样都不需要源片**。而想知道一条
    spec 的哪几段写长了，原来只能跑一趟 render——那会在通过的情况下**顺手渲
    出一条新成片并提交**，对已经发过的片子就是白白多一个 blob。

    量的是 mp3 的真实时长，不是 `words.json` 的末事件——后者**低估**，
    量出来是稳稳的 **0.83s**（见 `speech_seconds` 的推导）。
    """
    spoken_of: dict[int, float] = {}
    over: list[str] = []
    for index, (seg, (path, _marks)) in enumerate(zip(segments, voices)):
        if not seg.narration.strip():
            continue
        spoken_of[index] = probe_duration(path)
        if spoken_of[index] > seg.length + 0.12:
            over.append(f"  第 {index + 1} 段：画面 {seg.length:.1f}s，"
                        f"旁白 {spoken_of[index]:.2f}s，超出 "
                        f"{spoken_of[index] - seg.length:.2f}s"
                        f"　「{seg.narration[:24]}…」")
    return spoken_of, over


# 情绪风格听着「过不过头」，不必只靠耳朵 -----------------------------------
# 2026-08-04 账号所有者问「成片音轨听着行不行——这个怎么评判？」，随后又
# 「我现在不方便听啊，你能帮分析选择么」。**「听着行不行」拆得开**：音高、
# 响度、语速三样都能量，只有音色和自然度量不了。这个函数报前三样。
#
# ⚠️ **一定要量原始语音，不能量成片。** 第一版拿混音后的 mp4 量，基线那条
# （fritz-jodar，edge-tts）**七段全部「散」**——现场声把自相关污染了，可信
# 0/7。而这里拿的是 `synthesize()` 刚落下的 mp3，一个现场声像素都没有。
#
# ⚠️ **自相关基频最容易犯倍频错误**（把 200 Hz 读成 100 或 400），而且它
# **不吭声**。所以每一行都带四分位距：分布**紧**才是真的，散成两坨的那个数
# 不作数，报告里明写出来，别让读的人拿一个坏数去下结论。
_F0_SR = 16000
_F0_LO_HZ, _F0_HI_HZ = 70, 350
# 四分位距超过中位数这个比例就判为「散」。0.45 是拿存量量出来的：带风格那两段
# 是 0.18~0.24，而被现场声污染的那些一律 0.6 以上，两档分得很开。
_F0_SPREAD_BAD = 0.45


def voice_prosody(path: Path) -> dict | str:
    """量一条语音的基频和响度。量不了就返回**一句说明为什么**，不返回裸的 None。

    ⚠️ 第一版返回 `None`，报告里印一句「量不了（有声帧太少或缺 numpy／ffmpeg）」
    ——十一段全是这一句，而那三个原因**出路完全不同**（装包 / 修命令 / 换素材）。
    一个笼统的解释盖住一个具体的 bug，这个仓库栽过很多次。现在每一条都自己说。
    """
    try:
        import numpy as np  # noqa: PLC0415
    except ImportError as exc:
        return f"没装 numpy（{exc}）"
    if not path.is_file():
        return f"文件不在：{path}"
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
         "-ar", str(_F0_SR), "-f", "s16le", "-"],
        capture_output=True, check=False)
    raw = proc.stdout
    if not raw:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:160]
        return f"ffmpeg 解不出音频（码 {proc.returncode}）{(' ' + err) if err else ''}"
    x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    n, hop = int(0.040 * _F0_SR), int(0.010 * _F0_SR)
    frames = [x[i:i + n] for i in range(0, max(0, len(x) - n), hop)]
    if not frames:
        return f"音频太短：{len(x) / _F0_SR:.2f}s"
    rms = np.array([float(np.sqrt((f ** 2).mean())) for f in frames])
    # 只取有声帧：静音段的自相关是噪声，混进来会把中位数拖歪
    thr = max(float(np.median(rms)) * 0.5, 1e-4)
    lo, hi = int(_F0_SR / _F0_HI_HZ), int(_F0_SR / _F0_LO_HZ)
    pitches = []
    for frame, level in zip(frames, rms):
        if level < thr:
            continue
        frame = frame - frame.mean()
        auto = np.correlate(frame, frame, "full")[len(frame) - 1:]
        if auto[0] <= 0:
            continue
        auto = auto / auto[0]
        seg = auto[lo:hi]
        if not len(seg):
            continue
        # **取第一个够高的峰，不取全局最大**——全局最大常落在倍频下方，
        # 于是一把男声会被读成半个八度以下，而那个数看起来完全正常。
        peak = next((i + lo for i in range(1, len(seg) - 1)
                     if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]
                     and seg[i] > 0.35), None)
        if peak is None:
            best = int(np.argmax(seg))
            if seg[best] <= 0.30:
                continue
            peak = best + lo
        pitches.append(_F0_SR / peak)
    if len(pitches) < 12:
        return (f"有声帧太少：{len(frames)} 帧里只有 {len(pitches)} 帧定得出基频"
                f"（门槛 12）")
    arr = np.array(pitches)
    voiced = rms[rms >= thr]
    q1, q3 = (float(np.percentile(arr, 25)), float(np.percentile(arr, 75)))
    median = float(np.median(arr))
    return {"f0": median, "q1": q1, "q3": q3,
            "trusted": (q3 - q1) < median * _F0_SPREAD_BAD,
            "db": float(20 * math.log10(max(float(np.sqrt((voiced ** 2).mean())),
                                            1e-6)))}


def prosody_report(segments, voices, spoken_of: dict[int, float]) -> list[str]:
    """逐段报音高／响度／语速，并把**带风格的和不带的**摆在一起比。

    这是「情绪弧做出来没有」和「有没有做过头」唯一不用耳朵的答案。
    ⚠️ 它答不了**音色自不自然**——那一项没有仪器，只能听。报告末尾明写这句，
    免得一张全绿的表被读成「已经验过了」。
    """
    lines = ["", "[查韵律] 逐段音高／响度／语速（量的是**原始语音**，没有现场声）",
             f"{'段':>4}  {'风格':<26} {'字/秒':>6} {'基频Hz':>7} "
             f"{'四分位':>13} {'响度dB':>7}"]
    rows: list[tuple[int, str, float, dict | None]] = []
    for index, seg in enumerate(segments):
        if index not in spoken_of:
            continue
        # ⚠️ `Segment` 上是**平铺的四个字段**，不是一个 `voice` 字典。
        # 第一版写成 `seg.voice`＋`hasattr` 兜底——每段都取到空串，
        # 「带风格」那一组永远是空的，**而且不报错**。
        style = seg.voice_style
        rate = seg.voice_rate
        tag = f"{style}{' ' + rate if rate else ''}"
        chars = len([c for c in seg.narration if c.strip()])
        cps = chars / spoken_of[index] if spoken_of[index] else 0.0
        info = voice_prosody(voices[index][0])
        rows.append((index, style, cps, info if isinstance(info, dict) else None))
        if not isinstance(info, dict):
            lines.append(f"{index + 1:>4}  {tag:<26} {cps:>6.2f} "
                         f"{'量不了':>7}　{info}")
            continue
        flag = "" if info["trusted"] else "  ⚠️散，这个数不作数"
        lines.append(f"{index + 1:>4}  {tag:<26} {cps:>6.2f} {info['f0']:>7.1f} "
                     f"{info['q1']:>6.1f}–{info['q3']:<6.1f} {info['db']:>7.1f}{flag}")

    styled = [r for r in rows if r[1]]
    plain = [r for r in rows if not r[1]]
    if styled and plain:
        def band(items, key):
            vals = [key(r) for r in items if key(r) is not None]
            return (min(vals), max(vals)) if vals else None
        f0 = lambda r: r[3]["f0"] if r[3] and r[3]["trusted"] else None   # noqa: E731
        db = lambda r: r[3]["db"] if r[3] else None                        # noqa: E731
        cps = lambda r: r[2]                                              # noqa: E731
        lines.append("")
        for name, items in (("带风格", styled), ("不带风格", plain)):
            f, d, c = band(items, f0), band(items, db), band(items, cps)
            lines.append(
                f"  {name:<5} {len(items):>2} 段 ｜ 基频 "
                + (f"{f[0]:.0f}–{f[1]:.0f} Hz" if f else "全部不可信")
                + (f" ｜ 响度 {d[0]:.1f}–{d[1]:.1f} dB" if d else "")
                + f" ｜ 语速 {c[0]:.2f}–{c[1]:.2f} 字/秒")
        lines.append("  ⚠️ **响度**是判「吵不吵」的那一维：风格拉高音高不等于"
                     "拉高音量，两个要分开看。")
    lines.append("  ⚠️ 这张表答不了**音色自不自然**——那一项没有仪器，只能听。")
    return lines


def silent_stretches(segments, spoken_of: dict[int, float]) -> list[str]:
    """反过来的那一半：哪几段**空得太久**。

    和 `narration_overruns` 量的是**同一个数**，只是看另一头——余量为负是旁白
    写长了，余量太大是这一段大半时间没人在说话。这个数一直印在
    `mode=narration` 的输出里（「余量 +6.44s」），只是被当成「还很宽裕」读了，
    **没有人把它读成「这里有六秒半的哑场」**。

    所以这一条不要新数据、不要新一趟渲染：`mode=narration` 1 分 45 秒跑完就能
    回答，而它以前只回答一半。

    没有旁白的段不算——那是**故意**留给现场声的（见「有原声的片子：说话时压，
    不说话时放开」），不是忘了写。
    """
    idle: list[str] = []
    for index, seg in enumerate(segments):
        if index not in spoken_of:
            continue                      # 整段没有旁白：留给现场声，故意的
        gap = seg.length - spoken_of[index]
        if gap > MAX_SILENT_GAP:
            idle.append(f"  第 {index + 1} 段：画面 {seg.length:.1f}s，"
                        f"旁白只说了 {spoken_of[index]:.2f}s，"
                        f"**{gap:.2f}s 没人在说话**"
                        f"　「{seg.narration[:24]}…」")
    return idle


# 离线估旁白长度 -----------------------------------------------------------
# CLAUDE.md 里那个「`字数 × 0.23 + 句读 × 0.25 + 0.3`，再留 0.3 秒余量」是拍
# 出来的，而且**错得有方向**：它把长段估得太长（gea-shapovalov 第 5 段 91 字
# 估 21.4s，实测 16.7s），把短段估得太短。照它排段，长段会白白留出五秒空白，
# 短段则要等六分钟的 render 才知道装不下。
#
# 现在的系数是**从已发的成片里拟合出来的**，判据留在 `test_match_reel.py`：
#
#   样本：`specs/reels/*.json` 每一段旁白 × 它自己那份 `voice_NN.words.json`，
#         **按内容认领**（事件文本拼起来必须等于这段旁白去掉标点的样子）——
#         只比个数会被跨次重渲留下的旧文件骗过去，CLAUDE.md 记过这个坑，
#         这一轮真剔掉了 9 段对不上的。剩下 168 段、15 条 spec。
#   口径：闸量的是 **mp3 时长**，而 `words.json` 只到最后一个词末。两者的差
#         从 10 条有 `render.json` 的片子里反解出来（字幕末 − 词末，120 段）：
#         **min +0.800 / 中位 +0.829 / max +0.851**——常数得不像话，就是
#         edge-tts 结尾那段固定静音。它并进了下面的 `SPEECH_TAIL`。
#   拟合：0.1594·字 + 0.4248·句读 + 0.751，取整成下面三个数残差几乎不变。
#
# ⚠️ **这仍然是估，不是闸。** 残差范围 −1.28 ~ **+1.44** 秒，所以它只能回答
# 「估得再乐观也装不下」这一种问题；「差不多刚好」一律要 `--check-narration`
# 拿真 TTS 判。系数是按 `zh-CN-YunxiNeural +6%` 量的，换音色或语速要重量。
_SPEECH_PUNCT = "，。！？、；：—…,.!?;:"
_SPEECH_QUIET = "“”‘’\"'（）()《》「」 \t\n"
SPEECH_PER_CHAR = 0.16
SPEECH_PER_PUNCT = 0.42
SPEECH_TAIL = 0.75
# 实测最坏的一段被低估 1.44s，取整留一点：小于这个数的差额不算数。
SPEECH_EST_ERR = 1.5


def speech_seconds(text: str) -> float:
    """离线估这句话合出来有多长（秒）。不合语音、不联网。

    句读单独计一项是因为**停顿不按字数走**：短句里它占的比例最大——
    「那一年她二十一岁。从那儿到今天，一共两年。」18 个字带 3 个句读，
    实测 4.94 秒，合下来只有 3.6 字/秒，而长段能到 6 字/秒开外。
    """
    body = "".join(c for c in text if c not in _SPEECH_QUIET)
    punct = sum(1 for c in body if c in _SPEECH_PUNCT)
    chars = len(body) - punct
    if not chars and not punct:
        return 0.0
    return chars * SPEECH_PER_CHAR + punct * SPEECH_PER_PUNCT + SPEECH_TAIL


def narration_estimates(segments) -> list[tuple[int, float, float]]:
    """`[(段序号, 估出来的旁白秒数, 余量)]`，只给有旁白的段。"""
    out: list[tuple[int, float, float]] = []
    for index, seg in enumerate(segments):
        if seg.narration.strip():
            secs = speech_seconds(seg.narration)
            out.append((index, secs, seg.length - secs))
    return out


def column_base_style(spec: dict) -> tuple[str, str]:
    """这条片子的**基调**风格，按栏目来；顺带把判断依据打进日志。

    账号所有者 2026-08-04 问「以后所有配音都能自适应情绪么？」——**按文本自动
    判情绪不做**（判错了不吭声，还会把「机器猜的」伪装成「你想清楚了」），
    **按栏目定基调可以做，因为栏目是已知的、情绪不是**。

    ⚠️ **没有 Azure 就没有基调**，而且必须说出来。硬套的话，`tts_one` 会对
    **每一段**抛「这一段要 voice.style，而它只有 Azure 那条路有」——一个本来
    只是「音色朴素一点」的降级会变成整条片子渲不出来。
    """
    column = str(spec.get("column")
                 or (spec.get("cover") or {}).get("eyebrow") or "").strip()
    if not azure_tts.available():
        print(f"[配音] 没有 Azure，栏目「{column or '—'}」不套基调"
              f"（{azure_tts.why_unavailable()}）")
        return "", ""
    style, degree = azure_tts.base_style_for(column)
    if not style:
        print(f"[配音] 栏目「{column or '—'}」没登记基调，逐段按 spec 走"
              f"（已登记：{'、'.join(azure_tts.COLUMN_BASE_STYLE)}）")
    return style, degree


def synthesize(segments: list[Segment], outdir: Path, voice: str, rate: str,
               base_style: str = "", base_degree: str = ""
               ) -> list[tuple[Path, list[dict]]]:
    # 一段解说都没有就别碰 edge-tts——沙箱里根本装不上，而"没有解说的片子"
    # 是个合法的形态（先看画面剪得对不对，再配音）
    if not any(seg.narration.strip() for seg in segments):
        return [(outdir / f"voice_{i:02d}.mp3", []) for i in range(len(segments))]

    if base_style:
        # **两个数一起报**：只说基调是什么，看不出它到底盖住了几段；
        # 只说覆盖了几段，又不知道其余那些是什么调。
        overridden = sum(1 for s in segments if s.narration.strip() and s.voice_style)
        plain = sum(1 for s in segments if s.narration.strip()) - overridden
        print(f"[配音] 基调 {base_style}（styledegree {base_degree or '1.0'}）："
              f"{plain} 段用它，{overridden} 段在 spec 里各自覆盖")

    out: list[tuple[Path, list[dict]]] = []
    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        if not seg.narration.strip():
            out.append((path, []))
            continue
        # **段级永远赢。** 基调只填空位——「王欣瑜那条的第 7 段要 excited」
        # 是编辑判断，不能被一个按栏目算出来的默认值盖掉。
        out.append((path, tts_one(seg.narration, path, voice,
                                  seg.voice_rate or rate,
                                  seg.voice_pitch or "+0Hz",
                                  seg.voice_style or base_style,
                                  # ⚠️ **degree 要跟着 style 一起走。** 段级风格
                                  # 配基调的 degree 是张冠李戴——「excited 但只用
                                  # 五成力」不是任何人想清楚过的东西。
                                  seg.voice_styledegree if seg.voice_style
                                  else base_degree,
                                  seg.voice_lead_pause)))
    return out


def spec_sources(spec: dict) -> dict[str, str]:
    """spec 声明的源片：`{键: url}`。

    单源写 `source_url`（历史写法，全部存量都是它），键是 `""`。
    跨场次的片子写 `sources`，段里用 `"source": "<键>"` 指定取自哪条。

    休伊特那条就是跨两场：17 岁的克鲁兹从资格赛打进正赛、首轮赢下生涯第一场
    ATP 正赛（一条集锦），下一轮遇上他父亲带出来的德米纳尔（另一条集锦）。
    只用后一场，故事少了前半截；只用前一场，没有那个拥抱。
    """
    # **按键在不在判断，不按真假**：`"sources": []` 或 `{}` 是假值，用 `if multi:`
    # 会静静绕过校验、掉进 `spec["source_url"]` 的 KeyError——报错完全不说人话。
    # 自己的冒烟测试抓到的。
    if "sources" in spec:
        multi = spec["sources"]
        if "source_url" in spec:
            raise ReelError("`sources` 和 `source_url` 只能有一个，别两处各写一遍")
        if not isinstance(multi, dict) or not multi:
            raise ReelError(
                f'`sources` 要写成非空的 {{"键": "url"}}，段里用 "source": "键" 引用；'
                f"现在是 {multi!r}")
        return {str(k): str(v) for k, v in multi.items()}
    if "source_url" not in spec:
        raise ReelError('spec 里要有 `source_url`（单源）或 `sources`（多源）')
    return {"": spec["source_url"]}


def check_sources_match(paths: dict[str, Path], spec: dict | None = None) -> None:
    """多源要对得上，不一致就在这儿报，别渲到一半。**两样的严重程度不同：**

    - **尺寸**：裁切窗口按源片宽高算（`resolve_crop`），对不上就是**裁错**。
      没有出路，一律红
    - **帧率**：成片跟**主源**走（`FPS`），别的源会被 `fps=` 重采样。这有代价，
      但代价随内容差得很远：50 → 25 是整齐地隔帧丢，看不出来；30 → 25 是
      六帧丢一帧，**静态说话头几乎无感，回合镜头一眼能看出一顿一顿**

    所以帧率不一致**要在 spec 里显式认领**（`mixed_fps: {源键: 为什么可以}`），
    不认领就红。原来是一律红——那会把「让当事人自己说」这类素材整个挡在门外
    （采访多是 30，赛事集锦多是 25/50）；一律放行又回到「兜底出事的时候不吭声」。
    认领这一步的作用就是**让这个取舍留下判据**，而不是让它悄悄发生。
    """
    if len(paths) < 2:
        return
    seen = {k: (*probe_size(p), resolve_fps(p)[0]) for k, p in paths.items()}
    ref_key = next(iter(seen))
    rw, rh, rf = seen[ref_key]
    rows = "\n  ".join(f"{k or '(主源)'}: {w}×{h} @ {f}"
                       for k, (w, h, f) in seen.items())
    bad_size = [k for k, (w, h, _) in seen.items() if (w, h) != (rw, rh)]
    if bad_size:
        raise ReelError(
            f"这些源片和主源 {ref_key or '(主源)'} 的尺寸对不上，裁切会静默裁错："
            f"{bad_size}\n  " + rows +
            "\n尺寸没有出路——换一条同尺寸的源片。")
    declared = (spec or {}).get("mixed_fps") or {}
    bad_fps = [k for k, (_, _, f) in seen.items() if f != rf and k not in declared]
    if bad_fps:
        raise ReelError(
            f"这些源片的帧率和主源 {ref_key or '(主源)'}（{rf}）不一样：{bad_fps}\n  "
            + rows +
            f"\n成片跟主源走，它们会被重采样到 {rf}——**静态画面（采访、定镜）"
            "几乎无感，回合镜头会一顿一顿**。\n"
            "确实可以接受就在 spec 里认领，并写清为什么：\n"
            '  "mixed_fps": {"' + bad_fps[0] + '": "30 fps；这条只用来放采访的'
            '说话头，重采样看不出来"}')
    for key, why in declared.items():
        if key in seen and seen[key][2] != rf:
            print(f"[fps] {key} 是 {seen[key][2]}，重采样到主源的 {rf}——{why}")


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


def validate_spec(spec: dict) -> list[Segment]:
    """**只看 spec，不碰源片**——所以它能在开跑的第一秒跑完。

    这里拦下来的每一类错，原来都要先付一次 392 MB 的下载才报出来：
    `parse_segments` 排在第 1543 行，而下载在第 1516 行，可它只用 `sources`
    的**键**去校验段落引用（`{s.source} - set(sources)`），一个下载下来的
    文件都不碰。段落字段写错、`inset.corner` 写错、缺字段、贴图路径不存在
    ——四类错误就这么各自值一趟下载。

    今天 eala-fernandez 渲了 3 轮、wang-samsonova 2 轮；最近 30 趟 match-reel
    合计 211 分钟。**把「渲到一半才发现」变成「第 5 秒报错」是这条线上最便宜
    的一笔改动。**

    ⚠️ 只做**形状**校验，两类东西**故意不在这儿**：

    - **环境检查**（`_preflight_cutout` 查这台机器有没有 rembg）——那是「这台
      机器行不行」，不是「这份 spec 对不对」。混进来的话，本地想 dry-run 一下
      spec 就得先装 176 MB 的抠图模型。它留在 `render()` 里，照旧排在下载之前。
    - **要量源片才知道的**（裁切窗口越界、`frame_at` 超出片长）——这里做不了，
      别塞进来假装也提前了。
    """
    urls = spec_sources(spec)
    if not urls:
        raise ReelError("spec 里一个源都没有")
    return parse_segments(spec, urls, next(iter(urls)))


def _check_segments_fit(segments: list[Segment], sources: dict[str, Path]) -> None:
    """段落不许写过源片的末尾。

    **ffmpeg 越界时退出码是 0。** `-ss`/`-t` 指到片尾之后，它安安静静出一个
    比要求短的片段——没有报错、没有警告。而每段旁白是按 `seg.length`（spec 里
    写的长度）算偏移的，所以一旦某段被悄悄截短，**它后面每一句解说和字幕都
    整体错位**，症状是「后半段配音对不上」，人还未必定位得到是哪一段。

    源片时长 `probe_duration` 本来就在 render 里算了五次，却从来没跟段落比过。
    比一次是毫秒级的事，而漏掉一次就是一整轮六分钟的重渲加上人反复回看。

    容差 0.05s：源片时长本身有帧级误差，卡太死会误伤最后一段。

    ⚠️ **除了末段，每一段还要多留 `SEG_FADE` 秒**：溶解的底料是这一段之后的
    自然延续（见 `dissolve_filtergraph`）。取不到那几秒时 ffmpeg 照样退出码 0，
    只是给一段短的，然后 `xfade` 的 offset 落到流的末尾之外——**画面在这个
    接缝上会停住**，而这一整族毛病的共同点就是不吭声。末段不留尾巴，所以它
    仍然可以贴着源片末尾结束。
    """
    durations = {key: probe_duration(path) for key, path in sources.items()}
    over = []
    for index, seg in enumerate(segments):
        limit = durations.get(seg.source)
        need = seg.end + (0.0 if index == len(segments) - 1 else SEG_FADE)
        if limit is None or need <= limit + 0.05:
            continue
        over.append(f"  第 {index + 1} 段：{seg.start:.1f}–{seg.end:.1f}s"
                    f"（溶解还要往后多取 {need - seg.end:.2f}s）"
                    f"，而源片{('（' + seg.source + '）') if seg.source else ''}"
                    f"只有 {limit:.1f}s，超出 {need - limit:.2f}s")
    if over:
        raise ReelError(
            "有段写过了源片的末尾。**ffmpeg 越界不报错，只会悄悄出一段短的**，"
            "于是它后面每一句旁白和字幕都会整体错位：\n"
            + "\n".join(over)
            + "\n\n把 `end` 收回片长以内，或者换一条更长的源片。")


def render(spec: dict, outdir: Path, *, voice: str, rate: str,
           source_override: Path | None = None,
           cover_only: bool = False) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    # **先只看 spec，再看这台机器。** 两样都在下载之前，形状错和缺依赖都
    # 死在第 5 秒，不用等 392 MB 下完。
    validate_spec(spec)
    _preflight_cutout(spec)
    urls = spec_sources(spec)
    sources: dict[str, Path] = {}
    for key, url in urls.items():
        path = outdir / (f"source_{key}.mp4" if key else "source.mp4")
        if key == "" and source_override:
            path = source_override
        if not path.is_file():
            with stage(f"下载源片 {key or '(主源)'}"):
                path = download(url, path)
        sources[key] = path
    check_sources_match(sources, spec)
    primary = next(iter(sources))
    source = sources[primary]
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

    # 多源：几何必须一致，否则一套裁切窗口套在两种画幅上，剪出来一段满一段不满。
    # 这里**宁可报错也不自动缩放**——自动缩放会把「素材选错了」变成一个看不见的
    # 画质问题，而报错能让人当场发现。
    sizes = {name: probe_size(path) for name, path in sources.items()}
    if len(set(sizes.values())) > 1:
        raise ReelError(
            "多条源片的画幅不一致，裁切几何没法共用：\n  "
            + "\n  ".join(f"{n or '(单源)'}: {w}×{h}" for n, (w, h) in sizes.items())
            + "\n换一条同画幅的源片，或者把不一致的那条单独出片。")
    source_w, source_h = sizes[next(iter(sources))]

    # **只出封面就到此为止。** 封面是全流程返工最多的那一屏（CLAUDE.md 里
    # 68 行、10 个专门段落，每段都是一轮返工换来的），而它在完整 render 里
    # **第 63 秒就完成了**，却要等满 6 分钟才看得见（run 30624808733 的时间线：
    # 10:52:54 开跑 → 10:53:57 封面编码完 → 11:00:15 成片）。
    #
    # `build_cover` 不依赖 segments / tracks / TTS / voice——查过，一个都不用。
    # 所以「下载 → 出海报 → 退出」是干净的一条路，约 20 秒的活。
    if cover_only:
        cover = build_cover(sources, primary, spec,
                            outdir / "part_cover.mp4", source_w)
        poster = outdir / POSTER_NAME
        if not poster.is_file():
            raise ReelError(f"封面渲完了却没有 {POSTER_NAME}")
        print(f"[封面预览] {poster}（{poster.stat().st_size / 1024:.0f} KB）\n"
              f"  这一步不出成片。看着对了再跑完整 render。")
        cover.unlink(missing_ok=True)
        return poster

    # **量信号，不量流。** `_has_audio` 只查音频流存不存在，而 wong-brooksby
    # 的源片**有流、有码率、就是没声音**：成片里没有旁白的段落全是数字静音
    # （3 秒一格采样，29 个窗里 12 个低于 −70 dB；其余八条片子 0/23~0/39），
    # 而 spec 的 `_source` 写着「带原声」。整套闪避对它是空转，而两条分支都
    # 不打印，于是「源片是哑的」和「源片正常」在日志上一模一样。
    #
    # ⚠️ **这道闸排在只出封面那条路的后面。** 封面一个音频样本都不碰，
    # 拿「源片是哑的」去拦一次快速预览，等于把这条路的用处废掉——和
    # `_preflight_cutout` 那次是同一个错：别把无关的检查塞进它前面。
    require_live_sound(source, spec)

    # 成片帧率跟着源片走。硬定 30 而源片是 25，就是每 5 帧补一帧，一秒卡五次。
    # 多源时只能有一个输出帧率，取主源的；**别的源和它不一样就要打出来**——
    # 那意味着那几段在重采样，不打出来没人知道画面为什么发涩。
    global FPS, FPS_EXPR
    FPS_EXPR, FPS = resolve_fps(source)
    print(f"源片 {source_w}×{source_h}，{probe_duration(source):.1f}s")
    resolve_crop(source_w, source_h, spec.get("crop_y"))
    portrait = source_w * 4 < source_h * 3

    segments = parse_segments(spec, sources, primary)
    _check_segments_fit(segments, sources)
    # 封面那句先合出来——**封面停多久由它决定**，所以排在渲封面之前。
    cover_voice, cover_marks = synth_cover(spec, outdir, voice, rate)
    cover_secs = cover_length(cover_voice)
    total = sum(s.length for s in segments) + cover_secs
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

    # **TTS 和「旁白比画面长」那道闸排在编码之前。**
    #
    # 它们原来排在分段编码之后（第 115 行 TTS，闸在 141），而 TTS 只要 6 秒、
    # 一个源片像素都不碰。撞一次这道闸，白编的是：封面海报 2.6s + 抠图 8.4s
    # + **分段编码 47s** + 拼接 ≈ 50–60 秒——而这一整趟本来就要 6 分钟，
    # 于是「旁白写长了」这种改一行文案的事，代价是一整轮。
    #
    # 挪到前面之后，同样这条错在**开跑后一分半**就报出来，而且一次把所有
    # 超出的段都列出来（原来就是这么设计的，见下面的注释）。
    with stage("TTS 合成"):
        voices = synthesize(segments, outdir, voice, rate,
                            *column_base_style(spec))

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
    spoken_of, over = narration_overruns(segments, voices)
    if over:
        raise ReelError(
            "有旁白比它那一段的画面长，会和下一段的语音、字幕叠在一起：\n"
            + "\n".join(over)
            + "\n\n两条出路，选一条：把这几段的旁白删短，或者把画面拉长"
              "（`end` 往后挪，但别越过下一段的 `start`）。")

    # **同一个数的另一头：哪几段大半时间没人在说话。** 排在这儿是因为它和上面
    # 那道闸用的是同一批 TTS 时长，一个源片都不用碰——而下面就要开始编码了，
    # 在这之前红掉省的是整趟渲染。
    idle_total = sum(max(0.0, segments[i].length - v) for i, v in spoken_of.items())
    total_secs = sum(seg.length for seg in segments)
    print(f"[查哑场] 没人说话合计 {idle_total:.1f}s / {total_secs:.1f}s"
          f"（{idle_total / total_secs:.0%}），门槛：单段不超过 {MAX_SILENT_GAP}s")
    idle = silent_stretches(segments, spoken_of)
    if idle:
        raise ReelError(
            "有几段大半时间屏幕上没有字——**不是字幕丢了，是没人在说话**：\n"
            + "\n".join(idle)
            + "\n\n两条出路：把这几段的旁白补长（事实从 spec 已有的事实出处里取），"
              "或者把窗口收短（`end` 往前挪）。"
              "\n⚠️ 1~3 秒的空是句子之间正常的换气，别填——门槛卡的是"
              f" {MAX_SILENT_GAP}s 以上的整段哑场。")

    # 跟踪要**先整条镜头跟完再切**，所以排在切片之前统一算（见 track_shots）
    tracks = track_shots(sources, segments, source_w)

    # **每一段都多切 SEG_FADE 秒留给下一个接缝，最后一段不留**——长度账见
    # `dissolve_filtergraph`。多出来的那几秒从来不单独播，它只在溶解里当底。
    lengths = [cover_secs] + [seg.length for seg in segments]
    parts: list[Path] = [build_cover(sources, primary, spec,
                                 outdir / "part_cover.mp4", source_w,
                                 cover_secs, tail=SEG_FADE)]
    for index, seg in enumerate(segments):
        parts.append(cut_segment(sources[seg.source], seg,
                                 outdir / f"part_{index:02d}.mp4",
                                 source_w, tracks.get(index),
                                 tail=0.0 if index == len(segments) - 1
                                 else SEG_FADE))

    silent = outdir / "_video.mp4"
    with stage("拼接"):
        # ⚠️ **这儿不能再 `-c copy`。** 溶解要两段同时在滤镜图里，所以这一趟
        # 是一次真编码——按中间产物的参数走（`ultrafast`/`crf 12`，见
        # 「中间产物要花的是比特，不是时间」），成片那一步照旧 `slow`/`crf 18`。
        #
        # **每一段都要先量一遍再拼。** `cut_segment` 的 `-t` 越界时 ffmpeg
        # 退出码是 0，只给一段短的；而短了之后 `xfade` 的 offset 就落到流的
        # 末尾之外，**整条片子会在那个接缝上截断**——2026-08-02 那两趟就是
        # 这么出来的：段落加起来 114.46s，成片 12.44s，而日志里一个字都没说。
        # 量一遍是毫秒级的事，漏掉一次就是一整轮六分钟。
        measured = [probe_duration(p) for p in parts]
        short = [f"    {p.name} 要 {want:.2f}s，实际只有 {got:.2f}s"
                 for p, want, got, tail in zip(
                     parts, lengths, measured,
                     [SEG_FADE] * (len(parts) - 1) + [0.0])
                 if got + 0.08 < want + tail]
        if short:
            raise ReelError(
                "有分段比要求的短——多半是它后面那 "
                f"{SEG_FADE}s 溶解底料取不到（源片到头了）。"
                "ffmpeg 越界不报错，只给一段短的：\n" + "\n".join(short)
                + "\n\n把这几段的 `end` 往前收几帧，或者换一条更长的源片。")
        proc = run("ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                   *[arg for p in parts for arg in ("-i", str(p))],
                   "-filter_complex", dissolve_filtergraph(lengths, SEG_FADE),
                   "-map", "[vout]", "-map", "[aout]",
                   "-c:v", "libx264", "-preset", PART_PRESET, "-crf", PART_CRF,
                   "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "160k", "-ar", AUDIO_RATE, str(silent))
        # **ffmpeg 成功时说的话也要转出来。** `run()` 把 stderr 吃掉了，
        # 于是滤镜图的抱怨（`xfade` 的 offset 越界这类）一个字都看不见。
        if proc.stderr.strip():
            print("  [拼接] ffmpeg 说：" + proc.stderr.strip()[:1200])
        joined = probe_duration(silent)
        want_total = sum(lengths)
        print(f"  [拼接] {len(parts)} 段溶解成 {joined:.2f}s"
              f"（段落合计 {want_total:.2f}s）")
        if abs(joined - want_total) > 0.35:
            raise ReelError(
                f"拼出来的画面 {joined:.2f}s，而各段加起来是 {want_total:.2f}s。"
                "**溶解把时间轴弄错了**，而旁白和字幕的偏移全按段长累加，"
                "照这样出片后半段会整体错位。\n"
                f"  各段实测：{[round(x, 2) for x in measured]}\n"
                f"  spec 段长：{[round(x, 2) for x in lengths]}")

    # 每段解说落在它那一段的**开头**，字幕跟着同一个偏移
    cues: list[tuple[float, float, str]] = []
    mix_inputs: list[str] = []
    filters: list[str] = []
    # 标签跟着 filters 一起攒，**别在下面另拿一个条件重算一遍**：加封面配音那次
    # 就是这么差点漏的——`names` 原来是从 segments 里重新筛一遍，封面那一路
    # 定义了却没人接。这类「两处各写一遍同一个条件」迟早会分叉。
    voice_labels: list[str] = []
    # 封面这一句从第 0 秒起。**它也要出字幕**——「静音刷是默认状态」，
    # 只给耳朵不给眼睛，等于开场那句话对一半人不存在。
    if cover_voice is not None:
        mix_inputs.extend(["-i", str(cover_voice)])
        filters.append(f"[{len(mix_inputs)//2}:a]adelay=0|0[vcover]")
        voice_labels.append("[vcover]")
        cover_text = str(spec["cover"]["narration"]).strip()
        # **念的就是海报上印的那句，就别再排一行字幕。** 钩子在海报上是几十号的
        # 大字，字幕把同样的话在同一帧里再写一遍，只是把画面弄脏。
        # 判据是「一不一样」，不是「封面一律不出字幕」：封面那句要是**另说了
        # 一件事**（存量里没有，但迟早会有），它照样要有字幕——静音刷是默认状态。
        printed = drop_punctuation(
            str(spec["cover"].get("hook", "")).replace("\n", " "))
        if drop_punctuation(cover_text) == printed:
            print("[封面] 旁白就是海报上那句钩子，不另排字幕")
        else:
            cues.extend(subtitle_cues(readable(cover_text),
                                      probe_duration(cover_voice),
                                      boundaries=cover_marks, offset=0.0))
    offset = cover_secs
    for index, (seg, (path, marks)) in enumerate(zip(segments, voices)):
        if seg.quote:
            # 原声段：没有语音可对齐，按字数等比铺满整段。**行数不能太多**，
            # 否则每行只剩一瞬——一段 12 秒的采访塞 60 字就是这样。
            if seg.quote_cues:
                cues.extend(explicit_quote_cues(seg.quote_cues, seg.length,
                                                offset))
            else:
                cues.extend(subtitle_cues(readable(seg.quote), seg.length,
                                          offset=offset))
        elif seg.narration.strip():
            spoken = spoken_of[index]
            mix_inputs.extend(["-i", str(path)])
            filters.append(
                f"[{len(mix_inputs)//2}:a]adelay={int(offset*1000)}|"
                f"{int(offset*1000)}[v{index}]")
            voice_labels.append(f"[v{index}]")
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
            run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(silent), *mix_inputs,
                "-filter_complex", duck_filtergraph(filters, voice_labels),
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

    for junk in list(outdir.glob("part_*.mp4")) + [silent, mixed,
                                                   outdir / "_concat.txt",
                                                   outdir / "_cover_frame.jpg"]:
        junk.unlink(missing_ok=True)
    # **封面停多久要记下来。** 它现在跟着配音走，光看 spec 算不出来——
    # `check_reel_landed.py` 拿它对片长，没有这份就只能拿常量猜，而猜错的样子
    # 是「片长对不上」，和真出问题长得一模一样。
    # **每段旁白的真实秒数也记下来。** 离线估（`speech_seconds`）的系数就是从
    # 这些数拟合的，而在此之前唯一的出处是 `voice_NN.words.json` 的末事件——
    # 那是**词末**不是 mp3 时长，差着一个 0.83s 的固定尾巴，而且序号在跨次重渲
    # 的目录里会对不上。记在这儿的是闸自己量到的那个数，口径和序号都不用再猜。
    (outdir / "render.json").write_text(json.dumps({
        "cover_seconds": round(cover_secs, 3),
        "cover_narrated": cover_voice is not None,
        "segments_seconds": round(sum(s.length for s in segments), 3),
        "film_seconds": round(probe_duration(final), 3),
        "narration_voice": voice,
        "narration_rate": rate,
        # **哪条路配的音要记进产物**，不能靠「工作流当时配没配 key」去推。
        # `tts_one` 是「Azure 可用就整条片子都走 Azure」，所以同一份 spec、
        # 同一个 voice 名字，在配了 key 之前和之后合出来的**不是同一条音轨**——
        # 而 `narration_voice` 两边一模一样，光看它分不出来。解说片那条线早有
        # `check_explainer_voice.py` 读产物里的 `narration.json` 而不是从工作流
        # 参数推（CLAUDE.md：查产物，不查信号），这条线一直漏着。
        "narration_backend": "azure" if azure_tts.available() else "edge-tts",
        "narration_seconds": {str(i): round(v, 3)
                              for i, v in sorted(spoken_of.items())},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
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
    # **只看源片的一段。** WTA 的单场集锦不是每场都发，Day N 合集才是全覆盖的
    # ——整片扫一遍不但慢，缩略图墙还会出七十多张、绝大多数是别人的比赛。
    # 缩略图上烧的仍是**源片绝对秒数**，spec 里的窗口直接照抄，不用换算。
    p.add_argument("--from", dest="clip_from", default="",
                   help="只看源片的这一段（秒）。合集里取一场时用")
    p.add_argument("--to", dest="clip_to", default="",
                   help="同上，区间的终点（秒）")
    p.add_argument("--scorebox", default="",
                   help="记分条位置 x0,y0,x1,y1（源片像素）。给了就顺手量一遍"
                        "死球时刻写进 probe.json——趁源片还在，渲完就删了")

    r = sub.add_parser("render", help="按 spec 出成片")
    r.add_argument("--spec", required=True)
    r.add_argument("--outdir", required=True)
    r.add_argument("--source", help="已经下好的源片（跳过下载）")
    r.add_argument("--voice", default="zh-CN-YunxiNeural")
    r.add_argument("--rate", default="+6%")
    r.add_argument("--dry-run", action="store_true",
                   help="只校验 spec 的形状，不下载不渲染，秒级返回")
    r.add_argument("--check-narration", action="store_true",
                   help="只合语音、只报哪几段旁白写长了。**不下源片、不渲染、"
                        "不写产物**——已经发过的片子拿它查，不会多出一个成片")
    r.add_argument("--cover-only", action="store_true",
                   help="只出封面海报就停（约 20 秒），用来调 cx/scale/focus/box")

    args = parser.parse_args()
    outdir = Path(args.outdir)

    if args.mode == "probe":
        outdir.mkdir(parents=True, exist_ok=True)
        source = download(args.url, outdir / "source.mp4")
        w, h = probe_size(source)
        duration = probe_duration(source)
        # **帧率要记进 probe.json。** 多源那条线上，`check_sources_match` 拿
        # 尺寸和帧率一起判，对不上就红——而 probe 之前只报尺寸，于是「这条源
        # 能不能和已有的那条一起剪」要等到 render 跑六分钟之后才知道。
        # 探测的作用就是把这种问题提前，别让它藏到最后一步。
        fps_expr, fps = resolve_fps(source)
        # **只看一段。** WTA 的单场集锦不是每场都发，**Day N 合集才是全覆盖的**
        # ——王欣瑜对卡萨金娜那场就只在 61 分钟的 Day 2 合集里（章节
        # `2371–2553  X. Wang Vs. D. Kasatkina`）。整片扫一遍不但慢，缩略图墙
        # 还会出七十多张、绝大多数是别人的比赛，挑段等于大海捞针。
        clip_from = float(args.clip_from or 0.0)
        clip_to = float(args.clip_to) if args.clip_to else None
        if clip_from or clip_to is not None:
            print(f"[区间] 只看 {clip_from:.1f}–"
                  f"{(clip_to if clip_to is not None else duration):.1f}s"
                  "（缩略图上烧的仍是源片绝对秒数）")
        cuts = scene_changes(source, start=clip_from, stop=clip_to)
        # **低门槛那一份也趁源片还在的时候量。** 和死球时刻同一个道理：源片
        # 渲完就删，事后想查得自己再下一份几百 MB。
        loose = [t for t in scene_changes(source, LOOSE_CUT_THRESHOLD,
                                          start=clip_from, stop=clip_to)
                 if all(abs(t - c) > 0.05 for c in cuts)]
        print(f"源片 {w}×{h} @ {fps_expr}，{duration:.1f}s，检出 {len(cuts)} 个切点"
              f"，另有 {len(loose)} 个疑似切点（门槛 {LOOSE_CUT_THRESHOLD}）")
        if loose:
            print("  疑似切点（**线索不是判据**：落在你要取的窗口里就去缩略图墙"
                  "上看一眼，别直接拿它当切点）：\n    "
                  + " ".join(f"{t:.2f}" for t in loose))
        sheets = contact_sheet(source, outdir, every=args.every,
                               start=clip_from, stop=clip_to)
        # 记分条单独拼一版，否则整幅缩完读不出比分。位置按源片分辨率推：
        # 转播把记分条烧在左下，取左边 42%、底部往上 20% 那一块。
        w, h = probe_size(source)
        box = f"{w * 42 // 100}:{h * 20 // 100}:0:{h * 78 // 100}"
        sheets += contact_sheet(source, outdir, every=args.every,
                                crop=box, prefix="score", columns=4,
                                tile_w=520, start=clip_from, stop=clip_to)
        print(f"记分条缩略图墙：crop={box}（源片 {w}x{h}）")
        captions = fetch_captions(args.url, outdir)
        # **死球时刻要在源片还在的时候量。** `find_point_ends.py` 一直没有任何
        # 调用方，而它的 `--video` 指的是源片——源片渲完就删（清理那一步），
        # 于是想用它得自己另下一份。结果是段尾切错只能靠人在 2 秒一格的缩略图
        # 墙上看，wong-brooksby 那三处修正（`128.0→132.7`、`143.0→147.7`、
        # `173.0` 正好切在赛点那一分中间）每一处都先付了一趟渲染才发现。
        #
        # 记分条的位置**没法自动认**（每家转播不一样），所以要人给 `--scorebox`；
        # 不给就跳过，**而且要说为什么**——「没量」和「量出来是空的」长得一样。
        ends = point_end_candidates(source, args.scorebox)
        (outdir / "probe.json").write_text(json.dumps({
            "url": args.url, "width": w, "height": h, "duration": duration,
            "fps": fps_expr, "fps_value": round(fps, 3),
            "scene_cuts": cuts, "scene_cuts_loose": loose, "point_ends": ends,
            # 只看了一段就记下来——**下一个人拿 probe.json 排窗口时，
            # 「切点少」和「只扫了一段」长得一模一样**。
            "clip_from": clip_from or None,
            "clip_to": clip_to,
            "sheets": [s.name for s in sheets],
            "captions": captions.name if captions else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("缩略图墙:", ", ".join(s.name for s in sheets))
        return 0

    spec = load_spec(Path(args.spec))
    if args.check_narration:
        # **一个源片字节都不碰。** 这道闸比的是「TTS 时长 vs spec 里的段长」，
        # 两样都不需要源片；而跑一趟 render 去问同一个问题，在通过的情况下会
        # 顺手渲出一条新成片并提交——对已经发过的片子就是白多一个 blob。
        # 语音落**临时目录**，`output/` 一个字节都不动。
        import tempfile  # noqa: PLC0415

        segments = validate_spec(spec)
        with tempfile.TemporaryDirectory() as tmp:
            voices = synthesize(segments, Path(tmp), args.voice, args.rate,
                                *column_base_style(spec))
            spoken, over = narration_overruns(segments, voices)
            splits = _word_splits(spec, segments, voices)
            # ⚠️ **必须在这个 `with` 里量。** 语音只在临时目录里活着，出了这个
            # 块就被删——第一版印在外面，十一段全报「文件不在」（run 30901516117）。
            # 和 `_word_splits` 一样：里面算，外面印。
            prosody = prosody_report(segments, voices, spoken)
        total = sum(s.length for s in segments)
        print(f"[查旁白] {len(spoken)} 段有旁白，画面共 {total:.1f}s"
              f"（音色 {args.voice} {args.rate}）")
        for index, secs in sorted(spoken.items()):
            room = segments[index].length - secs
            flag = ("超出" if room < -0.12 else "很紧" if room < 0.3
                    else "**哑场**" if room > MAX_SILENT_GAP else "")
            print(f"  第 {index + 1:>2d} 段 画面 {segments[index].length:5.1f}s "
                  f"旁白 {secs:5.2f}s 余量 {room:+5.2f}s {flag}")
        # **同一个数的另一头也要报。** 余量为负是旁白写长了，余量太大是这一段
        # 大半时间没人在说话——这个数一直印在上面那一行里，只是从来没人把它
        # 读成「哑场」。整片的占比也印出来：只在超标时出声的检查证明不了它看过。
        idle_total = sum(max(0.0, segments[i].length - v) for i, v in spoken.items())
        idle = silent_stretches(segments, spoken)
        print(f"\n[查哑场] 没人说话合计 {idle_total:.1f}s / {total:.1f}s"
              f"（{idle_total / total:.0%}），单段最长 "
              f"{max((segments[i].length - v for i, v in spoken.items()), default=0):.2f}s"
              f"（门槛 {MAX_SILENT_GAP}s）")
        if idle:
            print("\n以下几段大半时间屏幕上没有字——不是字幕丢了，是没人在说话：")
            print("\n".join(idle))
            print("\n两条出路：把这几段的旁白补长（事实从 spec 的事实出处里取），"
                  "或者把窗口收短（`end` 往前挪）。"
                  "\n⚠️ 1~3 秒的空是句子之间正常的换气，别填。")
        if over:
            print("\n以下几段会和下一段的语音、字幕叠在一起：")
            print("\n".join(over))
            print("\n两条出路：把这几段的旁白删短，或者把画面拉长"
                  "（`end` 往后挪，但别越过下一段的 `start`）。")
        _print_word_splits(splits)
        # **风格做出来没有、有没有做过头**，报在这儿——语音还在临时目录里，
        # 这一刻是唯一能干净量到它的时候（成片混了现场声，量出来不可信）。
        print("\n".join(prosody))
        if over or idle:
            return 1
        print("\n[查旁白] 每段都装得下、也没有哑场，这条 spec 渲得过这道闸。")
        return 0

    if args.dry_run:
        segments = validate_spec(spec)
        total = sum(s.length for s in segments)
        print(f"[dry-run] spec 形状没问题：{len(segments)} 段，画面共 {total:.1f}s")
        print("  ⚠️ 只校验了形状。裁切越界、frame_at 超出片长这类要等源片，"
              "这里查不了。")
        # **旁白写长了不用等 render，也不用等 TTS。** 这一条离线估，误差
        # ±1.5s（见 `speech_seconds` 的推导），所以只判「估得再乐观也装不下」；
        # 剩下的交给 `--check-narration` 拿真语音量。
        est = narration_estimates(segments)
        if est:
            print(f"\n[估旁白] {len(est)} 段有旁白（离线估，误差 ±"
                  f"{SPEECH_EST_ERR}s）")
            for index, secs, room in est:
                flag = ("← 估得再乐观也装不下" if room < -SPEECH_EST_ERR
                        else ("← 悬，跑一次 mode=narration"
                              if room < SPEECH_EST_ERR
                              else ("← **哑场**，这一段大半时间没人说话"
                                    if room > MAX_SILENT_GAP else
                                    ("← 偏空，悬" if room > MAX_SILENT_GAP
                                     - SPEECH_EST_ERR else ""))))
                print(f"  第 {index + 1:>2d} 段 画面 "
                      f"{segments[index].length:5.1f}s 估旁白 {secs:5.2f}s "
                      f"余量 {room:+5.2f}s {flag}")
            sure = [i for i, _s, room in est if room < -SPEECH_EST_ERR]
            tight = [i for i, _s, room in est
                     if -SPEECH_EST_ERR <= room < SPEECH_EST_ERR]
            # **余量是同一个数的两头，这条离线估原来只看了一头。**
            # `eala-pegula-final` 第 6 段 dry-run 报「余量 +4.71s」——那一行
            # 我读成了「装得下，很好」，六分钟之后 render 里那道哑场闸才红：
            # 「画面 13.1s，旁白只说了 8.83s，4.27s 没人在说话」。
            # **它一直印在那儿，只是没被读成「太空」。**
            # ⚠️ **这儿拿点估值直接跟门槛比，不减误差带子。** 第一版我写的是
            # `room - SPEECH_EST_ERR > MAX_SILENT_GAP`（「估得再保守也超」），
            # 那要 room > 5.5s 才报——而真闸红在 4.27s，照样漏。
            # 离线估的**中位误差贴近 0**（`test_离线估旁白长度要对得上真产物`
            # 钉着这一条），所以点估值就是最好的猜测，和真闸同一个口径；
            # 落在 `门槛 ± 误差` 里的标「偏空，悬」，让人去跑 mode=narration。
            #
            # ⚠️ **只警告，不 `return 1`。** 第一版让它红，当场把已发的
            # `gea-shapovalov`（18 段）也判红了——那条片子当年是过了真闸的。
            # 真闸用**真语音**，离线估在这一头偏保守（本例估 4.71s、实测
            # 4.27s），拿它当硬闸会把一批好 spec 挡在门外，而**一条常年红的
            # 检查和没有检查是同一个毛病**。它的职责是让人早点看见，不是拍板。
            idle = [i for i, _s, room in est if room > MAX_SILENT_GAP]
            if idle:
                print(f"\n第 {[i + 1 for i in idle]} 段**估出来就是哑场**"
                      f"（单段门槛 {MAX_SILENT_GAP}s，估的误差 ±{SPEECH_EST_ERR}s）："
                      "render 里那道闸**可能**会红——它用真语音量，"
                      "离线估在这一头偏保守。先跑一次 mode=narration。\n"
                      "两条出路：把旁白补长（事实从 spec 已有的事实出处里取），"
                      "或者把窗口收短（`end` 往前挪）。")
            if sure:
                print(f"\n第 {[i + 1 for i in sure]} 段一定装不下：这几段删短，"
                      "或者把画面拉长（`end` 往后挪，别越过下一段的 `start`）。")
                return 1
            if tight:
                print(f"\n第 {[i + 1 for i in tight]} 段落在估算的误差里，"
                      "**这条离线估判不了**。开跑之前用真语音量一次：\n"
                      "  match-reel 工作流 mode=narration"
                      "（或本地 `render --check-narration`，要能联网）")
            else:
                print("\n[估旁白] 每段都留着一个误差以上的余量，估得再保守也装得下。")
        return 0

    render(spec, outdir,
           voice=args.voice, rate=args.rate,
           source_override=Path(args.source) if args.source else None,
           cover_only=args.cover_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
