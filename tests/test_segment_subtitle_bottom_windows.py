"""Measured header intervals move captions without changing their text or timing."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'src')]
import build_match_reel as reel
import render_inputs as ri
from tennislive.video.explainer import write_subtitles


def _raw():
    return {'start': 0, 'end': 10, 'narration': '实际字幕', 'subtitle_bottom': 306,
            'subtitle_bottom_windows': [[3, 6, 360]]}


def test_actual_ass_defaults_and_header_overrides_are_disjoint(tmp_path):
    segs = reel.parse_segments({'segments': [_raw()]}, {'main': Path('source.mp4')}, 'main')
    windows = reel.segment_subtitle_bottom_windows(segs, 1.2)
    assert windows == [(1.2, 4.2, 306), (4.2, 7.2, 360), (7.2, 11.2, 306)]
    assert segs[0].subtitle_bottom_windows == ((3., 6., 360),)
    cues = [(2., 3., '没有头标'), (5., 6., 'BREAK POINT\n破发点'), (8., 9., '恢复低字幕')]
    data = write_subtitles(cues, tmp_path / 'new.ass', height=1440,
                          bottom_margin_windows=windows).read_text()
    rows = [x for x in data.splitlines() if x.startswith('Dialogue:')]
    assert len(rows) == 3
    assert [int(x.split(',', 9)[7]) for x in rows] == [306, 360, 306]


def test_invalid_or_crossing_intervals_are_rejected(tmp_path):
    for intervals in ([[0, 11, 360]], [[0, 1, 95]], [[0, 1, 360.0]],
                      [[float('nan'), 1, 306]], [[0, 4, 306], [3, 6, 360]],
                      [[False, 1, 306]], [[-1, 1, 306]]):
        raw = {**_raw(), 'subtitle_bottom_windows': intervals}
        with pytest.raises(reel.ReelError):
            reel.parse_segments({'segments': [raw]}, {'main': Path('source.mp4')}, 'main')
    raw = _raw(); raw.pop('narration'); raw.pop('subtitle_bottom')
    with pytest.raises(reel.ReelError):
        reel.parse_segments({'segments': [raw]}, {'main': Path('source.mp4')}, 'main')
    segs = reel.parse_segments({'segments': [_raw()]}, {'main': Path('source.mp4')}, 'main')
    with pytest.raises(ValueError, match='crosses'):
        write_subtitles([(2., 4., '不会自动切断这一句')], tmp_path / 'bad.ass', height=1440,
                        bottom_margin_windows=reel.segment_subtitle_bottom_windows(segs, 0))


def test_interval_change_invalidates_render_projection():
    old = {'segments': [_raw()]}; changed = deepcopy(old)
    changed['segments'][0]['subtitle_bottom_windows'][0][2] = 306
    assert 'subtitle_bottom_windows' in reel._REAL_FIELDS['segment']
    assert ri.project(old) != ri.project(changed)
    problems = ri.spec_problems(json.dumps(changed).encode(), {'projection': ri.project(old)})
    assert problems and any('subtitle_bottom_windows' in p for p in problems)
