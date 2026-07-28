#!/usr/bin/env python3
"""栏目合集的封面 —— 品牌球钟 + 栏目名，没有第三样东西。

## 为什么是这个样子

合集封面和单集封面要**一眼分得开**。单集封面全是照片（压暗的实拍 + 大标题），
所以合集这一张反过来做：**纯品牌、无照片**。主页里它是唯一一张不是照片的封面，
不用读字就知道「这是一摞，不是一条」。

## 三条是渲出来比出来的，不是想出来的

1. **判据是缩到 220px 还认不认得出**，不是全尺寸好不好看。合集封面在主页里
   就是个图块。第一版把真实选题标题做成底纹（想说明「这里有很多」），全尺寸
   勉强能看，缩到图块尺寸只剩一团噪点 —— 又一次印证「图不好看不能靠加字补救」。
2. **球必须是完整的圆。** 试过让球左右出血、放到最大，全尺寸很有气势，缩小后
   变成「一块绿方块加两根指针」—— 圆形轮廓才是这个品牌被认出来的地方，裁掉
   它等于把 logo 扔了。
3. **别把球切在缝线上。** 中间那一版让色带压住球的下缘，正好切在下面那道缝线
   上，看着像渲坏了而不是刻意裁切。要么完整，要么裁得一眼看出是放大。

## 字只有栏目名

初稿还有副标（「规则、纪录，和没人细讲过的事」）和「已更新 11 集」。两个都删了：
在 220px 的图块上它们本来就糊成灰条，而集数还会过期 —— 平台自己会显示条数，
烧进图里只会有一天变成假的。

栏目从 `explainer.COLUMNS` 读，不在这里另抄一份：新登记一个栏目就自动有封面，
撤掉一个也不会留下孤儿文件。

用法：
    python tools/render_collection_cover.py                 # 全部栏目，1:1 + 3:4
    python tools/render_collection_cover.py --only 网球有故事
    python tools/render_collection_cover.py --check         # 只做缩略图自检
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_brand_logo import BALL, SEAM, icon  # noqa: E402
from tennislive.video.explainer import COLUMNS  # noqa: E402

OUT = REPO / "assets" / "logo" / "brand" / "collections"
CJK_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

FIELD = (16, 45, 35)      # #102D23 品牌深绿，和卡片底色同源
INK = (231, 243, 236)     # #e7f3ec 主文字。一屏只留一个强调色——绿给了球，字就中性

# icon() 画的球直径是画布的 0.92（四周留了透明边）。按球径摆位要除掉它，
# 否则「球占宽度的六成」会算成五成半，两版之间差得肉眼可见。
BALL_IN_CANVAS = 0.92
BALL_WIDTH = 0.615        # 球径占画面宽度
TITLE_MAX_WIDTH = 0.86    # 最长的那个栏目名最多占多宽（字号由它决定，全套共用）
THUMB = 220               # 主页图块的真实尺寸，自检按它来


def title_font(width: int) -> ImageFont.FreeTypeFont:
    """全套共用一个字号：按**最长的那个栏目名**收到刚好不超边。

    走过一次弯路：让每个名字各自撑满同样的宽度。结果「开球之前」四个字被放到
    199、「网球有故事」五个字收到 184，短名字显得虚胖 —— 摆在一起反而不像一套。
    一套封面该是**字号一致**，短名字就是短一点。

    所以字号由已登记栏目里最长的那个决定，加一个就自动重算；哪天来个七个字的
    栏目，全套一起变小，而不是它自己被压扁。
    """
    longest = max(COLUMNS, key=len) if COLUMNS else "网球有故事"
    size = int(width * 0.185)
    while size > 8:
        font = ImageFont.truetype(CJK_BOLD, size)
        box = font.getbbox(longest)
        if box[2] - box[0] <= width * TITLE_MAX_WIDTH:
            return font
        size -= 2
    return ImageFont.truetype(CJK_BOLD, 8)


def render(name: str, width: int = 1080, height: int | None = None) -> Image.Image:
    height = height or width
    img = Image.new("RGBA", (width, height), FIELD)

    # 一道极淡的缝线弧贴着底边。取自 logo 的缝线走向，是品牌语言的回声；
    # 透明度压到 20，站远一点几乎看不见 —— 它的作用是让底部不空，不是被读出来。
    arc_y = height * 0.955
    pts = [(x, arc_y + height * 0.05 * math.sin(math.pi * x / width))
           for x in range(0, width + 1, 6)]
    ImageDraw.Draw(img).line(pts, fill=(*SEAM, 20),
                             width=max(6, width // 90), joint="curve")

    # 球和标题当**一整块**居中，不是各自按高度的百分比定位。踩过：两个位置都写成
    # `height * 0.395` 和 `height * 0.815`，1:1 上正好，换到 3:4 画面一高，两者
    # 之间就被拉开一大片空 —— 百分比定位会把留白也按比例放大。
    font = title_font(width)
    ball_d = width * BALL_WIDTH
    title_h = font.getbbox(name)[3] - font.getbbox(name)[1]
    gap = width * 0.105
    block = ball_d + gap + title_h
    # 略微偏上：视觉重心比几何中心高一点才不显得往下坠。
    top = (height - block) / 2 * 0.88

    canvas = int(ball_d / BALL_IN_CANVAS)
    ball = icon(1500).resize((canvas, canvas), Image.LANCZOS)
    img.paste(ball, ((width - canvas) // 2, int(top + ball_d / 2 - canvas / 2)), ball)
    ImageDraw.Draw(img).text((width / 2, top + ball_d + gap + title_h / 2), name,
                             font=font, fill=INK, anchor="mm")
    return img.convert("RGB")


def contrast_ok(thumb: Image.Image) -> bool:
    """缩略图上，球那一块和底色还分得开吗。

    判据不是「好不好看」——那要人看。这里只挡一种回归：哪天有人把底色调亮或
    把球缩小，导致图块上分不出球和底。取球心一小块和四角比明度。
    """
    px = thumb.convert("L")
    w, h = px.size
    ball = px.crop((int(w * 0.42), int(h * 0.30), int(w * 0.58), int(h * 0.46)))
    corner = px.crop((0, 0, int(w * 0.10), int(h * 0.10)))
    return _mean(ball) - _mean(corner) > 60


def _mean(im: Image.Image) -> float:
    hist = im.histogram()
    total = sum(hist)
    return sum(i * n for i, n in enumerate(hist)) / total if total else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="只渲这一个栏目")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="只跑缩略图自检，不写文件")
    args = ap.parse_args()

    names = [args.only] if args.only else list(COLUMNS)
    unknown = [n for n in names if n not in COLUMNS]
    if unknown:
        raise SystemExit(f"没登记的栏目：{'、'.join(unknown)}；"
                         f"已登记的是 {'、'.join(COLUMNS)}")

    if not args.check:
        args.out.mkdir(parents=True, exist_ok=True)
    bad = []
    for name in names:
        square = render(name, 1080)
        thumb = square.resize((THUMB, THUMB), Image.LANCZOS)
        ok = contrast_ok(thumb)
        if not ok:
            bad.append(name)
        print(f"{name}　缩略图自检 {'通过' if ok else '不通过'}")
        if args.check:
            continue
        square.save(args.out / f"{name}-1x1.png")
        # 3:4 是按高度重排的，不是把 1:1 拉伸 —— 拉伸会把球压成椭圆。
        render(name, 1080, 1440).save(args.out / f"{name}-3x4.png")
        thumb.save(args.out / f"{name}-thumb.png")
    if bad:
        print(f"\n⚠ {'、'.join(bad)} 在 {THUMB}px 上球和底分不开了，别直接用。")
    elif not args.check:
        print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
