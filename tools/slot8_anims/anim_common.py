#!/usr/bin/env python3
"""Zverev No.1 story episode: four code-drawn animation segments (A1..A4).
Series visual language per walkover style-audit final standard (2026-10-30):
tokens from design_tokens.py DARK, mid-tier glow (R445/blur52/peak180/core
(109,166,236), rim #304D76), own-title ink top >= 190 (builder title block
clearance), chips/text blocks centred on ink bbox (<=2px), 1080x1440 30fps.
Motion grammar borrowed from lemo-opuscar styles (see anim-plan.md):
dataviz (marks land one at a time, verdict after settle), data-physical
(feed: units arrive piece by piece, counter rolls with landings),
briefing-board (evidence rows pinned sequentially, one reading per screen).
Usage: python3 render_anims.py [a1|a2|a3|a4|all] [duration_seconds]
Output: zv-aX-<name>-v<N>.mp4 in this dir (new filename per version).
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1440, 30
FD = "/home/hatch/workspace/tlrun/assets/fonts"
INTER = f"{FD}/Inter-SemiBold.ttf"
DISPLAY = f"{FD}/SmileySans-Oblique.ttf"      # 得意黑 titles
TLSCORE = f"{FD}/TLScore-Bold.ttf"
TLSCORE_R = f"{FD}/TLScore-Regular.ttf"
CJK_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

CREAM = (244, 251, 247)      # foreground #F4FBF7
CREAM_DIM = (207, 230, 216)  # muted-foreground #CFE6D8
FAINT = (169, 188, 178)      # subtle-foreground #A9BCB2
BRAND = (198, 246, 90)       # primary #C6F65A
GREEN = (74, 220, 140)       # win #4ADC8C
RED = (255, 90, 106)         # loss #FF5A6A
PANEL = (21, 36, 58)         # card #15243A
RIM = (48, 77, 118)          # glow rim #304D76

def clamp01(v): return max(0.0, min(1.0, v))
def ease(t): return 1 - (1 - clamp01(t)) ** 3
def ease_io(t):
    t = clamp01(t); return t * t * (3 - 2 * t)
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
def with_a(c, a): return (c[0], c[1], c[2], int(max(0, min(255, a))))

# ---------- background: series gradient + mid-tier glow + vignette ----------
def build_bg():
    R, blur, peak, core = 445, 52, 180, (109, 166, 236)
    arr = np.zeros((H, W, 3), np.float32)
    stops = [(0.0, (11, 17, 33)), (0.45, (15, 25, 46)), (0.78, (21, 35, 58)), (1.0, (28, 44, 66))]
    for y in range(H):
        t = y / H
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]; t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                arr[y, :, :] = lerp(c0, c1, (t - t0) / (t1 - t0)); break
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(R, 40, -14):
        f = 1 - r / R
        a = int(peak * f ** 1.7)
        col = lerp(RIM, core, f ** 1.5)
        gd.ellipse([W / 2 - r, 1130 - r * 0.6, W / 2 + r, 1130 + r * 0.6], fill=with_a(col, a))
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img, glow)

BG = build_bg()
yy, xx = np.mgrid[0:H, 0:W]
dist = np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.72)) ** 2)
VIG = np.clip(1 - 0.32 * np.clip(dist - 0.55, 0, 1) ** 1.6, 0.62, 1.0).astype(np.float32)

_NOISE_FIELDS = []

def finish(img, t):
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    global _NOISE_FIELDS
    if not _NOISE_FIELDS:
        for k in range(30):
            _NOISE_FIELDS.append(np.random.default_rng(k + 7).normal(0, 2.6, (H, W, 1)))
    noise = _NOISE_FIELDS[int(t * FPS) % 30]
    return Image.fromarray(np.clip((arr + noise) * VIG[..., None], 0, 255).astype(np.uint8))

def fade_io(img, t, dur, fi=0.7, fo=0.6):
    a = min(ease(t / fi), ease((dur - t) / fo))
    return Image.blend(Image.new("RGB", (W, H), (5, 8, 16)), img.convert("RGB"), a)

# ---------- ink-centred text helpers ----------
def ink(d, text, font):
    b = d.textbbox((0, 0), text, font=font)
    return b  # (x0,y0,x1,y1)

def text_c(d, cx, y_top, text, font, fill):
    """draw with ink horizontally centred at cx; y_top = ink top."""
    b = ink(d, text, font)
    d.text((cx - (b[0] + b[2]) / 2, y_top - b[1]), text, font=font, fill=fill)
    return b[3] - b[1]

def text_l(d, x, y_top, text, font, fill):
    b = ink(d, text, font)
    d.text((x - b[0], y_top - b[1]), text, font=font, fill=fill)
    return b[3] - b[1]

def chip(d, cx, cy, text, font, fg, outline, fill_a=0, pad_x=20, pad_y=12, width=2):
    """chip whose box = ink + symmetric padding; ink centred both axes."""
    b = ink(d, text, font)
    iw, ih = b[2] - b[0], b[3] - b[1]
    cw, ch = iw + 2 * pad_x, ih + 2 * pad_y
    x0, y0 = cx - cw / 2, cy - ch / 2
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=ch // 2,
                        fill=with_a(PANEL, fill_a) if fill_a else None,
                        outline=with_a(outline, 255), width=width)
    d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), text, font=font, fill=with_a(fg, 255))
    return cw, ch

def title_block(d, t, en, cn, sub=None):
    """own title: EN kicker ink top ~196, CN title below; clears builder block."""
    a = ease((t - 0.25) / 0.8)
    if a <= 0: return
    f_en = ImageFont.truetype(INTER, 34)
    # spaced EN kicker, centred on ink
    sp = 8
    widths = [d.textlength(ch, font=f_en) for ch in en]
    total = sum(widths) + sp * (len(en) - 1)
    b0 = d.textbbox((0, 0), en[0], font=f_en)
    x = W / 2 - total / 2
    for ch, w in zip(en, widths):
        d.text((x, 196 - b0[1]), ch, font=f_en, fill=with_a(CREAM_DIM, 235 * a))
        x += w + sp
    f_cn = ImageFont.truetype(DISPLAY, 66)
    text_c(d, W / 2, 246, cn, f_cn, with_a(CREAM, 255 * a))
    lw = 190 * ease((t - 0.55) / 0.8)
    d.line([W / 2 - lw, 348, W / 2 + lw, 348], fill=with_a(BRAND, 220 * a), width=3)
    if sub:
        f_s = ImageFont.truetype(CJK_R, 30)
        text_c(d, W / 2, 366, sub, f_s, with_a(FAINT, 230 * a))

def panel(d, x0, y0, x1, y1, a, outline_a=150):
    d.rounded_rectangle([x0, y0, x1, y1], radius=18,
                        fill=with_a(PANEL, int(190 * a)),
                        outline=with_a(CREAM_DIM, int(outline_a * a)), width=2)

def render(frames_fn, dur, out):
    n = int(FPS * dur)
    proc = subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                             "-preset", "veryfast", "-movflags", "+faststart", out],
                            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for i in range(n):
        proc.stdin.write(fade_io(finish(frames_fn(i / FPS), i / FPS), i / FPS, dur).tobytes())
    proc.stdin.close(); proc.wait()
    print("rendered", out, f"{dur}s")
