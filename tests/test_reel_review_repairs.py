"""Regression coverage for visual defects found in the Sabalenka reel."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path('tools').resolve()))
import build_match_reel as reel
from tennislive.video.explainer import write_subtitles


def test_band_bilingual_respects_higher_safe_margin(tmp_path):
    path = write_subtitles([(0, 2, 'Game.\n拿下这一局。'), (2, 3, '普通字幕')],
                           tmp_path / 's.ass', height=1440, margin_v=1124)
    rows = [s for s in path.read_text().splitlines() if s.startswith('Dialogue:')]
    assert ',0,0,1124,,' in rows[0]
    assert ',0,0,0,,' in rows[1]


@pytest.mark.parametrize('auto', [True, False])
def test_review_windows_remove_false_patch_without_forcing_presence(tmp_path, monkeypatch, auto):
    source = tmp_path / 'source.mp4'
    source.touch()
    # Real board until 3s; dark bench falsely detected again after 5s.
    timeline = [((k + .5) / 6, 620 if k < 18 else 700, k < 18 or k >= 30)
                for k in range(48)]
    monkeypatch.setattr(reel, 'board_edge_timeline', lambda *a: timeline)
    seg = reel.Segment(10, 18, .5, '', score_inset=(104, 888, 736, 978),
                       score_inset_auto=auto, score_inset_windows=((0, 4),))
    reel.resolve_board_insets({'': source}, [seg])
    assert seg.score_inset_spans == ((0.0, 3.0),)
    assert seg.score_inset[2] == (628 if auto else 736)
    monkeypatch.setattr(reel, 'board_edge_timeline',
                        lambda *a: [(t, e, False) for t, e, p in timeline])
    with pytest.raises(reel.ReelError, match='整段都没有记分条'):
        reel.resolve_board_insets({'': source}, [seg])


def test_review_windows_are_validated_in_source_time():
    spec = {'source_url': 'https://youtu.be/test', 'layout': 'band',
            'scorebox': [104, 888, 736, 978], 'segments': [
                {'start': 10, 'end': 18, 'narration': '说明', 'score_inset': True,
                 'score_inset_windows': [[10, 14]], '_score_inset_why': '逐帧证据'}]}
    assert reel.parse_segments(spec, {'': 'https://youtu.be/test'}, '')[0].score_inset_windows == ((0, 4),)
    for windows in ([], [[9, 14]], [[10, 19]], [[10, 14], [13, 17]], [[10, float('nan')]]):
        spec['segments'][0]['score_inset_windows'] = windows
        with pytest.raises(reel.ReelError, match='score_inset_windows'):
            reel.parse_segments(spec, {'': 'https://youtu.be/test'}, '')
