"""vibetennis 第 5 集《为什么红土慢、草地快？》封面（不进视频）。

docs/vibetennis.md §6：每期至少 3 个风格方案。标题完整问句，左上角网球时差 logo 加文字对齐，金色为主。
  A 比特新语风：画面直接讲概念——三条泳道（红土 / 草地 / 硬地），同一颗球砸下去，弹出三条不同的轨迹（3D 底图 t=2.3）
  B 小作坊风：黑底，金色发光的三条弹跳弧（2D 绘制）；顶部问句、中间字距拉开的大标题、底部发球指数
  C 许先森风：3D 大场面——四座中心球场全景（3D 底图 t=150）
底图（r3d/ 下起着静态服务）：
    (cd r3d && COVER=1 W=2160 H=2880 PORT=8766 OUT=stills_cover node still_cover.js 2.3 158)
    (cd r3d && COVER=1 W=1920 H=1080 PORT=8766 OUT=stills_cover169 node still_cover.js 2.3 158)
    (cd r3d && COVER=1 W=1080 H=1920 PORT=8766 OUT=stills_cover916 node still_cover.js 2.3 158)
合成：python3 cover/make_cover.py A|B|C tall|wide|story <输出.jpg> [zh|en]
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


def title(d, size, k, x, y):
    if size == "wide":
        f = font(SERIF, 84 if LANG == "zh" else 64)
        runs(d, (x, y), T("为什么【红土】慢、", "Why is 【clay】 slow"), f, WH, GOLD)
        runs(d, (x, y + int(f.size * 1.25)), T("【草地】快？", "and 【grass】 fast?"), f, WH, GOLD)
        return y + int(f.size * 2.6)
    f = font(SERIF, int((170 if LANG == "zh" else 118) * k))
    runs(d, (x, y), T("为什么【红土】慢、", "Why is 【clay】 slow"), f, WH, GOLD)
    runs(d, (x, y + int(f.size * 1.22)), T("【草地】快？", "and 【grass】 fast?"), f, WH, GOLD)
    return y + int(f.size * 2.6)


def foot(d, size, k, x, y):
    f1 = font(SANS, int((58 if size != "wide" else 38) * (k if size != "wide" else 1)))
    f2 = font(SANSR, int((42 if size != "wide" else 28) * (k if size != "wide" else 1)))
    d.text((x, y), T("同一颗球，落地那几毫秒：是被咬住，还是一路滑", "Same ball, a few milliseconds: grip, or slide through"), font=f1, fill=WH)  # 2026-11-03 摩擦段自查：不是每次都会被咬住
    d.text((x, y + int(f1.size * 1.6)), T("摩擦系数：红土最高可达 0.9 · 草地 0.5–0.6", "Friction: clay up to 0.9 · grass 0.5–0.6"), font=f2, fill=GR)


def runs_multi(d, xy, s, f, base, his):
    """【】里的字依次用 his 里的颜色（第一个【】用 his[0]……）"""
    x, y = xy; on = False; n = -1
    for ch in s:
        if ch == "【": on = True; n += 1; continue
        if ch == "】": on = False; continue
        d.text((x, y), ch, font=f, fill=his[n] if on else base); x += d.textlength(ch, font=f)


def glow_text(img, xy, s, f, base, hi, blur, strength=1.0):
    """标题：高亮字（【】里）下面垫一层同色辉光，让金字在暗底上发光"""
    W, H = img.size
    his = hi if isinstance(hi, list) else [hi] * 9
    g = Image.new("RGB", (W, H), (0, 0, 0)); gd = ImageDraw.Draw(g)
    x, y = xy; on = False; n = -1
    for ch in s:
        if ch == "【": on = True; n += 1; continue
        if ch == "】": on = False; continue
        if on: gd.text((x, y), ch, font=f, fill=his[n])
        x += gd.textlength(ch, font=f)
    g = g.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(img).astype(np.float32) + np.asarray(g).astype(np.float32) * 0.9 * strength
    img.paste(Image.fromarray(a.clip(0, 255).astype(np.uint8)))
    runs_multi(ImageDraw.Draw(img), xy, s, f, base, his)


def ball_glow(img, pts, r):
    """三颗球再亮一点：加一圈柔光（加色混合）"""
    W, H = img.size; yy, xx = np.mgrid[0:H, 0:W]
    a = np.asarray(img).astype(np.float32)
    for (x, y), col in pts:
        d2 = ((xx - x) ** 2 + (yy - y) ** 2) / (r * r)
        m = np.exp(-d2)[..., None] * 0.55 + np.exp(-d2 * 9)[..., None] * 0.6
        a += m * np.array(col, np.float32)[None, None, :]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def lane_tag(img, x1, y, k, col, name, val, speed, word):
    """全息标签（右对齐到 x1）：地面名 ＋ 摩擦系数 ＋ 速度格（1–3 格），玻璃底、彩色描边"""
    fN = font(SANS, int(66 * k)); fV = font(INTER_B if LANG == "en" else SANS, int(44 * k)); fW = font(SANS, int(40 * k))
    d0 = ImageDraw.Draw(img)
    w = int(max(d0.textlength(name, font=fN) + 40 * k + 3 * 46 * k + d0.textlength(word, font=fW) + 30 * k, d0.textlength(val, font=fV)) + 90 * k)
    h = int(196 * k); x0 = x1 - w
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.rounded_rectangle((x0, y, x1, y + h), radius=int(26 * k), fill=(6, 12, 30, 178), outline=col + (235,), width=max(2, int(4 * k)))
    od.rounded_rectangle((x0 + int(14 * k), y + int(22 * k), x0 + int(24 * k), y + h - int(22 * k)), radius=int(5 * k), fill=col + (255,))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))
    d = ImageDraw.Draw(img); tx = x0 + int(52 * k)
    d.text((tx, y + int(22 * k)), name, font=fN, fill=WH)
    cx = tx + d.textlength(name, font=fN) + int(34 * k); cy = y + int(22 * k) + int(fN.size * 0.62)
    for i in range(3):   # 速度格：▶ 越多越快
        on = i < speed; px = cx + i * int(46 * k); hw = int(17 * k)
        d.polygon([(px, cy - hw), (px + hw + int(8 * k), cy), (px, cy + hw)], fill=col if on else (60, 70, 92))
    d.text((cx + 3 * int(46 * k) + int(10 * k), cy - int(fW.size * 0.62)), word, font=fW, fill=col)
    d.text((tx, y + int(118 * k)), val, font=fV, fill=GOLD)


def style_A(size, out):
    W, H = SIZES[size]; k = W / 2160 if size != "wide" else 1.0
    img = hero(2.15, size)  # 2026-11-03 再往右挪（LX+1.5）； 所有者 2026-11-02：球场线往右扩、右边别空——机位左移、取球刚过底线那一刻
    # 镜头改成正前方俯看（所有者：场地朝屏幕倾斜）后泳道整体偏上，三种尺寸都把画面整体下移，顶部留暗给标题，标题不压在红土上
    dy = {"wide": 170, "tall": 0, "story": 0}[size]   # 封面静帧另用 cover=1 退远的机位，泳道已经在下半部
    if dy: base = Image.new("RGB", (W, H), (2, 4, 10)); base.paste(img.crop((0, 0, W, H - dy)), (0, dy)); img = base
    if size == "wide": img = shade(img, 0.0001, 0.86, 0, 0.92)
    img = shade(img, 0.42 if size != "wide" else 0.0001, 0.80, 0.9, 0.9)
    if size == "wide":
        a = np.asarray(img).astype(np.float32); yy = np.linspace(0, 1, H)[:, None, None]; a *= 1 - np.clip(1 - yy / 0.45, 0, 1) ** 1.3 * 0.85
        img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    # 2026-11-03 所有者「封面再精致一些，第一眼抓住人」：标题金字发光、三颗球加柔光、每条泳道右侧挂全息标签
    # （地面名＋摩擦系数＋速度格），底部那两行说明撤掉——数字搬进标签里，一眼对上哪条地面多快
    import json
    an = json.load(open(HERE.parent / "r3d" / BASE[size] / "s_0002.15.json"))
    S = W / {"tall": 2160, "wide": 1920, "story": 1080}[size]
    P = {kk: (an["lane_" + kk][0] * S, an["lane_" + kk][1] * S + dy) for kk in ("RG", "WIM", "AO")}
    img = ball_glow(img, [(P["RG"], (255, 150, 70)), (P["WIM"], (150, 255, 140)), (P["AO"], (130, 200, 255))], int(70 * (k if size != "wide" else 0.6)))
    d = ImageDraw.Draw(img); logo(img, d, k if size != "wide" else 0.9)
    if size == "wide":
        kk, tx, ty = 1.0, 110, 270; ft = font(SERIF, 84 if LANG == "zh" else 64)
    else:
        kk, tx, ty = k, int(134 * k), int(360 * k); ft = font(SERIF, int((176 if LANG == "zh" else 120) * k))
    l1, l2 = T("为什么【红土】慢、", "Why is 【clay】 slow"), T("【草地】快？", "and 【grass】 fast?")
    CLAY, GRASS = (255, 140, 64), (120, 228, 100)   # 所有者 2026-11-03：「草地」用草地的绿色——红土也跟着用红土的橙色，和下面泳道同色
    glow_text(img, (tx, ty), l1, ft, WH, [CLAY], int(ft.size * 0.18)); glow_text(img, (tx, ty + int(ft.size * 1.22)), l2, ft, WH, [GRASS], int(ft.size * 0.18))
    d = ImageDraw.Draw(img); fs = font(SANS, int((54 if size != "wide" else 34) * (k if size != "wide" else 1)))
    d.text((tx + 4, ty + int(ft.size * 2.62)), T("同一颗球，落地那几毫秒：是被咬住，还是一路滑", "Same ball, a few milliseconds: grip, or slide through"), font=fs, fill=(200, 210, 225))
    tk = (k if size != "wide" else 0.55); xr = W - int(60 * tk) if size != "wide" else W - 40
    tags = [("RG", (255, 140, 70), T("红土", "Clay"), T("摩擦系数 最高 0.9", "Friction up to 0.9"), 1, T("慢", "SLOW")),
            ("WIM", (130, 240, 130), T("草地", "Grass"), T("摩擦系数 0.5–0.6", "Friction 0.5–0.6"), 3, T("快", "FAST")),
            ("AO", (120, 200, 255), T("硬地", "Hard"), T("看面漆里的沙子", "Depends on the grit"), 2, T("居中", "MID"))]
    for key, col, nm, val, sp, wd in tags:
        ty_ = int(P[key][1] + 70 * tk) if size != "wide" else min(int(P[key][1] - 98 * tk), H - int(206 * tk))   # 横版：标签和球同高，最下一条别出画
        lane_tag(img, xr, ty_, tk, col, nm, val, sp, wd)
    img.save(out, quality=94, subsampling=0)


def style_C(size, out):
    W, H = SIZES[size]; k = W / 2160 if size != "wide" else 1.0
    if size == "wide": img = hero(158.0, size)
    else:   # 竖版：用 16:9 全景按宽度铺在中间，上下留黑给标题
        wide = hero(158.0, "wide"); ww = W; wh = int(ww * 1080 / 1920); wide = wide.resize((ww, wh), Image.LANCZOS)
        img = Image.new("RGB", (W, H), (2, 4, 10)); img.paste(wide, (0, int(H * (0.50 if size == "tall" else 0.48)) - wh // 2))
    img = shade(img, 0.42 if size != "wide" else 0.0001, 0.80, 0.9, 0.9)
    if size == "wide":
        a = np.asarray(img).astype(np.float32); xx = np.linspace(0, 1, W)[None, :, None]; a *= 1 - np.clip(1 - xx / 0.62, 0, 1) ** 1.0 * 0.97
        img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img); logo(img, d, k if size != "wide" else 0.9)
    f3 = font(SANS, int((58 if size != "wide" else 38) * (k if size != "wide" else 1)))
    lab = T("四大满贯 · 四种比赛", "Four Slams · four different games")
    if size == "wide":
        y = title(d, size, 1, 110, 300); d.text((112, y + 10), lab, font=f3, fill=GOLD)
        d.text((112, 960), T("发球指数（2015–2026）：澳网 1.12 · 温网 1.09 · 美网 1.02 · 法网 0.75", "Serve index (2015–2026): AO 1.12 · WIM 1.09 · USO 1.02 · RG 0.75"), font=font(SANSR, 28), fill=GR)
    else:
        y = title(d, size, k, int(134 * k), int(360 * k)); d.text((int(140 * k), y + int(20 * k)), lab, font=f3, fill=GOLD)
        d.text((int(140 * k), int(H * 0.9)), T("发球指数（2015–2026）：澳网 1.12 · 温网 1.09 · 美网 1.02 · 法网 0.75", "Serve index (2015–2026): AO 1.12 · WIM 1.09 · USO 1.02 · RG 0.75"), font=font(SANSR, int(40 * k)), fill=GR)
    img.save(out, quality=94, subsampling=0)


def style_B(size, out):
    """黑底＋三条金色发光弹跳弧（同一入射，红土 / 硬地 / 草地 依次由高到低）"""
    W, H = SIZES[size]; k = W / 2160 if size != "wide" else 1.0; S = 2
    glow = Image.new("RGB", (W * S, H * S), (0, 0, 0)); g = ImageDraw.Draw(glow)
    if size == "wide": x0, x1, gy, sc = 700 * S, 1840 * S, 930 * S, 26 * S
    elif size == "story": x0, x1, gy, sc = 40 * S, 1040 * S, 1560 * S, 24 * S
    else: x0, x1, gy, sc = 100 * S, 2060 * S, 2420 * S, 46 * S
    xb = x0 + (x1 - x0) * 0.42
    VIN, ANG, Gr = 25, math.radians(16), 9.81
    lanes = [("RG", 0.9, 0.85, (255, 150, 80)), ("AO", 0.65, 0.75, (120, 200, 255)), ("WIM", 0.55, 0.67, (140, 255, 160))]
    tip = []; sx = (x1 - xb) / (24.03 * 0.85) * 0.95; sy = sx * 3.0   # 示意：竖直放大 3 倍
    for key, mu, e, colr in lanes:
        vx, vy = VIN * math.cos(ANG), VIN * math.sin(ANG); vx2 = max(vx - mu * (1 + e) * vy, 0.55 * vx); vy2 = e * vy
        pts = [(xb + vx * t * sx, gy - (-vy * t - 0.5 * Gr * t * t) * sy) for t in np.linspace(-0.55, 0, 40)]
        g.line(pts, fill=(255, 210, 120), width=6 * S)
        out_pts = [(xb + vx2 * t * sx, gy - (vy2 * t - 0.5 * Gr * t * t) * sy) for t in np.linspace(0, 0.85, 60)]
        g.line(out_pts, fill=colr, width=9 * S); tip.append((out_pts[-1], key, colr))
    g.line([(x0, gy), (x1, gy)], fill=(200, 170, 110), width=3 * S)
    g.ellipse([xb - 14 * S, gy - 14 * S, xb + 14 * S, gy + 14 * S], fill=(255, 235, 170))
    glow = glow.resize((W, H), Image.LANCZOS)
    bloom = glow.filter(ImageFilter.GaussianBlur(24 * k + 2)); bloom2 = glow.filter(ImageFilter.GaussianBlur(80 * k + 6))
    a = np.asarray(glow).astype(np.float32) + np.asarray(bloom).astype(np.float32) * 0.9 + np.asarray(bloom2).astype(np.float32) * 0.6
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img); logo(img, d, k if size != "wide" else 0.9)
    fl = font(SANS, 30 if size != "tall" else int(52 * k))
    for (px, py), key, colr in tip:
        lab = {"RG": T("红土", "Clay"), "AO": T("硬地", "Hard"), "WIM": T("草地", "Grass")}[key]
        d.text((px / S + 12, py / S - fl.size * 0.6), lab, font=fl, fill=colr)
    if size == "wide":
        title(d, size, 1, 110, 230)
        spaced(d, 330, 560, T("先滑 · 后咬住", "SLIDE · GRIP"), font(SERIF, 56), (245, 232, 200), 18)
        d.text((112, 980), T("摩擦系数：红土最高 0.9 · 草地 0.5–0.6（Cross, Physics Today 2008）", "Friction: clay up to 0.9 · grass 0.5–0.6 (Cross, Physics Today 2008)"), font=font(SANSR, 26), fill=GR)
    else:
        x = int(134 * k); y = title(d, size, k, x, int(330 * k))
        ft, gt = font(SERIF, int(120 * k)), int(26 * k); st = T("先 滑 · 后 咬 住", "SLIDE · GRIP")
        wt = sum(d.textlength(ch, font=ft) for ch in st) + gt * (len(st) - 1)
        spaced(d, x + wt / 2, y + int(40 * k), st, ft, (245, 232, 200), gt)
        spaced(d, x + wt / 2, y + int(200 * k), "COURT PACE · FRICTION · BOUNCE", font(INTER, int(38 * k)), GR, int(10 * k))
        d.text((x, int(H * 0.89)), T("摩擦系数：红土最高 0.9 · 草地 0.5–0.6", "Friction: clay up to 0.9 · grass 0.5–0.6"), font=font(SANS, int(50 * k)), fill=WH)
    img.save(out, quality=94, subsampling=0)


if __name__ == "__main__":
    style, size, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if len(sys.argv) > 4: LANG = sys.argv[4]
    {"A": style_A, "B": style_B, "C": style_C}[style](size, out)
