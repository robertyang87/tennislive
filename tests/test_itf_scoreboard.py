"""比利·简·金杯（ITF 转播）比分板逐帧蒙版（账号所有者 2026-09-24）。

颜色取自 `zheng-paolini-bjk-cup-2026-qf` 源片逐帧实测（见 `tools/itf_scoreboard.py`）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import itf_scoreboard as f  # noqa: E402

ROYAL = (24, 79, 240)
CELL = (142, 255, 251)
DOT = (192, 255, 67)
WHITE = (228, 254, 255)
COURT = (117, 195, 252)
CROWD = (0, 46, 93)
H, W = 97, 480


def _band(board_w=None, *, dot=True, bg=COURT):
    band = np.zeros((H, W, 3), np.uint8)
    band[:] = bg
    if board_w is None:
        return band
    band[4:H - 4, :board_w - 40] = ROYAL
    band[4:H - 4, board_w - 40:board_w] = CELL                 # 小分格
    band[15:30, 40:130] = WHITE                                  # 名字
    band[60:75, 40:120] = WHITE
    if dot:
        band[20:34, board_w + 2:board_w + 16] = DOT              # 发球小球
    return band


def test_板右缘按这一帧的实际宽度量_小分格算板():
    assert f.board_edge(_band(298)) == 298
    assert f.board_edge(_band(343)) == 343


def test_亮蓝球场和暗蓝看台都不是板():
    """老判据按「暗」认板——看台被当成板贴出去。"""
    assert f.board_edge(_band(None)) is None
    assert f.board_edge(_band(None, bg=CROWD)) is None


def test_发球小球只取它自己那一小块():
    band = _band(343)
    x0, y0, x1, y1 = f.dot_rect(band, f.board_edge(band))
    assert x0 <= 345 and x1 >= 358 and y0 >= 18 and y1 <= 36
    assert f.dot_rect(_band(343, dot=False), 343) is None
