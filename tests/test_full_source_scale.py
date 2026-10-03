"""Whole-frame scaling retains the portrait foreground and existing framing defaults."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel
import render_inputs


def _parse(**extra):
    return reel.parse_segments({'segments': [{'start': 0.0, 'end': 7.3,
        'cx': 0.5, 'narration': '', **extra}]}, {'main': 'source.mp4'}, 'main')[0]


def test_default_and_declared_scale_reach_segment():
    assert _parse(fit='full_source').full_source_scale == 1.0
    assert _parse(fit='full_source', full_source_scale=0.78).full_source_scale == 0.78
    assert _parse(fit='contain').full_source_scale == 1.0


@pytest.mark.parametrize('value', [0.5, 0.78, 1.0])
def test_scale_accepts_both_closed_bounds(value):
    assert _parse(fit='full_source', full_source_scale=value).full_source_scale == value


@pytest.mark.parametrize('value', [False, True, 1, '0.78', None, 0.49, 1.01,
                                  float('nan'), float('inf'), float('-inf')])
def test_invalid_scale_is_rejected_before_render(value):
    with pytest.raises(reel.ReelError, match='full_source_scale'):
        _parse(fit='full_source', full_source_scale=value)


@pytest.mark.parametrize('fit', ['crop', 'contain', 'square'])
def test_scale_cannot_be_silently_ignored_by_other_fits(fit):
    with pytest.raises(reel.ReelError, match='full_source_scale'):
        _parse(fit=fit, full_source_scale=0.78)


def _graph(monkeypatch, tmp_path, fit, scale=1.0, size=(1080, 1440)):
    calls = []
    monkeypatch.setattr(reel, 'effective_size', lambda _: size)
    monkeypatch.setattr(reel, 'conform_prefilter', lambda _: '')
    monkeypatch.setattr(reel, '_has_audio', lambda _: True)
    monkeypatch.setattr(reel, 'run', lambda *args: calls.append(args))
    monkeypatch.setattr(reel, 'LAYOUT', 'full')
    seg = reel.Segment(0.0, 7.3, 0.5, '', fit=fit, full_source_scale=scale)
    reel.cut_segment(tmp_path/'source.mp4', seg, tmp_path/'cut.mp4', size[0])
    args = calls[-1]
    return args[args.index('-filter_complex') + 1]


def test_portrait_source_is_preserved_shrunk_and_centered(monkeypatch, tmp_path):
    graph = _graph(monkeypatch, tmp_path, 'full_source', 0.78)
    # 1080*.78=842.4 -> even842: full source, including yellow header and racket.
    assert '[fg]crop=1080:1440:0:0,scale=842:-2:flags=lanczos[fgs]' in graph
    assert '[bgb][fgs]overlay=(W-w)/2:(H-h)/2' in graph
    assert 'boxblur=42:2' in graph
    assert '[bg]crop=1080:1440:0:0,scale=1080:1440' in graph


def test_wide_scale_is_even_and_does_not_trim_source(monkeypatch, tmp_path):
    graph = _graph(monkeypatch, tmp_path, 'full_source', 0.781, (1920, 1080))
    # round(1080*.781)=843; round down one pixel to the encoder's even width.
    assert '[fg]crop=1920:1080:0:0,scale=842:-2' in graph


def test_default_full_source_and_contain_keep_old_portrait_fill(monkeypatch, tmp_path):
    for fit in ('full_source', 'contain'):
        graph = _graph(monkeypatch, tmp_path, fit)
        assert 'scale=1080:1440:force_original_aspect_ratio=increase:flags=lanczos' in graph
        assert 'boxblur' not in graph


def test_contain_keeps_its_existing_wide_crop_and_width(monkeypatch, tmp_path):
    graph = _graph(monkeypatch, tmp_path, 'contain', size=(1920, 1080))
    keep = reel.contain_keep_width(1920)
    x = (1920-keep)//2
    assert f'[fg]crop={keep}:1080:{x}:0,scale=1080:-2' in graph


def test_scale_change_invalidates_render_input_projection():
    old = {'segments': [{'fit': 'full_source', 'full_source_scale': 1.0}]}
    new = {'segments': [{'fit': 'full_source', 'full_source_scale': 0.78}]}
    assert render_inputs.diff_paths(render_inputs.project(old), render_inputs.project(new)) == [
        ['segments', 0, 'full_source_scale']]
    assert 'full_source_scale' in reel._REAL_FIELDS['segment']
