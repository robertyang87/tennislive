"""vibetennis 第 2 集《电子司线，真的准吗？》封面（3:4，2160×2880，不进视频）。

版式照第 1 集所有者审定的 v9：左上 logo＋网球时差、两行衬线问句大标题、一行英文灰字、
单一 3D 场景、底部白/黄两行＋一行灰色小字。字体用系统的 Noto CJK（Bold，TTC 第 3 个是简中）。

先渲底图（r3d/ 下起着静态服务）：
    cd r3d && W=2160 H=2880 OUT=stills_cover node still.js 300.5
再合成：
    python3 cover/make_cover.py r3d/stills_cover/s_0300.50.jpg poster.jpg
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[5]
W, H = 2160, 2880
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SC = 2  # TTC 里简中的序号
INTER = str(REPO / "assets/fonts/Inter-SemiBold.ttf")
Y = (255, 200, 40); WH = (245, 245, 240); GR = (150, 158, 170)


def main(hero_path: str, out_path: str) -> None:
    hero = Image.open(hero_path).convert("RGB")
    if hero.size != (W, H):
        hero = hero.resize((W, H), Image.LANCZOS)
    a = np.asarray(hero).astype(np.float32) / 255
    # 上下两条暗带托住文字，中间留给画面
    yy = np.linspace(0, 1, H)[:, None, None]
    top = np.clip(1 - yy / 0.40, 0, 1) ** 1.4 * 0.85
    bot = np.clip((yy - 0.70) / 0.30, 0, 1) ** 1.4 * 0.86
    a = a * (1 - np.maximum(top, bot))
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)

    # 左上：官方图标 + 网球时差（墨迹垂直居中对齐）
    icon = Image.open(REPO / "assets/logo/brand/account/icon-transparent-1024.png").convert("RGBA").resize((64, 64), Image.LANCZOS)
    icon = icon.crop(icon.split()[3].point(lambda v: 255 if v > 40 else 0).getbbox())
    fT = ImageFont.truetype(SANS, 60, index=SC)
    m = Image.new("L", (800, 200), 0); ImageDraw.Draw(m).text((50, 50), "网球时差", font=fT, fill=255)
    tb = m.getbbox(); th = tb[3] - tb[1]
    CY, x = 210, 140
    img.paste(icon, (x, CY - icon.size[1] // 2), icon); x += icon.size[0] + 22
    d.text((x - (tb[0] - 50), CY - th // 2 - (tb[1] - 50)), "网球时差", font=fT, fill=Y)

    # 标题：两行完整问句
    ftt = ImageFont.truetype(SERIF, 212, index=SC)
    d.text((134, 280), "电子司线", font=ftt, fill=WH)
    d.text((134, 510), "真的准吗？", font=ftt, fill=WH)
    d.text((150, 762), "H O W   E L E C T R O N I C   L I N E   C A L L I N G   S E E S", font=ImageFont.truetype(INTER, 38), fill=GR)

    # 底部：白一行、黄一行、灰一行
    f1 = ImageFont.truetype(SERIF, 124, index=SC)
    d.text((140, 2420), "回放里那个椭圆，", font=f1, fill=WH)
    d.text((140, 2580), "不是拍下来的", font=f1, fill=Y)
    d.text((146, 2770), "以 Hawk-Eye 为例：多台相机的视线交会成轨迹，落点是算出来的",
           font=ImageFont.truetype(SANS, 44, index=SC), fill=GR)
    img.save(out_path, quality=94, subsampling=0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
