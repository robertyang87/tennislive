#!/usr/bin/env python3
"""two-serves 封面 v2：全幅铺满（竖版原生渲染帧）＋库内同款字号（EP13 实测：标题字形高 180、
行距 250、品牌字形高 81，2160×2880 基准）。"""
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
FONTS = os.path.join(ROOT, 'assets', 'fonts')
ICON = os.path.join(ROOT, 'assets', 'logo', 'brand', 'account', 'icon-transparent-1024.png')
W, H = 2160, 2880
GOLD = (245, 185, 66); WHITE = (245, 248, 255); RED = (255, 92, 76)
def F(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
BLACK = 'NotoSansSC-Black-sub.ttf'
TITLE = F(BLACK, 195); PITCH = 250; X = 140; BOTTOM = 2545
def brand(im):
    ic = Image.open(ICON).convert('RGBA'); bb = ic.split()[3].getbbox()
    ic = ic.crop(bb).resize((100, 100), Image.LANCZOS)
    im.paste(ic, (120, 108), ic)
    d = ImageDraw.Draw(im); d.text((245, 106), '网球时差', font=F(BLACK, 88), fill=GOLD)
def scrim(im, frac=0.52, alpha=150):
    ov = Image.new('L', (1, int(H * frac)))
    for i in range(ov.height): ov.putpixel((0, i), int(alpha * (i / ov.height) ** 1.6))
    black = Image.new('RGB', (W, ov.height), (2, 4, 12))
    im.paste(black, (0, H - ov.height), ov.resize((W, ov.height)))
def base(raw):
    im = Image.open(os.path.join(HERE, 'raw', raw)).convert('RGB').resize((W, H), Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(1.05)
    scrim(im); brand(im)
    return im
def title(im, lines):
    d = ImageDraw.Draw(im)
    y = BOTTOM - 180 - (len(lines) - 1) * PITCH
    for segs in lines:
        x = X
        for text, color in segs:
            d.text((x + 4, y + 4), text, font=TITLE, fill=(0, 0, 0))
            d.text((x, y), text, font=TITLE, fill=color)
            x += d.textlength(text, font=TITLE)
        y += PITCH
def clean_band(im, y0, y1):
    import numpy as np
    a = np.asarray(im).astype(np.float32)
    above = np.median(a[y0 - 300:y0 - 60], axis=0)
    below = np.median(a[y1 + 60:y1 + 300], axis=0)
    n = y1 - y0
    for i in range(n):
        t = (i / max(n - 1, 1)) ** 1.2
        a[y0 + i] = above * (1 - t) + below * t
    im.paste(Image.fromarray(a.astype('uint8')), (0, 0))
def save(im, name): im.save(os.path.join(HERE, name), quality=92); print(name)
# A 场面版：为什么网球给你两次发球？
im = base('pA.png'); title(im, [[('为什么网球', WHITE)], [('给你', WHITE), ('两次', GOLD), ('发球？', WHITE)]]); save(im, 'opt_A_tall_zh.jpg')
# B 反差版：两发都拼，反而少赢 3 分
im = Image.open(os.path.join(HERE, 'raw', 'pC.png')).convert('RGB').resize((W, H), Image.LANCZOS)
clean_band(im, 2180, 2400)
scrim(im, 0.55, 215); brand(im); title(im, [[('两发都拼，', WHITE)], [('反而少赢', WHITE), ('3 分', RED)]]); save(im, 'opt_B_tall_zh.jpg')
# C 金句版：给你两次发球，不是福利，是算过的保险
im = Image.open(os.path.join(HERE, 'raw', 'pF.png')).convert('RGB').resize((W, H), Image.LANCZOS)
scrim(im); clean_band(im, 2200, 2420); brand(im); title(im, [[('给你两次发球', WHITE)], [('不是福利，', WHITE)], [('是算过的', WHITE), ('保险', GOLD)]]); save(im, 'opt_C_tall_zh.jpg')
