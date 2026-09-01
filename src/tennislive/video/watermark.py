"""常驻角标：视频播放时压在左上角的品牌 logo。

账号所有者 2026-09-01：「**视频播放时候左上角保留网球时差的 logo**」。

**这份是唯一的出处**，两条出片线（`tools/build_match_reel.py` 的竖版短片、
`tools/build_interview_clip.py` 的赛后开麦）都从这儿拿。⚠️ 别在任一条线上
再抄一份尺寸或阴影参数——「一个数写两处必分叉」，而分叉的样子是**同一个账号
出去的片子，logo 一大一小**，没有任何东西会报错。

⚠️ **知识解说片（`video/explainer.py`）不接这一条**，不是漏了：那条线每一屏
都是卡片，而卡片顶上本来就印着「网球时差 · 栏目」——再压一个角标是把同一个
标识在同一屏上说两遍。
"""
from __future__ import annotations

from pathlib import Path

#: ⚠️ **用现成的品牌 lockup，不自己排版。** `assets/logo/brand/` 里这张就是
#: 官方 logo（球标 ＋ 网球时差 ＋ TENNIS JETLAG，字体和间距都由
#: `tools/render_brand_logo.py` 定）。拿 PIL 自己拼「球标 ＋ 四个字」看着差不多，
#: 但那是**另一个 logo**——`band_foot_strip` 那条脚注是注脚所以可以自己拼，
#: 这一条是品牌标识本身，不能。
WATERMARK_SRC = "lockup-horizontal-dark.png"

#: logo 宽度（1080 画幅上占 24%）。三档都渲出来压在真源片帧上比过：
#: 220 太小（TENNIS JETLAG 糊成一条）、300 抢戏，260 是那一档。
WATERMARK_W = 260

#: 距画面边的内边距。
WATERMARK_PAD = 40

#: ⚠️⚠️ **阴影不是装饰，是这条能压在任何画面上的前提**——量出来的：
#: lockup 里「网球时差」四个字是近白的，压在**纯白**上（白球衣、亮天空、
#: 浅色看台）**整个消失**，只剩球标和金色那行英文还在。四种最坏的底
#: （纯白／红土／浅灰／天蓝）各渲一版并排比过，加了阴影四种全部读得出来。
#: **别为了「干净」把它去掉，也别把 alpha 调小去「淡一点」。**
WATERMARK_SHADOW_BLUR = 6
WATERMARK_SHADOW_ALPHA = 180

#: 阴影往四周溢出，所以 PNG 比 logo 本身大一圈。`overlay` 给的是 **PNG 的**
#: 左上角，所以贴的时候要把这一圈减掉，logo 才真的落在 `WATERMARK_PAD` 上。
WATERMARK_SHADOW_PAD = WATERMARK_SHADOW_BLUR * 3


def brand_watermark(dest: Path) -> Path:
    """PIL 渲常驻角标（透明底）：官方 lockup ＋ 一层软阴影。

    只贴在**正片区间**——封面自己的台头就印着「网球时差 · 栏目」，品牌片尾
    整屏就是这个 logo，两处再压一遍是把同一个标识说三遍。范围怎么卡由调用方
    决定（竖版短片靠 split 出来的那三段，赛后开麦靠这条链只管 body）。
    """
    from PIL import Image, ImageFilter  # noqa: PLC0415

    root = Path(__file__).resolve().parents[3]
    logo = Image.open(root / "assets" / "logo" / "brand" / WATERMARK_SRC)
    logo = logo.convert("RGBA")
    logo = logo.resize(
        (WATERMARK_W, max(2, round(logo.height * WATERMARK_W / logo.width))),
        Image.LANCZOS)
    pad = WATERMARK_SHADOW_PAD
    big = Image.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2),
                    (0, 0, 0, 0))
    big.paste(logo, (pad, pad), logo)
    # 阴影 ＝ logo 自己的 alpha 模糊之后压成黑。乘 1.7 再截顶，是为了让笔画
    # **内部**的影子够实——纯高斯出来的中心太淡，白底上仍然吃掉那四个字。
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

    `top_offset` 是**这条线上顶部被占掉多高**，由调用方按自己的版式给：
    顶栏的带、实色顶带、或者 0（顶上是空的）。角标要让开它，不然压在顶栏的
    字上——而那**不报错**，只是两样东西叠在一起。
    """
    return (WATERMARK_PAD - WATERMARK_SHADOW_PAD,
            top_offset + WATERMARK_PAD - WATERMARK_SHADOW_PAD)
