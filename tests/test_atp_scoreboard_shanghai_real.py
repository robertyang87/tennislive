"""Lossless ShSDhLGXYOk RGB crops: crop=760:110:92:922.

Source SHA256 b6c3f528c315274b54c694eec01123670acb01c7b7b57442dee06986f2b21cb6.
Regress actual background leakage and missing point/deciding-set columns.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import atp_scoreboard as atp

FIXTURES = Path(__file__).parent / 'fixtures/atp_scoreboard/shanghai2026'


@pytest.mark.parametrize('timestamp,expected', [
    ('23.570', 278), ('35.700', 278), ('47.833', 223),
    ('64.533', 325), ('64.900', 325), ('85.933', 372),
    ('88.800', 372), ('89.000', 372), ('64.433', 325),
    ('97.500', 372), ('ttv-91.200', 329),
    ('34.370', 278), ('34.500', 278), ('34.703', 278),
])
def test_actual_full_board_boundary(timestamp, expected):
    band = np.asarray(Image.open(FIXTURES / f'{timestamp}.png').convert('RGB'))
    assert atp.board_edge(band, cap=455) == expected


def test_withdrawn_board_does_not_flash_back_for_one_frame():
    frames = [(372, None)] * 3 + [(None, None)] * 2 + [(152, None), (None, None)]
    assert atp.stabilize(frames)[5] == (None, None)


def test_point_border_survives_backdrop_joining_the_entire_colour_scan():
    # Keep the actual two-row board and replace only pixels outside its known
    # boundary with a uniformly dark green backdrop. No low-colour break occurs
    # before the scan limit; the independent container contour must still win.
    band = np.asarray(Image.open(FIXTURES / '64.900.png').convert('RGB')).copy()
    band[:, 325:] = (40, 64, 56)
    assert atp.board_edge(band, cap=455) == 325


def test_removal_does_not_widen_last_contour_with_older_frames():
    frames = [(298, None), (271, None), (244, None), (None, None), (None, None)]
    assert atp.stabilize(frames)[2] == (244, None)
