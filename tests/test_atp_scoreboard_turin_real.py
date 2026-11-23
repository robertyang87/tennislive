"""Turin 2026 SF: retain blue set cells, exclude adjoining dark-blue backdrop.

Lossless RGB source crops: format=rgb24,crop=760:109:98:920 at
285.600s/288.600s/289.400s/289.700s/290.400s from official Tennis TV aJ_bIrNtrtA.
Source SHA256 63320c9fe9eba9ca28bc243206a2ffd458b96c040c1b99c096833a0749534567.
Native set cells have green near 80. The point cell ends at 332 before the
break; after it withdraws, the blue cell ends at 280 against a navy close-up.
The expected contours are source observations, not production dimensions.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import atp_scoreboard as atp


@pytest.mark.parametrize('timestamp,expected', [
    ('285.600', 332), ('288.600', 280),
    ('289.400', 280), ('289.700', 280), ('290.400', 280),  # Background lettering is not a point glyph.
])
@pytest.mark.parametrize('cap', [None, 280, 333, 421])
def test_real_blue_cells_keep_native_edge_against_dark_blue_closeup(timestamp, expected, cap):
    path = Path(__file__).parent / 'fixtures/atp_scoreboard/turin2026' / f'sf-{timestamp}.png'
    band = np.asarray(Image.open(path).convert('RGB'))
    assert atp.board_edge(band, cap=cap) == expected
