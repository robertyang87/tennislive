# -*- coding: utf-8 -*-
"""焦点复盘卡·高级感重设计原型（设计探针，非生产渲染器）。

目的：把主色调从"满屏深绿+荧光黄绿"改为"中性底 + 克制单一强调色"，
弱化绿、上高级感、留白透气。渲染两个方向供人工挑选：
  A 象牙浅底 + 赤陶红  B 暖炭深底 + 香槟金
真实数据：WTA250 汉堡半决赛 科尔帕奇(81) def. 谢里夫(73) 6-1 2-0 退赛。
输出到 --out 目录；渲染效果须人工亲眼核对后再决定是否落地 cards.py。
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tennislive.render.cards import _find_font  # noqa: E402

# 字体走生产同一套解析（系统 Noto CJK → 仓库自带 NotoSansSC 子集），
# 原来写死的 /usr/share/fonts/opentype/... 在没装 fonts-noto-cjk 的机器上
# 直接 OSError，看不到样张。
CJK_B, _B_IDX = _find_font(bold=True)
CJK_R, _R_IDX = _find_font(bold=False)

W, H = 1080, 1440
ROWS = [("总得分", "17", "37"), ("一发成功率", "64%", "44%"),
        ("一发得分率", "36%", "57%"), ("二发得分率", "25%", "78%"),
        ("ACE / 双误", "1 / 2", "0 / 1"), ("破发点", "0/0", "3/3")]
KEY_ROW = "破发点"  # 唯一点亮的决胜数据


def fb(s):
    return ImageFont.truetype(CJK_B, s, index=_B_IDX)


def fr(s):
    return ImageFont.truetype(CJK_R, s, index=_R_IDX)


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

# —— 与「网球有故事」知识贴对齐的两版 ——
# 知识贴的色板在 render/webcards.py 的 CSS 变量里：:root 是深绿底
# （--ground0 #061D17 → --ground1 #0B3B2C），html.light 是暖沙底
# （#F2EDE2 → #E9E2D2）。两套共用同一批强调色：--coral #FF7657、
# --gold #D5B44D、--ivory #F7F3E8。日报卡要"中性底 + 弱化绿"，所以
# 底色不能照抄深绿，但**强调色可以完全共用**——这就是一致性的落点。
#
# SAND：直接用 html.light 的 ground/pagetext/reason/fade/divider，
#   accent 取 --coral 的同色相深色版（#C2482B，色相 11° 对 13°），
#   因为纯 #FF7657 压在沙底上只有 2.2:1，数字会发飘。
# COAL：中性暖炭底，accent 用**一模一样的 --coral #FF7657**（对比度
#   6.8:1），跨栏目共用同一个色值。
# 金色（#D5B44D）两版都只走细线，绝不做文字——它在沙底上只有 1.7:1。
SAND = dict(bg=(242, 237, 226), ink=(30, 51, 40), sub=(77, 97, 87),
            line=(229, 214, 169), accent=(194, 72, 43), panel=(231, 223, 206),
            winbg=(237, 231, 219), flagA=(30, 51, 40), flagB=(149, 153, 143))
COAL = dict(bg=(24, 26, 25), ink=(247, 243, 232), sub=(154, 168, 159),
            line=(58, 56, 44), accent=(255, 118, 87), panel=(34, 37, 35),
            winbg=(31, 34, 32), flagA=(247, 243, 232), flagB=(110, 118, 112))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/card-redesign")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, theme in (("ivory", IVORY), ("charcoal", CHARCOAL),
                        ("sand", SAND), ("coal", COAL)):
        draw_card(theme).save(out / f"focus_{name}.png")
    print(f"渲染完成 → {out}/focus_{{ivory,charcoal,sand,coal}}.png")


if __name__ == "__main__":
    main()
