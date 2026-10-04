"""Native geometry must preserve score details without carrying the search-band court."""
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import wta_scoreboard as w

COURT = (64, 159, 226)
BODY = (6, 46, 32)
MINT = (21, 255, 171)
WHITE = (254, 255, 253)


def band(width=390, top=50, height=110, header=True):
    image = np.full((200, 760, 3), COURT, np.uint8)
    image[top:top+height, 4:width] = BODY
    image[top:top+height, width-80:width-54] = MINT
    image[top+20:top+30, 25:120] = WHITE
    image[top+70:top+80, 25:120] = WHITE
    image[top+20:top+30, width-40:width-20] = WHITE
    # Native service ball/icon is part of the body, not a mask hole.
    image[top+70:top+78, 9:18] = (125, 190, 145)
    if header:
        image[top-40:top, 4:118] = MINT
        image[top-30:top-20, 22:100] = BODY  # BREAK POINT letters
    return image


def test_body_and_narrow_header_keep_native_details_and_transparent_gap():
    geometry = w.frame_geometry(band())
    assert geometry['body'][1:] == (49, 390, 161)
    assert geometry['header'][2] <= 120
    mask = w.alpha_frame(geometry, (0, 0, 760, 200))
    assert mask[20, 50] == 255  # header text remains opaque
    assert mask[20, 200] == 0  # court next to short header never becomes a patch
    assert mask[125, 15] == 255  # native service icon
    assert mask[75, 360] == 255  # point-score text
    assert mask[:8].sum() == 0
    assert mask[165:].sum() == 0


def test_no_header_does_not_keep_empty_search_band_above_body():
    geometry = w.frame_geometry(band(header=False))
    assert geometry['header'] is None
    assert geometry['bounds'][1] == 49
    assert w.alpha_frame(geometry, (0, 0, 760, 200))[:49].sum() == 0


def test_native_width_and_height_change_without_fixed_canvas_shape():
    narrow = w.frame_geometry(band(width=354, top=80, height=90, header=False))
    wide = w.frame_geometry(band(width=470, top=35, height=130, header=True), cap=390)
    assert narrow['body'][2] < wide['body'][2]
    assert narrow['body'][3] - narrow['body'][1] == 92
    assert wide['body'][3] - wide['body'][1] == 132
    assert wide['body'][2] >= 470


def test_board_absent_is_fully_transparent_even_when_scene_is_dark():
    for bg in (COURT, (20, 17, 22), (98, 61, 104)):
        assert w.frame_geometry(np.full((200, 760, 3), bg, np.uint8)) is None
        assert w.alpha_frame(None, (0, 0, 390, 160)).sum() == 0


def test_clipped_native_header_is_retained_without_inventing_missing_text():
    image = band(top=10, height=95, header=False)
    image[2:10, 4:130] = MINT
    geometry = w.frame_geometry(image)
    assert geometry['header'] is not None
    assert geometry['header'][3] <= 10
    mask = w.alpha_frame(geometry, (0, 0, 760, 200))
    assert mask[5, 100] == 255
    assert mask[5, 200] == 0


def test_resolve_crops_to_measured_union_records_bounds_and_preserves_absence(tmp_path, monkeypatch):
    native = w.frame_geometry(band(header=False))
    captured = {}
    monkeypatch.setattr(w, 'scan_geometry', lambda *a: ([native, native, native, None, None], 760))
    def write(frames, bounds, fps, dest):
        captured.update(frames=frames, bounds=bounds)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'bound native mask')
    monkeypatch.setattr(w, 'write_geometry_mask', write)
    seg = SimpleNamespace(score_inset=(86,827,554,1027), start=0., end=1., speed=1., source=0)
    proof = w.resolve_masks({0: Path('source.mp4')}, [seg], tmp_path, '25', .18)
    assert seg.score_inset[1] >= 875  # no original 49px court padding
    assert seg.score_inset[3] < 1000
    assert captured['frames'][-1] is None
    import json
    record = json.loads(proof.read_text())['segments'][0]
    assert record['source_bounds'] == list(seg.score_inset)
    assert record['header_bounds'] == []
    assert record['alpha_geometry'] == 'native-body-and-header-rows'


def test_present_board_with_unmeasurable_body_fails_without_rectangle(monkeypatch):
    monkeypatch.setattr(w, 'present', lambda _: True)
    image = np.full((200,760,3), COURT, np.uint8)
    with pytest.raises(RuntimeError, match='body height'):
        w.frame_geometry(image)


def test_large_black_game_digits_do_not_split_two_player_body():
    image = band(header=False)
    # The printed digits remove most mint pixels for 28px on BOTH player rows.
    image[65:93, 312:334] = BODY
    image[115:143, 312:334] = BODY
    geometry = w.frame_geometry(image)
    assert geometry['body'][1] <= 50
    assert geometry['body'][3] >= 160
    mask = w.alpha_frame(geometry, (0,0,760,200))
    assert mask[80, 80] == 255
    assert mask[130, 80] == 255
    assert mask[130, 320] == 255


def test_sliding_out_name_remnant_never_becomes_single_player_patch():
    image = band(header=False)
    image[:, 110:] = COURT
    assert w.present(image) is False
    assert w.frame_geometry(image) is None


def test_long_native_point_header_keeps_its_actual_width_not_name_width_cap():
    image = band()
    image[10:50, 4:245] = MINT
    image[20:30, 24:40] = BODY
    image[20:30, 60:80] = BODY
    image[20:30, 95:115] = BODY
    image[20:30, 160:180] = BODY
    geometry = w.frame_geometry(image)
    assert geometry['header'][2] >= 245
    mask = w.alpha_frame(geometry, (0,0,760,200))
    assert mask[25, 220] == 255
    assert mask[25, 280] == 0


def test_mint_point_numerals_do_not_act_as_an_extra_filled_games_cell():
    image = band(header=False)
    image[:,390:] = (87,88,91)  # dark court/stand passes the old dark-colour test
    image[65:93,360:364] = MINT
    image[65:93,375:378] = MINT
    image[115:143,360:364] = MINT
    image[115:143,375:378] = MINT
    geometry = w.frame_geometry(image)
    assert geometry['body'][2] <= 392
    assert w.alpha_frame(geometry,(0,0,760,200))[:,394:].sum() == 0


def test_stat_panel_without_point_slot_does_not_copy_dark_racket_to_right():
    image = band(width=360, header=True)
    image[50:160,310:346] = MINT
    image[50:160,346:360] = BODY
    image[50:160,360:] = (0,22,74)  # blue racket/court mistaken for dark graphic
    geometry = w.frame_geometry(image)
    assert geometry['body'][2] <= 362
    assert geometry['header'] is not None
    assert w.alpha_frame(geometry,(0,0,760,200))[:,362:].sum() == 0
