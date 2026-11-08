#!/usr/bin/env python3
"""Finals-alternate episode (wta-finals-alternate-2026): 12 code-drawn
animation segments, all narration carriers (no match footage, owner-approved
cards+animation format). Series tokens via anim_common (walkover style-audit
final standard): own-title ink top >=190, text bottom <=1240 (subtitle band
starts y1299), chips/blocks centred on ink bbox, mid-tier glow in BG.
All key elements land by ~80% of each clip; the tail is a hold so spec
windows can be trimmed without cutting a landing.
Usage: python3 render_anims.py [a1|..|a12|all] [dur_override] [ver]
Output: alt-segNN-<ver>.mp4 in this dir (new filename per version).
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anim_common import *

DURS = {"a1": 45, "a2": 32, "a3": 42, "a4": 57, "a5": 41, "a6": 23,
        "a7": 28, "a8": 30, "a9": 45, "a10": 22, "a11": 38, "a12": 35}

F_TITLE_SUB = None  # set per-font below via helper

def F(name, size):
    return ImageFont.truetype(name, size)

def land(t, start, dur=0.6):
    return ease((t - start) / dur)

def fade_layer(base, layer, a):
    if a <= 0: return
    if a < 1:
        arr = np.array(layer)
        arr[..., 3] = (arr[..., 3].astype(np.float32) * a).astype(np.uint8)
        layer = Image.fromarray(arr)
    base.alpha_composite(layer)

def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))

def dashed_rect(d, x0, y0, x1, y1, fill, dash=16, gap=10, width=3):
    x = x0
    while x < x1:
        d.line([x, y0, min(x + dash, x1), y0], fill=fill, width=width)
        d.line([x, y1, min(x + dash, x1), y1], fill=fill, width=width)
        x += dash + gap
    y = y0
    while y < y1:
        d.line([x0, y, x0, min(y + dash, y1)], fill=fill, width=width)
        d.line([x1, y, x1, min(y + dash, y1)], fill=fill, width=width)
        y += dash + gap

# ---------------- shared: finals seats diagram ----------------
GROUPS = [("第一组", ["莱巴金娜", "高芙", "佩古拉", "诺斯科娃"]),
          ("第二组", ["萨巴伦卡", "安德列娃", "斯维托丽娜", "穆霍娃"])]
SEAT_PANELS = [(60, 470, 525, 835), (555, 470, 1020, 835)]

def seat_rects(px0):
    out = []
    for r in range(2):
        for c in range(2):
            x0 = px0 + 20 + c * (212 + 13)
            y0 = 548 + r * (118 + 12)
            out.append((x0, y0, x0 + 212, y0 + 118))
    return out

def draw_seats(base, t, states, a=1.0, pulse=False):
    """states: dict name -> 'lit'|'dim'|'empty'|'alt' (default 'lit')."""
    lay = layer(); d = ImageDraw.Draw(lay)
    f_head = F(CJK_B, 28); f_name = F(CJK_B, 32)
    for gi, ((gname, names), (px0, py0, px1, py1)) in enumerate(zip(GROUPS, SEAT_PANELS)):
        panel(d, px0, py0, px1, py1, 1.0)
        text_l(d, px0 + 25, 494, gname, f_head, with_a(FAINT, 235))
        for (name, (x0, y0, x1, y1)) in zip(names, seat_rects(px0)):
            st = states.get(name, "lit")
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if st == "empty":
                al = 200 if not pulse else int(150 + 70 * math.sin(t * 3.2))
                dashed_rect(d, x0, y0, x1, y1, with_a(CREAM_DIM, al))
                b = ink(d, name, f_name)
                d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), name,
                       font=f_name, fill=with_a(FAINT, 55))
            elif st == "dim":
                d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=with_a(PANEL, 110),
                                    outline=with_a(CREAM_DIM, 70), width=2)
                b = ink(d, name, f_name)
                d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), name,
                       font=f_name, fill=with_a(FAINT, 200))
            elif st == "alt":
                d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=with_a(PANEL, 250),
                                    outline=with_a(BRAND, 255), width=3)
                b = ink(d, name, f_name)
                d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), name,
                       font=f_name, fill=with_a(BRAND, 255))
            else:
                d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=with_a(PANEL, 235),
                                    outline=with_a(CREAM_DIM, 150), width=2)
                b = ink(d, name, f_name)
                d.text((cx - (b[0] + b[2]) / 2, cy - (b[1] + b[3]) / 2), name,
                       font=f_name, fill=with_a(CREAM, 255))
    fade_layer(base, lay, a)

def row_line(d, x, y_top, label, value, a, f_lab=None, f_val=None, vcol=None):
    f_lab = f_lab or F(CJK_R, 38); f_val = f_val or F(CJK_B, 40)
    if a <= 0: return
    text_l(d, x, y_top, label, f_lab, with_a(FAINT, int(240 * a)))
    text_l(d, x + 150, y_top - 2, value, f_val, with_a(vcol or CREAM, int(255 * a)))

# ---------------- a1: the withdrawal ----------------
def fa1(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE WITHDRAWAL", "卫冕冠军，退赛了")
    # phase 1: news card
    a_out = 1 - ease((t - 15) / 1.5)
    if a_out > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        panel(ld, 90, 430, 990, 1010, 1.0)
        chip(ld, 540, 512, "退赛官宣", F(CJK_B, 38), RED, RED)
        rows = [("人物", "莱巴金娜", 1.5), ("身份", "年终第一 · 卫冕冠军", 4.5),
                ("原因", "病毒性疾病", 7.5), ("时间", "周六 11:14", 10.5)]
        for i, (lab, val, st) in enumerate(rows):
            row_line(ld, 170, 620 + i * 100, lab, val, land(t, st))
        fade_layer(img, lay, a_out); d = ImageDraw.Draw(img, "RGBA")
    # phase 2+3: seats
    if t > 16:
        a_in = ease((t - 16.5) / 1.5)
        states = {}
        lit_order = ["萨巴伦卡", "高芙", "安德列娃", "佩古拉",
                     "斯维托丽娜", "诺斯科娃", "穆霍娃", "莱巴金娜"]
        for i, nm in enumerate(lit_order):
            states[nm] = "lit" if t > 18 + i * 0.9 else "dim"
        if t > 31:
            states["莱巴金娜"] = "empty"
        draw_seats(img, t, states, a=a_in, pulse=t > 36)
        d = ImageDraw.Draw(img, "RGBA")
        a_chip = land(t, 27) * (1 - ease((t - 30.5) / 1.0))
        if a_chip > 0:
            lay = layer(); ld = ImageDraw.Draw(lay)
            chip(ld, 292, 892, "媒体日 · 缺席", F(CJK_B, 30), FAINT, FAINT)
            fade_layer(img, lay, a_chip); d = ImageDraw.Draw(img, "RGBA")
        a_q = land(t, 38)
        if a_q > 0:
            lay = layer(); ld = ImageDraw.Draw(lay)
            text_c(ld, 540, 1120, "揭幕战就在明天——这一场，谁来打？",
                   F(CJK_B, 40), with_a(CREAM, 255))
            fade_layer(img, lay, a_q)
    return img

# ---------------- a2: the door opens ----------------
def fa2(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE COMEBACK SEAT", "顶上来的人")
    # phase 1: R6-2 callback card
    a_out = 1 - ease((t - 11.5) / 1.2)
    if a_out > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        panel(ld, 90, 430, 990, 920, 1.0)
        text_c(ld, 540, 478, "三天前 · 她被挡在门外", F(CJK_B, 36), with_a(CREAM_DIM, 245))
        d2 = ImageDraw.Draw(lay)
        d2.line([150, 560, 930, 560], fill=with_a(RED, 170), width=4)
        chip(ld, 838, 560, "门槛", F(CJK_B, 26), RED, RED, fill_a=200)
        rows = [(2.0, "全年竞逐榜 · Race 第十", CREAM, F(CJK_B, 40)),
                (4.5, "3,910 分", BRAND, F(TLSCORE, 62)),
                (7.0, "冠军保留席 · 把门槛抬高", CREAM, F(CJK_B, 40)),
                (9.5, "必须连赢两站 · 才够格", CREAM, F(CJK_B, 40))]
        for st, txt, col, fnt in rows:
            a = land(t, st)
            if a > 0:
                text_c(ld, 540, 612 + int((st - 2.0) / 2.5) * 78 if False else 0, "", fnt, col)
        ys = [606, 690, 776, 852]
        for (st, txt, col, fnt), y in zip(rows, ys):
            a = land(t, st)
            if a > 0:
                lay2 = layer(); l2 = ImageDraw.Draw(lay2)
                text_c(l2, 540, y, txt, fnt, with_a(col, 255))
                fade_layer(lay, lay2, a)
        fade_layer(img, lay, a_out); d = ImageDraw.Draw(img, "RGBA")
    # phase 2: seats, the empty slot fills
    if t > 12.5:
        a_in = ease((t - 12.5) / 1.2) * (1 - ease((t - 24.5) / 1.2))
        states = {nm: "lit" for names in GROUPS for nm in names[1]}
        states["莱巴金娜"] = "empty"
        draw_seats(img, t, states, a=a_in, pulse=t < 16)
        d = ImageDraw.Draw(img, "RGBA")
        if t > 16:
            lay = layer(); ld = ImageDraw.Draw(lay)
            px0, py0 = SEAT_PANELS[0][0], SEAT_PANELS[0][1]
            x0, y0, x1, y1 = seat_rects(px0)[0]
            a_fill = land(t, 16, 0.9)
            if a_fill > 0:
                ld.rounded_rectangle([x0, y0, x1, y1], radius=16,
                                     fill=with_a(PANEL, int(250 * a_fill)),
                                     outline=with_a(BRAND, int(255 * a_fill)), width=3)
                b = ink(ld, "科斯秋克", F(CJK_B, 32))
                ld.text(((x0 + x1) / 2 - (b[0] + b[2]) / 2, (y0 + y1) / 2 - (b[1] + b[3]) / 2),
                        "科斯秋克", font=F(CJK_B, 32), fill=with_a(BRAND, int(255 * a_fill)))
            fade_layer(img, lay, 1 - ease((t - 24.5) / 1.2)); d = ImageDraw.Draw(img, "RGBA")
            a_c1 = land(t, 19) * (1 - ease((t - 24.5) / 1.2)); a_c2 = land(t, 21) * (1 - ease((t - 24.5) / 1.2))
            if a_c1 > 0:
                lay = layer(); ld = ImageDraw.Draw(lay)
                chip(ld, 330, 898, "第一替补 (ALT)", F(CJK_B, 30), BRAND, BRAND)
                fade_layer(img, lay, a_c1); d = ImageDraw.Draw(img, "RGBA")
            if a_c2 > 0:
                lay = layer(); ld = ImageDraw.Draw(lay)
                chip(ld, 660, 898, "签位 [9]", F(CJK_B, 30), CREAM, CREAM_DIM)
                fade_layer(img, lay, a_c2); d = ImageDraw.Draw(img, "RGBA")
    # phase 3: golden line
    if t > 24.5:
        a_g = land(t, 25, 1.0)
        lay = layer(); ld = ImageDraw.Draw(lay)
        ld.rounded_rectangle([90, 520, 990, 780], radius=18, fill=with_a((8, 14, 29), 252),
                             outline=with_a(CREAM_DIM, 160), width=2)
        text_c(ld, 540, 566, "门从里面开了", F(DISPLAY, 84), with_a(CREAM, 255))
        text_c(ld, 540, 692, "三天前关上 · 三天后，从里面开", F(CJK_R, 30), with_a(FAINT, 235))
        fade_layer(img, lay, a_g)
    return img

# ---------------- a3: full entry ----------------
def fa3(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "FULL ENTRY", "答案：满格入场")
    a_out = 1 - ease((t - 26.5) / 1.2)
    if a_out > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        panel(ld, 90, 440, 990, 880, 1.0)
        a = land(t, 1.5)
        if a > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 520, "赛前顶入 ＝ 满格正选", F(DISPLAY, 66), with_a(CREAM, 255))
            fade_layer(lay, lay2, a)
        for st, txt in [(6.0, "三场小组赛 · 一场不少"), (9.5, "积分 · 奖金 · 按正选口径"),
                        (13.0, "她，不是来凑数的")]:
            a = land(t, st)
            if a > 0:
                lay2 = layer(); l2 = ImageDraw.Draw(lay2)
                y = 650 + int((st - 6.0) / 3.5) * 76
                text_c(l2, 540, y, txt, F(CJK_B, 38), with_a(CREAM_DIM, 245))
                fade_layer(lay, lay2, a)
        # trophy path bar
        a_bar = land(t, 17, 1.0)
        if a_bar > 0:
            text_c(ld, 540, 918, "捧杯的通道", F(CJK_B, 34), with_a(CREAM, int(255 * a_bar)))
            ld.rounded_rectangle([150, 978, 930, 1032], radius=27, outline=with_a(CREAM_DIM, 160), width=2)
            fw = 150 + 780 * ease((t - 18) / 6)
            if fw > 190:
                ld.rounded_rectangle([150, 978, fw, 1032], radius=27, fill=with_a(BRAND, 200))
            ld.ellipse([906, 984, 954, 1028], outline=with_a(BRAND, 255), width=3)
        a_cap = land(t, 24.5)
        if a_cap > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 1078, "规则上 · 真实敞开", F(CJK_R, 32), with_a(BRAND, 255))
            fade_layer(lay, lay2, a_cap)
        fade_layer(img, lay, a_out); d = ImageDraw.Draw(img, "RGBA")
    # phase 3: the watershed
    if t > 27.5:
        lay = layer(); ld = ImageDraw.Draw(lay)
        a_in = ease((t - 27.5) / 1.2)
        ld.line([120, 700, 960, 700], fill=with_a(CREAM_DIM, 200), width=3)
        ld.ellipse([528, 688, 552, 712], fill=with_a(CREAM, 255))
        chip(ld, 540, 622, "首战", F(CJK_B, 30), CREAM, CREAM_DIM)
        ld.line([470, 712, 330, 800], fill=with_a(BRAND, 200), width=3)
        ld.line([610, 712, 750, 800], fill=with_a(FAINT, 160), width=3)
        panel(ld, 90, 810, 500, 1020, 1.0)
        text_c(ld, 295, 852, "赛前顶入", F(CJK_B, 42), with_a(BRAND, 255))
        text_c(ld, 295, 928, "满格入场", F(CJK_R, 34), with_a(CREAM, 255))
        panel(ld, 580, 810, 990, 1020, 1.0)
        text_c(ld, 785, 852, "赛中顶入", F(CJK_B, 42), with_a(FAINT, 255))
        text_c(ld, 785, 928, "半路接盘", F(CJK_R, 34), with_a(CREAM_DIM, 255))
        a_cap = land(t, 36)
        if a_cap > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 1096, "分水岭 ＝ 顶进来的时间点", F(CJK_B, 36), with_a(CREAM, 255))
            fade_layer(lay, lay2, a_cap)
        fade_layer(img, lay, a_in)
    return img

# ---------------- a4: how alternates are named ----------------
def fa4(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE QUEUE", "替补，怎么点名")
    # phase 1: the queue
    a_out = 1 - ease((t - 25.5) / 1.2)
    if a_out > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        panel(ld, 70, 420, 1010, 1090, 1.0)
        rows = [(8, "诺斯科娃", "正选", FAINT, 2.0), (9, "斯瓦泰克", "赛季结束", RED, 5.0),
                (10, "科斯秋克", "第一替补", BRAND, 8.0), (11, "施耐德", "第二替补", CREAM_DIM, 11.0),
                (12, "约维奇", "排队", FAINT, 14.0)]
        for i, (rk, nm, tag, tcol, st) in enumerate(rows):
            a = land(t, st)
            if a <= 0: continue
            y = 470 + i * 92
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_l(l2, 120, y + 18, str(rk), F(TLSCORE, 44), with_a(CREAM_DIM, 255))
            text_l(l2, 215, y + 16, nm, F(CJK_B, 40), with_a(CREAM, 255))
            b = ink(l2, tag, F(CJK_B, 30))
            l2.text((950 - b[2], y + 24 - b[1]), tag, font=F(CJK_B, 30), fill=with_a(tcol, 255))
            if rk == 9 and t > 22:
                l2.line([205, y + 44, 480, y + 44], fill=with_a(RED, 220), width=4)
            fade_layer(lay, lay2, a)
        a_chip = land(t, 18)
        if a_chip > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            chip(l2, 540, 985, "第 8–20 名 · 第二位大满贯冠军？—— 无", F(CJK_B, 32), CREAM, CREAM_DIM)
            fade_layer(lay, lay2, a_chip)
        if t > 22:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            chip(l2, 790, 985 - 0, "", F(CJK_B, 30), RED, RED) if False else None
            text_c(l2, 540, 1030, "不来 ＝ 不占位", F(CJK_R, 28), with_a(RED, 235))
            fade_layer(lay, lay2, land(t, 22.5))
        fade_layer(img, lay, a_out); d = ImageDraw.Draw(img, "RGBA")
    # phase 2: the bench reshuffles
    if 26.5 < t <= 40.5:
        lay = layer(); ld = ImageDraw.Draw(lay)
        a_in = ease((t - 26.5) / 1.2) * (1 - ease((t - 39.5) / 1.0))
        text_c(ld, 540, 462, "她顶进去之后 · 替补席顺延一位", F(CJK_B, 34), with_a(CREAM, 255))
        slots = [("第一替补", "科斯秋克"), ("第二替补", "施耐德"), ("下一位", "约维奇")]
        shift = ease_io((t - 33) / 3)
        for i, (lab, nm) in enumerate(slots):
            x0 = 80 + i * 320
            if i == 0:
                y0 = 620 - 150 * shift
                al = 1 - shift
                if al > 0.02:
                    ld.rounded_rectangle([x0, y0, x0 + 280, y0 + 140], radius=16,
                                         fill=with_a(PANEL, int(240 * al)),
                                         outline=with_a(BRAND, int(255 * al)), width=3)
                    text_c(ld, x0 + 140, y0 + 48, nm, F(CJK_B, 38), with_a(BRAND, int(255 * al)))
                    text_c(ld, x0 + 140, 800, lab, F(CJK_R, 28), with_a(FAINT, int(235 * al)))
                if shift > 0.05:
                    text_c(ld, x0 + 140, 452 + 0, "", F(CJK_B, 30), with_a(BRAND, 255))
            else:
                nx = x0 - 320 * shift
                ld.rounded_rectangle([nx, 620, nx + 280, 760], radius=16,
                                     fill=with_a(PANEL, 240), outline=with_a(CREAM_DIM, 150), width=2)
                text_c(ld, nx + 140, 668, nm, F(CJK_B, 38), with_a(CREAM, 255))
                newlab = ["第一替补", "第二替补", "下一位"][i - 1] if shift > 0.5 else lab
                text_c(ld, nx + 140, 800, newlab, F(CJK_R, 28), with_a(FAINT, 235))
        if shift > 0.3:
            text_c(ld, 220, 420, "顶入正选", F(CJK_B, 30), with_a(BRAND, int(255 * min(1, shift))))
        a_note = land(t, 37)
        if a_note > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 900, "替补必须本人到场 · 整个小组赛随叫随到", F(CJK_R, 32), with_a(CREAM_DIM, 245))
            fade_layer(lay, lay2, a_note)
        fade_layer(img, lay, a_in); d = ImageDraw.Draw(img, "RGBA")
    # phase 3: WTA vs ATP
    if t > 41:
        lay = layer(); ld = ImageDraw.Draw(lay)
        a_in = ease((t - 41) / 1.2)
        for x0, x1, head, rows in [
                (70, 520, "WTA", ["替补 2 名", "本人到场待命", "小组赛全程 · 随叫随到"]),
                (560, 1010, "ATP", ["官方指定 1 名", "须出席赛前发布会", "待命至最后一场小组赛开打"])]:
            panel(ld, x0, 440, x1, 1050, 1.0)
            text_c(ld, (x0 + x1) / 2, 486, head, F(TLSCORE, 56), with_a(BRAND, 255))
            for i, r in enumerate(rows):
                a = land(t, 43 + i * 2.2 + (0 if x0 < 500 else 0.8))
                if a > 0:
                    lay2 = layer(); l2 = ImageDraw.Draw(lay2)
                    text_c(l2, (x0 + x1) / 2, 620 + i * 130, r, F(CJK_B, 33), with_a(CREAM, 255))
                    fade_layer(ld.__self__ if False else lay, lay2, a) if False else fade_layer(lay, lay2, a)
        a_nm = land(t, 52)
        if a_nm > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            chip(l2, 785, 1128, "今年都灵 · 德米纳尔", F(CJK_B, 30), CREAM, CREAM_DIM)
            fade_layer(lay, lay2, a_nm)
        fade_layer(img, lay, a_in)
    return img

# ---------------- a5: three timings (branches 1-2) ----------------
def _axis(ld, y=620):
    ld.line([110, y, 970, y], fill=with_a(CREAM_DIM, 200), width=3)
    for x, lab in [(200, "第 1 场"), (460, "第 2 场"), (720, "第 3 场"), (930, "半决赛")]:
        ld.line([x, y - 12, x, y + 12], fill=with_a(CREAM_DIM, 200), width=3)
        text_c(ld, x, y - 62, lab, F(CJK_R, 28), with_a(FAINT, 235))

def fa5(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THREE TIMINGS", "三种顶入，三个命")
    lay = layer(); ld = ImageDraw.Draw(lay)
    if land(t, 0.5) > 0:
        _axis(ld)
    # branch 1
    a1 = land(t, 4)
    if a1 > 0:
        lay2 = layer(); l2 = ImageDraw.Draw(lay2)
        l2.ellipse([98, 608, 122, 632], fill=with_a(BRAND, 255))
        l2.line([110, 632, 110, 760], fill=with_a(BRAND, 200), width=3)
        panel(l2, 70, 760, 520, 1090, 1.0)
        text_c(l2, 295, 796, "首战前顶入", F(CJK_B, 42), with_a(BRAND, 255))
        text_c(l2, 295, 884, "满格正选", F(CJK_R, 34), with_a(CREAM, 255))
        text_c(l2, 295, 950, "打满三场 · 从零攒战绩", F(CJK_R, 30), with_a(CREAM_DIM, 245))
        chip(l2, 295, 1036, "科斯秋克 · 这一种", F(CJK_B, 26), BRAND, BRAND)
        fade_layer(lay, lay2, a1)
    # branch 2
    a2 = land(t, 19)
    if a2 > 0:
        lay2 = layer(); l2 = ImageDraw.Draw(lay2)
        l2.ellipse([578, 608, 602, 632], fill=with_a(CREAM, 255))
        l2.line([590, 632, 590, 760], fill=with_a(CREAM_DIM, 200), width=3)
        panel(l2, 560, 760, 1010, 1090, 1.0)
        text_c(l2, 785, 796, "打了一两场后顶入", F(CJK_B, 42), with_a(CREAM, 255))
        text_c(l2, 785, 884, "只继承席位和赛程", F(CJK_R, 32), with_a(CREAM, 255))
        text_c(l2, 785, 950, "战绩不继承 · 0 胜 0 负起步", F(CJK_R, 30), with_a(CREAM_DIM, 245))
        text_c(l2, 785, 1012, "只打剩下的场次", F(CJK_R, 30), with_a(CREAM_DIM, 245))
        fade_layer(lay, lay2, a2)
    fade_layer(img, lay, 1.0)
    return img

# ---------------- a6: the hard line + the classic mix-up ----------------
def fa6(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE HARD LINE", "最后一条硬线")
    a_out = 1 - ease((t - 10.5) / 1.0)
    if a_out > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        panel(ld, 90, 440, 990, 900, 1.0)
        a = land(t, 1.2)
        if a > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 520, "只剩最后一场 · 照样能换人", F(CJK_B, 42), with_a(CREAM, 255))
            fade_layer(lay, lay2, a)
        a = land(t, 4.5)
        if a > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 620, "2024 卡萨金娜 · 2023 胡尔卡奇", F(CJK_R, 33), with_a(CREAM_DIM, 245))
            text_c(l2, 540, 684, "都只打了一场", F(CJK_R, 33), with_a(CREAM_DIM, 245))
            fade_layer(lay, lay2, a)
        a = land(t, 7.5)
        if a > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            chip(l2, 540, 806, "半决赛开始 · 不再递补 · 对手轮空晋级", F(CJK_B, 32), RED, RED)
            fade_layer(lay, lay2, a)
        fade_layer(img, lay, a_out); d = ImageDraw.Draw(img, "RGBA")
    if t > 11.5:
        lay = layer(); ld = ImageDraw.Draw(lay)
        a_in = ease((t - 11.5) / 1.2)
        panel(ld, 70, 430, 1010, 1100, 1.0)
        text_c(ld, 540, 486, "最容易讲错的一点", F(CJK_R, 30), with_a(FAINT, 235))
        a = land(t, 12.5)
        if a > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 556, "比赛中退赛，不等于退出赛事", F(DISPLAY, 56), with_a(CREAM, 255))
            fade_layer(lay, lay2, a)
        for st, txt in [(16.0, "比赛中退赛：人留在赛事里 · 替补不上"),
                        (19.0, "正式退出赛事：递补触发 · 退了不能回来")]:
            a = land(t, st)
            if a > 0:
                lay2 = layer(); l2 = ImageDraw.Draw(lay2)
                y = 720 + int((st - 16.0) / 3.0) * 110
                text_c(l2, 540, y, txt, F(CJK_B, 34), with_a(CREAM_DIM, 245))
                fade_layer(lay, lay2, a)
        fade_layer(img, lay, a_in)
    return img

# ---------------- a7: the money ladder ----------------
def fa7(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE MONEY", "替补席，值多少钱")
    steps = [
        (90, 900, "替补费", "$100,000", "一场没打 · 坐着能领", 2.0),
        (405, 815, "参赛费", "按场次另算", "真上了场 · 按自己打的场次", 8.0),
        (720, 730, "胜场奖金", "+$230,000", "小组赛每赢一场 · 再加 200 分", 14.0),
    ]
    for x0, ytop, lab, amt, cap, st in steps:
        a = land(t, st, 0.8)
        if a <= 0: continue
        lay = layer(); ld = ImageDraw.Draw(lay)
        rise = (1 - a) * 40
        ld.rounded_rectangle([x0, ytop + rise, x0 + 270, 1020 + rise], radius=14,
                             fill=with_a(PANEL, 235), outline=with_a(CREAM_DIM, 150), width=2)
        text_c(ld, x0 + 135, ytop + 26 + rise, lab, F(CJK_B, 34), with_a(CREAM_DIM, 245))
        f_amt = F(TLSCORE, 44) if amt.startswith("$") or amt.startswith("+") else F(CJK_B, 38)
        text_c(ld, x0 + 135, ytop + 78 + rise, amt, f_amt, with_a(BRAND, 255))
        text_c(ld, x0 + 135, 1062, cap, F(CJK_R, 27), with_a(FAINT, 235))
        fade_layer(img, lay, a); d = ImageDraw.Draw(img, "RGBA")
    a_fin = land(t, 21.5)
    if a_fin > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        text_c(ld, 540, 1146, "科斯秋克按正选口径 · 和任何正选分毫不差", F(CJK_B, 34), with_a(CREAM, 255))
        fade_layer(img, lay, a_fin)
    return img

# ---------------- a8: the math wall ----------------
def fa8(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE MATH WALL", "那堵数学的墙")
    lay = layer(); ld = ImageDraw.Draw(lay)
    panel(ld, 70, 430, 1010, 1000, 1.0)
    def rank_row(y, rk, who, rec, tag, st, dim=False, slide=0):
        a = land(t, st)
        if a <= 0: return
        lay2 = layer(); l2 = ImageDraw.Draw(lay2)
        yy = y + slide
        chip(l2, 150, yy + 42, rk, F(TLSCORE, 36), FAINT if dim else BRAND,
             FAINT if dim else BRAND)
        text_l(l2, 215, yy + 14, f"{who} · {rec}", F(CJK_B, 38),
               with_a(FAINT if dim else CREAM, 255))
        b = ink(l2, tag, F(CJK_R, 28))
        l2.text((950 - b[2], yy + 22 - b[1]), tag, font=F(CJK_R, 28),
                fill=with_a(FAINT, 235))
        fade_layer(lay, lay2, a * (0.55 if dim else 1.0))
    rank_row(500, "1", "甲", "2 胜 1 负", "打满三场", 2.0)
    rank_row(610, "2", "乙", "2 胜 0 负", "只打两场", 6.0)
    a_note = land(t, 11)
    if a_note > 0:
        lay2 = layer(); l2 = ImageDraw.Draw(lay2)
        text_c(l2, 540, 742, "同为两胜 · 第二条比已赛场次", F(CJK_B, 33), with_a(CREAM, 255))
        fade_layer(lay, lay2, a_note)
    rank_row(830, "3", "丙", "2 胜 · 只打两场", "三人同分 · 先出局", 16.0, dim=True, slide=26)
    # the wall: a barrier slab lands between the standings note and the
    # short-handed row (never over text)
    a_wall = ease((t - 19) / 2.5)
    if a_wall > 0:
        bw = 860 * a_wall
        ld.rounded_rectangle([110, 790, 110 + bw, 808], radius=9,
                             fill=with_a(RIM, 210), outline=with_a(CREAM_DIM, 130), width=2)
        x = 170
        while x < 110 + bw - 30:
            ld.line([x, 792, x, 806], fill=with_a(CREAM_DIM, 90), width=3)
            x += 43
    fade_layer(img, lay, 1.0); d = ImageDraw.Draw(img, "RGBA")
    a_cap = land(t, 24)
    if a_cap > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        text_c(ld, 540, 1058, "半路顶进来的人 · 全赢也几乎被压住", F(CJK_B, 33), with_a(CREAM, 255))
        fade_layer(img, lay, a_cap); d = ImageDraw.Draw(img, "RGBA")
    a_cap2 = land(t, 26.5)
    if a_cap2 > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        text_c(ld, 540, 1128, "不是实力问题 · 是规则砌的墙", F(CJK_R, 30), with_a(FAINT, 235))
        fade_layer(img, lay, a_cap2)
    return img

# ---------------- a9: precedents I ----------------
def fa9(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "PRECEDENTS · I", "历史，划好了线")
    a_v = land(t, 1.5)
    if a_v > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        text_c(ld, 540, 442, "赛前顶入，上限看实力 · 赛中顶入，至今无人进四强",
               F(CJK_B, 33), with_a(CREAM, 255))
        fade_layer(img, lay, a_v); d = ImageDraw.Draw(img, "RGBA")
    cards = [
        ("2018", "贝尔滕斯", "赛前顶替哈勒普 · 两胜一负 · 打进四强", BRAND, 5.0),
        ("2011", "巴托丽", "只打最后一场 · 赢了阿扎伦卡 · 仍列小组第四", CREAM_DIM, 16.0),
        ("2021", "辛纳", "开赛前 4 小时接通知 · 横扫一场 · 没出线", CREAM_DIM, 27.0),
    ]
    for i, (yr, nm, line, rim, st) in enumerate(cards):
        a = land(t, st, 0.8)
        if a <= 0: continue
        lay = layer(); ld = ImageDraw.Draw(lay)
        y0 = 530 + i * 168
        ld.rounded_rectangle([80, y0, 1000, y0 + 150], radius=16, fill=with_a(PANEL, 235),
                             outline=with_a(rim, 220), width=2)
        text_l(ld, 120, y0 + 44, yr, F(TLSCORE, 54), with_a(BRAND if rim == BRAND else CREAM_DIM, 255))
        text_l(ld, 330, y0 + 26, nm, F(CJK_B, 42), with_a(CREAM, 255))
        text_l(ld, 330, y0 + 92, line, F(CJK_R, 29), with_a(CREAM_DIM, 245))
        fade_layer(img, lay, a); d = ImageDraw.Draw(img, "RGBA")
    return img

# ---------------- a10: precedents II (Stepanek) ----------------
def _racket(ld, cx, cy, s, col):
    ld.ellipse([cx - 52 * s, cy - 66 * s, cx + 52 * s, cy + 66 * s], outline=col, width=4)
    for dx in (-26, 0, 26):
        ld.line([cx + dx * s, cy - 60 * s, cx + dx * s, cy + 60 * s], fill=col, width=2)
    for dy in (-33, 0, 33):
        ld.line([cx - 46 * s, cy + dy * s, cx + 46 * s, cy + dy * s], fill=col, width=2)
    ld.line([cx, cy + 66 * s, cx, cy + 128 * s], fill=col, width=6)

def _sock(ld, cx, cy, s, col):
    ld.rounded_rectangle([cx - 26 * s, cy - 70 * s, cx + 26 * s, cy + 6 * s], radius=10, outline=col, width=4)
    ld.arc([cx - 26 * s, cy - 20 * s, cx + 56 * s, cy + 62 * s], start=0, end=90, fill=col, width=4)
    ld.line([cx + 26 * s, cy + 6 * s, cx + 26 * s, cy + 20 * s], fill=col, width=4)

def _case(ld, cx, cy, s, col):
    ld.rounded_rectangle([cx - 58 * s, cy - 38 * s, cx + 58 * s, cy + 52 * s], radius=10, outline=col, width=4)
    ld.rounded_rectangle([cx - 22 * s, cy - 62 * s, cx + 22 * s, cy - 38 * s], radius=8, outline=col, width=4)
    ld.line([cx - 58 * s, cy - 6 * s, cx + 58 * s, cy - 6 * s], fill=col, width=2)

def fa10(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "PRECEDENTS · II", "最仓促的替补")
    lay = layer(); ld = ImageDraw.Draw(lay)
    panel(ld, 80, 430, 1000, 1030, 1.0)
    a = land(t, 1.2)
    if a > 0:
        lay2 = layer(); l2 = ImageDraw.Draw(lay2)
        text_l(l2, 130, 478, "2008", F(TLSCORE, 54), with_a(CREAM_DIM, 255))
        text_l(l2, 330, 484, "斯捷潘内克", F(CJK_B, 44), with_a(CREAM, 255))
        fade_layer(lay, lay2, a)
    for st, txt in [(4.0, "世界第 27 · 正在泰国度假"),
                    (7.0, "排在他前面的 16 个人 · 都拒绝来当替补"),
                    (10.0, "装备卡在海关")]:
        a = land(t, st)
        if a > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            y = 596 + int((st - 4.0) / 3.0) * 62
            text_c(l2, 540, y, txt, F(CJK_R, 32), with_a(CREAM_DIM, 245))
            fade_layer(lay, lay2, a)
    a_ic = land(t, 13.5, 1.0)
    if a_ic > 0:
        lay2 = layer(); l2 = ImageDraw.Draw(lay2)
        col = with_a(CREAM, int(235 * a_ic))
        _case(l2, 250, 872, 0.9, col)
        _racket(l2, 540, 838, 0.9, col)
        _sock(l2, 800, 864, 0.9, col)
        _sock(l2, 862, 864, 0.9, col)
        text_c(l2, 250, 962, "行李 · 卡住了", F(CJK_R, 26), with_a(FAINT, int(235 * a_ic)))
        text_c(l2, 540, 984, "球拍 · 借德约科维奇的", F(CJK_R, 26), with_a(FAINT, int(235 * a_ic)))
        text_c(l2, 830, 962, "袜子 · 借穆雷的", F(CJK_R, 26), with_a(FAINT, int(235 * a_ic)))
        fade_layer(lay, lay2, 1.0)
    fade_layer(img, lay, 1.0); d = ImageDraw.Draw(img, "RGBA")
    a_fin = land(t, 19)
    if a_fin > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        text_c(ld, 540, 1096, "上场 · 打了费德勒", F(CJK_B, 36), with_a(BRAND, 255))
        fade_layer(img, lay, a_fin)
    return img

# ---------------- a11: the debate ----------------
def fa11(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE DEBATE", "该不该有资格")
    cols = [
        (60, 520, "该", BRAND, [(4.0, ["替补是规则预先点名的", "正式角色"]),
                                (13.0, ["她赢下的每一分", "都是真打出来的"])]),
        (560, 1020, "不该", RED, [(8.0, ["出线名额，属于", "从头打满的人"]),
                                  (17.0, ["只打一场挤掉打满三场的人", "对正选不公平"])]),
    ]
    for x0, x1, head, hcol, items in cols:
        lay = layer(); ld = ImageDraw.Draw(lay)
        panel(ld, x0, 430, x1, 980, 1.0)
        chip(ld, (x0 + x1) / 2, 505, head, F(CJK_B, 40), hcol, hcol)
        fade_layer(img, lay, 1.0); d = ImageDraw.Draw(img, "RGBA")
        for st, lines in items:
            a = land(t, st)
            if a <= 0: continue
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            y = 620 + (0 if st < 10 else 170)
            for j, ln in enumerate(lines):
                text_c(l2, (x0 + x1) / 2, y + j * 52, ln, F(CJK_R, 31), with_a(CREAM, 255))
            fade_layer(img, lay2, a); d = ImageDraw.Draw(img, "RGBA")
    a_v = land(t, 24)
    if a_v > 0:
        lay = layer(); ld = ImageDraw.Draw(lay)
        ld.rounded_rectangle([140, 1030, 940, 1184], radius=16, fill=with_a(PANEL, 245),
                             outline=with_a(BRAND, 220), width=2)
        text_c(ld, 540, 1058, "资格，给 · 路，用数学压窄", F(DISPLAY, 44), with_a(CREAM, 255))
        text_c(ld, 540, 1128, "规则自己 · 判了个折中", F(CJK_R, 28), with_a(FAINT, 235))
        fade_layer(img, lay, a_v)
    return img

# ---------------- a12: closing ----------------
def fa12(t, dur):
    img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
    title_block(d, t, "THE LAST QUESTION", "最后一个问题")
    a_out = 1 - ease((t - 10.5) / 1.2)
    if a_out > 0:
        states = {nm: "dim" for names in GROUPS for nm in names[1]}
        states["莱巴金娜"] = "empty"
        states["高芙"] = "lit"; states["佩古拉"] = "lit"; states["诺斯科娃"] = "lit"
        draw_seats(img, t, states, a=a_out)
        d = ImageDraw.Draw(img, "RGBA")
        # Kostyuk's filled seat over the empty slot
        lay = layer(); ld = ImageDraw.Draw(lay)
        x0, y0, x1, y1 = seat_rects(SEAT_PANELS[0][0])[0]
        ld.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=with_a(PANEL, 250),
                             outline=with_a(BRAND, 255), width=3)
        b = ink(ld, "科斯秋克", F(CJK_B, 32))
        ld.text(((x0 + x1) / 2 - (b[0] + b[2]) / 2, (y0 + y1) / 2 - (b[1] + b[3]) / 2),
                "科斯秋克", font=F(CJK_B, 32), fill=with_a(BRAND, 255))
        fade_layer(img, lay, a_out); d = ImageDraw.Draw(img, "RGBA")
        a_l = land(t, 7.5) * a_out
        if a_l > 0:
            lay = layer(); ld = ImageDraw.Draw(lay)
            text_c(ld, 540, 892, "她是满格入场 · 和正选同一条起跑线", F(CJK_B, 34), with_a(CREAM, 255))
            fade_layer(img, lay, a_l); d = ImageDraw.Draw(img, "RGBA")
    if 11.5 < t <= 22.5:
        lay = layer(); ld = ImageDraw.Draw(lay)
        a_in = ease((t - 11.5) / 1.2) * (1 - ease((t - 21.5) / 1.0))
        panel(ld, 80, 470, 1000, 950, 1.0)
        lines = [(13.0, "替补席从来不是观众席"), (16.0, "它离冠军，只隔着一次退赛"),
                 (19.0, "和一条写在规则里的路")]
        for i, (st, ln) in enumerate(lines):
            a = land(t, st)
            if a > 0:
                lay2 = layer(); l2 = ImageDraw.Draw(lay2)
                text_c(l2, 540, 566 + i * 118, ln, F(DISPLAY, 54), with_a(CREAM, 255))
                fade_layer(lay, lay2, a)
        fade_layer(img, lay, a_in); d = ImageDraw.Draw(img, "RGBA")
    if t > 23:
        lay = layer(); ld = ImageDraw.Draw(lay)
        a_in = ease((t - 23) / 1.2)
        text_c(ld, 540, 500, "她真捧起奖杯", F(CJK_B, 42), with_a(CREAM, 255))
        text_c(ld, 540, 566, "这座冠军，你认不认？", F(DISPLAY, 58), with_a(CREAM, 255))
        fade_layer(img, lay, a_in); d = ImageDraw.Draw(img, "RGBA")
        a_c = land(t, 26.5)
        if a_c > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            chip(l2, 380, 800, "认", F(CJK_B, 48), BRAND, BRAND, pad_x=56, pad_y=20)
            chip(l2, 700, 800, "不认", F(CJK_B, 48), RED, RED, pad_x=56, pad_y=20)
            fade_layer(img, lay2, a_c); d = ImageDraw.Draw(img, "RGBA")
        a_s = land(t, 29.5)
        if a_s > 0:
            lay2 = layer(); l2 = ImageDraw.Draw(lay2)
            text_c(l2, 540, 950, "评论区 · 站个队", F(CJK_R, 30), with_a(FAINT, 235))
            fade_layer(img, lay2, a_s)
    return img

FNS = {"a1": fa1, "a2": fa2, "a3": fa3, "a4": fa4, "a5": fa5, "a6": fa6,
       "a7": fa7, "a8": fa8, "a9": fa9, "a10": fa10, "a11": fa11, "a12": fa12}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    dur_o = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
    ver = sys.argv[3] if len(sys.argv) > 3 else "v1"
    keys = list(FNS) if which == "all" else [which]
    for k in keys:
        dur = dur_o if (dur_o and len(keys) == 1) else DURS[k]
        out = f"alt-seg{int(k[1:]):02d}-{ver}.mp4"
        render(lambda tt, fn=FNS[k], dd=dur: fn(tt, dd), dur, out)
