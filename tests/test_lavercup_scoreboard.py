"""拉沃尔杯转播比分板逐帧蒙版（账号所有者 2026-09-25：「比分板补一套适配，彻底解决」）。

颜色和几何取自 `ruud-cerundolo-laver-cup-2026` 源片 `10c-Msjex6s` 逐帧实测
（见 `tools/lavercup_scoreboard.py`）。标定带 y 878–1022（高 144）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import lavercup_scoreboard as f  # noqa: E402

FILL = (7, 7, 7)
BLUE = (15, 47, 85)
RED = (55, 0, 13)
GOLD = (131, 120, 74)
WHITE = (185, 183, 186)
COURT = (80, 73, 81)
BENCH_RED = (150, 20, 35)
BACKDROP_BLUE = (0, 43, 97)
H, W = 144, 572


def _band(left=17, right=382, *, label=(21, 148), bg=COURT):
    band = np.zeros((H, W, 3), np.uint8)
    band[:] = bg
    if right is None:
        return band
    for (y0, y1), edge in (((42, 90), BLUE), ((92, 138), RED)):
        band[y0:y1, left:right] = edge                       # 描边
        band[y0 + 4:y1 - 4, left + 4:right - 4] = FILL        # 近黑底
        band[y0 + 16:y1 - 16, left + 30:left + 120] = WHITE   # 名字
    if label:
        band[6:38, label[0]:label[1]] = GOLD
    return band


def test_紧凑版两行加标签_三块胶囊各切各的():
    ps = f.pills(_band())
    assert ps is not None and len(ps) == 3
    rows = [p for p in ps if p[2] > 30]
    assert all(abs(p[0] - 17) <= 2 and abs(p[1] - 382) <= 2 for p in rows)
    lab = next(p for p in ps if p[2] < 30)
    assert lab[1] <= 152        # 标签比两行窄，右边的球场不跟着抠进来


def test_开局没有标签那几秒_只切两行():
    ps = f.pills(_band(label=None))
    assert ps is not None and len(ps) == 2


def test_球场红色替补席蓝色背板都不是板():
    assert f.pills(_band(right=None)) is None
    assert f.pills(_band(right=None, bg=BENCH_RED)) is None
    assert f.pills(_band(right=None, bg=BACKDROP_BLUE)) is None


def test_红色背景上板的左右端不外溢():
    """「两行同时有描边」才往两端延——只看一种颜色会一路延到带边上（frame 76s）。"""
    ps = f.pills(_band(bg=BENCH_RED))
    assert ps is not None
    assert all(p[0] >= 12 and p[1] <= 390 for p in ps if p[2] > 30)


def test_宽版全名板不贴():
    """开场／赛后的全名板横跨源片 85–960，放大后比画布宽，右半截本来就在居中窗口里。"""
    assert f.pills(_band(left=261, right=W)) is None


def test_蒙版是胶囊形_四角外的球场透明():
    m = np.zeros((H, W), np.uint8)
    f.paint(m, (17, 382, 41, 91))
    assert m[66, 200] == 255              # 行中间
    assert m[41, 17] == 0 and m[90, 381] == 0   # 四角
    assert m[66, 18] == 255               # 左端半圆的中点


def test_板要连着两帧在才认_宽度取前后并集():
    a = [(17, 380, 41, 91), (17, 380, 91, 139)]
    b = [(17, 390, 41, 91), (17, 390, 91, 139)]
    out = f.stabilize([None, a, None, None, a, b, a])
    assert out[1] is None                 # 前后都不在：孤帧不认
    assert out[5][0][1] == 390 and out[4][0][1] == 390
