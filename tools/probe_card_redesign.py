# -*- coding: utf-8 -*-
"""焦点复盘卡·高级感重设计原型（设计探针，非生产渲染器）。

目的：把主色调从"满屏深绿+荧光黄绿"改为"中性底 + 克制单一强调色"，
弱化绿、上高级感、留白透气。渲染两个方向供人工挑选：
  A 象牙浅底 + 赤陶红  B 暖炭深底 + 香槟金
真实数据：WTA250 汉堡半决赛 科尔帕奇(81) def. 谢里夫(73) 6-1 2-0 退赛。
输出到 --out 目录；渲染效果须人工亲眼核对后再决定是否落地 cards.py。
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CJK_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

W, H = 1080, 1440
ROWS = [("总得分", "17", "37"), ("一发成功率", "64%", "44%"),
        ("一发得分率", "36%", "57%"), ("二发得分率", "25%", "78%"),
        ("ACE / 双误", "1 / 2", "0 / 1"), ("破发点", "0/0", "3/3")]
KEY_ROW = "破发点"  # 唯一点亮的决胜数据


def fb(s):
    return ImageFont.truetype(CJK_B, s)


def fr(s):
    return ImageFont.truetype(CJK_R, s)


def draw_card(t):
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    M = 76
    ink, sub, line, accent = t["ink"], t["sub"], t["line"], t["accent"]
    panel, winbg = t["panel"], t["winbg"]

    # 品牌行（logo 用真身 icon，若缺失退回简笔）
    lg = Path(__file__).resolve().parents[1] / "assets/logo/brand/icon.png"
    if lg.exists():
        ic = Image.open(lg).convert("RGBA").resize((44, 44), Image.LANCZOS)
        img.paste(ic, (M, 60), ic)
    d.text((M + 58, 82), "网球时差", font=fb(30), fill=ink, anchor="lm")
    d.text((W - M, 82), "7.26", font=fb(28), fill=sub, anchor="rm")

    # 栏目标签 + 大标题
    d.text((M, 172), "MATCH BREAKDOWN", font=fb(20), fill=accent, anchor="lm")
    d.text((M, 244), "焦点复盘", font=fb(72), fill=ink, anchor="lm")
    d.text((W - M, 250), "WTA250 · 汉堡 · 半决赛", font=fr(24), fill=sub, anchor="rm")
    d.line([M, 316, W - M, 316], fill=line, width=2)

    # 比分区（唯一视觉主角）
    y = 360
    d.rounded_rectangle([M, y, W - M, y + 96], radius=14, fill=winbg)
    d.rectangle([M + 26, y + 34, M + 66, y + 62], fill=t["flagA"])
    d.text((M + 84, y + 48), "科尔帕奇", font=fb(44), fill=ink, anchor="lm")
    wname = fb(44).getlength("科尔帕奇")
    d.text((M + 84 + wname + 12, y + 52), "81", font=fr(22), fill=sub, anchor="lm")
    d.text((W - M - 150, y + 48), "6", font=fb(54), fill=accent, anchor="mm")
    d.text((W - M - 66, y + 48), "2", font=fb(54), fill=accent, anchor="mm")
    y2 = y + 96
    d.rectangle([M + 26, y2 + 34, M + 66, y2 + 62], fill=t["flagB"])
    d.text((M + 84, y2 + 48), "谢里夫", font=fb(44), fill=sub, anchor="lm")
    wname2 = fb(44).getlength("谢里夫")
    d.text((M + 84 + wname2 + 12, y2 + 52), "73", font=fr(22), fill=sub, anchor="lm")
    d.text((W - M - 150, y2 + 48), "1", font=fb(54), fill=sub, anchor="mm")
    d.text((W - M - 66, y2 + 48), "0", font=fb(54), fill=sub, anchor="mm")
    d.rounded_rectangle([W - M - 210, y2 + 74, W - M, y2 + 110], radius=18, fill=panel)
    d.text((W - M - 105, y2 + 92), "谢里夫伤退", font=fb(22), fill=accent, anchor="mm")

    # 技术统计（中性、克制，只点亮决胜手）
    ty = y2 + 158
    d.text((M, ty), "技术统计", font=fb(26), fill=sub, anchor="lm")
    d.text((W / 2 + 110, ty), "谢里夫", font=fb(24), fill=sub, anchor="mm")
    d.text((W - M - 80, ty), "科尔帕奇", font=fb(24), fill=ink, anchor="mm")
    ty += 52
    for i, (label, a, b) in enumerate(ROWS):
        ry = ty + i * 80
        key = (label == KEY_ROW)
        if key:
            d.rounded_rectangle([M - 10, ry - 4, W - M + 10, ry + 56], radius=10, fill=panel)
        d.text((M, ry + 26), label, font=fr(29), fill=(ink if key else sub), anchor="lm")
        d.text((W / 2 + 110, ry + 26), a, font=fb(33), fill=(ink if key else sub), anchor="mm")
        d.text((W - M - 80, ry + 26), b, font=fb(37), fill=(accent if key else ink), anchor="mm")
        d.line([M, ry + 68, W - M, ry + 68], fill=line, width=1)

    # 一句判断（真实解读，非套话——修掉"退赛却说熬过硬仗"）
    jy = ty + len(ROWS) * 80 + 34
    d.rectangle([M, jy, M + 6, jy + 96], fill=accent)
    d.text((M + 28, jy - 2), "一句判断", font=fb(24), fill=accent, anchor="lm")
    judge = ("谢里夫首盘失守后因伤退赛，科尔帕奇不战晋级决赛——\n"
             "一发状态未起，但机会一到手就 3/3 全部兑现。")
    d.multiline_text((M + 28, jy + 40), judge, font=fr(27), fill=ink, spacing=12)

    d.text((W - M, H - 56), "@网球时差 · TENNIS JETLAG", font=fr(22), fill=sub, anchor="rm")
    return img


IVORY = dict(bg=(244, 242, 236), ink=(26, 29, 26), sub=(146, 148, 140),
             line=(222, 220, 212), accent=(190, 84, 54), panel=(234, 231, 223),
             winbg=(237, 234, 226), flagA=(40, 42, 52), flagB=(150, 152, 150))
CHARCOAL = dict(bg=(22, 24, 28), ink=(238, 238, 234), sub=(138, 144, 150),
                line=(46, 50, 56), accent=(216, 180, 112), panel=(32, 35, 40),
                winbg=(30, 33, 39), flagA=(210, 210, 206), flagB=(96, 100, 106))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/card-redesign")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    draw_card(IVORY).save(out / "focus_ivory.png")
    draw_card(CHARCOAL).save(out / "focus_charcoal.png")
    print(f"渲染完成 → {out}/focus_ivory.png, focus_charcoal.png")


if __name__ == "__main__":
    main()
