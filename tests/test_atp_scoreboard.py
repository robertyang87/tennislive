"""ATP 比分板逐帧蒙版：板多宽切多宽，黄条单独切（账号所有者 2026-09-24）。

颜色取自成都 Tennis TV 转播的实测像素（见 `tools/atp_scoreboard.py` 模块说明）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import atp_scoreboard as a  # noqa: E402

NAVY = (6, 16, 36)
BLUE = (22, 16, 248)
COURT = (123, 167, 128)
TAG = (215, 245, 100)
H, W = 108, 760


def _band(board_w: int, tag: tuple[int, int] | None = None,
          present: bool = True) -> np.ndarray:
    """board_w：板宽（相对带左缘）；tag：(宽, 起始行)，贴在板右边、只占下半行。"""
    band = np.zeros((H, W, 3), np.uint8)
    band[:] = COURT
    if not present:
        return band
    band[:, :board_w] = NAVY
    band[:, board_w - 60:board_w - 30] = BLUE          # 盘分格
    band[20:30, 20:120] = (240, 255, 250)                # 名字（白字）
    if tag:
        tw, top = tag
        band[top:, board_w:board_w + tw] = TAG
        band[top + 10:top + 20, board_w + 10:board_w + 60] = (20, 30, 20)   # 黄条上的深色字
    return band


def test_板右缘按这一帧的实际宽度量():
    assert a.board_edge(_band(280)) == 280
    assert a.board_edge(_band(330)) == 330
    assert a.board_edge(_band(330), cap=300) == 300, "上限是 spec scorebox 的最宽状态"


def test_板不在或没有盘分格就不是板():
    assert a.board_edge(_band(300, present=False)) is None
    band = _band(300)
    band[:, 240:270] = NAVY          # 抹掉蓝格：盘间大图形 / 深色挡板长这样
    assert a.board_edge(band) is None


def test_黄条只取它自己那一行的外框():
    band = _band(330, tag=(210, 54))
    e = a.board_edge(band)
    x0, y0, x1, y1 = a.tag_rect(band, e)
    assert (x0, y0) == (330, 54) and abs(x1 - 540) <= 2 and y1 == H
    assert a.tag_rect(_band(330), 330) is None


def test_蒙版里只有板和黄条是实的(tmp_path):
    frames = [(330, None), (280, None), (330, (330, 54, 540, H)), (None, None)]
    dest = tmp_path / "m.mkv"
    a.write_mask(frames, 560, H, "25", dest)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(dest), "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    m = np.frombuffer(raw, np.uint8).reshape(-1, H, 560)
    assert len(m) == 4
    e = a.EDGE_PAD
    # 第 1 帧：板 330 宽，右边一列都不多抠
    assert m[0][:, :330 + e].min() == 255 and m[0][:, 330 + e:].max() == 0
    # 第 2 帧：板变窄到 280，蒙版跟着窄——不按这一段最宽的那一刻切
    assert m[1][:, :280 + e].min() == 255 and m[1][:, 280 + e:].max() == 0
    # 第 3 帧：黄条只占下半行，上半行板右边仍是透明（不把球场带进来）
    assert m[2][54:, 330:540].min() == 255
    assert m[2][:54, 330 + e:].max() == 0
    # 第 4 帧：板不在，整张透明
    assert m[3].max() == 0


def test_中位数压掉一两帧的毛刺_黄条要连着出现才认():
    frames = [(330, None), (330, None), (600, None), (330, None), (330, None)]
    assert [e for e, _ in a.stabilize(frames)] == [330] * 5
    lone = [(330, None), (330, (330, 54, 540, H)), (330, None)]
    assert all(t is None for _, t in a.stabilize(lone)), "只闪一帧的黄条不认"


def test_半透明小分格压在蓝场上也算板():
    """杭州蓝场：小分格 (36,62,86)，蓝通道被球场抬过 80（zhang-wong 两趟 render 整列没贴）。"""
    band = np.zeros((H, W, 3), np.uint8)
    band[:] = (100, 165, 220)                       # 杭州球场蓝
    band[:, :330] = NAVY
    band[:, 270:320] = BLUE                         # 盘分格
    band[:, 320:372] = (36, 62, 86)                 # 小分格（半透明，透着蓝场）
    band[40:70, 330:360] = (240, 255, 250)          # 小分里的白字
    band[20:30, 20:120] = (240, 255, 250)
    assert a.board_edge(band) == 372
    # 球场本身不许被这一档扫进来
    assert not a.board_mask(np.full((4, 4, 3), (100, 165, 220), np.uint8)).any()
    assert not a.board_mask(np.full((4, 4, 3), (123, 167, 128), np.uint8)).any()
