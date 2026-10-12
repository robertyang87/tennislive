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


def test_beijing_swiatek_break_point_two_and_centred_result_real_pixels():
    from PIL import Image
    root = Path(__file__).parent / "fixtures" / "wta_scoreboard"
    image = np.asarray(Image.open(root / "beijing-swiatek-224040-break-point-2.png"))
    geometry = w.frame_geometry(image, cap=482)
    assert geometry is not None
    assert geometry["header"] is not None
    alpha = w.alpha_frame(geometry, (0, 0, 760, 161))
    assert alpha[20, 120] == 255  # BREAK POINT #2 remains visible
    assert alpha[20, 220] == 0  # transparent beside the native short tag
    assert alpha[75, 440] == 255  # rightmost current-point cell survives
    assert not alpha[:, 465:].any()
    result = np.asarray(Image.open(root / "beijing-swiatek-297600-centred-result.png"))
    assert w.frame_geometry(result, cap=482) is None


def test_native_wipe_glow_keeps_measured_edge_without_guessing_point_slot():
    from PIL import Image
    path = Path(__file__).parent / "fixtures" / "wta_scoreboard" / "beijing-swiatek-036960-wipe-glow.png"
    image = np.asarray(Image.open(path))
    geometry = w.frame_geometry(image, cap=482)
    assert geometry["edge"] == 342
    alpha = w.alpha_frame(geometry, (0, 0, 760, 161))
    assert alpha[125, 320] == 255
    assert not alpha[:, 342:].any()


def test_beijing_sun_gauff_ad_gradient_keeps_point_slot_without_court_patch():
    from PIL import Image
    path = (Path(__file__).parent / "fixtures" / "wta_scoreboard"
            / "beijing-sun-gauff-232880-ad-gradient.png")
    image = np.asarray(Image.open(path))
    geometry = w.frame_geometry(image, cap=460)
    # Real AV1 frame 232.88s: intact games cell plus Ad score. Before the fix,
    # the 28px games cell was classified as a wipe and the Ad slot was erased.
    assert geometry["edge"] == 436
    alpha = w.alpha_frame(geometry, (0, 0, 760, 170))
    assert alpha[99, 407] == 255  # native Ad text and its slot survive
    assert alpha[145, 420] == 255  # complete lower player's point slot
    assert not alpha[:, 436:].any()  # measured edge, no padded dark rectangle
    assert alpha[25, 125] == 255  # BREAK POINT #3 header survives
    assert alpha[25, 200] == 0  # court alongside the narrow header transparent


def test_complete_games_cell_uses_its_native_height_when_body_has_fringe():
    image = band(width=390, top=45, height=108, header=False)[42:159]
    image[:, 310:336] = BODY
    image[3:111, 310:338] = MINT
    image[:, 338:] = (10, 27, 42)  # dark, no measurable outer point boundary
    # Intact 28px/108px cell must not be treated as a truncated cell merely
    # because the surrounding body/search band is 117px high.
    with pytest.raises(RuntimeError, match="native right boundary"):
        w.board_edge(image)


def test_zheng_championship_point_real_frame_separates_header_and_keeps_40_30():
    from PIL import Image
    path = (Path(__file__).parent / "fixtures" / "wta_scoreboard"
            / "beijing-zheng-andreeva-267000-championship-point.png")
    image = np.asarray(Image.open(path))
    geometry = w.frame_geometry(image, cap=472)
    # The 205px championship tag used to enter the games anchors, producing
    # one 152px-high body with edge 376 and deleting both point numerals.
    assert geometry["body"] == (1, 43, 428, 155)
    assert geometry["header"] == (1, 3, 205, 44)
    assert geometry["edge"] == 428
    alpha = w.alpha_frame(geometry, (0, 0, 760, 158))
    assert alpha[75, 400] == 255  # Zheng's native 40
    assert alpha[125, 400] == 255  # Andreeva's native 30
    assert alpha[20, 180] == 255  # full championship tag and its text
    assert alpha[20, 240] == 0  # court alongside the tag remains transparent
    assert not alpha[:, 428:].any()


@pytest.mark.parametrize("header_width", [205, 350, 440])
def test_wide_header_never_becomes_games_anchor_even_across_games_column(header_width):
    # Use the real search-band height: 40 header pixels exceed the old 25%
    # column threshold. The largest tag crosses the games column and body edge.
    image = band(top=44, height=110, header=False)[:158]
    image[3:44, 4:header_width] = MINT
    image[12:27, 24:130] = BODY
    geometry = w.frame_geometry(image)
    assert geometry["body"] == (3, 43, 390, 155)
    assert geometry["edge"] == 390
    assert geometry["header"][2] >= header_width
    alpha = w.alpha_frame(geometry, (0, 0, 760, 158))
    assert alpha[20, header_width - 5] == 255
    assert alpha[20, header_width + 5] == 0
    assert alpha[80, 365] == 255  # points slot independent of tag width
    assert not alpha[60:, 390:].any()


def test_native_window_mask_roundtrip_preserves_points_and_header_only_inside_windows(tmp_path, monkeypatch):
    import json
    import subprocess
    from PIL import Image
    path = (Path(__file__).parent / "fixtures" / "wta_scoreboard"
            / "beijing-zheng-andreeva-267000-championship-point.png")
    geometry = w.frame_geometry(np.asarray(Image.open(path)), cap=472)
    # Ten genuine, identical native graphics. The last two frames represent
    # dissolve tail; a segment-local window must never leak into that tail.
    def scanned(*args, **kwargs):
        windows = kwargs["allowed_windows"]
        return ([geometry if any(a <= k / 25 < b for a, b in windows) else None
                 for k in range(10)], 760)
    monkeypatch.setattr(w, "scan_geometry", scanned)
    seg = SimpleNamespace(score_inset=(88, 828, 560, 986), start=267., end=267.32,
                          speed=1., source=0,
                          score_inset_windows=((.04, .12), (.20, .32)))
    proof = w.resolve_masks({0: Path("source.mp4")}, [seg], tmp_path, "25", .08)
    record = json.loads(proof.read_text())["segments"][0]
    x0, y0, x1, y1 = record["source_bounds"]
    width, height = x1 - x0, y1 - y0
    decoded = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", seg.score_inset_mask,
        "-pix_fmt", "gray", "-f", "rawvideo", "-"])
    alpha = np.frombuffer(decoded, np.uint8).reshape(10, height, width)
    # Half-open intervals: start frames 1/5 included; end frames 3/8 excluded.
    assert np.flatnonzero(alpha.any(axis=(1, 2))).tolist() == [1, 2, 5, 6, 7]
    for frame in (1, 2, 5, 6, 7):
        assert alpha[frame, 75 - (y0 - 828), 400 - (x0 - 88)] == 255  # 40
        assert alpha[frame, 125 - (y0 - 828), 400 - (x0 - 88)] == 255  # 30
        assert alpha[frame, 20 - (y0 - 828), 180 - (x0 - 88)] == 255  # tag
        assert alpha[frame, 20 - (y0 - 828), 240 - (x0 - 88)] == 0  # court gap
    assert record["allowed_source_windows"] == [[267.04, 267.12], [267.2, 267.32]]
    assert record["measured_present_frames"] == 5
    assert record["present_frames"] == 5
    assert record["window_excluded_present_frames"] == 0
    assert record["outside_window_frames_not_scanned"] == 5
    assert record["measurement_scope"] == "reviewed_windows_only"
    assert record["window_policy"].endswith("before-geometry-and-after-debounce")


def test_unset_windows_keep_each_existing_native_geometry_unchanged(tmp_path, monkeypatch):
    geometry = w.frame_geometry(band())
    original = [geometry, geometry, geometry, None, None]
    captured = {}
    monkeypatch.setattr(w, "scan_geometry", lambda *a: (original, 760))
    def write(frames, bounds, fps, dest):
        captured["frames"] = frames
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"native-mask")
    monkeypatch.setattr(w, "write_geometry_mask", write)
    seg = SimpleNamespace(score_inset=(88, 828, 560, 1028), start=12., end=12.2,
                          speed=1., source=0, score_inset_windows=())
    w.resolve_masks({0: Path("source.mp4")}, [seg], tmp_path, "25", 0)
    assert captured["frames"] == original


def test_window_cannot_borrow_a_native_board_from_outside_its_declared_time(tmp_path, monkeypatch):
    geometry = w.frame_geometry(band())
    monkeypatch.setattr(w, "scan_geometry", lambda *a, **kw: ([geometry] * 3 + [None] * 3, 760))
    def forbidden_write(*args):
        pytest.fail("empty declared window must fail before creating a mask")
    monkeypatch.setattr(w, "write_geometry_mask", forbidden_write)
    seg = SimpleNamespace(score_inset=(88, 828, 560, 1028), start=12., end=12.24,
                          speed=1., source=0, score_inset_windows=((.12, .24),))
    with pytest.raises(RuntimeError, match="score_inset_windows.*真实 WTA"):
        w.resolve_masks({0: Path("source.mp4")}, [seg], tmp_path, "25", 0)
