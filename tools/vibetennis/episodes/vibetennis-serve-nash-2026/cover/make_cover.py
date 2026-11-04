"""vibetennis 第 6 集《发球，该往哪边发？》封面（不进视频）。

docs/vibetennis.md §6：每期至少 3 个风格方案。标题完整问句，左上角网球时差 logo 加文字对齐，金色为主。
  A 钩子：抛球冻在最高点，两条发球轨迹一左一右分叉（3D 底图 t=3.6，片头那一幕）
  B 石头剪刀布：布吃掉石头（3D 底图 t=43.6，第二局亮出）——冯·诺依曼 1928 原文举的就是它
  C 证据：1,056 块方砖，56 块亮红＝5.3%（3D 底图 t=95.0）
底图都用 16:9（r3d/ 下起着静态服务）：
    (cd r3d && COVER=1 W=1920 H=1080 PORT=8771 OUT=stills_cover169 node still_cover.js 3.6 43.6 95.0)
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
BASE = "stills_cover169"   # 三种尺寸都用横版底图：场景机位按 16:9 摆，竖版直接渲会把主体裁掉
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




OPT = {  # 底图时刻、裁掉顶部比例（A 的底图上方是片中的 3D 问句，封面自己排标题就裁掉）、副题、一行注
    "A": (3.6, 0.30, T, ("答案是一个拿过诺贝尔奖的理论", "The answer won a Nobel Prize"), ("纳什均衡 · 混着发，让对手往哪边猜都不占便宜", "Nash equilibrium · mix it so no guess pays off")),
    "B": (43.6, 0.0, T, ("就像石头剪刀布：总出一样，一定会输", "Like rock-paper-scissors: always the same, always lose"), ("冯·诺依曼 1928 · 纳什 1950", "von Neumann 1928 · Nash 1950")),
    "C": (95.0, 0.0, T, ("2,151 场男子比赛，重做论文里的检验", "2,151 men's matches, the papers' test redone"), ("外角 65.0% · 中路 64.7% · 只有 5.3% 偏离理论", "Wide 65.0% · T 64.7% · only 5.3% deviate")),
}


def base(t, crop):
    im = Image.open(HERE.parent / "r3d" / BASE / f"s_{t:07.2f}.jpg").convert("RGB")
    if crop: im = im.crop((0, int(im.size[1] * crop), im.size[0], im.size[1]))
    return im


def feather(im, top=0.18, bot=0.22):
    a = np.asarray(im).astype(np.float32); h = a.shape[0]; yy = np.linspace(0, 1, h)[:, None, None]
    m = np.clip(yy / top, 0, 1) ** 1.2 * np.clip((1 - yy) / bot, 0, 1) ** 1.2
    return Image.fromarray((a * m).clip(0, 255).astype(np.uint8))


def title_lines(d, x, y, f, anchor="la"):
    runs(d, (x, y), T("发球，", "Serve:"), f, WH, GOLD, anchor)
    runs(d, (x, y + int(f.size * 1.22)), T("该往【哪边】发？", "which 【side】?"), f, WH, GOLD, anchor)
    return y + int(f.size * 2.5)


def make(style, size, out):
    W, H = SIZES[size]; t, crop, _, sub, note = OPT[style]
    img = Image.new("RGB", (W, H), (4, 6, 16)); bg = base(t, crop)
    if size == "wide":
        hero = bg.resize((W, int(bg.size[1] * W / bg.size[0])), Image.LANCZOS)
        img.paste(hero, ({"A": 0, "B": 520, "C": 560}[style], H - hero.size[1]))   # 主体右移，左边留给标题
        a = np.asarray(img).astype(np.float32); xx = np.linspace(0, 1, W)[None, :, None]
        a *= 1 - np.clip(1 - xx / 0.62, 0, 1) ** 1.3 * 0.82; img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
        d = ImageDraw.Draw(img); logo(img, d, 0.9)
        y = title_lines(d, 112, 300, font(SERIF, 96 if LANG == "zh" else 72))
        d.text((114, y + 30), sub[LANG == "en"], font=font(SANS, 40), fill=(245, 232, 200))
        d.text((114, 990), note[LANG == "en"], font=font(SANSR, 28), fill=GR)
    else:
        k = W / 2160
        bh = int(H * 0.56); hw = int(bg.size[0] * bh / bg.size[1]); hero = bg.resize((hw, bh), Image.LANCZOS)   # 主图按高铺满中段，左右裁
        cx = {"A": 0.62, "B": 0.48, "C": 0.5}[style]; x0 = int(min(max(0, hw * cx - W / 2), hw - W)); hero = feather(hero.crop((x0, 0, x0 + W, bh)), 0.14, 0.2)
        img.paste(hero, (0, int(H * 0.33)))
        d = ImageDraw.Draw(img); logo(img, d, k)
        y = title_lines(d, int(134 * k), int(360 * k), font(SERIF, int((200 if LANG == "zh" else 150) * k)))
        d.text((int(138 * k), y + int(10 * k)), sub[LANG == "en"], font=font(SANS, int(64 * k)), fill=(245, 232, 200))
        d.text((int(138 * k), int(H * 0.90)), note[LANG == "en"], font=font(SANS, int(52 * k)), fill=WH)
    img.save(out, quality=94, subsampling=0)


if __name__ == "__main__":
    style, size, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if len(sys.argv) > 4: LANG = sys.argv[4]
    make(style, size, out)
