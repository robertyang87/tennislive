"""WTA 比分板逐帧蒙版：板在才贴、板多宽切多宽（账号所有者 2026-09-24）。

「裁剪的比分板，有时候消失后背景还在……像狗皮膏药贴上去的」「右边突然多一块
补丁」。颜色取自新加坡 WTA500 转播（`prozorova-eala-singapore-2026-r2` 源片
逐秒抽帧实测，见 `tools/wta_scoreboard.py` 模块说明）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

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


def test_beijing_native_wipe_and_tag_transition_real_crops():
    """Real 25fps source crops: disappearing cell and animated mint tag.

    Old detection either mistook the wide tag for a games cell, or searched
    beyond the disappearing cell where no point slot remained.
    """
    cases = {
        "beijing-052520-wipe.png": 322,
        "beijing-133800-wipe.png": 376,
        "beijing-234720-wipe.png": 411,
        "beijing-194060-tag-transition.png": 390,
        "beijing-200340-wipe.png": 336,
        "beijing-267920-wipe.png": 365,
    }
    root = Path(__file__).parent / "fixtures" / "wta_scoreboard"
    for name, native_right in cases.items():
        band = np.asarray(Image.open(root / name).convert("RGB"))
        geometry = w.frame_geometry(band, cap=460)
        assert geometry is not None
        assert geometry["edge"] == native_right
        alpha = w.alpha_frame(geometry, (0, 0, band.shape[1], band.shape[0]))
        assert alpha[:, :native_right].any()
        assert not alpha[:, native_right:].any(), name
        if name in {"beijing-133800-wipe.png", "beijing-234720-wipe.png"}:
            # Both player rows retain the intact games cell after the points
            # slot wipes away; accepting the frame must not hide its scores.
            assert alpha[75, native_right - 10] == 255
            assert alpha[125, native_right - 10] == 255


def test_full_games_cell_cannot_replace_unmeasurable_points_boundary():
    band = np.empty((110, 760, 3), np.uint8)
    band[:] = BOARD_DARK
    band[:, 310:340] = MINT
    # An intact games cell plus uniform point/background area provides no
    # native outer boundary. Its internal divider is insufficient evidence.
    with pytest.raises(RuntimeError, match="native right boundary"):
        w.board_edge(band)


def test_wuhan_green_background_wipe_has_a_measured_edge():
    path = (Path(__file__).parent / "fixtures" / "wta_scoreboard"
            / "wuhan-sabalenka-li-008960-green-wipe.png")
    band = np.asarray(Image.open(path).convert("RGB"))
    geometry = w.frame_geometry(band, cap=464)
    assert geometry["edge"] == 411
    alpha = w.alpha_frame(geometry, (0, 0, 760, 158))
    assert alpha[75, 400] == 255  # native games numeral remains
    assert not alpha[:, 411:].any()  # no exposed court rectangle


def test_uniform_green_point_slot_is_not_exposed_background():
    band = np.empty((110, 760, 3), np.uint8)
    band[:] = BOARD
    band[:, 310:340] = MINT
    with pytest.raises(RuntimeError, match="native right boundary"):
        w.board_edge(band)


def test_reviewed_windows_gate_real_wuhan_result_before_geometry(monkeypatch):
    """A real centred result at 194.48s is outside the small-board window.

    Keep the original error without reviewed windows, and retain the complete
    genuine set-point graphic inside them. The excluded frame is transparent.
    """
    from types import SimpleNamespace

    root = Path(__file__).parent / "fixtures" / "wta_scoreboard"
    good = np.asarray(Image.open(root / "wuhan-175080-setpoint-band.png").convert("RGB"))
    result = np.asarray(Image.open(root / "wuhan-194480-centred-result-band.png").convert("RGB"))
    assert good.shape == result.shape == (155, 760, 3)
    monkeypatch.setattr(w.subprocess, "check_output", lambda *a, **kw: "1920\n")
    monkeypatch.setattr(w.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=good.tobytes() + result.tobytes(), stderr=b""))
    with pytest.raises(RuntimeError, match="native body row geometry"):
        w.scan_geometry(Path("same-source.mp4"), (89, 827, 552, 982), 0, .08, "25")
    measured = w.frame_geometry(good, cap=463)
    assert measured is not None and measured["header"] is not None
    frames, width = w.scan_geometry(
        Path("same-source.mp4"), (89, 827, 552, 982), 0, .08, "25",
        allowed_windows=((0, .04),))
    assert width == 760 and frames == [measured, None]
    assert not w.alpha_frame(frames[1], (0, 0, 760, 155)).any()
    assert np.array_equal(w.alpha_frame(frames[0], (0, 0, 760, 155)),
                          w.alpha_frame(measured, (0, 0, 760, 155)))


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
