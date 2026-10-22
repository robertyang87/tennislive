"""Explicit original-audio scene types reject conflicting rendering requests."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


def _scene():
    return {'kind': 'quote', 'source': 'main', 'start': 1, 'end': 4,
            '_quote_skip_why': 'Source-bound reviewed window contains only court/crowd sound.'}


def test_explicit_original_audio_scene_keeps_video_and_optional_ambient_sound():
    scene = _scene()
    spec = {'segments': [scene]}
    before = copy.deepcopy(spec)
    reel._validate_segment_kinds(spec)
    assert spec == before
    scene['quote'] = [{'at': .2, 'end': 2., 'text': 'Come on.\n加油。'}]
    reel._validate_segment_kinds(spec)
    assert 'kind' in reel._REAL_FIELDS['segment']


@pytest.mark.parametrize('change', [
    {'kind': 'quuote'}, {'kind': None}, {'narration': '这句是自配旁白。'},
    {'image': 'photo.jpg'}, {'title_card': '标题'}, {'stat_card': True}, {'mute': True},
])
def test_scene_type_cannot_silently_hide_a_typo_or_change_audio_mode(change):
    scene = {**_scene(), **change}
    with pytest.raises(reel.ReelError, match='kind'):
        reel._validate_segment_kinds({'segments': [scene]})


def test_original_audio_scene_needs_an_actual_video_window():
    scene = _scene()
    del scene['start']
    with pytest.raises(reel.ReelError, match='kind'):
        reel._validate_segment_kinds({'segments': [scene]})
