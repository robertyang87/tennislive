#!/usr/bin/env python3
"""「赛场之上」的固定海报：两位球员 + VS，一眼抓住。

这一屏是唯一决定人点不点的画面，所以版式定死、每次只换素材，不再现搓：

- **两个人必须同框**。这个栏目讲的是一场对决，封面只放一个人就少了一半
- **名字要大**。只有两张脸的 VS 卡等于让人猜这是谁打谁——中文名是这条片子
  在信息流里唯一能被扫到的东西
- **一句钩子压在下三分之一**，上面留给人脸
- 台头、比分、赛事轮次各有固定位置，换片子只换字

四种版式，`layout` 选：

    cutout    **默认，也是账号所有者定下来的那一版**。背景从本场比赛视频截取
              底线全场机位（虚化压暗），两个人用官方抠图站在品牌绿斜线上
    diagonal  斜切。两格各一张实拍，中缝一道品牌绿
    split     上下平分，中缝压一个 VS 圆牌
    stack     上下平分但名字压在各自那一格里，比分居中

**为什么默认换成 `cutout`**：`diagonal` 要两张「本场、比赛中、有冲击力、够清晰」
的实拍，四道闸门同时过——王欣瑜那条折腾了十几轮，因为帕雷哈（17 岁资格赛球员）
根本没有一张能用的比赛照，最后只能拿握手那一帧顶，结果**王欣瑜在同一张海报上
出现了两次**、帕雷哈的脸还是糊的、两个名字压在中缝上谁是谁都说不清。

抠图这条路把「认人」这件事一次性解决掉。人物有两个来源，**首选本场抽帧**：

- **本场抽帧（首选）**：从这场球的源片里挑一帧近景抠出来。衣服、光、球场都是
  这一场的。账号所有者的原话：「因为更贴近比赛的服装，感觉会更好，用之前资料
  就有点脱节」。挑帧判据是三条——**正脸或稍微侧脸、上半身直立、表情读得出**，
  收在 `tools/pick_cover_frames.py`；spec 里写
  `versus.top = {"frame_at": 142.4, "box": [x0,y0,x1,y1]}`
- **WTA 官方棚拍（兜底）**：`api.wtatennis.com/tennis/players/?name=<姓>` 查 ID，
  抠图在 `photoresources.wtatennis.com/.../<Name>-Torso_<wta_id>.png?width=3000`，
  3000×2813 透明底。**文件名自带 WTA ID，人物这一要素由来源自己写死**
- **ATP 官方棚拍（兜底）**：总站 403，但赛事自己的域名镜像着同一批
  `/-/media/alias/player-gladiator-image/<atp_id>`，379×603 全身抠图。
  尺寸是 alias 定死的（`?w=` 无效）

**棚拍图是全套素材里最软的一档**，这个能量（槽位 634px 高）：ATP 那张裁到胯
只有 265×410，铺上去是 **1.55× 放大**；同一场源片抓的近景 660×1040，
**0.61× 缩小**。看着"正规"，实际更糊。

素材：`cutout` 版式每格给 `cutout`（透明 PNG），原始 spec 的背景给
`versus.background = {frame_at, shot: "wide_court"}`；渲染管线会从本场源片
抽帧并在调用本模块前换成本地 `image`。`diagonal` 等版式每格给 `image`，可调
`focus` / `focus_y` / `zoom`——铺满不等于人够大。

    python tools/versus_poster.py --spec specs/reels/wang-pareja.json \\
        --layout cutout --out /tmp/poster.jpg
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.render.webcards import _font_css  # noqa: E402
from tennislive.video.explainer import _data_uri  # noqa: E402

# **海报和成片同一个画幅：3:4（1080×1440）。**
# 小红书的视频静态展示就是 3:4——9:16 的海报在信息流里被裁掉上下两条，
# 台头、比分、赛事行首当其冲，而那几行正是让人看懂这是哪一场的东西。
# 画幅本身定成 3:4，就不用再留什么「安全区」，整张海报都露得出来。
VIDEO_W, VIDEO_H = 1080, 1440
BRAND = "#c6f65a"          # 品牌绿
INK = "#04120d"            # 深底
TEXT = "#f4fbf7"
DIM = "#9fb4aa"


SEAM_ANGLE = 7.4           # 中缝那条绿线的倾角（度）
# 斜切带的半高，**从倾角推出来，不是另拍一个数**。画布 1080 宽，斜线从中点到
# 一端升 540·tan(7.4°)=70px，占 1440 高的 4.87%。原来这里写死 7%——比画出来的
# 那条线更陡，于是两张照片的交界和绿线**对不上**，而且下格被多切掉一条，
# 伊埃拉的头正好卡在那一条里。两个数必须同源。
BAND = 100.0 * (VIDEO_W / 2) * math.tan(math.radians(SEAM_ANGLE)) / VIDEO_H

# ── cutout 版式的几个数，都是按画幅算出来的，不是拍的 ────────────────────
# 斜线（＝两个人站的那条地平线）把画面分成「上面留给脸」和「下面留给字」。
# 0.60 那一版**下面的文案看着被挤压**：钩子块 `bottom:150px` 起算，两行 100px
# 的钩子 + 比分 + 赛事约 348px 高，顶边落在 942；斜线 864 加名字半高 35 到 899，
# 中间只剩 43px。提到 0.545 之后是 785 → 817，留出 125px，字才透得过气。
# 人物跟着一起上去（底边永远收在斜线上方），所以要同时缩一点，否则头顶会钻进
# 左上角那块台头。
CUT_SEAM = 0.545
CUT_SCALE = 0.44           # 抠图高度占画幅的比例 → 634px
CUT_CX = (0.29, 0.71)      # 左右两人的横向中心
CUT_VS_Y = 0.40            # VS 圆压在两人胸口高度，不在脚下
# 抠图的底边**收在斜线上方**，不压过去。
# 第一版是沉到线下 40px、想让线横过小腿，渲出来是**线从胯部穿过去，像在切人**；
# 而且名字压在斜线上，正好落在两个人身上，白字盖白衣看不清。收到线上方之后，
# 线下那一条是干净的暗底，名字才有地方待。
CUT_SINK = -36
# 半身抠图截在腰上，硬边一眼看得出来，所以底部这一段淡出去。
CUT_FADE = "mask-image:linear-gradient(180deg,#000 80%,transparent 99%)"


def _cut_crop(image: Path, box) -> Path:
    """抠图的裁切，**走 PNG 保住透明通道**——不能用 `_precrop`，那个存 JPEG。

    存在的理由是两家给的画幅不一样：WTA 是**半身**（`<Name>-Torso_<id>.png`），
    ATP 是**全身**（`player-gladiator-image`）。同一个 662px 的槽位里，全身的
    那张脸会小掉四成——而这张海报的全部作用就是让人一眼认出是谁打谁。
    所以 ATP 那两格要 `crop: [0, 0, 1, 0.68]` 裁到胯，脸的大小才对得上。

    代价照实记：ATP 原图去掉透明边只有 256×584，裁到 68% 再铺到 662px 是
    1.67 倍放大，比 WTA 那边软一档。
    """
    if not box:
        return image
    from PIL import Image  # noqa: PLC0415

    if len(box) != 4:
        raise SystemExit(f"cutout 的 crop 要四个数 [x0,y0,x1,y1]（0~1）：{box}")
    im = Image.open(image).convert("RGBA")
    w, h = im.size
    x0, y0, x1, y1 = box
    out = image.with_suffix(".crop.png")
    im.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))).save(out)
    return out


def _cutout_geometry(cx: float, seam: float) -> float:
    """抠图底边落在斜线上的位置（px）。

    线是 `rotate(-7.4deg)`：**左端低、右端高**，所以两个人的脚不在同一水平线上。
    按各自的横向中心去算，人才像真的站在这条线上；两边都用同一个 y，
    右边那个就会浮起来 62px（1080 宽两端差 2·540·tan7.4° = 140px）。
    """
    dx = (cx - 0.5) * VIDEO_W
    return seam * VIDEO_H - dx * math.tan(math.radians(SEAM_ANGLE))


def _cutout_body(cover: dict, versus: dict, names: list) -> tuple[str, str]:
    """cutout 版式：背景是本场视频的全场机位，两个官方抠图站在斜线上。"""
    bg = versus.get("background") or {}
    if not bg.get("image"):
        raise SystemExit(
            "cutout 版式渲染前要把本场视频的 `frame_at` 全场机位抽成 "
            "versus.background.image；不要用场馆资料图或通用球场图。")
    seam = float(versus.get("split", CUT_SEAM))
    vs_y = float(versus.get("vs_y", CUT_VS_Y)) * 100
    css = [
        f".bg{{background-image:url('{_data_uri(Path(bg['image']))}');"
        f"background-size:cover;background-position:"
        f"{float(bg.get('focus', 0.5)) * 100:.1f}% "
        f"{float(bg.get('focus_y', 0.5)) * 100:.1f}%;"
        # scale 给模糊留溢出量，否则四边透底
        # blur 22 + dim .5 渲出来是一片黑绿，**完全看不出是个球场**——背景的
        # 全部作用就是给棚拍抠图一个「这是一场球」的语境，糊到认不出等于没有。
        # 12 / .72 是渲了三档比出来的：dim .88 又太亮，场地线和看台开始跟人抢。
        f"filter:blur({float(bg.get('blur', 12)):.0f}px) "
        f"brightness({float(bg.get('dim', 0.72)):.2f});transform:scale(1.1)}}"
    ]
    imgs = []
    for side, key, cx0 in (("a", "top", CUT_CX[0]), ("b", "bottom", CUT_CX[1])):
        panel = versus[key]
        if not panel.get("cutout"):
            raise SystemExit(
                f"cutout 版式的 {key} 格要 `cutout`：一张透明 PNG。\n"
                "首选本场抽帧（spec 里写 frame_at + box，由 build_match_reel 抠好"
                "再传进来）；拿不到再退官方棚拍：\n"
                "WTA 走 photoresources 的 <Name>-Torso_<wta_id>.png?width=3000，"
                "ATP 走赛事域名的 /-/media/alias/player-gladiator-image/<atp_id>。\n"
                "**这个球员根本没有官方抠图，就退回 `layout: diagonal` 的照片版**"
                "（账号所有者定的兜底）——别拿头像凑：头像只到锁骨，贴进这个"
                "版式里头身比对不上，要让两颗头一样大得把它压到 0.16 倍，"
                "成了一颗没有身子的浮头，而且头像本身是方图、三边硬边。")
        cx = float(panel.get("cx", cx0))
        h = float(panel.get("scale", CUT_SCALE)) * VIDEO_H
        src = _cut_crop(Path(panel["cutout"]), panel.get("crop"))
        sink = float(versus.get("sink", CUT_SINK)) + float(panel.get("dy", 0))
        bottom = _cutout_geometry(cx, seam) + sink
        css.append(f".c-{side}{{left:{cx * 100:.2f}%;top:{bottom - h:.0f}px;"
                   f"height:{h:.0f}px}}")
        imgs.append(f'<img class="cut c-{side}" src="{_data_uri(src)}">')
    body = (f'<div class="bg"></div><div class="shade cutshade"></div>{"".join(imgs)}'
            f'<div class="seam" style="top:{seam * 100:.1f}%"></div>'
            f'<div class="nm" style="top:{seam * 100:.1f}%">'
            f'<span>{names[0]}</span><i></i><span>{names[1]}</span></div>'
            f'<div class="vs" style="top:{vs_y:.1f}%">VS</div>')
    extra = ("".join(css) + """
.bg{position:absolute;inset:0;background-repeat:no-repeat}
/* `.shade` 那一档是给实拍海报调的（52% 起就压到 .96），压在**已经调暗过**的
   背景上就是一片纯黑——渲出来完全看不出人站在球场上。cutout 这一档把中段
   放开，只在斜线以下压住，给钩子一个能读的底。 */
.cutshade{background:linear-gradient(180deg,
  rgba(4,18,13,.34) 0%,rgba(4,18,13,.06) 24%,rgba(4,18,13,.06) 50%,
  rgba(4,18,13,.70) 64%,rgba(4,18,13,.94) 78%)}
.cut{position:absolute;transform:translateX(-50%);z-index:3;
  filter:drop-shadow(0 18px 40px rgba(0,0,0,.55));""" + CUT_FADE + "}")
    return body, extra


def _solo_body(cover: dict) -> tuple[str, str]:
    """`solo`：**「网球有故事」的封面版式**——照片铺满整幅，钩子压在正中。

    这不是我另拟的一套。这个栏目在知识贴／解说片那条线上早就有固定封面
    （`src/tennislive/video/explainer.py` 的 cover 屏、`webcards.py` 的
    `knowledge-cover`），账号所有者 2026-07-31 指出剪辑线这版**不是那个版式**。
    所以照着搬：同一个 1080×1440 画幅、同一条顶部彩条、同一组品牌行、
    同一颗品牌绿药丸、同一档标题字号和阴影。

    和「赛场之上」的 VS 海报的差别只在讲什么：

    - 赛场之上讲一**场对决** → 两格 + 中缝 + VS 圆牌 + 两个名字 + 赛果行
    - 网球有故事讲一**个人** → 一张照片铺满 + 一颗药丸 + 一句钩子，
      **底下什么都不加**

    ⚠️ 三条硬约定，都是账号所有者当场指出来的：

    1. **底下那一行去掉**。原来印着「ATP 500 · 17 岁 · 2026 华盛顿」——
       赛果那一行本来就该去（它是最后一拍），级别／年龄／赛事这三颗药丸
       同样不属于这个栏目的封面：知识贴那十三条封面上一颗都没有
    2. **照片铺满，不留垫层**（`background-size:cover`）。上一版走
       `fit: width` + 上下垫模糊，等于把 3:4 的画幅让掉一半
    3. **要全身、要看得见球场**。铺满意味着 16:9 的横素材横向只剩中间
       42%，所以素材本身必须是竖着能站住的一张——半身特写铺满就是一张脸

    ⚠️ **赛场之上仍然只能用 VS 模板**，判据在 test_封面只有海报模板一条路。
    """
    art = cover.get("portrait") or {}
    if not art.get("image"):
        raise SystemExit(
            "solo 版式要 `cover.portrait.image`：这条片子主角的一张实拍。\n"
            "四道闸门照旧（时间地点人物对得上 / 在比赛中 / 有冲击力 / 够清晰）；"
            "四类源都拿不到本场的，就从本场源片抓一帧（portrait.frame_at）。\n"
            "**要全身、要看得见是球场**——照片铺满整幅，半身特写铺满就是一张脸。")
    src = _precrop(Path(art["image"]), art)
    uri = _data_uri(src)
    focus = float(art.get("focus", 0.5)) * 100
    focus_y = float(art.get("focus_y", 0.5)) * 100
    zoom = float(art.get("zoom", 1.0)) * 100
    # **上下叠一张的变体**：`cover.portrait_above` 有图时，画幅分成两格，
    # 上格是另一个人、下格是主角，中间一道品牌绿。
    #
    # 这是给「这条片子讲的就是两个人做同一件事」用的——休伊特那条的父子同一个
    # 庆祝动作。Tennis TV 自己发过同一个构图（标题 THE HEWITT CELEBRATION），
    # 那张**不能直接用**（带他们的台标和横幅，把别人的包装摆在我们台头下面），
    # 但构图是对的：**上下并排比左右并排好**，因为竖版画幅本来就是上下长。
    #
    # 和「赛场之上」的 VS 海报不是一回事：VS 讲的是两个人**对打**，这里讲的是
    # 两个人**做同一件事**，所以没有中缝斜切、没有 VS 圆牌、没有两个名字并列，
    # 只有一道平直的分界线。
    #
    # **两格都不挂名条**（账号所有者 2026-07-31：「这里名字没必要」）。理由站得住：
    # 台头那行已经写着「十七岁的休伊特，和那个没有名字的动作」，钩子写着
    # 「他做了父亲的那个动作」——谁是父亲、谁是儿子，字已经说完了，名条只是
    # 在两张脸上各压一块黑。
    above = cover.get("portrait_above") or {}
    icon = Path("assets/logo/brand/icon.png")
    icon_html = (f'<img class="brand-icon" src="{_data_uri(icon)}" alt="">'
                 if icon.is_file() else "")
    topic = str(cover.get("topic", "")).strip()
    lines = [ln.strip() for ln in str(cover.get("hook", "")).split("\n") if ln.strip()]
    hook = "".join(f"<div>{html.escape(ln)}</div>" for ln in lines)
    # 标题字号按**最长那一行**算，别写死。左右各留 70px，可用 940px；一个汉字
    # 约占一个字号的宽，写死 96px 时 10 个字就是 960px——**顶出去自动折行**，
    # 而钩子本来已经手写好了断行，再折一次就多出一个孤行。
    title_px = min(96, int(940 / max((len(ln) for ln in lines), default=1)))
    column = html.escape(str(cover.get("eyebrow", "网球有故事")))
    if above:
        if not above.get("image"):
            raise SystemExit("portrait_above 要 `image`：上格那个人的一张实拍。")
        asrc = _precrop(Path(above["image"]), above)
        split = float(cover.get("split", 0.47)) * 100
        hero = (f'<div class="hero hero-a"></div><div class="hero hero-b"></div>'
                f'<div class="hseam" style="top:{split:.1f}%"></div>')
        stack_css = (
            f".hero-a{{bottom:{100 - split:.1f}%;"
            f"background-image:url('{_data_uri(asrc)}');background-size:cover;"
            f"background-position:{float(above.get('focus', .5)) * 100:.1f}% "
            f"{float(above.get('focus_y', .5)) * 100:.1f}%}}"
            f"\n.hero-b{{top:{split:.1f}%;"
            f"background-image:url('{uri}');background-size:cover;"
            f"background-position:{focus:.1f}% {focus_y:.1f}%}}")
    else:
        hero = '<div class="hero"></div>'
        stack_css = ""
    body = (
        f'{hero}<div class="scrim"></div><div class="bar"></div>'
        f'<div class="head"><div class="brandwrap">{icon_html}'
        f'<div class="brandlines"><span class="brand">网球时差 · {column}</span>'
        + (f'<span class="topic">{html.escape(topic)}</span>' if topic else "")
        + f'</div></div></div>'
        f'<div class="storycopy"><span class="kicker">{column}</span>'
        f'<div class="storytitle">{hook}</div></div>')
    solo_bg = "" if above else (
        f"background-image:url('{uri}');background-size:cover;"
        + (f"background-size:auto {zoom:.1f}%;" if zoom != 100 else "")
        + f"background-position:{focus:.1f}% {focus_y:.1f}%")
    extra = (
        # 照片铺满。`zoom` 留着给「人在画面里太小」的素材再推一档，默认 1.0。
        f".hero{{position:absolute;inset:0;background-repeat:no-repeat;"
        f"{solo_bg}}}" + stack_css
        # 下面这几档全部照抄解说片的 cover 屏，一个数都没动——两条线出去的
        # 封面必须是同一个样子，各调各的就会慢慢漂开。
        + """
.scrim{position:absolute;inset:0;background:
 linear-gradient(180deg,rgba(6,28,20,.62) 0%,rgba(6,28,20,.16) 17%,
  rgba(6,28,20,.08) 32%,rgba(6,28,20,.08) 66%,rgba(6,28,20,.22) 84%,
  rgba(6,28,20,.58) 100%),
 radial-gradient(128% 40% at 50% 50%,rgba(6,28,20,.58) 0%,
  rgba(6,28,20,.30) 58%,rgba(6,28,20,0) 100%)}
.bar{position:absolute;top:0;left:0;right:0;height:12px;z-index:5;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%)}
.head{position:absolute;top:44px;left:70px;right:70px;z-index:5;display:flex;
 align-items:center;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.brandwrap{display:flex;align-items:center;gap:14px}
.brandlines{display:flex;flex-direction:column;gap:2px}
.brand-icon{width:52px;height:52px;object-fit:contain;
 filter:drop-shadow(0 2px 8px rgba(0,0,0,.55))}
.brand{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;
 font-weight:400;letter-spacing:1px;color:#f4fbf7}
.topic{font-family:'TL Sans SC',sans-serif;font-size:27px;font-weight:700;
 color:#dcefe4;letter-spacing:1px;
 text-shadow:0 2px 10px rgba(0,0,0,.9),0 0 24px rgba(6,28,20,.8)}
.storycopy{position:absolute;left:70px;right:70px;top:50%;
 transform:translateY(-50%);z-index:5;display:flex;flex-direction:column;
 gap:34px;align-items:flex-start}
.hseam{position:absolute;left:0;right:0;height:6px;background:#c6f65a;z-index:4;
 transform:translateY(-50%);box-shadow:0 0 26px rgba(0,0,0,.55)}
.kicker{align-self:flex-start;background:#c6f65a;color:#062018;font-size:30px;
 font-weight:800;letter-spacing:4px;padding:11px 26px;border-radius:999px}
.storytitle{font-family:'TL Display SC','TL Sans SC',sans-serif;
 line-height:1.24;font-weight:400;color:#f4fbf7;white-space:nowrap;
 text-shadow:0 2px 6px rgba(0,0,0,.9),0 6px 30px rgba(0,0,0,.85),
 0 0 60px rgba(6,28,20,.7)}
"""
        + f".storytitle{{font-size:{title_px}px}}"
        # 上下叠一张时文案压到底部——**居中会正好骑在分界线上**，把上格的下半
        # 和下格的上半（那只搭在眉骨上的手，正是这条片子的落点）一起盖住。
        # 追加在最后，同特异性下后写的赢。
        + (".storycopy{top:auto;bottom:96px;transform:none;gap:26px}"
           if above else ""))
    return body, extra


def _precrop(image: Path, panel: dict) -> Path:
    """`crop: [x0, y0, x1, y1]`（0~1 的比例）——**先裁再铺**。

    `focus` / `zoom` 只能在整幅图里挪窗口，挪不动主体在图里的位置。照片可以
    自己先裁好再入库（伊埃拉那张就是裁到右边六成六处，给钩子让出空场），
    但**从源片抓的帧没有这一步**：转播机位怎么拍就是怎么拍，近景天然居中，
    落到底格就正好被文案块压住；换大全景又小得看不清。

    所以给面板一个裁切框，照片和抽帧共用。裁完的图落在原图旁边，
    带 `.crop.jpg` 后缀——渲染的中间物，不进仓库。
    """
    box = panel.get("crop")
    if not box:
        return image
    from PIL import Image, ImageOps  # noqa: PLC0415

    if len(box) != 4:
        raise SystemExit(f"crop 要四个数 [x0, y0, x1, y1]（0~1 的比例）：{box}")
    im = ImageOps.exif_transpose(Image.open(image)).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = box
    out = image.with_suffix(".crop.jpg")
    im.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))
            ).save(out, quality=95)
    return out


def _panel_css(side: str, image: Path, panel: dict,
               top: float, height: float, clip: str) -> str:
    """一格的底图。**盒子只占自己那一格**，图在这一格里铺满。

    踩过：先前让两块都占满整幅 1080×1920、再用 clip-path 切。那样
    `background-size` 的百分比是按**整幅画布**算的，横图缩到 1920 高会宽出
    画布好几倍，`focus` 调的其实是整幅里的位置，而看得见的只有被切剩的一条——
    渲出来像「一张照片没出来」。盒子先摆对，cover 才是这一格的 cover。

    两种 `fit`，判据是**人头顶还剩多少留白**：

    - `cover`（默认）：`auto <高度>%`，横素材铺到格高就等于 cover。人在画面
      中间、上下都有余量时用这个
    - `width`：按格宽铺，高度不够的那一条垫**同图的模糊放大版**（和解说卡
      信箱式缩放那几屏同一招）。给「人头顶几乎没有留白」的素材用——郑钦文
      那张 690×460 头顶只剩 2%，按高度铺满会**既切头又放大到 2.21 倍**；
      按宽度铺是 1.57 倍，还多出 298px 让头顶透气

    `zoom` 是在此之上再推一档，给「人在画面里很小」的素材用。
    """
    uri = _data_uri(_precrop(image, panel))
    focus = float(panel.get("focus", 0.5)) * 100
    focus_y = float(panel.get("focus_y", 0.5)) * 100
    zoom = float(panel.get("zoom", 1.0)) * 100
    box = (f".p-{side}{{top:{top:.2f}%;height:{height:.2f}%;"
           f"clip-path:{clip};overflow:hidden}}")
    if panel.get("fit") != "width":
        return (box + f".p-{side}::after{{background-image:url('{uri}');"
                f"background-size:auto {zoom:.1f}%;"
                f"background-position:{focus:.1f}% {focus_y:.1f}%}}")
    # 垫底那层要 scale(1.2) 给模糊留溢出量，否则边缘透底
    return (box
            + f".p-{side}::before{{background-image:url('{uri}');"
            f"background-size:cover;background-position:{focus:.1f}% 50%;"
            f"filter:blur(44px) brightness(.42);transform:scale(1.2)}}"
            + f".p-{side}::after{{background-image:url('{uri}');"
            f"background-size:{zoom:.1f}% auto;"
            f"background-position:{focus:.1f}% {focus_y:.1f}%;"
            f"{_feather(image, panel, height)}}}")


def _feather(image: Path, panel: dict, height: float) -> str:
    """照片和模糊垫层的交界要**羽化**，否则是一条硬边，一眼看出是拼的。

    只羽化真的有垫层的那一侧：照片正好贴住盒子边的那一侧再羽化，
    等于把边缘的照片抹掉、露出底下的模糊层——反而更糟。
    """
    from PIL import Image  # noqa: PLC0415

    iw, ih = Image.open(image).size
    box_h = height / 100 * VIDEO_H
    draw_h = VIDEO_W * float(panel.get("zoom", 1.0)) * ih / iw
    slack = max(0.0, box_h - draw_h)
    if slack < 12:                                   # 没垫层，不用羽化
        return ""
    pad_top = float(panel.get("focus_y", 0.5)) * slack / box_h * 100
    pad_bot = 100 - (pad_top + draw_h / box_h * 100)
    # 羽化带要够宽：2.6%（≈27px）时模糊层和照片的亮度差还是一条看得见的横线，
    # 7% 才化成一片渐暗，顺带给左上角那块台头腾出压得住字的底
    fade, stops = 7.0, []
    if pad_top > fade:
        stops += [f"transparent {pad_top:.2f}%", f"#000 {pad_top + fade:.2f}%"]
    if pad_bot > fade:
        stops += [f"#000 {100 - pad_bot - fade:.2f}%",
                  f"transparent {100 - pad_bot:.2f}%"]
    if not stops:
        return ""
    return f"mask-image:linear-gradient(180deg,{','.join(stops)})"


def _geometry(layout: str, seam: float) -> tuple[tuple, tuple, str]:
    """两格的盒子和裁切。斜切时两格在中缝**重叠**一条带，各自切掉一半。"""
    if layout != "diagonal":
        return ((0.0, seam, "none"), (seam, 100.0 - seam, "none"), "")
    ha, hb = seam + BAND, 100.0 - (seam - BAND)
    # 在各自盒子的坐标系里写裁切：上格右边收到中缝上沿，左边落到下沿
    a_right = (seam - BAND) / ha * 100
    b_left = (2 * BAND) / hb * 100
    clip_a = f"polygon(0 0,100% 0,100% {a_right:.2f}%,0 100%)"
    clip_b = f"polygon(0 {b_left:.2f}%,100% 0,100% 100%,0 100%)"
    return ((0.0, ha, clip_a), (seam - BAND, hb, clip_b),
            f'<div class="seam" style="top:{seam:.1f}%"></div>')


def _result_block(cover: dict, names: list) -> str:
    """钩子下面那一块：结果 + 元信息。

    原来是两行平铺——`score` 一整句「王欣瑜 7-6(3) 6-3 帕雷哈」加一行灰色
    `sub`。毛病是**只有两级**：级别（WTA 500）、轮次（R1）、赛事、时长四样
    信息挤在同一行灰字里，扫过去一样重。

    现在是：

        王欣瑜 7-6(3) 6-3 帕雷哈      赢家（白）· 盘分（品牌绿，数字大一档）· 输家（灰）
        [WTA 500] [R1]  华盛顿 · 1 小时 51 分

    **两个人的名字都要在，输的那个置灰、不能省。** 中间改过一版只留赢家，
    理由是名字已经印在绿线上了；账号所有者一句「怎么对手的名字没了」——
    这一行是**赛果**，赛果本来就是「谁赢了谁」，少一个人它就不成句。
    置灰解决的是层次问题，不是删掉。

    输家**从 `versus.names` 里推**，不另开字段：这样它和绿线上印的那个
    永远是同一个，不会两处各写一遍再对不上。

    级别和轮次做成**描边药丸**——它们是标签不是句子，而且描边用的是同一个
    品牌绿，不引入第二个强调色（一屏最多一个强调色）。

    老的 `score` / `sub` 两个字段继续认，斜切那两条已发布的片子不受影响。

    **赛果那一行可以整行不要**（只给 `tier` / `round` / `meta`，不给 `result`）。
    「赛场之上」讲的是一场对决，赛果就是标题；**网球有故事讲的是一个人**，
    把「德米纳尔 6-2 6-3 克鲁兹·休伊特」印在封面上等于**先把结局说了**——
    休伊特那条六拍的结构里，比分是第 5 拍，而第 5 拍恰恰是「片子不能停在
    这儿」的那一拍。封面剧透完，后面五拍就没人看了。
    """
    result = str(cover.get("result") or "")
    event_badge = cover.get("event_badge") or {}
    has_footer = bool(event_badge or cover.get("tier")
                      or cover.get("round") or cover.get("meta"))
    if not result and not has_footer:
        return (f'<div class="score">{cover.get("score", "")}</div>'
                f'<div class="sub">{cover.get("sub", "")}</div>')
    winner = str(cover.get("winner", "")).strip()
    loser = next((n for n in names if str(n).strip() != winner), "")
    # 三盘的比分比两盘长一截（「6-7(3) 6-3 6-4」比「7-6(3) 6-3」多四个字位），
    # 加上两个名字会顶出 948px 的可用宽度。长了就降一档，别让它折行。
    sets_px = 62 if len(result) <= 11 else 54
    if event_badge:
        tour = str(event_badge.get("tour", "")).strip().lower()
        if tour not in {"atp", "wta"}:
            raise SystemExit("event_badge.tour 只能是 ATP 或 WTA。")
        logo_path = Path(f"assets/logo/tours/{tour}.svg")
        if not logo_path.is_file():
            raise SystemExit(f"找不到官方巡回赛标识：{logo_path}")
        logo = logo_path.read_text(encoding="utf-8").replace(
            "<svg ", '<svg class="tour-logo" aria-hidden="true" ', 1)
        level = html.escape(str(event_badge.get("level", "")).strip())
        text = html.escape(str(event_badge.get("text", "")).strip())
        footer = (
            '<div class="eventline">'
            f'<span class="tourmark">{logo}<b>{level}</b></span>'
            f'<span class="eventtext">{text}</span>'
            "</div>"
        )
    else:
        pills = "".join(f'<span class="pill">{p}</span>'
                        for p in (cover.get("tier"), cover.get("round")) if p)
        meta = str(cover.get("meta", "")).strip()
        footer = (
            f'<div class="meta">{pills}'
            + (f'<span class="mtx">{meta}</span>' if meta else "")
            + "</div>"
        )
    if not result:
        return footer
    return (
        '<div class="res">'
        + (f'<span class="win">{winner}</span>' if winner else "")
        + f'<span class="sets" style="font-size:{sets_px}px">{result}</span>'
        + (f'<span class="lose">{loser}</span>' if loser else "")
        + "</div>"
        + footer)


def build(spec: dict, layout: str, out: Path) -> Path:
    return build_poster(spec["cover"], out, layout=layout)


def build_poster(cover: dict, out: Path, layout: str = "diagonal") -> Path:
    """把一个 `cover` 段落渲成 1080×1440 的海报。`build_match_reel` 直接调它。"""
    # **`solo` 是给「讲一个人」的片子用的，不是 VS 的降级。**
    #
    # 账号所有者 2026-07-31：休伊特那条「是讲休伊特的儿子的话题，不是赛场之上的
    # 内容」「所以封面只有休伊特儿子照片」——栏目是**网球有故事**，只是这次用
    # 视频呈现。VS 那套（两格 + 中缝 + VS 圆牌 + 两个名字）讲的是一场对决，
    # 套在讲人的片子上，等于让读者去猜这是谁打谁。
    #
    # ⚠️ **赛场之上仍然只能用 VS 模板**——那条规矩没变，判据在
    # `test_封面只有海报模板一条路`。solo 认的是别的栏目。
    if layout == "solo":
        names = [str(cover.get("subject", "")).strip()]
        if not names[0]:
            raise SystemExit(
                "solo 版式要 `cover.subject`：这条片子讲的是谁（中文名）。\n"
                "名字查 src/tennislive/zh/player_names_top500.json，别手打。")
    else:
        versus = cover["versus"]
        top, bottom = versus["top"], versus["bottom"]
        # 名字是模板的一部分，不是可选装饰：只有两张脸的 VS 卡等于让人猜这是谁
        # 打谁，而中文名是这条片子在信息流里唯一能被扫到的东西。
        # **一律以译名表为准**，别手打——莱巴金娜、奥斯塔彭科都是这么错的。
        names = versus.get("names") or []
        if len(names) != 2 or not all(str(n).strip() for n in names):
            raise SystemExit(
                "赛场之上的海报要两个人的中文名：versus.names = [上格, 下格]。\n"
                "名字查 src/tennislive/zh/player_names_top500.json，别手打。")

    hook = "".join(f"<div>{line.strip()}</div>"
                   for line in str(cover.get("hook", "")).split("\n") if line.strip())

    if layout == "solo":
        body, panels = _solo_body(cover)
    elif layout == "cutout":
        body, panels = _cutout_body(cover, versus, names)
    else:
        # 斜切的两块交界处压一条品牌绿的细边——**没有这条边，两张照片会像没对齐的
        # 拼贴**；有了它，斜线成了设计的一部分。
        seam = float(versus.get("split", 0.5)) * 100
        (box_a, box_b, seam_el) = _geometry(layout, seam)
        panels = "".join(
            _panel_css(side, Path(s["image"]), s, box[0], box[1], box[2])
            for side, s, box in (("a", top, box_a), ("b", bottom, box_b))
        )
        badge = f'<div class="vs" style="top:{seam:.1f}%">VS</div>'
        # stack：名字压在各自那一格，其余版式名字并排在 VS 两侧
        if layout == "stack":
            name_els = (
                f'<div class="na n-a" style="top:{seam - 12:.1f}%">{names[0]}</div>'
                f'<div class="na n-b" style="top:{seam + 5:.1f}%">{names[1]}</div>')
        else:
            name_els = (f'<div class="nm" style="top:{seam:.1f}%">'
                        f'<span>{names[0]}</span><i></i><span>{names[1]}</span></div>')
        body = (f'<div class="p p-a"></div><div class="p p-b"></div>{seam_el}'
                f'<div class="shade"></div>{name_els}{badge}')

    # **solo 自带整块文案，不再接 VS 那一套。** VS 的尾巴是「台头药丸 + 钩子 +
    # 赛果行」；网球有故事的封面版式里，台头在顶部的品牌行里、钩子压在正中，
    # **底下什么都不加**——赛果是最后一拍，级别／年龄／赛事那三颗药丸也不属于
    # 这个栏目的封面（知识贴那十三条封面上一颗都没有）。
    tail = "" if layout == "solo" else (
        f'<div class="top">{cover.get("eyebrow", "")}</div>'
        f'<div class="copy"><div class="hook">{hook}</div>'
        f'{_result_block(cover, names)}</div>')

    html = f"""<!doctype html><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{VIDEO_W}px;height:{VIDEO_H}px;overflow:hidden;background:{INK};
  position:relative;font-family:'TL Sans SC',sans-serif}}
.p{{position:absolute;left:0;right:0}}
.p::before,.p::after{{content:'';position:absolute;inset:0;
  background-repeat:no-repeat}}
{panels}
/* 压暗只压文字那一段：上面留给脸，糊了就看不出是谁 */
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,
  rgba(4,18,13,.42) 0%,rgba(4,18,13,0) 18%,rgba(4,18,13,0) 52%,
  rgba(4,18,13,.80) 72%,rgba(4,18,13,.96) 86%)}}
.seam{{position:absolute;left:-6%;right:-6%;height:10px;background:{BRAND};
  transform:translateY(-50%) rotate(-{SEAM_ANGLE}deg);box-shadow:0 0 40px rgba(0,0,0,.5)}}
.vs{{position:absolute;left:50%;transform:translate(-50%,-50%);z-index:5;
  width:176px;height:176px;border-radius:50%;background:{BRAND};color:{INK};
  font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:70px;display:flex;align-items:center;justify-content:center;
  box-shadow:0 12px 46px rgba(0,0,0,.5)}}
.nm{{position:absolute;left:0;right:0;transform:translateY(-50%);z-index:4;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 66px;font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:62px;color:{TEXT};text-shadow:0 4px 26px rgba(0,0,0,.75)}}
.nm i{{flex:1}}
.na{{position:absolute;left:66px;z-index:4;font-size:62px;color:{TEXT};
  font-family:'TL Display SC','TL Sans SC',sans-serif;
  text-shadow:0 4px 26px rgba(0,0,0,.75)}}
.n-b{{left:auto;right:66px}}
.top{{position:absolute;top:66px;left:66px;z-index:6;background:{BRAND};
  color:{INK};font-size:30px;font-weight:800;letter-spacing:4px;
  padding:11px 26px;border-radius:999px}}
.copy{{position:absolute;left:66px;right:66px;bottom:150px;z-index:6}}
.hook{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:100px;
  line-height:1.14;color:{TEXT};text-shadow:0 4px 30px rgba(0,0,0,.6)}}
.score{{margin-top:26px;font-family:'TL Numeral','TL Sans SC',sans-serif;
  font-weight:600;font-size:50px;color:{BRAND}}}
.sub{{margin-top:12px;font-size:32px;color:{DIM};letter-spacing:2px}}
/* 结果那一行按基线对齐：赢家是汉字、盘分是西文数字，两种字的墨高差着一截，
   按 center 对齐会看出高低不齐（和字幕里数字要单独放大一档是同一回事）。 */
.res{{margin-top:28px;display:flex;align-items:baseline;gap:22px}}
.win{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:46px;
  color:{TEXT};text-shadow:0 4px 22px rgba(0,0,0,.6)}}
.sets{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:62px;color:{BRAND};letter-spacing:1px}}
/* 输的一方**要写，但置灰**：这一行是赛果，少一个人就不成句；灰是层次，不是删除 */
.lose{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:46px;
  color:{DIM}}}
.meta{{margin-top:20px;display:flex;align-items:center;gap:14px}}
/* 没有赛果那一行时（网球有故事），药丸直接顶着钩子，20px 太紧——那 20px
   本来是接在 `.res` 的 28px 下面的。 */
.hook+.meta,.hook+.eventline{{margin-top:34px}}
.eventline{{margin-top:20px;display:flex;align-items:center;gap:22px}}
.tourmark{{height:48px;min-width:158px;border:2px solid {BRAND};
  border-radius:999px;color:{BRAND};display:inline-flex;align-items:center;
  justify-content:center;gap:11px;padding:7px 18px 8px}}
.tour-logo{{display:block;width:76px;height:25px;color:{BRAND}}}
.tourmark b{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:29px;
  line-height:1;font-weight:800;letter-spacing:1px}}
.eventtext{{font-size:31px;color:{DIM};letter-spacing:2px}}
.pill{{border:2px solid {BRAND};color:{BRAND};border-radius:999px;
  font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:26px;letter-spacing:3px;padding:6px 18px 7px;white-space:nowrap}}
.mtx{{font-size:30px;color:{DIM};letter-spacing:2px}}
</style>
{body}
{tail}"""

    return _render_html(html, out)


def _render_html(html: str, out: Path) -> Path:
    """把一段 HTML 渲成 1080×1440 的 JPEG。solo 和 VS 两条版式共用这一段，
    免得浏览器查找的那串兜底路径在两处各写一遍、改一处漏一处。"""
    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(args=["--no-sandbox"])
        except Exception as default_error:  # noqa: BLE001
            # 本地 Work 环境和 GitHub runner 的浏览器位置不同。优先尊重显式配置，
            # 再找项目旁的本地 Chromium，最后兼容既有 runner 镜像；不要因为
            # Playwright 缓存目录不同就把每次封面预览都送去 Actions。
            candidates = [
                os.environ.get("CHROMIUM_PATH"),
                str(Path(__file__).resolve().parents[2]
                    / ".local-browser" / "chromium"),
                "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            ]
            browser = None
            for executable in candidates:
                if not executable or not Path(executable).is_file():
                    continue
                browser = pw.chromium.launch(
                    executable_path=executable, args=["--no-sandbox"])
                break
            if browser is None:
                raise default_error
        tab = browser.new_page(viewport={"width": VIDEO_W, "height": VIDEO_H},
                               device_scale_factor=1)
        tab.goto(page.resolve().as_uri())
        tab.wait_for_timeout(600)
        tab.screenshot(path=str(out), type="jpeg", quality=95)
        browser.close()
    return out



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--layout", default="cutout",
                    choices=("cutout", "diagonal", "split", "stack", "solo"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = build(spec, args.layout, Path(args.out))
    print(f"[poster] {args.layout} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
