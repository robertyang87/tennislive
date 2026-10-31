"""vibetennis 第 2 集《电子司线，真的准吗？》封面（3:4，2160×2880，不进视频）。

docs/vibetennis.md §6：每期至少出 3 个风格方案给所有者挑选或混搭。共同要求：标题是完整问句，
左上角网球时差 logo 加文字对齐，不加分类标签、不加装饰黄竖条，金色为主。

  A 比特新语风：画面直接讲概念——低机位贴着底线，12 道视线汇聚到将落地的球（3D 底图 t=300.5）
  B 小作坊风：黑底，一个金色发光主视觉（压在线上的球、接触椭圆、汇聚的视线、毫米尺，2D 绘制）；
     顶部问句关键词高亮，中间字距拉开的大标题配英文，底部副标题＋核心数字
  C 许先森风：3D 大场面，高空斜俯整座球场，视线在球上汇聚（3D 底图 t=302.5）

底图（r3d/ 下起着静态服务，在本集目录下运行）：
    W=2160 H=2880 OUT=r3d/stills_cover node r3d/still.js 300.5 302.5
合成：
    python3 cover/make_cover.py A r3d/stills_cover/s_0300.50.jpg poster_A.jpg
    python3 cover/make_cover.py B - poster_B.jpg
    python3 cover/make_cover.py C r3d/stills_cover/s_0302.50.jpg poster_C.jpg
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[5]
W, H = 2160, 2880
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SANSR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SC = 2  # TTC 里简中的序号
INTER = str(REPO / "assets/fonts/Inter-SemiBold.ttf")
Y = (255, 200, 40); GOLD = (255, 186, 70); WH = (245, 245, 240); GR = (150, 158, 170)


def font(path, size):
    return ImageFont.truetype(path, size, index=SC) if path.endswith(".ttc") else ImageFont.truetype(path, size)


def logo(img, d):
    """左上：官方图标 + 网球时差，墨迹垂直居中对齐（第 1 集 v9 的写法）"""
    icon = Image.open(REPO / "assets/logo/brand/account/icon-transparent-1024.png").convert("RGBA").resize((64, 64), Image.LANCZOS)
    icon = icon.crop(icon.split()[3].point(lambda v: 255 if v > 40 else 0).getbbox())
    fT = font(SANS, 60)
    m = Image.new("L", (800, 200), 0); ImageDraw.Draw(m).text((50, 50), "网球时差", font=fT, fill=255)
    tb = m.getbbox(); th = tb[3] - tb[1]
    CY, x = 210, 140
    img.paste(icon, (x, CY - icon.size[1] // 2), icon); x += icon.size[0] + 22
    d.text((x - (tb[0] - 50), CY - th // 2 - (tb[1] - 50)), "网球时差", font=fT, fill=Y)


def runs(d, xy, s, f, base, hi):
    """【】里的字用高亮色"""
    x, y = xy; on = False
    for ch in s:
        if ch in "【】": on = ch == "【"; continue
        d.text((x, y), ch, font=f, fill=hi if on else base); x += d.textlength(ch, font=f)


def spaced(d, cx, y, s, f, fill, gap):
    w = sum(d.textlength(ch, font=f) for ch in s) + gap * (len(s) - 1); x = cx - w / 2
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + gap


def shade(img, top_end, bot_start, top_k=0.85, bot_k=0.86):
    a = np.asarray(img).astype(np.float32) / 255
    yy = np.linspace(0, 1, H)[:, None, None]
    top = np.clip(1 - yy / top_end, 0, 1) ** 1.4 * top_k
    bot = np.clip((yy - bot_start) / (1 - bot_start), 0, 1) ** 1.4 * bot_k
    return Image.fromarray((np.clip(a * (1 - np.maximum(top, bot)), 0, 1) * 255).astype(np.uint8))


def style_A(hero_path, out):
    img = shade(Image.open(hero_path).convert("RGB").resize((W, H), Image.LANCZOS), 0.40, 0.70)
    d = ImageDraw.Draw(img); logo(img, d)
    ftt = font(SERIF, 212)
    d.text((134, 280), "电子司线", font=ftt, fill=WH)
    runs(d, (134, 510), "【真的准吗】？", ftt, WH, Y)
    d.text((150, 800), "H O W   E L E C T R O N I C   L I N E   C A L L I N G   S E E S", font=font(INTER, 38), fill=GR)
    f1 = font(SERIF, 124)
    d.text((140, 2420), "回放里那个椭圆，", font=f1, fill=WH)
    d.text((140, 2580), "不是拍下来的", font=f1, fill=Y)
    d.text((146, 2770), "以 Hawk-Eye 为例：多台相机的视线交会成轨迹，落点是算出来的", font=font(SANS, 44), fill=GR)
    img.save(out, quality=94, subsampling=0)


def style_B(_hero, out):
    """黑底＋金色发光主视觉（2D 绘制）"""
    S = 2  # 超采样
    glow = Image.new("RGB", (W * S, H * S), (0, 0, 0)); g = ImageDraw.Draw(glow)
    cx, cy = W * S // 2, int(H * 0.56) * S         # 球心
    R = 210 * S                                      # 球半径
    flat = 34 * S                                    # 压扁量
    gy = cy + R - flat                               # 地面高度
    # 线：地面上一条亮白偏金的线带，外沿正好穿过接触区
    g.rectangle([0, gy - 6 * S, W * S, gy + 6 * S], fill=(120, 105, 70))
    g.rectangle([0, gy - 2 * S, W * S, gy + 2 * S], fill=(255, 235, 190))
    # 12 道视线：从上方一圈点汇聚到球心
    for i in range(12):
        a = math.pi * (1.08 + 0.84 * i / 11)
        sx, sy = cx + math.cos(a) * 2600 * S, cy + math.sin(a) * 2200 * S
        g.line([(sx, sy), (cx, cy)], fill=(255, 175, 60), width=4 * S)
        for k in range(1, 14):                        # 光点从远处流向球（视线方向示意）
            u = k / 14; px, py = sx + (cx - sx) * u, sy + (cy - sy) * u
            g.ellipse([px - 5 * S, py - 5 * S, px + 5 * S, py + 5 * S], fill=(255, 210, 120))
    # 球：发光的金色轮廓，底部被地面压平
    ring = Image.new("L", glow.size, 0); rd = ImageDraw.Draw(ring)
    rd.ellipse([cx - R, cy - R, cx + R, cy + R], outline=255, width=16 * S)
    rd.rectangle([0, gy, W * S, H * S], fill=0)
    rd.line([(cx - math.sqrt(R * R - (R - flat) ** 2), gy), (cx + math.sqrt(R * R - (R - flat) ** 2), gy)], fill=255, width=10 * S)
    glow.paste((255, 205, 90), (0, 0), ring)
    # 接触椭圆（落在线上）
    a2 = math.sqrt(R * R - (R - flat) ** 2)
    g.ellipse([cx - a2, gy - 30 * S, cx + a2, gy + 30 * S], fill=(255, 190, 70))
    # 毫米尺
    for k in range(-40, 41):
        x = cx + k * 22 * S; h = (34 if k % 10 == 0 else 22 if k % 5 == 0 else 12) * S
        g.line([(x, gy + 70 * S), (x, gy + 70 * S + h)], fill=(200, 180, 140), width=2 * S)
    glow = glow.resize((W, H), Image.LANCZOS)
    bloom = glow.filter(ImageFilter.GaussianBlur(28)); bloom2 = glow.filter(ImageFilter.GaussianBlur(90))
    a = np.asarray(glow).astype(np.float32) + np.asarray(bloom).astype(np.float32) * 1.7 + np.asarray(bloom2).astype(np.float32) * 1.6
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    img = shade(img, 0.30, 0.80, 0.9, 0.9)
    d = ImageDraw.Draw(img); logo(img, d)
    # 顶部：完整问句，关键词高亮
    fq = font(SERIF, 150)
    runs(d, (134, 330), "电子司线，", fq, WH, GOLD)
    runs(d, (134, 520), "【真的准吗】？", fq, WH, GOLD)
    # 中间：字距拉开的大标题＋英文小字
    spaced(d, W / 2, 760, "毫 米 之 争", font(SERIF, 96), (235, 225, 200), 30)
    spaced(d, W / 2, 900, "ELECTRONIC LINE CALLING", font(INTER, 40), GR, 14)
    # 底部：副标题＋核心数字
    d.text((140, 2440), "回放里那个椭圆，不是拍下来的", font=font(SANS, 70), fill=WH)
    d.text((140, 2560), "离线 5 mm 以外", font=font(SANS, 96), fill=WH)
    d.text((140 + d.textlength("离线 5 mm 以外", font=font(SANS, 96)) + 30, 2546), "= 100% 判对", font=font(SANS, 110), fill=GOLD)
    d.text((146, 2770), "ITF 最高一级认证：离线 5–100 mm 的测试球必须全部判对", font=font(SANSR, 44), fill=GR)
    img.save(out, quality=94, subsampling=0)


def style_C(hero_path, out):
    # 仿第 1 集：球场竖直居中，标题在球场上方，副标题在底线下方（所有者 2026-10-30：别斜着放、别压球场）
    img = shade(Image.open(hero_path).convert("RGB").resize((W, H), Image.LANCZOS), 0.28, 0.80, 0.85, 0.9)
    d = ImageDraw.Draw(img); logo(img, d)
    ftt = font(SERIF, 168)
    d.text((134, 270), "电子司线", font=ftt, fill=WH)
    runs(d, (134, 455), "【真的准吗】？", ftt, WH, Y)
    f1 = font(SERIF, 96)
    d.text((140, 2440), "12 台相机盯着一颗球，", font=f1, fill=WH)
    d.text((140, 2570), "落点却是算出来的", font=f1, fill=Y)
    d.text((146, 2760), "温网每块场地 12 台相机 · 以 Hawk-Eye 为例", font=font(SANS, 44), fill=GR)
    img.save(out, quality=94, subsampling=0)


if __name__ == "__main__":
    style, hero, out = sys.argv[1], sys.argv[2], sys.argv[3]
    {"A": style_A, "B": style_B, "C": style_C}[style](hero, out)
