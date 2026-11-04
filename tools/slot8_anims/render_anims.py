#!/usr/bin/env python3
"""A1-A4 animations for wta-finals-slot8-2026 (网球有故事 · 第八席冠军专座).
Series tokens + alignment standard via anim_common (walkover/zverev定版).
A1 判定顺序 | A2 积分对撞 | A3 2024先例账 | A4 总决赛签表.
Usage: python3 render_anims.py [a1|a2|a3|a4|all] [dur] [ver]
"""
import sys
sys.path.insert(0, "/home/hatch/workspace/wta-finals-slot8-20261103/prod/anim")
from anim_common import *

F_CHIP = ImageFont.truetype(CJK_B, 34)
F_NAME = ImageFont.truetype(CJK_B, 42)
F_ROW = ImageFont.truetype(CJK_B, 40)
F_ROWS = ImageFont.truetype(CJK_B, 36)
F_VERDICT = ImageFont.truetype(CJK_B, 44)
F_BIG = ImageFont.truetype(TLSCORE, 92)
F_NUM = ImageFont.truetype(TLSCORE, 64)
F_SRC = ImageFont.truetype(CJK_R, 26)
F_EN = ImageFont.truetype(INTER, 26)

def bar_row(d, t, t0, y, name, race_txt, pts, pts_max, date_txt, brand, note=None):
    a = ease((t - t0) / 0.7)
    if a <= 0: return
    text_l(d, 110, y, name, F_NAME, with_a(BRAND if brand else CREAM, 255 * a))
    text_l(d, 110, y + 56, race_txt, F_EN, with_a(FAINT, 240 * a))
    # points right aligned at x=970
    b = d.textbbox((0, 0), str(pts), font=F_NUM)
    d.text((970 - (b[2] - b[0]) - b[0], y - 6 - b[1]), str(pts), font=F_NUM,
           fill=with_a(BRAND if brand else CREAM, 255 * a))
    # bar
    bw = 860 * (pts / pts_max) * ease_io((t - t0 - 0.25) / 1.0)
    d.rounded_rectangle([110, y + 108, 110 + max(bw, 6), y + 128], radius=10,
                        fill=with_a(BRAND if brand else (58, 84, 120), int(235 * a)))
    text_l(d, 110, y + 142, date_txt, F_ROWS, with_a(CREAM_DIM, 255 * a))
    if note:
        nb = d.textbbox((0, 0), note, font=F_ROWS)
        d.text((970 - (nb[2] - nb[0]) - nb[0], y + 142 - nb[1]), note, font=F_ROWS,
               fill=with_a(RED, 255 * a))

# ================= A2: 积分对撞 (S0) =================
def a2_frame(dur):
    P = lambda x: x * dur / 24.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "THE CUT LINE MOVED", "门槛，抬高了一名")
        bar_row(d, t, P(1.0), 470, "穆霍娃", "RACE 7", 4665, 4665, "10 月 21 日 · 名额才落定", False)
        bar_row(d, t, P(5.0), 740, "诺斯科娃", "RACE 8", 4343, 4665, "10 月 9 日 · 官宣入围", True)
        bar_row(d, t, P(9.0), 1010, "斯瓦泰克", "RACE 9", 4188, 4665, "只差 155 分", False,
                note="追回来也进不去")
        va = ease((t - P(15.5)) / 0.9)
        if va > 0:
            vt = "分少的人先上车 · 分多的多等 12 天"
            d.rounded_rectangle([120, 1300, 960, 1382], radius=16, outline=with_a(BRAND, int(240 * va)), width=3)
            b = d.textbbox((0, 0), vt, font=F_VERDICT)
            d.text((W / 2 - (b[0] + b[2]) / 2, 1341 - (b[1] + b[3]) / 2), vt, font=F_VERDICT, fill=with_a(BRAND, 255 * va))
        return img
    return fn

# ================= A1: 判定顺序 (S2) =================
def seat_chips(d, t, t0):
    # 8 seats: 1-7 cream fill sequentially, 8th brand outline
    for i in range(8):
        ca = ease((t - t0 - i * 0.28) / 0.5)
        if ca <= 0: continue
        x0 = 110 + i * 110
        last = (i == 7)
        d.rounded_rectangle([x0, 452, x0 + 92, 544], radius=14,
                            fill=with_a(BRAND if last else PANEL, int((235 if last else 190) * ca)),
                            outline=with_a(BRAND if last else CREAM_DIM, int(230 * ca)), width=2)
        s = str(i + 1)
        b = d.textbbox((0, 0), s, font=F_NUM)
        d.text((x0 + 46 - (b[0] + b[2]) / 2, 498 - (b[1] + b[3]) / 2), s, font=F_NUM,
               fill=with_a((8, 14, 29) if last else CREAM, 255 * ca))

def rule_row(d, t, t0, y, head, body, brand):
    a = ease((t - t0) / 0.7)
    if a <= 0: return
    slide = (1 - a) * 26
    d.rounded_rectangle([110, y - 44 + slide, 970, y + 96 + slide], radius=14,
                        fill=with_a(PANEL, int(185 * a)))
    d.rectangle([110, y - 44 + slide, 122, y + 96 + slide],
                fill=with_a(BRAND if brand else CREAM_DIM, int(225 * a)))
    text_l(d, 150, y - 22 + slide, head, F_ROW, with_a(BRAND if brand else CREAM, 255 * a))
    text_l(d, 150, y + 38 + slide, body, F_ROWS, with_a(CREAM_DIM, 255 * a))

def a1_frame(dur):
    P = lambda x: x * dur / 30.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "HOW THE 8TH SEAT WORKS", "第八个名额，怎么定")
        seat_chips(d, t, P(0.8))
        rule_row(d, t, P(4.2), 640, "前七个名额 · 按积分排队", "Race 前 7 名，依次直入", False)
        rule_row(d, t, P(9.2), 830, "第八个名额 · 先找冠军", "当年大满贯冠军、第 8–20 名内，顺位最高者", True)
        rule_row(d, t, P(14.6), 1020, "没有这样的冠军", "才轮到积分第八名", False)
        va = ease((t - P(20.5)) / 0.9)
        if va > 0:
            vt = "第八个名额不排队 · 它先找冠军"
            d.rounded_rectangle([120, 1300, 960, 1382], radius=16, outline=with_a(BRAND, int(240 * va)), width=3)
            b = d.textbbox((0, 0), vt, font=F_VERDICT)
            d.text((W / 2 - (b[0] + b[2]) / 2, 1341 - (b[1] + b[3]) / 2), vt, font=F_VERDICT, fill=with_a(BRAND, 255 * va))
        return img
    return fn

# ================= A3: 2024 先例账 (S4) =================
def a3_frame(dur):
    P = lambda x: x * dur / 22.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "YEAR ONE OF THE RULE", "新规第一年，2024")
        bar_row(d, t, P(1.0), 500, "纳瓦罗", "RACE 8", 3568, 3568, "按老规矩 · 本该入围", False,
                note="拒绝当候补")
        bar_row(d, t, P(5.4), 770, "克雷吉茨科娃", "RACE 12", 2706, 3568, "温网冠军 · 新规直送入围", True)
        va = ease((t - P(11.5)) / 0.9)
        if va > 0:
            panel(d, 110, 1060, 970, 1240, va, outline_a=0)
            d.rounded_rectangle([110, 1060, 970, 1240], radius=18, outline=with_a(BRAND, int(230 * va)), width=3)
            l1 = "然后她小组头名出线 · 打进四强"
            l2 = "全年只赢 21 场球的人 · 交出的答卷"
            b1 = d.textbbox((0, 0), l1, font=F_VERDICT); b2 = d.textbbox((0, 0), l2, font=F_ROWS)
            block_h = (b1[3] - b1[1]) + 18 + (b2[3] - b2[1])
            top = 1060 + (180 - block_h) / 2
            text_c(d, W / 2, top, l1, F_VERDICT, with_a(CREAM, 255 * va))
            text_c(d, W / 2, top + (b1[3] - b1[1]) + 18, l2, F_ROWS, with_a(CREAM_DIM, 255 * va))
        return img
    return fn

# ================= A4: 签表 (S8) =================
G1 = ["莱巴金娜", "高芙", "佩古拉", "诺斯科娃"]
G2 = ["萨巴伦卡", "安德列娃", "斯维托丽娜", "穆霍娃"]

def group_panel(d, t, t0, x0, title, names, hot_idx):
    a = ease((t - t0) / 0.7)
    if a <= 0: return
    panel(d, x0, 430, x0 + 410, 880, a)
    text_c(d, x0 + 205, 486, title, ImageFont.truetype(CJK_B, 38), with_a(CREAM_DIM, 255 * a))
    for i, nm in enumerate(names):
        ra = ease((t - t0 - 0.5 - i * 0.55) / 0.6)
        if ra <= 0: continue
        y = 584 + i * 78
        hot = (i == hot_idx)
        if hot:
            d.rounded_rectangle([x0 + 24, y - 34, x0 + 386, y + 34], radius=12,
                                fill=with_a(BRAND, int(235 * ra)))
        text_c(d, x0 + 205, y - 26, nm, F_NAME,
               with_a((8, 14, 29) if hot else CREAM, 255 * ra))

def a4_frame(dur):
    P = lambda x: x * dur / 24.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "THE DRAW · INDIAN WELLS", "总决赛分组")
        group_panel(d, t, P(0.8), 90, "第 1 组", G1, 3)
        group_panel(d, t, P(3.4), 580, "第 2 组", G2, 3)
        rule_row(d, t, P(8.6), 990, "周日揭幕战", "莱巴金娜 vs 诺斯科娃", True)
        rule_row(d, t, P(12.6), 1180, "周一首战", "萨巴伦卡 vs 穆霍娃", False)
        va = ease((t - P(17.0)) / 0.9)
        if va > 0:
            text_c(d, W / 2, 1330, "温网决赛重演？先各自出线 · 最早半决赛见",
                   ImageFont.truetype(CJK_B, 38), with_a(BRAND, 255 * va))
        return img
    return fn

ANIMS = {"a1": (a1_frame, 30.0, "slot8-a1-rules"), "a2": (a2_frame, 24.0, "slot8-a2-points"),
         "a3": (a3_frame, 22.0, "slot8-a3-2024"), "a4": (a4_frame, 24.0, "slot8-a4-draw")}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    dur_override = float(sys.argv[2]) if len(sys.argv) > 2 else None
    ver = sys.argv[3] if len(sys.argv) > 3 else "v1"
    keys = list(ANIMS) if which == "all" else [which]
    for k in keys:
        fn_factory, base_dur, name = ANIMS[k]
        dur = dur_override or base_dur
        render(fn_factory(dur), dur, f"/home/hatch/workspace/wta-finals-slot8-20261103/prod/anim/{name}-{ver}.mp4")
