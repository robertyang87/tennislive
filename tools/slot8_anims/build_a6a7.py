#!/usr/bin/env python3
"""A6/A7 animations for wta-finals-slot8-2026 （利雅得一拍动画补位）.
A6 利雅得答卷 (S4 下半) | A7 第一候补 (S5 引子 + 卡萨金娜引言卡底).
Why animation: WTA 官方利雅得 2024 集锦全系列最高 720p（kedd/YepX/Fpz/iKp 四条实测），
触本系列 1080p 硬闸；按所有者定规「无视频可阐述处用动画补位」以代码动画承载此拍，
旁白与事实不变。Series tokens + alignment standard via anim_common.
Usage: python3 build_a6a7.py [a6|a7] [dur] [ver] [outdir]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anim_common import *

F_CHIP = ImageFont.truetype(CJK_B, 34)
F_NAME = ImageFont.truetype(CJK_B, 46)
F_ROW = ImageFont.truetype(CJK_B, 40)
F_ROWS = ImageFont.truetype(CJK_B, 34)
F_VERDICT = ImageFont.truetype(CJK_B, 44)
F_SCORE = ImageFont.truetype(TLSCORE, 58)
F_SRC = ImageFont.truetype(CJK_R, 26)

def score_row(d, t, t0, y, label, opp, score, win):
    """one match row: label+opponent left, TL Score right, win/loss dot."""
    a = ease((t - t0) / 0.7)
    if a <= 0: return
    panel(d, 110, y - 52, 970, y + 118, a)
    dot = GREEN if win else RED
    d.ellipse([146, y + 8, 174, y + 36], fill=with_a(dot, int(255 * a)))
    text_l(d, 200, y - 26, label, ImageFont.truetype(CJK_B, 30), with_a(FAINT, int(240 * a)))
    text_l(d, 200, y + 16, opp, F_ROW, with_a(CREAM, int(255 * a)))
    b = d.textbbox((0, 0), score, font=F_SCORE)
    d.text((934 - (b[2] - b[0]) - b[0], y + 2 - b[1]), score, font=F_SCORE,
           fill=with_a(BRAND if win else CREAM_DIM, int(255 * a)))

# ================= A6: 利雅得的答卷 (S4b) =================
def a6_frame(dur):
    P = lambda x: x * dur / 12.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "RIYADH 2024 · THE ANSWER", "利雅得，她交的答卷",
                    sub="克雷吉茨科娃 · 2024 总决赛小组赛")
        score_row(d, t, P(1.2), 520, "小组赛", "胜 佩古拉", "6-3 6-3", True)
        score_row(d, t, P(3.6), 730, "小组赛", "胜 高芙", "7-5 6-4", True)
        score_row(d, t, P(6.0), 940, "半决赛", "负 郑钦文", "3-6 5-7", False)
        va = ease((t - P(8.6)) / 0.9)
        if va > 0:
            vt = "小组第一出线 · 打进四强"
            d.rounded_rectangle([150, 1150, 930, 1240], radius=16,
                                outline=with_a(BRAND, int(240 * va)), width=3)
            b = d.textbbox((0, 0), vt, font=F_VERDICT)
            d.text((W / 2 - (b[0] + b[2]) / 2, 1195 - (b[1] + b[3]) / 2), vt,
                   font=F_VERDICT, fill=with_a(BRAND, int(255 * va)))
        return img
    return fn

# ================= A7: 第一候补 (S5a + 引言卡底) =================
def a7_frame(dur):
    P = lambda x: x * dur / 36.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        # phase 2 (quote-card backdrop): whole board dims so card text reads clean
        dim = 1.0 - 0.72 * ease_io((t - P(11.6)) / 1.6)
        title_block(d, t * 1.0, "THE FIRST ALTERNATE", "第一候补",
                    sub="卡萨金娜 · 2024 利雅得")
        # re-draw title dimmed is complex; instead overlay a translucent base veil
        # in phase 2 after all elements are drawn (below).
        a1 = ease((t - P(1.0)) / 0.7)
        if a1 > 0:
            panel(d, 110, 470, 970, 640, a1)
            text_c(d, W / 2, 500, "佩古拉退赛 · 第一候补临上场", F_ROW,
                   with_a(CREAM, int(255 * a1)))
            text_c(d, W / 2, 566, "替补出场，只打了一场", F_ROWS,
                   with_a(CREAM_DIM, int(255 * a1)))
        score_row(d, t, P(4.2), 760, "小组赛 · 替补出场", "负 斯瓦泰克", "1-6 0-6", False)
        a3 = ease((t - P(7.4)) / 0.8)
        if a3 > 0:
            chip(d, W / 2, 1010, "全场 51 分钟 · 只赢一局", F_CHIP, RED, RED,
                 fill_a=int(120 * a3))
            text_c(d, W / 2, 1096, "赛后，她把话说透了", F_ROWS,
                   with_a(CREAM_DIM, int(255 * a3)))
        if dim < 1.0:
            veil = Image.new("RGBA", (W, H), (8, 14, 29, int(190 * (1 - dim))))
            img.paste(Image.alpha_composite(img, veil), (0, 0))
            d = ImageDraw.Draw(img, "RGBA")
            wa = 0.35 + 0.1 * (0.5 + 0.5 * math.sin(t * 0.9))
            text_c(d, W / 2, 1240, "RIYADH · 2024", ImageFont.truetype(INTER, 30),
                   with_a(CREAM_DIM, int(160 * wa / 0.45)))
        return img
    return fn

ANIMS = {"a6": (a6_frame, 12.0, "slot8-a6-riyadh"), "a7": (a7_frame, 36.0, "slot8-a7-alternate")}

if __name__ == "__main__":
    which = sys.argv[1]
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else ANIMS[which][1]
    ver = sys.argv[3] if len(sys.argv) > 3 else "v2"
    outdir = sys.argv[4] if len(sys.argv) > 4 else os.path.dirname(os.path.abspath(__file__))
    fn, _, name = ANIMS[which]
    render(fn(dur), dur, os.path.join(outdir, f"{name}-{ver}.mp4"))
