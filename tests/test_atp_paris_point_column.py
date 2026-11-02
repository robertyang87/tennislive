"""Paris 2025 R2: yellow set cells and a single-row AD point column.

One PNG stores three unscaled lossless RGB source crops, each760x96 at
x192/y904, stacked in time order115.2s/122.4s/128.96s.
Official source4392293 fixed archive SHA256:
d7d2d6e9ada937da8e5a5f0b6ff5cad82f618f7aba4fd71ccf63d00794ffd9d1.
The expected right edge is observed in the source, not a production constant.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import atp_scoreboard as atp


@pytest.fixture
def band():
    path = Path(__file__).parent/'fixtures/atp_scoreboard/paris2025/r2-native-ad.png'
    return np.asarray(Image.open(path).convert('RGB'))[96:192].copy()


@pytest.mark.parametrize('cap', [None, 320, 412])
def test_real_yellow_set_anchor_preserves_single_row_ad(band, cap):
    assert atp.board_edge(band, cap=cap) == 410


@pytest.mark.parametrize('row,expected', [(0, 408), (2, 409)])
def test_real_ad_separator_survives_dark_closeup_background(row, expected):
    path = Path(__file__).parent/'fixtures/atp_scoreboard/paris2025/r2-native-ad.png'
    crop = np.asarray(Image.open(path).convert('RGB'))[row*96:(row+1)*96]
    edge = atp.board_edge(crop, cap=412)
    assert edge == expected
    # The observed row-rule fades over the last two anti-aliased columns.
    # Native mask padding retains all of those columns as well as the AD.
    assert edge+atp.EDGE_PAD >= 410


@pytest.mark.parametrize('extra_name_width', [37, 91])
def test_actual_container_and_point_width_move_with_longer_name_panel(band, extra_name_width):
    # Repeat only native empty name-panel padding, shifting every actual set
    # and point cell. The original narrow hint must not become a fixed edge.
    padding = np.repeat(band[:, 199:200], extra_name_width, axis=1)
    expanded = np.concatenate((band[:, :200], padding, band[:, 200:]), axis=1)
    assert atp.board_edge(expanded, cap=412) == 410+extra_name_width


def test_one_row_yellow_tag_does_not_become_a_later_set_cell(band):
    # Remove only the point cell/background, leaving the real highlighted set.
    band[:, 364:] = (110, 108, 112)
    without_points = atp.board_edge(band, cap=412)
    assert without_points == 362
    band[48:, 364:544] = (215, 245, 100)
    assert atp.board_edge(band, cap=412) == without_points
    assert atp.tag_rect(band, without_points) is not None


def test_white_shirt_cannot_supply_a_fake_single_row_point_cell(band):
    band[:, 364:] = (110, 108, 112)
    band[48:, 364:500] = (245, 245, 245)
    assert atp.board_edge(band, cap=412) == 362


def test_court_without_name_container_is_not_a_scoreboard(band):
    band[:, :150] = band[:, 450:600]
    assert atp.board_edge(band, cap=412) is None
