"""WTA 比分板逐帧蒙版：板在才贴、板多宽切多宽（账号所有者 2026-09-24）。

「裁剪的比分板，有时候消失后背景还在……像狗皮膏药贴上去的」「右边突然多一块
补丁」。颜色取自新加坡 WTA500 转播（`prozorova-eala-singapore-2026-r2` 源片
逐秒抽帧实测，见 `tools/wta_scoreboard.py` 模块说明）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import wta_scoreboard as w  # noqa: E402

BOARD = (55, 95, 66)          # 板底，压在球场上
BOARD_DARK = (6, 46, 32)      # 同一块板压在深色背景上
MINT = (21, 255, 171)         # 当前盘局分格
WHITE = (254, 255, 253)
COURT = (125, 179, 110)
CROWD = (20, 17, 22)          # 夜场看台
FLOWERS = (98, 61, 104)       # 场边花墙
H, W = 110, 760


def _band(board_w: int | None, *, bg=COURT, body=BOARD, mint: bool = True) -> np.ndarray:
    band = np.zeros((H, W, 3), np.uint8)
    band[:] = bg
    if board_w is None:
        return band
    band[:, :board_w] = body
    band[20:30, 30:120] = WHITE                                  # 名字（白字）
    band[70:80, 30:110] = WHITE
    if mint:
        band[:, board_w - 80:board_w - 54] = MINT                # 局分格
        band[20:30, board_w - 40:board_w - 20] = WHITE           # 小分
    return band


def test_板右缘按这一帧的实际宽度量():
    assert w.board_edge(_band(390)) == 390
    assert w.board_edge(_band(459)) == 459
    assert w.board_edge(_band(459), cap=420) == 459, "spec 右缘是提示：薄荷绿撑得住就按量到的走"
    assert w.board_edge(_band(459, mint=False), cap=420) == 420, "没有签名色撑着照旧封顶"


def test_深色背景上右缘钉在局分格右边一格小分宽_不一路量出去():
    band = _band(390, bg=CROWD, body=BOARD_DARK)
    edge = w.board_edge(band)
    assert edge is not None and edge <= 390 - 54 + w.POINTS_MAX, edge
    assert edge >= 390 - 4


def test_深色人群和花墙不是板():
    """老判据按「暗」认板，夜场看台和花墙比真板还暗——整块人群被当成板贴出去。"""
    assert w.board_edge(_band(None, bg=CROWD)) is None
    assert w.board_edge(_band(None, bg=FLOWERS)) is None
    assert w.board_edge(_band(None)) is None


def test_盘间大图形有薄荷绿但名字栏是白底_不是板():
    band = _band(None)
    band[:, :500] = WHITE
    band[10:100, 200:700] = MINT                               # 绿条几乎占满这一行高
    assert (w.mint_mask(band).mean(axis=0) > 0.4).sum() >= w.MINT_COLS, "没走到薄荷绿那条分支，这条判据是假绿"
    assert w.board_edge(band) is None


def test_开局还没有局分时认板底色():
    assert w.board_edge(_band(354, mint=False)) is not None
    assert w.board_edge(_band(None, bg=CROWD)) is None


def test_在场要连着几帧才翻_单帧毛刺不贴():
    frames = [(None, None), (390, None), (None, None), (None, None)]
    assert all(e is None for e, _ in w.debounce(frames))
    steady = [(390, None)] * 4
    assert w.debounce(steady) == steady
