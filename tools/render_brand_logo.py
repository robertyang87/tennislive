#!/usr/bin/env python3
"""网球时差品牌 logo 生成器（定稿：B 严格对称）。

设计依据（都经实物对照）：
- 球色 #C3DC4A、缝色 #DDE2CF、品牌深绿 #102D23、品牌黄 #F2B32A —— 取自 4 颗真球
  实拍（Penn/Wilson×2/链网旁）的中位取色区间。
- 缝线 = 网球缝线球面参数方程 (a=0.8, b=0.2) 的精确投影，只画正对观察者的
  正面段并硬裁进球内（不溢出成圆环）；取对称视角 → 上下两道镜像双弧。
- 指针：时针短粗、分针长细，斜上对称摆位（严格左右镜像），点出"时差"。

用法：python tools/render_brand_logo.py  → 生成全套到 assets/logo/brand/
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "logo" / "brand"

BALL = (195, 220, 74)      # #C3DC4A 球身（荧光黄绿）
SEAM = (221, 226, 207)     # #DDE2CF 缝线
DARK = (16, 45, 35)        # #102D23 品牌深绿（指针/深底）
YELLOW = (242, 179, 42)    # #F2B32A 品牌黄
WHITE = (255, 255, 255)
CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def _seam_points(n=3200, a=0.8, b=0.2):
    for i in range(n):
        t = 2 * math.pi * i / n
        yield (a * math.cos(t) + b * math.cos(3 * t),
               a * math.sin(t) - b * math.sin(3 * t),
               2 * math.sqrt(a * b) * math.sin(2 * t))


def icon(size=1024, bg=None, hands=True):
    """返回 RGBA 图标。bg=None 透明；bg=颜色元组填底（头像/深底用）。"""
    S = size
    img = Image.new("RGBA", (S, S), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    R = S * 0.46
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=BALL)
    # 缝线：正面段 + 面内 45° 使镜像轴竖直
    w = int(S * 0.05)
    r_in = R - w * 0.6
    c45, s45 = math.cos(math.pi / 4), math.sin(math.pi / 4)
    seg = []
    for (x, y, z) in _seam_points():
        x, y = x * c45 - y * s45, x * s45 + y * c45
        if z > 0.06:
            seg.append((cx + x * r_in, cy - y * r_in))
        elif len(seg) > 1:
            d.line(seg, fill=SEAM, width=w, joint="curve")
            seg = []
        else:
            seg = []
    if len(seg) > 1:
        d.line(seg, fill=SEAM, width=w, joint="curve")
    # 硬裁进球内
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    clipped = Image.new("RGBA", (S, S), bg or (0, 0, 0, 0))
    if bg:
        clipped.paste(img, (0, 0))
    else:
        clipped.paste(img, (0, 0), mask)
    img = clipped
    d = ImageDraw.Draw(img)
    if hands:
        def hand(deg, length, width):
            a = math.radians(deg - 90)
            x2, y2 = cx + length * math.cos(a), cy + length * math.sin(a)
            d.line([cx, cy, x2, y2], fill=DARK, width=width)
            d.ellipse([x2 - width * .5, y2 - width * .5,
                       x2 + width * .5, y2 + width * .5], fill=DARK)
        hand(-52, R * 0.52, int(S * 0.062))   # 时针 短粗（左）
        hand(52, R * 0.72, int(S * 0.040))    # 分针 长细（右）
        d.ellipse([cx - S * 0.05, cy - S * 0.05,
                   cx + S * 0.05, cy + S * 0.05], fill=DARK)
        d.ellipse([cx - S * 0.019, cy - S * 0.019,
                   cx + S * 0.019, cy + S * 0.019], fill=BALL)
    return img


def lockup(dark_bg=True, stacked=False, size=1500):
    """横版/竖版字标锁定。"""
    fg = WHITE if dark_bg else DARK
    ic_px = 240
    ic = icon(1024).resize((ic_px, ic_px), Image.LANCZOS)
    if stacked:
        W, H = 900, 660
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.paste(ic, ((W - ic_px) // 2, 30), ic)
        d = ImageDraw.Draw(img)
        d.text((W / 2, 400), "网球时差", font=ImageFont.truetype(CJK, 150),
               fill=fg, anchor="mm")
        d.text((W / 2, 530), "T E N N I S   J E T L A G",
               font=ImageFont.truetype(CJK, 46), fill=YELLOW, anchor="mm")
    else:
        W, H = 1500, 300
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.paste(ic, (30, 30), ic)
        d = ImageDraw.Draw(img)
        d.text((320, 110), "网球时差", font=ImageFont.truetype(CJK, 150),
               fill=fg, anchor="lm")
        d.text((326, 225), "T E N N I S   J E T L A G",
               font=ImageFont.truetype(CJK, 46), fill=YELLOW, anchor="lm")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 图标：透明 / 深底头像 / 各尺寸
    icon(1024).save(OUT / "icon.png")
    icon(1024, bg=(*DARK, 255)).save(OUT / "avatar-dark.png")
    icon(1024, bg=(*WHITE, 255)).save(OUT / "avatar-light.png")
    for sz in (512, 256, 180, 96, 48, 32, 16):
        icon(max(sz, 256)).resize((sz, sz), Image.LANCZOS).save(OUT / f"icon-{sz}.png")
    icon(64).resize((32, 32), Image.LANCZOS).save(OUT / "favicon.png")
    # 字标
    lockup(dark_bg=True).save(OUT / "lockup-horizontal-dark.png")
    lockup(dark_bg=False).save(OUT / "lockup-horizontal-light.png")
    lockup(dark_bg=True, stacked=True).save(OUT / "lockup-stacked-dark.png")
    lockup(dark_bg=False, stacked=True).save(OUT / "lockup-stacked-light.png")
    # 水印（半透明白，视频角标用）
    wm = icon(512)
    alpha = wm.split()[3].point(lambda a: int(a * 0.6))
    wm.putalpha(alpha)
    wm.save(OUT / "watermark.png")
    print(f"全套 logo 已生成到 {OUT}")


if __name__ == "__main__":
    main()
