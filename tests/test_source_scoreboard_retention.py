"""An original broadcast board is allowed only with the entire source retained."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


def spec():
    return {'slug': 'original-board-fixture', 'cover': {'eyebrow': '赛场之上'},
            'source_scorebox': [183, 890, 645, 1000],
            'segments': [{'source': 'main', 'start': 10, 'end': 15, 'fit': 'contain',
                          'contain_keep': 1.0, 'cx': .5, 'score_inset': False,
                          '_score_inset_why': '完整保留源画面原始比分板'}]}


def test_retained_original_board_is_not_an_inset():
    seg = reel.parse_segments(spec(), {'main': 'local.mp4'}, 'main')[0]
    assert seg.score_inset is None
    assert seg.source_scorebox == (183, 890, 645, 1000)
    assert reel.scoreboard_profile(spec()) is None


@pytest.mark.parametrize('changes', [{'fit': 'crop'}, {'contain_keep': .82},
                                      {'cx': .6}, {'track': True}, {'score_inset': True}])
def test_original_board_cannot_exempt_cropped_or_pasted_views(changes):
    s = spec()
    s['segments'][0].update(changes)
    with pytest.raises(reel.ReelError):
        reel.parse_segments(s, {'main': 'local.mp4'}, 'main')


def test_normal_fill_still_requires_scorebox():
    s = spec()
    del s['source_scorebox']
    s['segments'][0]['fit'] = 'crop'
    del s['segments'][0]['contain_keep']
    with pytest.raises(reel.ReelError, match='顶层缺 `scorebox`'):
        reel.parse_segments(s, {'main': 'local.mp4'}, 'main')


def test_real_source_geometry_checked_before_encoding(monkeypatch, tmp_path):
    seg = reel.parse_segments(spec(), {'main': 'local.mp4'}, 'main')[0]
    monkeypatch.setattr(reel, 'effective_size', lambda source: (640, 360))
    with pytest.raises(reel.ReelError, match='原板超出真实源画面取景'):
        reel.cut_segment(Path('local.mp4'), seg, tmp_path / 'part.mp4', 640)
