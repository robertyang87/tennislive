#!/usr/bin/env python3
"""Designed cover for wta-finals-alternate-2026 (1080x1440, series tokens).
Layout follows the hotmic v2 compliant geometry (owner ruling 2026-11-06):
- 12px spectrum brand bar (design_tokens BRAND_BAR_CSS)
- standard top-left title block: 52px brand icon + brand line 38px
  (ink top y47) + topic line 27px bold (ink top y100), left x70/136
- motif: the two finals groups as seat panels; Rybakina's seat dashed and
  empty, Kostyuk's arrival as one brand chip under the panels; motif fully
  clear of the title block and of the hook zone
- hook at ink tops y800/y917, left x70, 94px display, both lines cream
  upright bold with hook shadow; nothing below y~1030, so the cover
  segment's narration subtitles land in a clean band (y>=1284).
Topic: 年终第一退赛，第一替补满格入场 (15 chars, <=30 gate; ink ~420px ~39%)
"""
import sys
sys.path.insert(0, "/home/hatch/workspace/finals-alternate-20261108/prod/anim")
from anim_common import *
from render_anims import dashed_rect, GROUPS

ICON = "/home/hatch/workspace/tlrun/assets/logo/brand/icon.png"
TOPIC_HEX = (220, 239, 228)
TOPIC = "年终第一退赛，第一替补满格入场"

img = BG.copy()
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([540 - 420, 560 - 420, 540 + 420, 560 + 420], fill=(109, 166, 236, 60))
glow = glow.filter(ImageFilter.GaussianBlur(90))
img.alpha_composite(glow)
d = ImageDraw.Draw(img, "RGBA")

def tracked(drw, x, y_top, text, font, fill, tracking=1):
    b0 = drw.textbbox((0, 0), text, font=font)
    cx = x - b0[0]
    xs0, xs1 = None, None
    for ch in text:
        b = drw.textbbox((0, 0), ch, font=font)
        drw.text((cx - b[0], y_top - b[1]), ch, font=font, fill=fill)
        xs0 = cx + b[0] if xs0 is None else min(xs0, cx + b[0])
        xs1 = cx + b[2] if xs1 is None else max(xs1, cx + b[2])
        cx += (b[2] - b[0]) + tracking
    return (xs0, y_top, xs1, y_top + (b0[3] - b0[1]))

def shadowed_text(base, draw_fn, blur=5, dy=2, alpha=150):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    draw_fn(sd, (0, 0, 0, alpha), dy)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(sh)
    dd = ImageDraw.Draw(base, "RGBA")
    draw_fn(dd, None, 0)
    return dd

# ---- 1. spectrum brand bar ----
stops = [(0.0, (198, 246, 90)), (0.34, (55, 226, 154)),
         (0.67, (255, 90, 106)), (1.0, (75, 184, 255))]
bar = Image.new("RGBA", (W, 12), (0, 0, 0, 255))
bd = ImageDraw.Draw(bar)
for x in range(W):
    t = x / (W - 1)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]; t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            col = lerp(c0, c1, (t - t0) / (t1 - t0)); break
    bd.line([x, 0, x, 11], fill=col + (255,))
img.alpha_composite(bar, (0, 0))
d = ImageDraw.Draw(img, "RGBA")

# ---- 2. standard title block ----
icon = Image.open(ICON).convert("RGBA").resize((52, 52), Image.LANCZOS)
img.alpha_composite(icon, (70, 59))
d = ImageDraw.Draw(img, "RGBA")
F_BRAND = ImageFont.truetype(DISPLAY, 38)
F_TOPIC = ImageFont.truetype(CJK_B, 27)
topic_box = {}

def _head(dd, shadow_fill, dy):
    if shadow_fill is not None:
        tracked(dd, 136, 47 + dy, "网球时差 · 网球有故事", F_BRAND, shadow_fill)
        tracked(dd, 136, 100 + dy, TOPIC, F_TOPIC, shadow_fill)
    else:
        tracked(dd, 136, 47, "网球时差 · 网球有故事", F_BRAND, CREAM + (255,))
        topic_box['b'] = tracked(dd, 136, 100, TOPIC, F_TOPIC, TOPIC_HEX + (255,))

d = shadowed_text(img, _head, blur=6, dy=2, alpha=150)

# ---- 3. motif: group seat panels (y250..640), Rybakina seat empty ----
F_GHEAD = ImageFont.truetype(CJK_B, 27)
F_SEAT = ImageFont.truetype(CJK_B, 30)
for gi, ((gname, names), px0) in enumerate(zip(GROUPS, [70, 560])):
    panel(d, px0, 250, px0 + 450, 640, 1.0)
    text_l(d, px0 + 24, 272, gname, F_GHEAD, with_a(FAINT, 235))
    for idx, name in enumerate(names):
        r, c = divmod(idx, 2)
        x0 = px0 + 18 + c * (201 + 12)
        y0 = 322 + r * (128 + 12)
        x1, y1 = x0 + 201, y0 + 128
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if name == "莱巴金娜":
            dashed_rect(d, x0, y0, x1, y1, with_a(CREAM_DIM, 210))
            b = ink(d, name, F_SEAT)
            d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), name,
                   font=F_SEAT, fill=with_a(FAINT, 45))
        else:
            d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=with_a(PANEL, 235),
                                outline=with_a(CREAM_DIM, 150), width=2)
            b = ink(d, name, F_SEAT)
            d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), name,
                   font=F_SEAT, fill=with_a(CREAM, 255))
chip(d, 540, 706, "科斯秋克 · 第一替补 (ALT)", ImageFont.truetype(CJK_B, 34), BRAND, BRAND)

# ---- 4. hook (ink tops y800/y917, left x70, display 94, cream) ----
F_HOOK = ImageFont.truetype(DISPLAY, 94)
hook_box = {}

def _hook(dd, shadow_fill, dy):
    if shadow_fill is not None:
        text_l(dd, 70, 800 + dy, "她全年排第十", F_HOOK, shadow_fill)
        text_l(dd, 70, 917 + dy, "怎么捧起总决赛奖杯？", F_HOOK, shadow_fill)
    else:
        text_l(dd, 70, 800, "她全年排第十", F_HOOK, CREAM + (255,))
        b = ink(dd, "怎么捧起总决赛奖杯？", F_HOOK)
        text_l(dd, 70, 917, "怎么捧起总决赛奖杯？", F_HOOK, CREAM + (255,))
        hook_box['w'] = b[2] - b[0]

sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(sh)
_hook(sd, (0, 0, 0, 235), 6)
img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(15)))
sh2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd2 = ImageDraw.Draw(sh2)
_hook(sd2, (0, 0, 0, 235), 2)
img.alpha_composite(sh2.filter(ImageFilter.GaussianBlur(3)))
d = ImageDraw.Draw(img, "RGBA")
_hook(d, None, 0)

out = "/home/hatch/workspace/finals-alternate-20261108/prod/wta-finals-alternate-2026-cover.png"
img.convert("RGB").save(out)
tb = topic_box['b']
print("saved", out)
print(f"topic ink: x {tb[0]:.0f}..{tb[2]:.0f} width {tb[2]-tb[0]:.0f}px = {(tb[2]-tb[0])/1080*100:.0f}% of frame")
print(f"hook line2 ink width: {hook_box['w']:.0f}px (right edge {70 + hook_box['w']:.0f})")
