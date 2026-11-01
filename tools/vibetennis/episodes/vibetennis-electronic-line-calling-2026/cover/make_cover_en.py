"""vibetennis 第 2 集英文版封面（品牌 Tennis Jetlag）：版式照搬中文版 C 方案（make_cover.style_C），文字换成英文。

    python3 cover/make_cover_en.py r3d/stills_cover/s_0302.50.jpg poster_en.jpg
"""
import sys
from PIL import Image, ImageDraw
import make_cover as mc

SERIF_L = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"   # 拉丁字形同中文版标题
INTER_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
INTER_R = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"


def logo_en(img, d):
    icon = Image.open(mc.REPO / "assets/logo/brand/account/icon-transparent-1024.png").convert("RGBA").resize((64, 64), Image.LANCZOS)
    icon = icon.crop(icon.split()[3].point(lambda v: 255 if v > 40 else 0).getbbox())
    fT = mc.font(INTER_B, 58)
    m = Image.new("L", (1000, 200), 0); ImageDraw.Draw(m).text((50, 50), "Tennis Jetlag", font=fT, fill=255)
    tb = m.getbbox(); th = tb[3] - tb[1]
    CY, x = 210, 140
    img.paste(icon, (x, CY - icon.size[1] // 2), icon); x += icon.size[0] + 22
    d.text((x - (tb[0] - 50), CY - th // 2 - (tb[1] - 50)), "Tennis Jetlag", font=fT, fill=mc.Y)


def style_C_en(hero_path, out):
    img = mc.shade(Image.open(hero_path).convert("RGB").resize((mc.W, mc.H), Image.LANCZOS), 0.28, 0.80, 0.85, 0.9)
    d = ImageDraw.Draw(img); logo_en(img, d)
    d.text((134, 290), "Electronic line calling:", font=mc.font(SERIF_L, 140), fill=mc.WH)
    mc.runs(d, (134, 470), "【How accurate is it?】", mc.font(SERIF_L, 168), mc.WH, mc.Y)
    f1 = mc.font(SERIF_L, 92)
    d.text((140, 2440), "12 cameras watch one ball,", font=f1, fill=mc.WH)
    d.text((140, 2570), "yet the bounce is calculated", font=f1, fill=mc.Y)
    d.text((146, 2760), "12 cameras per court at Wimbledon · Hawk-Eye as the example", font=mc.font(INTER_R, 44), fill=mc.GR)
    img.save(out, quality=94, subsampling=0)


if __name__ == "__main__":
    style_C_en(sys.argv[1], sys.argv[2])
