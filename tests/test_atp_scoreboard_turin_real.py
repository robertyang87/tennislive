"""Turin 2026 SF: retain blue set cells, exclude adjoining dark-blue backdrop.

Lossless RGB source crops: format=rgb24,crop=760:109:98:920 at
285.600s/288.600s/289.400s/289.700s/290.400s from official Tennis TV aJ_bIrNtrtA.
Source SHA256 63320c9fe9eba9ca28bc243206a2ffd458b96c040c1b99c096833a0749534567.
Native set cells have green near 80. The point cell ends at 332 before the
break; after it withdraws, the blue cell ends at 280 against a navy close-up.
The expected contours are source observations, not production dimensions.
"""
import sys
import subprocess
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


@pytest.mark.parametrize('stem,expected', [
    ('rr2-361.520', 354), ('rr2-361.600', 354), ('rr2-361.720', 354),
    ('sf-401.400', 380), ('final-433.660', 334),
])
@pytest.mark.parametrize('cap', [None, 333, 421])
def test_real_point_panel_contour_can_remain_visible_in_only_one_player_row(stem, expected, cap):
    # Lossless RGB crop=760:109:98:920. The point divider is visibly inset;
    # stopping there truncates actual point digits/container padding.
    # RR2 GBdXpIAAgv4 SHA256:
    # 0bca55bcd19a760b8c67a01a2faffcf2047b997dc0a8b3f8f0819eac76eb29be.
    # Final YiWjCKWBWog SHA256:
    # 1b06b27ff247d36ec427e5f9807b52be165b1be6bc27cb637dd9a58372886bd9.
    # SF is the same official aJ_bIrNtrtA source documented above.
    path = Path(__file__).parent / 'fixtures/atp_scoreboard/turin2026' / f'{stem}.png'
    band = np.asarray(Image.open(path).convert('RGB'))
    assert atp.board_edge(band, cap=cap) == expected


def _final_band(timestamp):
    path = Path(__file__).parent / 'fixtures/atp_scoreboard/turin2026' / f'final-{timestamp}.png'
    return np.asarray(Image.open(path).convert('RGB')).copy()


def _scan_native_bands(tmp_path, bands):
    source = tmp_path / 'native.mkv'
    h, w = bands[0].shape[:2]
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                    '-s', f'{w}x{h}', '-r', '25', '-i', '-', '-c:v', 'ffv1',
                    '-pix_fmt', 'bgr0', str(source)], input=b''.join(b.tobytes() for b in bands),
                   check=True, capture_output=True)
    frames, _ = atp.scan(source, (0, 0, 421, h), 0, len(bands) / 25, '25')
    return [edge for edge, _ in frames]


def test_three_native_ambiguous_frames_keep_recent_edge_but_retraction_does_not(tmp_path):
    bands = [_final_band(t) for t in ['195.920', '195.960', '196.000', '196.040', '196.080']]
    assert _scan_native_bands(tmp_path, bands) == [286, 286, 286, 286, 350]


@pytest.mark.parametrize('padding', [37, 91])
def test_real_temporary_widening_is_not_smoothed_into_previous_native_width(tmp_path, padding):
    narrow = _final_band('195.920')
    # Extend genuine empty name-panel pixels and move every native score
    # cell together. This is a real wider graphic in the synthetic source,
    # rather than a similarly coloured foreground added beside a panel.
    fill = np.repeat(narrow[:, 150:151], padding, axis=1)
    wide = np.concatenate((narrow[:, :150], fill, narrow[:, 150:-padding]), axis=1)
    assert _scan_native_bands(tmp_path, [narrow, wide, narrow]) == [286, 286 + padding, 286]


def test_continuation_never_chains_past_four_frames_or_reuses_changed_digit_shape(tmp_path):
    reference = _final_band('195.920')
    ambiguous = _final_band('195.960')
    edges = _scan_native_bands(tmp_path, [reference] + [ambiguous] * 5)
    assert edges[:5] == [286] * 5
    assert edges[5] > 300
    changed = ambiguous.copy()
    # Remove interior white glyph pixels, retaining both exact bounding boxes.
    white = (changed.min(2) > 150) & (changed.max(2) - changed.min(2) < 50)
    yy, xx = np.nonzero(white[73:90, 245:275])
    changed[yy[:30] + 73, xx[:30] + 245] = (6, 16, 36)
    assert _scan_native_bands(tmp_path, [reference, changed])[1] > 300
