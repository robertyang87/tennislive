#!/usr/bin/env python3
"""《平分之后》封面定版：EP13 案例式——本集 3D 场景全幅铺满＋左上品牌＋底部左对齐大标题。
字号照 EP13 实测基准（2160×2880）：标题字形高≈180（font 195）、行距 250、品牌字形 81（font 88）。"""
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.expanduser('~/workspace/tl-ep13-work/assets')
FONTS = os.path.join(ASSETS, 'fonts')
ICON = os.path.join(ASSETS, 'logo', 'brand', 'account', 'icon-transparent-1024.png')
W, H = 2160, 2880
GOLD = (245, 185, 66); WHITE = (245, 248, 255)
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
im = Image.open(os.path.join(HERE, 'raw', 't_5_3.png')).convert('RGB').resize((W, H), Image.LANCZOS)
im = ImageEnhance.Color(im).enhance(1.05)
scrim(im); brand(im)
title(im, [[('为什么平分之后', WHITE)], [('还要', WHITE), ('再赢两分', GOLD), ('？', WHITE)]])
out = os.path.join(HERE, 'cover_final.jpg')
im.save(out, quality=92); print(out)
