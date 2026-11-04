# -*- coding: utf-8 -*-
"""A5 ATP 对照:同一条规则今年没触发——四冠三人全在前七,专座空置,顺延第九。
与 render_anims.py 同一视觉语法(BG/title_block/rule_row/panel)。"""
import sys
sys.path.insert(0, "/home/hatch/workspace/wta-finals-slot8-20261103/prod/anim")
from anim_common import *  # noqa
from render_anims import rule_row, F_VERDICT, F_ROWS  # noqa
from PIL import ImageDraw

def a5_frame(dur):
    P = lambda x: x * dur / 24.0
    def fn(t):
        img = BG.copy(); d = ImageDraw.Draw(img, "RGBA")
        title_block(d, t, "SAME RULE · ATP FINALS", "男子那边，同一条规则")
        rule_row(d, t, P(1.2), 560, "今年四座大满贯 · 三位冠军", "三个人，全部排在 Race 前七", False)
        rule_row(d, t, P(7.6), 800, "冠军专座", "今年空置 · 没有人需要它", True)
        rule_row(d, t, P(13.6), 1040, "第八个名额", "老老实实顺延 · 给了积分第九名", False)
        va = ease((t - P(19.0)) / 0.9)
        if va > 0:
            vt = "同一张入场券 · 两种发法"
            d.rounded_rectangle([120, 1300, 960, 1382], radius=16, outline=with_a(BRAND, int(240 * va)), width=3)
            b = d.textbbox((0, 0), vt, font=F_VERDICT)
            d.text((W / 2 - (b[0] + b[2]) / 2, 1341 - (b[1] + b[3]) / 2), vt, font=F_VERDICT, fill=with_a(BRAND, 255 * va))
        return img
    return fn

if __name__ == "__main__":
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
    ver = sys.argv[2] if len(sys.argv) > 2 else "v1"
    render(a5_frame(dur), dur, f"/home/hatch/workspace/wta-finals-slot8-20261103/prod/anim/slot8-a5-atp-{ver}.mp4")
    print("A5 done")
