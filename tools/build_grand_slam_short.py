"""生成《网球四大满贯》竖屏科普样片（1080×1920）。

按 data/grand_slam_video.json 的分镜规格，用 Pillow 合成每个镜头（电影感「灯光球场」
背景 + 亮色大标题 + 赛事分区 + 底部描边字幕），再用 ffmpeg 加轻微 Ken Burns、
淡入淡出并拼接成片。

版权：静态画面只用仓库内可复用授权图（CC / 公有领域），片中**不烧录署名**，署名改由
`发布文案.txt` 的致谢承载（CC 许可要求署名，公有领域/CC0 除外）；需要官方比赛画面的
镜头输出醒目占位卡，由你在拿到授权后填入。脚本没有下载器，不抓取任何受版权保护的视频。

用法：
    pip install Pillow imageio-ffmpeg
    python tools/build_grand_slam_short.py --overwrite

可选：--voiceover a.mp3（自备/授权配音）、--tts（edge-tts，需可访问语音服务）、--overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"

YELLOW = (245, 190, 40)
YELLOW_SHADOW = (110, 20, 10)
WHITE = (245, 247, 250)
MUTED = (155, 167, 182)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        sys.exit(f"找不到 ffmpeg，请 `pip install imageio-ffmpeg`（{exc}）")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def F_BLACK(sz):
    return font("NotoSerifSC-Black-sub.ttf", sz)


def F_BOLD(sz):
    return font("NotoSansSC-Bold-sub.ttf", sz)


def F_REG(sz):
    return font("NotoSansSC-Regular-sub.ttf", sz)


def F_LATIN(sz):
    return font("BarlowCondensed-Bold.ttf", sz)


def hex2rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# 电影感背景：深色渐变 + 球场聚光 + 透视球场线 + 暗角
# ---------------------------------------------------------------------------
def cinematic_bg(w: int, h: int, accent=(245, 190, 40)) -> Image.Image:
    top, mid, bot = (6, 8, 13), (14, 19, 28), (4, 6, 10)
    col = Image.new("RGB", (1, h))
    cpx = col.load()
    for y in range(h):
        t = y / h
        if t < 0.5:
            f, a, b_ = t / 0.5, top, mid
        else:
            f, a, b_ = (t - 0.5) / 0.5, mid, bot
        cpx[0, y] = tuple(int(a[k] + (b_[k] - a[k]) * f) for k in range(3))
    base = col.resize((w, h))

    # 上方聚光晕（用 accent 淡淡上色）
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    cx, cy, rad = w // 2, int(h * 0.30), int(w * 0.72)
    gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    tint = Image.new("RGB", (w, h), tuple(min(255, int(c * 0.9 + 30)) for c in accent))
    base = Image.composite(Image.blend(base, tint, 0.5), base, glow)

    # 透视半场线（真实规格投影：站在底线后看向球网）
    # 半场纵深 11.885m（底线→网），发球线距网 6.40m；双打宽 10.97m、单打 8.23m。
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    lc = (*accent, 46)
    lc2 = (*accent, 34)
    DEPTH, SVC_FROM_NET, CAM = 11.885, 6.40, 6.0   # 米；CAM=视点在底线后方距离
    yb, yf = h * 0.94, h * 0.58                      # 底线 / 网 的屏幕高度
    half_near = w * 0.46                             # 底线处双打半宽（屏幕）

    def proj(z):
        """底线起纵深 z 米 → (屏幕y, 宽度缩放)。针孔模型：尺度 ∝ 1/(CAM+z)。"""
        t = (z * (CAM + DEPTH)) / (DEPTH * (CAM + z))
        return yb + (yf - yb) * t, CAM / (CAM + z)

    def xpos(frac_half_width, z):
        _, s = proj(z)
        return w / 2 + frac_half_width * half_near * s

    z_svc = DEPTH - SVC_FROM_NET                     # 底线→发球线 5.485m
    y_base, _ = proj(0.0)
    y_svc, _ = proj(z_svc)
    y_net, _ = proj(DEPTH)
    SGL = 8.23 / 10.97                               # 单打线相对双打半宽
    for frac in (-1.0, -SGL, SGL, 1.0):              # 双打+单打边线
        od.line([(xpos(frac, 0), y_base), (xpos(frac, DEPTH), y_net)],
                fill=lc if abs(frac) == 1.0 else lc2, width=3)
    od.line([(xpos(-1, 0), y_base), (xpos(1, 0), y_base)], fill=lc, width=4)      # 底线
    od.line([(xpos(-SGL, z_svc), y_svc), (xpos(SGL, z_svc), y_svc)], fill=lc2, width=2)  # 发球线
    od.line([(xpos(-1, DEPTH), y_net), (xpos(1, DEPTH), y_net)], fill=lc, width=2)       # 网
    od.line([(w / 2, y_svc), (w / 2, y_net)], fill=lc2, width=2)   # 中央发球线：仅发球线→网
    od.line([(w / 2, y_base - 14), (w / 2, y_base)], fill=lc, width=3)  # 底线中点标记
    base = Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB")

    # 暗角
    vig = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-int(w * 0.35), -int(h * 0.18), int(w * 1.35), int(h * 1.18)], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    base = Image.composite(base, dark, vig)
    return base


def fit_cover(img, box_w, box_h, focal=(0.5, 0.5)):
    src_w, src_h = img.size
    scale = max(box_w / src_w, box_h / src_h)
    nw, nh = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = max(0, min(int((nw - box_w) * focal[0]), nw - box_w))
    top = max(0, min(int((nh - box_h) * focal[1]), nh - box_h))
    return img.crop((left, top, left + box_w, top + box_h))


def rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width, img.height], radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def wrap_cjk(text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if fnt.getlength(cur + ch) <= max_w or not cur:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def center(draw, cx, y, text, fnt, fill, shadow=None, off=(6, 7)):
    x = cx - fnt.getlength(text) / 2
    if shadow:
        draw.text((x + off[0], y + off[1]), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def pill(draw, cx, cy, text, fnt, bg, fg, pad_x=28, height=None):
    """圆角药丸：文字以 anchor=mm 精确对中（修复中文视觉偏下）。"""
    h = height or int(fnt.size * 1.7)
    w = fnt.getlength(text) + pad_x * 2
    x0, y0 = cx - w / 2, cy - h / 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h // 2, fill=bg)
    draw.text((cx, cy - fnt.size * 0.04), text, font=fnt, fill=fg, anchor="mm")


def outline(draw, xy, text, fnt, fill=WHITE, oc=(0, 0, 0), width=5):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width:
                draw.text((x + dx, y + dy), text, font=fnt, fill=oc)
    draw.text((x, y), text, font=fnt, fill=fill)


def brand_mark(img, brand):
    """统一 logo 形态：品牌黄圆点 + 文字，无外框。"""
    d = ImageDraw.Draw(img)
    f = F_BOLD(36)
    pad = 48
    cy = pad + 20
    d.ellipse([pad, cy - 10, pad + 20, cy + 10], fill=YELLOW)
    d.text((pad + 34, cy), brand, font=f, fill=WHITE, anchor="lm")


def progress_dots(img, active):
    if not active:
        return
    d = ImageDraw.Draw(img)
    W = img.width
    gap, r = 46, 9
    x0 = W / 2 - (3 * gap) / 2
    y = img.height - 150
    for i in range(4):
        cx = x0 + i * gap
        on = (i + 1) == active
        if on:
            d.ellipse([cx - r - 3, y - r - 3, cx + r + 3, y + r + 3], fill=(0, 0, 0))
        d.ellipse([cx - r, y - r, cx + r, y + r], fill=YELLOW if on else (70, 78, 92))


def section_header(img, section):
    d = ImageDraw.Draw(img)
    W = img.width
    color = hex2rgb(section["color"])
    y = 150
    center(d, W / 2, y, section.get("en", ""), F_LATIN(60), YELLOW)
    center(d, W / 2, y + 74, section.get("zh", ""), F_BOLD(46), WHITE)


def caption_band(img, caption):
    if not caption:
        return
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    fnt = F_BOLD(60)
    lines = wrap_cjk(caption, fnt, W - 150)
    lh = 82
    y0 = H - 300 - lh * len(lines)
    for i, ln in enumerate(lines):
        x = W / 2 - fnt.getlength(ln) / 2
        outline(d, (x, y0 + i * lh), ln, fnt, fill=WHITE, oc=(0, 0, 0), width=6)


def render_title(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img)
    big = scene.get("big", [])
    fnt = F_BLACK(180)
    y = H / 2 - len(big) * 105 - 130
    for line in big:
        center(d, W / 2, y, line, fnt, YELLOW, shadow=YELLOW_SHADOW, off=(8, 10))
        y += 210
    if scene.get("sub"):
        center(d, W / 2, y + 24, scene["sub"], F_BOLD(50), WHITE)
    brand_mark(img, meta["brand"])
    return img


def render_section(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img, "RGBA")
    sec = scene["section"]
    # 背景大写城市水印
    word = sec.get("word", "")
    if word:
        fw = F_LATIN(220)
        center(d, W / 2, H / 2 - 250, word, fw, (*accent, 40))
    # 主标题
    center(d, W / 2, H / 2 - 40, sec["en"], F_LATIN(120), YELLOW,
           shadow=YELLOW_SHADOW, off=(6, 8))
    center(d, W / 2, H / 2 + 120, sec["zh"], F_BOLD(58), WHITE)
    # 场地条
    surf = sec.get("surface", "")
    ft = F_BOLD(38)
    tw = ft.getlength(surf) + 64
    bx0 = W / 2 - tw / 2
    by0 = H / 2 + 214
    d.rounded_rectangle([bx0, by0, bx0 + tw, by0 + 60], radius=30, fill=accent)
    center(d, W / 2, by0 + 9, surf, ft, (8, 10, 14))
    court = sec.get("court", "")
    seats = sec.get("seats", "")
    if court:
        center(d, W / 2, by0 + 96, court, F_BOLD(42), WHITE)
    if seats:
        center(d, W / 2, by0 + 156, seats, F_BOLD(44), accent)
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_photo(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    # 照片卡：圆角 + accent 发光边，浮在背景上
    card_w, card_h = W - 120, int(H * 0.52)
    card_x, card_y = 60, int(H * 0.24)
    src = Image.open(ROOT / scene["image"]).convert("RGB")
    photo = fit_cover(src, card_w, card_h, scene.get("focal", [0.5, 0.5]))
    card = rounded(photo, 32)
    # 柔和投影（无描边框）
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([card_x - 4, card_y + 14, card_x + card_w + 4, card_y + card_h + 26],
                         radius=36, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    img = Image.alpha_composite(img.convert("RGBA"), shadow)
    img.paste(card, (card_x, card_y), card)
    img = img.convert("RGB")
    # 卡内上下压暗，便于分区标题/字幕
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(90):
        a = int(150 * (1 - i / 90))
        d.line([(card_x, card_y + i), (card_x + card_w, card_y + i)], fill=(6, 8, 12, a))
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_placeholder(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img)
    section_header(img, scene["section"])
    slot = scene["slot"]
    bx0, by0, bx1, by1 = 90, int(H * 0.34), W - 90, int(H * 0.70)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=28, outline=accent, width=4)
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2 - 60
    d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=accent, width=5)
    d.polygon([(cx - 24, cy - 34), (cx - 24, cy + 34), (cx + 40, cy)], fill=accent)
    center(d, W / 2, cy + 92, "插入官方授权集锦", F_BOLD(48), accent)
    for i, ln in enumerate(wrap_cjk(slot["desc"], F_REG(34), bx1 - bx0 - 80)):
        center(d, W / 2, cy + 162 + i * 46, ln, F_REG(34), WHITE)
    center(d, W / 2, by1 - 58, f"素材：{slot['source']} · 约 {slot['secs']} 秒", F_REG(30), MUTED)
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def resolve_img(path, key):
    """若 assets/local/<key>.<ext> 存在则优先用本地自备图（不入库）；否则用规格里的图。"""
    if key:
        for ext in ("jpg", "jpeg", "png", "webp"):
            cand = ROOT / "assets" / "local" / f"{key}.{ext}"
            if cand.exists():
                return str(cand)
    return path


def paste_rounded_photo(base, path, x, y, w, h, focal=(0.5, 0.5), radius=22,
                        border=None, bw=0, key=None):
    p = Path(resolve_img(path, key))
    src = Image.open(p if p.is_absolute() else ROOT / p).convert("RGB")
    card = rounded(fit_cover(src, w, h, focal), radius)
    rgba = base.convert("RGBA")
    rgba.paste(card, (x, y), card)
    out = rgba.convert("RGB")
    if border and bw:
        ImageDraw.Draw(out).rounded_rectangle([x, y, x + w, y + h], radius=radius,
                                              outline=border, width=bw)
    return out


def render_triptych(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    card_x, card_y = 60, int(H * 0.24)
    card_w, card_h = W - 120, int(H * 0.52)
    panels = scene["panels"]
    gap = 14
    pw = (card_w - gap * (len(panels) - 1)) // len(panels)
    for i, p in enumerate(panels):
        px = card_x + i * (pw + gap)
        col = hex2rgb(p["color"])
        img = paste_rounded_photo(img, p["image"], px, card_y, pw, card_h,
                                  tuple(p.get("focal", [0.5, 0.5])), radius=18)
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_collage(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    card_x, card_y = 60, int(H * 0.215)
    card_w, card_h = W - 120, int(H * 0.55)
    cells = scene["cells"]
    cols, rows, gap = 3, 2, 12
    cw = (card_w - gap * (cols - 1)) // cols
    ch = (card_h - gap * (rows - 1)) // rows
    for i, c in enumerate(cells[:cols * rows]):
        r, cc = divmod(i, cols)
        img = paste_rounded_photo(img, c["image"], card_x + cc * (cw + gap),
                                  card_y + r * (ch + gap), cw, ch,
                                  tuple(c.get("focal", [0.5, 0.4])), radius=16)
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_grid4(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    card_x, card_y = 60, int(H * 0.215)
    card_w, card_h = W - 120, int(H * 0.55)
    cells = scene["cells"]
    gap = 14
    cw = (card_w - gap) // 2
    ch = (card_h - gap) // 2
    for i, c in enumerate(cells[:4]):
        r, cc = divmod(i, 2)
        x = card_x + cc * (cw + gap)
        y = card_y + r * (ch + gap)
        col = hex2rgb(c.get("color", "#f2b32a"))
        if c.get("placeholder") or not c.get("image"):
            d0 = ImageDraw.Draw(img, "RGBA")
            d0.rounded_rectangle([x, y, x + cw, y + ch], radius=18,
                                 fill=(18, 22, 30), outline=col, width=4)
            note = c.get("note", "插入授权画面")
            fn = F_BOLD(34)
            lines = wrap_cjk(note, fn, cw - 70)
            for j, ln in enumerate(lines):
                center(d0, x + cw / 2, y + ch / 2 - 40 + j * 44, ln, fn, col)
        else:
            img = paste_rounded_photo(img, c["image"], x, y, cw, ch,
                                      tuple(c.get("focal", [0.5, 0.4])), radius=18,
                                      key=c.get("local_key"))
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_courtcard(meta, scene, W, H):
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    d = ImageDraw.Draw(img, "RGBA")
    sec = scene.get("section", {})
    center(d, W / 2, 140, sec.get("en", ""), F_LATIN(58), YELLOW)
    center(d, W / 2, 214, sec.get("zh", ""), F_BOLD(42), WHITE)
    cx, cy = 60, int(H * 0.21)
    cw, ch = W - 120, int(H * 0.46)
    img = paste_rounded_photo(img, scene["image"], cx, cy, cw, ch,
                              tuple(scene.get("focal", [0.5, 0.5])), radius=28,
                              key=scene.get("local_key"))
    d = ImageDraw.Draw(img, "RGBA")
    court, seats = scene.get("court", ""), scene.get("seats", "")
    yb = cy + ch + 56
    if court:
        center(d, W / 2, yb, court, F_BOLD(56), WHITE)
    if seats:
        pill(d, W / 2, yb + 126, seats, F_BOLD(56), accent, (8, 10, 14),
             pad_x=36, height=84)
    credit = scene.get("credit", "")
    if credit:
        d.text((44, H - 92), credit, font=F_REG(24), fill=(150, 160, 172))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


def render_logogrid(meta, scene, W, H):
    """四大满贯官方 logo 2x2：白色圆角卡托底，深色电影背景。"""
    accent = hex2rgb(scene.get("accent", "#f2b32a"))
    img = cinematic_bg(W, H, accent)
    card_x, card_y = 90, int(H * 0.24)
    card_w, card_h = W - 180, int(H * 0.50)
    gap = 26
    cw = (card_w - gap) // 2
    ch = (card_h - gap) // 2
    rgba = img.convert("RGBA")
    for i, c in enumerate(scene["cells"][:4]):
        r, cc = divmod(i, 2)
        x = card_x + cc * (cw + gap)
        y = card_y + r * (ch + gap)
        card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, cw, ch], radius=30, fill=(255, 255, 255, 246))
        logo = Image.open(ROOT / c["logo"]).convert("RGBA")
        box = int(min(cw, ch) * 0.72)
        s = min(box / logo.width, box / logo.height)
        logo = logo.resize((int(logo.width * s), int(logo.height * s)), Image.LANCZOS)
        card.paste(logo, ((cw - logo.width) // 2, (ch - logo.height) // 2), logo)
        rgba.paste(card, (x, y), card)
    img = rgba.convert("RGB")
    section_header(img, scene["section"])
    caption_band(img, scene.get("caption", ""))
    brand_mark(img, meta["brand"])
    progress_dots(img, scene.get("index", 0))
    return img


RENDERERS = {"title": render_title, "section": render_section,
             "logogrid": render_logogrid,
             "photo": render_photo, "placeholder": render_placeholder,
             "triptych": render_triptych, "collage": render_collage,
             "grid": render_grid4, "courtcard": render_courtcard}


def srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(scenes, path):
    out, t, idx = [], 0.0, 1
    for sc in scenes:
        vo = sc.get("vo", "").strip()
        dur = float(sc["dur"])
        if vo:
            out += [str(idx), f"{srt_time(t)} --> {srt_time(t + dur)}", vo, ""]
            idx += 1
        t += dur
    path.write_text("\n".join(out), encoding="utf-8")


def write_description(scenes, meta, path):
    """发布文案：标题候选 + 简介 + 话题 + 图片致谢（CC 许可需署名，放这里）。"""
    seen, credits = set(), []
    def add(c):
        c = (c or "").strip()
        if c and c not in seen:
            seen.add(c)
            credits.append(f"· {c}")
    for sc in scenes:
        add(sc.get("credit"))
        for p in sc.get("panels", []):
            add(p.get("credit"))
        for cell in sc.get("cells", []):
            add(cell.get("credit"))
    lines = [
        "【标题候选】",
        "网球四大满贯，一个视频看懂它们的性格",
        "四大满贯，网球人一生想征服的四座球场",
        "硬地·红土·草地，四大满贯到底有什么不同？",
        "",
        "【简介】",
        "澳网的热烈、法网的坚韧、温网的优雅、美网的疯狂——"
        "四片战场，四种荣耀。关注@" + meta["brand"] + "，一起看懂每一场巅峰对决。",
        "",
        "【话题】",
        "#网球 #四大满贯 #澳网 #法网 #温网 #美网 #网球科普 #网球时差",
        "",
        "【画面素材致谢（CC 许可要求署名，故放在简介）】",
    ]
    lines += credits if credits else ["·（若全部替换为自有/授权素材，可删除本段）"]
    lines += [
        "· 公有领域/CC0 素材无需署名；官方集锦请按你取得的授权标注。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _audio_dur(ff, path):
    r = subprocess.run([ff, "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _synth_edge(text, dst, voice, rate):
    import asyncio
    import ssl

    import edge_tts
    import edge_tts.communicate as ec
    ca = "/root/.ccr/ca-bundle.crt"
    if Path(ca).exists():
        ec._SSL_CTX = ssl.create_default_context(cafile=ca)
    asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(dst)))


def _synth_gtts(text, dst):
    from gtts import gTTS
    gTTS(text, lang="zh-CN").save(str(dst))


def _piper_model():
    """离线神经语音模型路径：env PIPER_MODEL 或 assets/local/piper/*.onnx。"""
    envp = os.environ.get("PIPER_MODEL")
    if envp and Path(envp).exists():
        return envp
    d = ROOT / "assets" / "local" / "piper"
    if d.exists():
        for f in sorted(d.glob("*.onnx")):
            return str(f)
    return None


def _synth_piper(text, dst, model):
    subprocess.run(["piper", "-m", model, "-f", str(dst)], input=text, text=True,
                   check=True, capture_output=True)


def try_tts(scenes, meta, outdir, ff):
    """生成中文配音（原创解说文案）。优先 edge-tts（音质更好），不可用时回退 gTTS。
    每句按镜头时长对齐：过长则加速，过短则补静音，保证音画同步。"""
    voice = meta.get("voice", "zh-CN-YunjianNeural")
    rate = meta.get("voice_rate", "+8%")
    tdir = outdir / "_tts"
    tdir.mkdir(exist_ok=True)
    probe = next((s["vo"] for s in scenes if s.get("vo", "").strip()), "测试")
    piper_model = _piper_model()
    candidates = [("edge", ".mp3", lambda t, d: _synth_edge(t, d, voice, rate))]
    if piper_model:  # 离线神经语音，音质远好于 gTTS
        candidates.append(("piper", ".wav", lambda t, d: _synth_piper(t, d, piper_model)))
    candidates.append(("gtts", ".mp3", lambda t, d: _synth_gtts(t, d)))
    engine = ext = synth = None
    for name, e, fn in candidates:
        try:
            fn(probe, tdir / ("probe" + e))
            engine, ext, synth = name, e, fn
            break
        except Exception as exc:
            print(f"  · {name} 配音不可用（{type(exc).__name__}）")
    if not engine:
        print("  · 无可用 TTS，输出静音；用 captions.srt / narration.txt 自行配音。")
        return None
    print(f"  · 配音引擎：{engine}")

    def silence(dst, dur):
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", f"{dur:.3f}", str(dst)], check=True, capture_output=True)

    clips = []
    for i, sc in enumerate(scenes):
        vo = sc.get("vo", "").strip()
        dur = float(sc["dur"])
        raw = tdir / f"v{i:02d}{ext}"
        if vo:
            try:
                synth(vo, raw)
            except Exception:
                silence(raw, 0.4)
        else:
            silence(raw, 0.4)
        ad = _audio_dur(ff, raw)
        af = []
        if ad > dur > 0:
            af.append(f"atempo={min(ad / dur, 1.8):.3f}")
        af.append("apad")
        fit = tdir / f"f{i:02d}.mp3"
        subprocess.run([ff, "-y", "-i", str(raw), "-af", ",".join(af), "-t", f"{dur:.3f}",
                        "-ar", "44100", str(fit)], check=True, capture_output=True)
        clips.append(fit)
    lst = tdir / "list.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    out = outdir / "voiceover.mp3"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:a", "libmp3lame", "-b:a", "192k", str(out)],
                   check=True, capture_output=True, cwd=str(tdir))
    return out


def storyboard_sheet(frames, path, cols=4):
    thumbs = [Image.open(p).resize((270, 480)) for p in frames]
    rows = (len(thumbs) + cols - 1) // cols
    pad = 12
    sheet = Image.new("RGB", (cols * 270 + (cols + 1) * pad, rows * 480 + (rows + 1) * pad),
                      (16, 18, 24))
    for i, th in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(th, (pad + c * (270 + pad), pad + r * (480 + pad)))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="data/grand_slam_video.json")
    ap.add_argument("--outdir", default="output/grand-slam-vertical")
    ap.add_argument("--voiceover", default=None)
    ap.add_argument("--tts", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    ff = _ffmpeg()
    spec = json.loads((ROOT / args.spec).read_text(encoding="utf-8"))
    meta = spec["meta"]
    W, H, FPS = meta["width"], meta["height"], meta["fps"]
    scenes = spec["scenes"]

    outdir = ROOT / args.outdir
    final = outdir / "grand-slam.mp4"
    if final.exists() and not args.overwrite:
        sys.exit(f"{final} 已存在，加 --overwrite 覆盖。")
    frames_dir, clips_dir = outdir / "frames", outdir / "_clips"
    for d in (outdir, frames_dir, clips_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"合成 {len(scenes)} 个镜头 …")
    frame_paths, clip_paths = [], []
    for i, sc in enumerate(scenes):
        img = RENDERERS[sc["type"]](meta, sc, W, H)
        fp = frames_dir / f"{sc['id']}.png"
        img.save(fp)
        frame_paths.append(fp)
        dur = float(sc["dur"])
        nframes = int(dur * FPS)
        clip = clips_dir / f"{i:02d}.mp4"
        vf = (
            f"scale={W}:{H},zoompan=z='min(zoom+0.00045,1.05)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nframes}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur-0.3:.2f}:d=0.3,format=yuv420p"
        )
        subprocess.run([ff, "-y", "-loop", "1", "-i", str(fp), "-t", f"{dur}", "-r", str(FPS),
                        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
                       check=True, capture_output=True)
        clip_paths.append(clip)
        print(f"  [{i+1:2d}/{len(scenes)}] {sc['id']} ({dur:.0f}s)")

    lst = clips_dir / "concat.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clip_paths), encoding="utf-8")
    silent = outdir / "_silent.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(silent)], check=True, capture_output=True, cwd=str(clips_dir))

    total = sum(float(s["dur"]) for s in scenes)
    audio = None
    if args.voiceover:
        audio = ROOT / args.voiceover
    elif args.tts:
        audio = try_tts(scenes, meta, outdir, ff)

    if audio and Path(audio).exists():
        subprocess.run([ff, "-y", "-i", str(silent), "-i", str(audio), "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)],
                       check=True, capture_output=True)
    else:
        subprocess.run([ff, "-y", "-i", str(silent), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:v", "copy", "-c:a", "aac", "-t", f"{total:.2f}", "-shortest",
                        str(final)], check=True, capture_output=True)

    write_srt(scenes, outdir / "captions.srt")
    (outdir / "narration.txt").write_text(
        "\n".join(s["vo"].strip() for s in scenes if s.get("vo")), encoding="utf-8")
    write_description(scenes, meta, outdir / "发布文案.txt")
    shutil.copy(frame_paths[0], outdir / "cover.png")
    storyboard_sheet(frame_paths, outdir / "storyboard.png")

    shutil.rmtree(clips_dir, ignore_errors=True)
    silent.unlink(missing_ok=True)
    shutil.rmtree(outdir / "_tts", ignore_errors=True)

    print(f"\n完成：{final}  ({total:.0f}s, {final.stat().st_size/1e6:.1f} MB)")
    print(f"  分镜连拍：{outdir/'storyboard.png'} · 字幕：{outdir/'captions.srt'} · 发布文案：{outdir/'发布文案.txt'}")
    if not (audio and Path(audio).exists()):
        print("  · 当前为静音样片：用剪映/CapCut 文本朗读或人声，按 captions.srt 配音即可。")


if __name__ == "__main__":
    main()
