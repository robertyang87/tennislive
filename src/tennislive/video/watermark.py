"""常驻角标：视频播放时压在左上角的品牌 logo。

账号所有者 2026-09-01：「**视频播放时候左上角保留网球时差的 logo**」，
随后一句「**用封面上的 logo 和位置**」。

⚠️ **所以这一条不是自己设计一个角标，是把封面台头那一块原样搬到播放画面上。**
第一版用的是横版 lockup（球标 ＋ 网球时差 ＋ TENNIS JETLAG）贴在 (22, 22)——
那是**另一个 logo、另一个位置**，被这句话推翻了。现在是封面上那一块：

    球标 52px ── gap 14 ── 「网球时差 · <栏目>」38px 得意黑
    落位 left 70 / top 44

**这几个数只有一处出处，就是封面自己的 CSS**（`versus_poster` 的 `.head` /
`.brandwrap` / `.brand-icon` / `.brand`，赛后开麦封面那份逐项相同）。抄一份到
这儿的样子是「封面上的 logo 和播放时的 logo 慢慢漂开」，而那不报错。判据拿
封面 CSS 里的数直接比。

**这份是唯一的出处**，两条出片线（`tools/build_match_reel.py` 的竖版短片、
`tools/build_interview_clip.py` 的赛后开麦）都从这儿拿。⚠️ 别在任一条线上
再抄一份尺寸或阴影参数——「一个数写两处必分叉」，而分叉的样子是**同一个账号
出去的片子 logo 一大一小**，没有任何东西会报错。

⚠️ **知识解说片（`video/explainer.py`）不接这一条**，不是漏了：那条线每一屏
都是卡片，而卡片顶上本来就印着「网球时差 · 栏目」——再压一个角标是把同一个
标识在同一屏上说两遍。
"""
from __future__ import annotations

from pathlib import Path

#: ⚠️ **封面台头用的是球标（`icon.png`），不是横版 lockup。** 两个都在
#: `assets/logo/brand/` 里，长得都像「网球时差的 logo」——拿错的样子是角标比
#: 封面那一块宽出一倍还多带一行英文，而它照样渲得出来。
BRAND_ICON = "icon.png"

#: 下面这一组**逐项对应封面的 CSS**，改任何一个都要连封面一起改：
#:
#:     .brand-icon{width:52px;height:52px}          → BRAND_ICON_PX
#:     .brandwrap{gap:14px}                         → BRAND_GAP_PX
#:     .brand{font-size:38px}                       → BRAND_TEXT_PX
#:     .brand{letter-spacing:1px}                   → BRAND_TRACKING_PX
#:     .brand{color:#f4fbf7}                        → BRAND_COLOUR
#:     .head{left:70px;top:44px}                    → WATERMARK_LEFT/TOP
BRAND_ICON_PX = 52
BRAND_GAP_PX = 14
BRAND_TEXT_PX = 38
BRAND_TRACKING_PX = 1
BRAND_COLOUR = (244, 251, 247)

#: 得意黑。封面写的是 `font-family:'TL Display SC'`，而 `TL Display SC` 这个族名
#: 在 `render/webcards._font_css()` 里绑的就是这个文件——**量宽度和渲画面都要用
#: 仓库里这一份**，拿系统字体渲出来的和封面对不上。
BRAND_FONT = "SmileySans-Oblique.ttf"

#: 落位，就是封面 `.head` 的 `left` / `top`。⚠️ 纵向要**在这个基础上再让开顶部
#: 那条带**（见 `watermark_xy`）——封面顶上是空的，播放时可能压着顶栏。
WATERMARK_LEFT = 70
WATERMARK_TOP = 44

#: 字标的**墨**离 `.head` 顶边多远。CSS 那头是行高和字体的 ascent 算出来的，
#: 这儿只能量——所以它是从**真封面**量的（`.head{top:44px}`，字标墨从 y=47 起）。
BRAND_INK_TOP_PX = 3

#: ⚠️ **球标要比字标的墨再低一截，这个数不是拍的。** 封面的 `.brandwrap` 是
#: `align-items:center`，而它里面的 `.brandlines` 有**两行**（`.brand` ＋
#: `.topic`）——球标压的是两行的中线，比「网球时差 · 栏目」那一行低。
#: 角标只有一行，照单行居中会把球标画高 18px，和封面一叠就看得出来。
#: **量出来的**：真封面上球标墨顶 64、字标墨顶 47。判据拿真封面比，不是比这个数。
BRAND_ICON_DROP_PX = 15

#: ⚠️⚠️ **阴影不是装饰，是这条能压在任何画面上的前提**——量出来的：
#: 「网球时差」这几个字是近白的（`#f4fbf7`），压在**纯白**上（白球衣、亮天空、
#: 浅色看台）**整个消失**，只剩球标。四种最坏的底各渲一版并排比过。
#:
#: ⚠️ **封面那份 `text-shadow:0 2px 12px rgba(0,0,0,.6)` 不能照抄**，因为它
#: **依赖一个播放时不存在的前提**：封面顶上那条带被 `.scrim` 压暗着（CLAUDE.md
#: 「上下两头必须留着：台头压在顶上、比分板压在底下」），字是压在暗底上的；
#: 而播放画面上那一块可能是纯白。这正是本仓库记过的「抄了规则，没抄它依赖的
#: 前提」——所以这儿的阴影比封面的重，数是在纯白上量出来的，不是抄的。
#: **别为了「和封面一模一样」把它调回 .6，也别为了「干净」去掉。**
WATERMARK_SHADOW_BLUR = 6
WATERMARK_SHADOW_ALPHA = 180

#: 阴影往四周溢出，所以 PNG 比 logo 本身大一圈。`overlay` 给的是 **PNG 的**
#: 左上角，所以贴的时候要把这一圈减掉，logo 才真的落在封面那个位置上。
WATERMARK_SHADOW_PAD = WATERMARK_SHADOW_BLUR * 3


def brand_label(column: str) -> str:
    """台头那一行字，和封面 `<span class=brand>网球时差 · {column}</span>` 一样。"""
    return f"网球时差 · {column}".strip(" ·")


def brand_watermark(dest: Path, column: str) -> Path:
    """PIL 渲常驻角标（透明底）：封面台头那一块 ＋ 一层软阴影。

    只贴在**正片区间**——封面自己就印着这一块，品牌片尾整屏是这个 logo，
    两处再压一遍是把同一个标识说三遍。范围怎么卡由调用方决定（竖版短片靠
    split 出来的那三段，赛后开麦靠这条链只管 body）。
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: PLC0415

    root = Path(__file__).resolve().parents[3]
    icon = Image.open(root / "assets" / "logo" / "brand" / BRAND_ICON)
    icon = icon.convert("RGBA").resize(
        (BRAND_ICON_PX, BRAND_ICON_PX), Image.LANCZOS)
    font = ImageFont.truetype(
        str(root / "assets" / "fonts" / BRAND_FONT), BRAND_TEXT_PX)

    text = brand_label(column)
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    # **逐字排，因为封面有 `letter-spacing:1px`**——PIL 一次画一整串是不带
    # 字距的，差出来的宽度会让角标比封面窄几个像素。
    advances = [probe.textlength(ch, font=font) + BRAND_TRACKING_PX
                for ch in text]
    bbox = probe.textbbox((0, 0), text, font=font)
    text_w = int(round(sum(advances)))
    ink_h = bbox[3] - bbox[1]

    # **纵向按封面量到的两个数摆**（`BRAND_INK_TOP_PX` / `BRAND_ICON_DROP_PX`），
    # 不按「和字标居中」摆——理由见那两个常量上面。坐标都相对 `.head` 的顶边，
    # 也就是这张 PNG 的内容框顶边。
    icon_inset = icon.split()[3].getbbox()[1]      # 球标 PNG 自带的透明留白
    icon_top = BRAND_INK_TOP_PX + BRAND_ICON_DROP_PX - icon_inset
    block_h = max(icon_top + icon.height, BRAND_INK_TOP_PX + ink_h)
    block_w = icon.width + BRAND_GAP_PX + text_w

    pad = WATERMARK_SHADOW_PAD
    big = Image.new("RGBA", (block_w + pad * 2, block_h + pad * 2), (0, 0, 0, 0))
    big.paste(icon, (pad, pad + icon_top), icon)
    draw = ImageDraw.Draw(big)
    x = pad + icon.width + BRAND_GAP_PX
    y = pad + BRAND_INK_TOP_PX - bbox[1]
    for ch, adv in zip(text, advances):
        draw.text((x, y), ch, font=font, fill=BRAND_COLOUR + (255,))
        x += adv

    # 阴影 ＝ 整块自己的 alpha 模糊之后压成黑。乘 1.7 再截顶，是为了让笔画
    # **内部**的影子够实——纯高斯出来的中心太淡，白底上仍然吃掉那几个字。
    blurred = big.split()[3].filter(
        ImageFilter.GaussianBlur(WATERMARK_SHADOW_BLUR))
    shadow = Image.new("RGBA", big.size, (0, 0, 0, 0))
    shadow.putalpha(blurred.point(
        lambda v: min(WATERMARK_SHADOW_ALPHA,
                      round(v * WATERMARK_SHADOW_ALPHA / 255 * 1.7))))
    Image.alpha_composite(shadow, big).save(dest)
    return dest


def watermark_xy(top_offset: int) -> tuple[int, int]:
    """那张 PNG 的左上角坐标（阴影那一圈已经减掉）。

    横向就是封面的 `left:70px`；纵向是封面的 `top:44px` **再让开顶部被占掉的
    那一段**——`top_offset` 由调用方按自己的版式给：顶栏的带、实色顶带、或者
    0（顶上是空的，这时落位和封面逐像素相同）。不让开的话角标压在顶栏的字上，
    而那**不报错**，只是两样东西叠在一起。
    """
    return (WATERMARK_LEFT - WATERMARK_SHADOW_PAD,
            top_offset + WATERMARK_TOP - WATERMARK_SHADOW_PAD)
