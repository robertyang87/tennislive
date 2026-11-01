"""vibetennis 第 4 集《费德勒只赢了 54% 的分，凭什么赢了 82% 的比赛？》封面（不进视频）。

docs/vibetennis.md §6：每期至少 3 个风格方案给所有者挑选。共同要求：标题是完整问句，左上角网球时差 logo 加文字对齐，
不加分类标签、不加装饰黄竖条，金色为主。§9：选定的方案再出 16:9 横版（嵌进成片）与 9:16 竖版。

  A 比特新语风：画面直接讲概念——四条 S 曲线（每分 / 局 / 盘 / 场）在 54% 处被扫描线读出 60 / 76 / 91（3D 底图 t=300.5）
  B 小作坊风：黑底，一个金色发光主视觉（54 → 60 → 76 → 91 的发光阶梯，2D 绘制）；顶部问句关键词高亮，
     中间字距拉开的大标题配英文，底部副标题＋核心公式
  C 许先森风：3D 大场面——比分河道，上千个模拟对局的粒子分流注入两个发光水库（3D 底图 t=302.5）

底图（r3d/ 下起着静态服务，在本集目录下运行）：
    (cd r3d && W=2160 H=2880 PORT=8766 OUT=stills_cover node still.js 300.5 302.5)
    (cd r3d && W=1920 H=1080 PORT=8766 OUT=stills_cover169 node still.js 300.5 302.5)
    (cd r3d && W=1080 H=1920 PORT=8766 OUT=stills_cover916 node still.js 300.5 302.5)
合成：
    python3 cover/make_cover.py A|B|C [tall|wide|story] <输出.jpg> [zh|en]
      tall＝3:4 2160×2880（推送海报）；wide＝16:9 1920×1080（片头与 YouTube）；story＝9:16 1080×1920
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[5]
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SANSR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
INTER = str(REPO / "assets/fonts/Inter-SemiBold.ttf")
INTER_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
MATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"   # 公式要上标 ⁴ 与减号 −，Inter 没有这两个字形
Y = (255, 200, 40); GOLD = (255, 186, 70); WH = (245, 245, 240); GR = (150, 158, 170); CY = (120, 220, 255)
SIZES = {"tall": (2160, 2880), "wide": (1920, 1080), "story": (1080, 1920)}
BASE = {"tall": "stills_cover", "wide": "stills_cover169", "story": "stills_cover916"}
LANG = "zh"


def T(zh, en):
    return en if LANG == "en" else zh


def font(path, size):
    if LANG == "en" and path in (SANS, SANSR):
        path = INTER_B if path == SANS else "/usr/share/fonts/opentype/inter/Inter-Regular.otf"
    return ImageFont.truetype(path, size, index=2) if path.endswith(".ttc") else ImageFont.truetype(path, size)


def logo(img, d, k):
    """左上：官方图标 + 网球时差（英文版 Tennis Jetlag），墨迹垂直居中对齐"""
    icon = Image.open(REPO / "assets/logo/brand/account/icon-transparent-1024.png").convert("RGBA").resize((int(64 * k), int(64 * k)), Image.LANCZOS)
    icon = icon.crop(icon.split()[3].point(lambda v: 255 if v > 40 else 0).getbbox())
    name = T("网球时差", "Tennis Jetlag")
    fT = font(SANS if LANG == "zh" else INTER_B, int(60 * k))
    m = Image.new("L", (int(1200 * k) + 200, int(200 * k) + 100), 0); ImageDraw.Draw(m).text((50, 50), name, font=fT, fill=255)
    tb = m.getbbox(); th = tb[3] - tb[1]
    CYv, x = int(210 * k), int(140 * k)
    img.paste(icon, (x, CYv - icon.size[1] // 2), icon); x += icon.size[0] + int(22 * k)
    d.text((x - (tb[0] - 50), CYv - th // 2 - (tb[1] - 50)), name, font=fT, fill=Y)


def runs(d, xy, s, f, base, hi, anchor="la"):
    """【】里的字用高亮色；anchor 'ma' 时整行水平居中"""
    x, y = xy
    if anchor == "ma":
        x -= sum(d.textlength(ch, font=f) for ch in s if ch not in "【】") / 2
    on = False
    for ch in s:
        if ch in "【】": on = ch == "【"; continue
        d.text((x, y), ch, font=f, fill=hi if on else base); x += d.textlength(ch, font=f)


def spaced(d, cx, y, s, f, fill, gap):
    w = sum(d.textlength(ch, font=f) for ch in s) + gap * (len(s) - 1); x = cx - w / 2
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + gap


def shade(img, top_end, bot_start, top_k=0.85, bot_k=0.86):
    W, H = img.size
    a = np.asarray(img).astype(np.float32) / 255
    yy = np.linspace(0, 1, H)[:, None, None]
    top = np.clip(1 - yy / top_end, 0, 1) ** 1.4 * top_k
    bot = np.clip((yy - bot_start) / (1 - bot_start), 0, 1) ** 1.4 * bot_k
    return Image.fromarray((np.clip(a * (1 - np.maximum(top, bot)), 0, 1) * 255).astype(np.uint8))


def hero(t, size):
    W, H = SIZES[size]
    return Image.open(HERE.parent / "r3d" / BASE[size] / f"s_{t:07.2f}.jpg").convert("RGB").resize((W, H), Image.LANCZOS)


def headline(d, size, k):
    """完整问句：只赢 54% 的分，凭什么赢下 82% 的比赛？"""
    W, H = SIZES[size]
    if size == "wide":
        f = font(SERIF, int(96 * k)) if LANG == "zh" else font(SERIF, int(78 * k))
        runs(d, (int(130 * k), int(300 * k)), T("只赢 【54%】 的分，", "He won 【54%】 of points."), f, WH, GOLD)
        runs(d, (int(130 * k), int(300 * k) + int(130 * k)), T("凭什么赢下 【82%】 的比赛？", "How did he win 【82%】 of matches?"), f, WH, GOLD)
        return
    f = font(SERIF, int((150 if LANG == "zh" else 112) * k))
    y0 = int(330 * k); gap = int((190 if LANG == "zh" else 150) * k)
    runs(d, (int(134 * k), y0), T("只赢 【54%】 的分，", "He won 【54%】"), f, WH, GOLD)
    runs(d, (int(134 * k), y0 + gap), T("凭什么赢下", "of points. How did"), f, WH, GOLD)
    runs(d, (int(134 * k), y0 + 2 * gap), T("【82%】 的比赛？", "he win 【82%】 of matches?"), f, WH, GOLD)


def ladder_line(d, x, y, f, k):
    s = T("每一分 54% → 一局 60% → 一盘 76% → 一场 91%", "Point 54% → Game 60% → Set 76% → Match 91%")
    d.text((x, y), s, font=f, fill=WH)


def style_A(size, out):
    W, H = SIZES[size]; k = W / 2160 if size != "wide" else W / 1920 * 1.0
    img = shade(hero(300.5, size), 0.40 if size != "wide" else 0.0001, 0.78 if size != "wide" else 0.80, 0.9, 0.9)
    if size == "wide":
        img = shade(img, 0.0001, 0.80, 0, 0.85)
        a = np.asarray(img).astype(np.float32); xx = np.linspace(0, 1, W)[None, :, None]; a *= 1 - np.clip(1 - xx / 0.55, 0, 1) ** 1.2 * 0.85
        img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img); logo(img, d, k if size != "wide" else 0.9)
    headline(d, size, k if size != "wide" else 1.0)
    if size == "wide":
        ladder_line(d, 130, 620, font(SANS, 40), 1); d.text((130, 690), T("马尔可夫链 · 计分把微小的优势层层放大", "Markov chains: scoring amplifies a tiny edge"), font=font(SANSR, 30), fill=GR)
    else:
        by = int(H * 0.83)
        ladder_line(d, int(140 * k), by, font(SANS, int(62 * k)), k)
        d.text((int(146 * k), by + int(130 * k)), T("马尔可夫链：网球的计分，把微小的优势层层放大", "Markov chains: tennis scoring amplifies a tiny edge, layer by layer"), font=font(SANSR, int(44 * k)), fill=GR)
    img.save(out, quality=94, subsampling=0)


def style_C(size, out):
    W, H = SIZES[size]; k = W / 2160
    img = shade(hero(302.5, size), 0.40 if size != "wide" else 0.0001, 0.80, 0.9, 0.9)
    if size == "wide":
        a = np.asarray(img).astype(np.float32); xx = np.linspace(0, 1, W)[None, :, None]; a *= 1 - np.clip(1 - xx / 0.6, 0, 1) ** 1.2 * 0.85
        img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img); logo(img, d, k if size != "wide" else 0.9)
    headline(d, size, k if size != "wide" else 1.0)
    if size == "wide":
        d.text((130, 620), T("1200 局模拟对局，每分 54%：", "1,200 simulated games at 54% per point:"), font=font(SANS, 40), fill=WH)
        d.text((130, 680), T("赢局 60% · 输局 40%", "60% won · 40% lost"), font=font(SANS, 56), fill=GOLD)
    else:
        by = int(H * 0.84)
        d.text((int(140 * k), by), T("1200 局，每分都按 54% 掷骰子", "1,200 games, every point at 54%"), font=font(SANS, int(66 * k)), fill=WH)
        d.text((int(140 * k), by + int(100 * k)), T("赢下来的局：60%", "Games won: 60%"), font=font(SANS, int(84 * k)), fill=GOLD)
    img.save(out, quality=94, subsampling=0)


def style_B(size, out):
    """黑底＋金色发光阶梯（2D 绘制）：54 → 60 → 76 → 91"""
    W, H = SIZES[size]; k = W / 2160 if size != "wide" else 1.0
    S = 2
    glow = Image.new("RGB", (W * S, H * S), (0, 0, 0)); g = ImageDraw.Draw(glow)
    vals = [54, 60, 76, 91]; labs = [T("一分", "POINT"), T("一局", "GAME"), T("一盘", "SET"), T("一场", "MATCH")]
    if size == "wide":
        x0, x1, base, top = 1080 * S, 1820 * S, 900 * S, 300 * S
    elif size == "story":
        x0, x1, base, top = 140 * S, 940 * S, 1500 * S, 820 * S
    else:
        x0, x1, base, top = 260 * S, 1900 * S, 2330 * S, 1420 * S
    n = len(vals); bw = (x1 - x0) / n * 0.56
    pts = []
    for i, v in enumerate(vals):
        cx = x0 + (x1 - x0) * (i + 0.5) / n; h = (base - top) * (v - 40) / 60
        g.rectangle([cx - bw / 2, base - h, cx + bw / 2, base], outline=(255, 190, 80), width=6 * S)
        for yy in range(int(base - h), int(base), 18 * S):
            g.line([(cx - bw / 2, yy), (cx + bw / 2, yy)], fill=(120, 80, 25), width=2 * S)
        g.rectangle([cx - bw / 2, base - h - 6 * S, cx + bw / 2, base - h + 6 * S], fill=(255, 225, 150))
        pts.append((cx, base - h))
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        g.line([(ax, ay), (bx, by)], fill=(255, 210, 120), width=4 * S)
    g.line([(x0 - 40 * S, base), (x1 + 40 * S, base)], fill=(200, 170, 110), width=3 * S)
    glow = glow.resize((W, H), Image.LANCZOS)
    bloom = glow.filter(ImageFilter.GaussianBlur(24 * k + 2)); bloom2 = glow.filter(ImageFilter.GaussianBlur(80 * k + 6))
    a = np.asarray(glow).astype(np.float32) + np.asarray(bloom).astype(np.float32) * 0.9 + np.asarray(bloom2).astype(np.float32) * 0.6
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img); logo(img, d, k if size != "wide" else 0.9)
    fn = font(INTER_B, int((96 if size != "story" else 64) * k if size != "wide" else 58))
    fl = font(SANS, int((48 if size != "story" else 40) * k if size != "wide" else 30))
    for (cx, cy), v, lab in zip(pts, vals, labs):
        cx, cy = cx / S, cy / S
        t = f"{v}%"; d.text((cx - d.textlength(t, font=fn) / 2, cy - fn.size * 1.35), t, font=fn, fill=GOLD if v != 54 else CY)
        d.text((cx - d.textlength(lab, font=fl) / 2, base / S + fl.size * 0.6), lab, font=fl, fill=WH)
    if size == "wide":
        f = font(SERIF, 78 if LANG == "zh" else 64)
        runs(d, (120, 300), T("只赢 【54%】 的分，", "He won 【54%】 of points."), f, WH, GOLD)
        runs(d, (120, 410), T("凭什么赢下 【82%】 的比赛？", "How did he win 【82%】?"), f, WH, GOLD)
        spaced(d, 480, 590, T("层层放大", "AMPLIFIED"), font(SERIF, 64), (235, 225, 200), 24)
        d.text((120, 720), "P(game) = p⁴(1+4q+10q²) + 20p³q³·p²/(1−2pq)", font=ImageFont.truetype(MATH, 26), fill=GR)
    else:
        headline(d, size, k)
        my = int(H * (0.385 if size == "tall" else 0.33))
        spaced(d, W / 2, my, T("层 层 放 大", "AMPLIFIED"), font(SERIF, int(96 * k)), (235, 225, 200), int(30 * k))
        spaced(d, W / 2, my + int(140 * k), "MARKOV CHAIN · 1906", font(INTER, int(40 * k)), GR, int(14 * k))
        by = int(H * (0.86 if size == "tall" else 0.86))
        d.text((int(140 * k), by), T("每一分只多赢 1%，五盘三胜就从 50% 变成 63%", "Win 1% more points: best-of-five goes 50% → 63%"), font=font(SANS, int(60 * k)), fill=WH)
        d.text((int(146 * k), by + int(110 * k)), "P(game) = p⁴(1+4q+10q²) + 20p³q³·p²/(1−2pq)", font=ImageFont.truetype(MATH, int(42 * k)), fill=GR)
    img.save(out, quality=94, subsampling=0)


if __name__ == "__main__":
    style, size, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if len(sys.argv) > 4: LANG = sys.argv[4]
    {"A": style_A, "B": style_B, "C": style_C}[style](size, out)
