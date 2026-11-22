#!/usr/bin/env python3
"""EP13 网中间矮：浅 V 网高、斜线长度、真空弹道余量。

假设写在输出里，和 sources.md 第四节一致。不计空气阻力和旋转。
"""
from __future__ import annotations
import math

G = 9.81
H_CENTRE = 0.914
H_POST = 1.07
DH = H_POST - H_CENTRE
COURT_L = 23.77
SINGLES_W = 8.23
DOUBLES_W = 10.97
OUTSET = 0.914
STICK = SINGLES_W / 2 + OUTSET
POST = DOUBLES_W / 2 + OUTSET


def h_linear(x: float, half: float) -> float:
    return H_CENTRE + DH * min(abs(x), half) / half


def diagonal(length: float, width: float) -> float:
    return math.hypot(length, width)


def net_crossing(x0, y0, x1, y1):
    t = (0 - y0) / (y1 - y0)
    x = x0 + t * (x1 - x0)
    s_net = math.hypot(x - x0, 0 - y0)
    s_land = math.hypot(x1 - x0, y1 - y0)
    return x, s_net, s_land


def angles_for_landing(v, R, y0, y_land=0.0):
    a = G * R * R / (2 * v * v)
    disc = R * R - 4 * a * (a - (y0 - y_land))
    if disc < 0:
        return []
    u1 = (R - math.sqrt(disc)) / (2 * a)
    u2 = (R + math.sqrt(disc)) / (2 * a)
    return sorted(math.atan(u) for u in (u1, u2))


def y_at(s, v, theta, y0):
    return y0 + s * math.tan(theta) - G * s * s / (2 * v * v * math.cos(theta) ** 2)


def angles_clipping_net(v, s_net, y0, h_net):
    a = G * s_net * s_net / (2 * v * v)
    disc = s_net * s_net - 4 * a * (a - (y0 - h_net))
    if disc < 0:
        return []
    u1 = (s_net - math.sqrt(disc)) / (2 * a)
    u2 = (s_net + math.sqrt(disc)) / (2 * a)
    return sorted(math.atan(u) for u in (u1, u2))


def main():
    print("stick from centre {:.3f} m; post from centre {:.3f} m".format(STICK, POST))
    print("official drop {:.3f} m = {:.1f} cm".format(DH, DH * 100))
    print("corner-to-corner {:.3f} m (extra {:.3f} m, {:.2f}%)".format(
        diagonal(COURT_L, SINGLES_W),
        diagonal(COURT_L, SINGLES_W) - COURT_L,
        100 * (diagonal(COURT_L, SINGLES_W) / COURT_L - 1),
    ))

    # typical: 1 m inside sideline, land 1 m inside far baseline
    x0, y0 = SINGLES_W / 2 - 1.0, -COURT_L / 2
    dtl = net_crossing(x0, y0, x0, COURT_L / 2 - 1.0)
    cc = net_crossing(x0, y0, -x0, COURT_L / 2 - 1.0)
    print("typical DTL path {:.3f} m, cross x={:.3f}, net {:.1f} cm".format(
        dtl[2], dtl[0], h_linear(dtl[0], STICK) * 100))
    print("typical CC  path {:.3f} m, cross x={:.3f}, net {:.1f} cm".format(
        cc[2], cc[0], h_linear(cc[0], STICK) * 100))

    y_hit = 1.00
    for kmh in (80, 100, 120):
        v = kmh / 3.6
        print(f"\n{kmh} km/h vacuum, contact {y_hit:.2f} m, land 1 m inside baseline")
        for name, trip, half in (("DTL", dtl, STICK), ("CC", cc, STICK)):
            x, s_net, R = trip
            h = h_linear(x, half)
            th = angles_for_landing(v, R, y_hit)[0]
            clear = (y_at(s_net, v, th, y_hit) - h) * 100
            clip = angles_clipping_net(v, s_net, y_hit, h)[0]
            win = math.degrees(th - clip)
            print("  {} theta={:.2f} deg  clearance={:.1f} cm  angle window to 1m-in={:.2f} deg".format(
                name, math.degrees(th), clear, win))


if __name__ == "__main__":
    main()
