#!/usr/bin/env python3
"""Animations for wta-finals-hotmic-2026 (网球有故事 · 热麦克风事件).
Series tokens + alignment standard via anim_common (walkover/zverev/slot8 定版).
All card text ink bottoms <= 1240 (checklist #24). No tennis being played is
drawn; only mechanisms, cards, timelines, tables.
hm1 直播链路 | hmq 引言卡背板 | hm4 声明与报道 | hm5 冯德罗索娃帖卡背板
hm6 时间线 | hm7 分组表
Usage: python3 render_anims.py [hm1|hmq|hm4|hm5|hm6|hm7|all] [dur] [ver]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
F_ENB = ImageFont.truetype(INTER, 40)
F_QUOTE = ImageFont.truetype(DISPLAY, 150)

def verdict(d, t, t0, text, font=F_VERDICT):
    a = ease((t - t0) / 0.9)
    if a <= 0: return
    d.rounded_rectangle([120, 1158, 960, 1240], radius=16, outline=with_a(BRAND, int(240 * a)), width=3)
    b = d.textbbox((0, 0), text, font=font)
    d.text((W / 2 - (b[0] + b[2]) / 2, 1199 - (b[1] + b[3]) / 2), text, font=font, fill=with_a(BRAND, 255 * a))

def row_card(d, t, t0, y, head, body, brand=False, h=140):
    a = ease((t - t0) / 0.7)
    if a <= 0: return
    slide = (1 - a) * 26
    d.rounded_rectangle([110, y + slide, 970, y + h + slide], radius=14, fill=with_a(PANEL, int(185 * a)))
    d.rectangle([110, y + slide, 122, y + h + slide], fill=with_a(BRAND if brand else CREAM_DIM, int(225 * a)))
    text_l(d, 150, y + 22 + slide, head, F_ROW, with_a(BRAND if brand else CREAM, 255 * a))
    text_l(d, 150, y + 82 + slide, body, F_ROWS, with_a(CREAM_DIM, 255 * a))

# ================= hm1: 直播链路示意 =================
def hm1_frame(dur):
    P = lambda x: x * dur / 16.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "THE MIC WAS ON", "麦克风，一直开着")
        # court schematic (top-down, lines only -- no players)
        ca = ease((t - P(1.0)) / 0.8)
        if ca > 0:
            x0, y0, x1, y1 = 240, 470, 840, 830
            d.rounded_rectangle([x0, y0, x1, y1], radius=10, outline=with_a(CREAM_DIM, int(200 * ca)), width=3)
            d.line([540, y0, 540, y1], fill=with_a(CREAM_DIM, int(160 * ca)), width=3)
            d.line([x0, 650, x1, 650], fill=with_a(CREAM_DIM, int(160 * ca)), width=3)
            text_c(d, 540, 852, "训练场 · 印第安维尔斯", F_ROWS, with_a(FAINT, 230 * ca))
        # two mic nodes with pulsing rings
        for i, (mx, my) in enumerate([(240, 900), (840, 900)]):
            ma = ease((t - P(2.2) - i * 0.5) / 0.6)
            if ma <= 0: continue
            pulse = 0.5 + 0.5 * math.sin(t * 3.2 + i)
            for r in (26, 44, 62):
                d.ellipse([mx - r, my - r, mx + r, my + r], outline=with_a(RED, int(120 * ma * pulse)), width=3)
            d.ellipse([mx - 13, my - 13, mx + 13, my + 13], fill=with_a(RED, 255 * ma))
        ma2 = ease((t - P(3.4)) / 0.6)
        if ma2 > 0:
            text_c(d, 540, 972, "场边麦克风 · 开着", F_ROW, with_a(RED, 255 * ma2))
        # chain chips
        chip(d, 250, 1085, "直播信号", F_CHIP, CREAM, CREAM_DIM)
        aa = ease((t - P(5.2)) / 0.5)
        if aa > 0:
            d.line([360, 1085, 470, 1085], fill=with_a(BRAND, int(255 * aa)), width=4)
        chip(d, 590, 1085, "全世界都听得见", F_CHIP, BRAND, BRAND)
        verdict(d, t, P(11.0), "悄悄话，就这么出去了")
        return img
    return fn

# ================= hmq: 引言卡背板 =================
def hmq_frame(dur):
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        a = ease(t / 1.0)
        # giant quote glyph, top area (builder title zone kept clear: glyph starts y>=210)
        d.text((120, 210), "“", font=F_QUOTE, fill=with_a(BRAND, int(150 * a)))
        # thin rule near bottom of card zone, well above subtitle band
        d.line([140, 1150, 940, 1150], fill=with_a(CREAM_DIM, int(90 * a)), width=2)
        return img
    return fn

# ================= hm4: 声明与报道 =================
def hm4_frame(dur):
    P = lambda x: x * dur / 30.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "FULL RESPONSIBILITY", "全部责任，我们担")
        row_card(d, t, P(2.0), 470, "训练直播 · 全部下架", "本届所有训练直播，自官方频道撤下", brand=True)
        row_card(d, t, P(8.0), 660, "声明致歉 · 承担全部责任", "SKY SPORTS / FRONT OFFICE SPORTS / BBC", brand=False)
        row_card(d, t, P(14.0), 850, "余下直播 · 取消音频", "直播继续，但不再收音", brand=False)
        verdict(d, t, P(22.0), "删得掉视频，删不回传播")
        return img
    return fn

# ================= hm5: 冯德罗索娃帖卡背板 =================
def hm5_frame(dur):
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        a = ease((t - 0.3) / 0.8)
        if a > 0:
            # social-post frame outline; quote text is rendered by builder cues inside
            d.rounded_rectangle([90, 300, 990, 1120], radius=22, outline=with_a(CREAM_DIM, int(170 * a)), width=2)
            text_l(d, 130, 336, "INSTAGRAM · 公开发帖", F_EN, with_a(FAINT, 240 * a))
            text_l(d, 130, 388, "冯德罗索娃", F_NAME, with_a(CREAM, 255 * a))
            text_l(d, 470, 396, "前温网冠军", F_ROWS, with_a(BRAND, 255 * a))
            d.line([130, 480, 950, 480], fill=with_a(CREAM_DIM, int(120 * a)), width=2)
        return img
    return fn

# ================= hm6: 时间线 =================
def hm6_frame(dur):
    P = lambda x: x * dur / 24.0
    nodes = [
        ("2023", "美网", "萨巴伦卡幕后砸拍，被镜头拍下"),
        ("2026.01", "澳网", "高芙躲镜头砸拍 · 球员讨隐私"),
        ("2026.11", "总决赛", "训练麦克风未关 · 悄悄话流出"),
    ]
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "NOT THE FIRST TIME", "这条边界，吵了三年")
        x = 540
        la = ease((t - P(1.0)) / 0.8)
        if la > 0:
            d.line([x, 470, x, 1080], fill=with_a(CREAM_DIM, int(170 * la)), width=3)
        for i, (yr, ev, desc) in enumerate(nodes):
            y = 520 + i * 240
            na = ease((t - P(2.5 + i * 4.5)) / 0.7)
            if na <= 0: continue
            last = i == 2
            d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=with_a(BRAND if last else PANEL, 255 * na),
                      outline=with_a(BRAND, int(230 * na)), width=3)
            text_l(d, 130, y - 52, yr, F_NUM, with_a(BRAND if last else CREAM, 255 * na))
            text_l(d, 130, y + 22, ev, F_ROW, with_a(CREAM, 255 * na))
            text_l(d, 620, y - 30, desc, F_ROWS, with_a(CREAM_DIM, 255 * na))
        verdict(d, t, P(19.0), "吵了三年，边界还没划出来")
        return img
    return fn

# ================= hm7: 分组表 =================
def hm7_frame(dur):
    P = lambda x: x * dur / 16.0
    g1 = ["莱巴金娜", "高芙", "佩古拉", "诺斯科娃"]
    g2 = ["萨巴伦卡", "安德列娃", "斯维托丽娜", "穆霍娃"]
    def group(d, t, t0, x0, title, names, hot):
        a = ease((t - t0) / 0.7)
        if a <= 0: return
        panel(d, x0, 450, x0 + 420, 1010, a)
        text_c(d, x0 + 210, 486, title, F_ROW, with_a(CREAM, 255 * a))
        for i, n in enumerate(names):
            y = 590 + i * 105
            is_hot = (n == hot)
            if is_hot:
                d.rounded_rectangle([x0 + 28, y - 12, x0 + 392, y + 66], radius=12,
                                    outline=with_a(BRAND, int(230 * a)), width=3)
            text_c(d, x0 + 210, y, n, F_NAME, with_a(BRAND if is_hot else CREAM_DIM, 255 * a))
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "THE GROUPS", "周日开打 · 分组已定")
        group(d, t, P(1.5), 70, "第一组", g1, "佩古拉")
        group(d, t, P(3.0), 590, "第二组", g2, "安德列娃")
        na = ease((t - P(7.0)) / 0.7)
        if na > 0:
            text_c(d, 540, 1052, "佩古拉 × 安德列娃 · 最早半决赛相遇", F_ROWS, with_a(CREAM, 255 * na))
        verdict(d, t, P(11.5), "话传出去了，球还得照打")
        return img
    return fn

BUILDERS = {
    "hm1": (hm1_frame, 16), "hmq": (hmq_frame, 48), "hm4": (hm4_frame, 30),
    "hm5": (hm5_frame, 28), "hm6": (hm6_frame, 24), "hm7": (hm7_frame, 16),
}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    dur_o = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
    ver = sys.argv[3] if len(sys.argv) > 3 else "v1"
    keys = list(BUILDERS) if which == "all" else [which]
    for k in keys:
        fnf, base = BUILDERS[k]
        dur = dur_o if (dur_o and len(keys) == 1) else base
        out = os.path.join(os.environ.get("HOTMIC_OUT", os.path.dirname(os.path.abspath(__file__))), f"hotmic-{k}-{ver}.mp4")
        render(fnf(dur), dur, out)
