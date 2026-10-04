"""Audio-tail policy is proven through actual cut_segment FFmpeg output, not flags."""
import copy
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel
import foreground_audio_gate as audio_gate
import render_inputs


def _pcm(path):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-vn',
                                   '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4')


def test_policy_is_parsed_validated_and_bound_to_audio_review():
    raw = {'segments': [{'start': .4, 'end': 1.4, 'audio_tail': 'silence'}]}
    seg = reel.parse_segments(raw, {'': 1}, '')[0]
    assert seg.audio_tail == 'silence'
    ordinary = copy.deepcopy(raw); ordinary['segments'][0].pop('audio_tail')
    assert reel.parse_segments(ordinary, {'': 1}, '')[0].audio_tail == ''
    assert audio_gate.plan_hash(raw) != audio_gate.plan_hash(ordinary)
    assert render_inputs.project(raw) != render_inputs.project(ordinary)
    assert 'audio_tail' in reel._REAL_FIELDS['segment']
    for value in [None, True, 1, 'mute', 'source', {}]:
        invalid = copy.deepcopy(raw); invalid['segments'][0]['audio_tail'] = value
        with pytest.raises(reel.ReelError, match='audio_tail'):
            reel.parse_segments(invalid, {'': 1}, '')
    with pytest.raises(reel.ReelError, match='audio_tail'):
        reel.parse_segments({'segments': [{'image': 'unused.png', 'narration': '结果说明', 'seconds': 2,
                                           'audio_tail': 'silence'}]}, {'': 1}, '')


@pytest.mark.parametrize('speed', [1.0, .6])
def test_real_cut_keeps_body_and_video_but_zero_fills_only_dissolve_audio(tmp_path, monkeypatch, speed):
    # Original behavior must be audible in the transition tail, so this test
    # cannot pass just because the source is silent or the whole part is muted.
    monkeypatch.setattr(reel, 'VIDEO_W', 108)
    monkeypatch.setattr(reel, 'VIDEO_H', 144)
    monkeypatch.setattr(reel, 'CROP_W', 134)
    monkeypatch.setattr(reel, 'CROP_H', 180)
    monkeypatch.setattr(reel, 'PART_PRESET', 'ultrafast')
    source = tmp_path / 'tone.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=320x180:rate=25:duration=3', '-f', 'lavfi', '-i',
                    'sine=frequency=1000:sample_rate=48000:duration=3', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-c:a', 'alac', str(source)], check=True)
    outputs = {}
    for policy in ['', 'silence']:
        seg = reel.Segment(.4, 1.4, .5, '', audio_tail=policy, speed=speed)
        out = tmp_path / (policy or 'original')
        out = out.with_suffix('.mp4')
        reel.cut_segment(source, seg, out, 320, tail=.18)
        outputs[policy] = _pcm(out)
        duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams',
                         'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', str(out)]))
        assert duration >= seg.length + .18 - .04, 'video continuation must remain available for xfade'
    body, end = round(seg.length * 48000), round((seg.length + .18) * 48000)
    assert len(outputs['silence']) >= end
    assert np.sqrt(np.mean(outputs[''][body:end] ** 2)) > .05, 'old tail must actually leak tone'
    assert np.sqrt(np.mean(outputs['silence'][4000:body-4000] ** 2)) > .05, 'body audio must remain'
    assert np.count_nonzero(outputs['silence'][body:end]) == 0, 'every decoded tail sample must be zero'


def test_slow_motion_counts_tail_samples_after_atempo_and_preserves_mute_floor():
    seg = reel.Segment(1, 2, .5, '', speed=.5, mute=True, audio_tail='silence')
    chain = reel._seg_audio_chain(seg, .18)
    assert chain.startswith(f'atempo=0.5,volume={reel.MUTE_FLOOR},aresample=48000')
    assert 'atrim=end_sample=96000' in chain and 'apad=whole_len=104640' in chain
