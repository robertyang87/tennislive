"""Lossless source crops expose dark crowd edges and the set-end board without blue cells.

cjaHThpISKk source SHA256 2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2;
ffmpeg crop=760:109:98:920, one frame at each source timestamp, RGB PNG.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import atp_scoreboard as atp

FIXTURES = Path(__file__).parent / 'fixtures/atp_scoreboard/beijing2026'


@pytest.mark.parametrize('timestamp,expected', [
    ('000.5', 295), ('010.5', 244), ('032.5', 245),
    ('108.5', 290), ('280.5', 388), ('282.5', 338),
])
def test_real_board_ends_before_crowd_and_survives_set_end(timestamp, expected):
    band = np.asarray(Image.open(FIXTURES / f'{timestamp}.png').convert('RGB'))
    assert atp.board_edge(band, cap=421) == expected


def test_two_row_board_signature_does_not_accept_only_dark_background():
    # Same actual crowd pixels, no scoreboard at the expected origin.
    band = np.asarray(Image.open(FIXTURES / '280.5.png').convert('RGB')).copy()
    band[:, :338] = band[:, 422:760]
    assert atp.board_edge(band, cap=421) is None
