"""An explicitly absent source board has no crop coordinates to reinsert."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


def _video(**changes):
    return {'source': 'sina', 'start': 0.0, 'end': 7.3, 'cx': 0.5,
            'score_inset': False,
            '_score_inset_why': '本场场边近景无转播比分板，逐帧查看未出现记分条',
            **changes}


def _spec(segments):
    return {'slug': 'fresh-no-board-test', 'cover': {'eyebrow': '赛场之上'},
            'segments': segments}


def _parse(spec):
    return reel.parse_segments(spec, {'sina': Path('source.mp4')}, 'sina')


def test_three_explicit_no_board_video_segments_need_no_fictitious_scorebox():
    spec = _spec([_video(), _video(start=7.3, end=9.0), _video(start=29.0, end=32.0)])
    assert 'scorebox' not in spec
    assert all(seg.score_inset is None for seg in _parse(spec))


def test_story_cards_do_not_need_source_board_declarations():
    card = {'title_card': '首盘0比5落后', 'seconds': 3.0, 'narration': '首盘零比五落后'}
    segments = _parse(_spec([_video(), card, _video(start=7.3, end=9.0)]))
    assert len(segments) == 3 and segments[1].image.startswith(reel.TITLE_CARD_PREFIX)


@pytest.mark.parametrize('mutation', ['missing_declaration', 'missing_reason', 'blank_reason'])
def test_one_incomplete_absence_claim_cannot_waive_the_missing_box(mutation):
    other = _video(start=7.3, end=9.0)
    if mutation == 'missing_declaration':
        del other['score_inset']
    elif mutation == 'missing_reason':
        del other['_score_inset_why']
    else:
        other['_score_inset_why'] = ' \n '
    with pytest.raises(reel.ReelError, match='scorebox'):
        _parse(_spec([_video(), other]))


@pytest.mark.parametrize('reason', [None, False, True, 0, [], {'source': 'checked'}])
def test_absence_reason_must_be_real_text(reason):
    with pytest.raises(reel.ReelError, match='scorebox'):
        _parse(_spec([_video(_score_inset_why=reason)]))


@pytest.mark.parametrize('requested', [True, {'x2': 200}])
def test_any_inset_request_still_requires_real_source_coordinates(requested):
    with pytest.raises(reel.ReelError, match='scorebox'):
        _parse(_spec([_video(), _video(score_inset=requested)]))


def test_no_video_segments_does_not_vacuously_waive_the_existing_gate():
    with pytest.raises(reel.ReelError, match='scorebox'):
        _parse(_spec([{'title_card': '首盘0比5落后', 'seconds': 3.0}]))


def test_true_inset_with_real_box_and_declared_absence_keeps_working():
    spec = _spec([_video(score_inset=True), _video(start=7.3, end=9.0)])
    spec['scorebox'] = [0, 100, 200, 140]
    segments = _parse(spec)
    assert segments[0].score_inset == (0, 100, 200, 140)
    assert segments[1].score_inset is None
