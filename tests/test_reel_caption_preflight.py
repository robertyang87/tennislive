"""The final native ASS must be validated before any film encoding starts."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'src')]
import build_match_reel as reel

# Actual Edge WordBoundary events from the published Paolini / Bejlek landing.
# Kept inline because CI does not check out production output/ artifacts.
MARKS = [
    {'offset': 471659, 'duration': 6957500, 'text': '帕奥利尼'},
    {'offset': 7665000, 'duration': 1768750, 'text': '赢'},
    {'offset': 9434160, 'duration': 1532910, 'text': '下'},
    {'offset': 10967080, 'duration': 4599160, 'text': '两盘'},
    {'offset': 17570830, 'duration': 4599160, 'text': '过程'},
    {'offset': 22405830, 'duration': 1886660, 'text': '却'},
    {'offset': 24410410, 'duration': 2358330, 'text': '并'},
    {'offset': 26768750, 'duration': 1179160, 'text': '不'},
    {'offset': 27947910, 'duration': 4245410, 'text': '轻松'},
]


class BeforeTracking(Exception):
    pass


@pytest.fixture
def prepared_render(monkeypatch, tmp_path):
    """Isolate subtitle scheduling from independent source/TTS review gates.

    Timing, quote parsing, WordBoundary cue construction and ASS writing are
    native. The boundary spy stops before tracking or any encoder, after board geometry is resolved.
    """
    import foreground_audio_gate
    import winners_ue_gate
    import production_style
    import tennislive.video.crop_policy as crop_policy

    source = tmp_path / 'source.mp4'
    source.write_bytes(b'fixture: not decoded in this scheduling test')
    for name in ('validate_spec', '_preflight_cutout', 'check_native_quality_exceptions',
                 'conform_sources', 'check_sources_match', 'precheck_cover_face',
                 'require_live_sound', 'resolve_crop', '_check_segments_fit',
                 '_render_silence_gate'):
        monkeypatch.setattr(reel, name, lambda *_a, **_k: None)
    monkeypatch.setattr(foreground_audio_gate, 'require', lambda *_a, **_k: None)
    monkeypatch.setattr(foreground_audio_gate, 'bind_sources', lambda *_a, **_k: None)
    monkeypatch.setattr(winners_ue_gate, 'require', lambda *_a, **_k: None)
    monkeypatch.setattr(production_style, 'match_footage_problem', lambda *_a: None)
    monkeypatch.setattr(crop_policy, 'require_reel_center', lambda *_a: None)
    monkeypatch.setattr(reel, 'effective_size', lambda _p: (1920, 1080))
    monkeypatch.setattr(reel, 'resolve_fps', lambda _p: ('25', 25))
    monkeypatch.setattr(reel, 'probe_duration', lambda p: 4.032 if p.name.startswith('voice_') else 100.)
    monkeypatch.setattr(reel, 'synth_cover', lambda *_a: (None, []))
    monkeypatch.setattr(reel, 'cover_length', lambda _p: 1.2)
    monkeypatch.setattr(reel, 'synth_outro', lambda *_a: (tmp_path / 'outro.mp3', []))
    monkeypatch.setattr(reel, 'outro_length', lambda _p: 1.75)
    monkeypatch.setattr(reel, 'synthesize', lambda segs, *_a:
                        [(tmp_path / f'voice_{i:02d}.mp3', MARKS if seg.narration else [])
                         for i, seg in enumerate(segs)])
    monkeypatch.setattr(reel, '_TIMINGS', [])
    # Globals that native render changes must not leak into other tests.
    for name in ('FPS', 'FPS_EXPR', '_INSET_TOP_CLEAR_Y'):
        monkeypatch.setattr(reel, name, getattr(reel, name))
    for name, value in {'LAYOUT': 'full', 'VIDEO_H': 1440, 'VIDEO_W': 1080}.items():
        monkeypatch.setattr(reel, name, value)

    def tracking_boundary(*_a, **_k):
        raise BeforeTracking

    monkeypatch.setattr(reel, 'scoreboard_profile', lambda *_a, **_k: None)
    monkeypatch.setattr(reel, 'track_shots', tracking_boundary)
    for name in ('build_cover', 'cut_segment', 'cut_still_segment', 'build_outro', 'run'):
        monkeypatch.setattr(reel, name, lambda *_a, **_k: pytest.fail('encoder reached'))
    spec = {
        'slug': 'caption-preflight-fixture',
        'source_url': 'https://example.com/match.mp4', 'cover': {},
        'segments': [
            {'start': 0, 'end': 4., 'cx': .5,
             'narration': '帕奥利尼赢下两盘，过程却并不轻松。', 'subtitle_bottom': 306},
            {'start': 4., 'end': 7., 'cx': .5, 'subtitle_bottom': 306,
             'subtitle_bottom_windows': [[1., 2., 360]],
             'quote': [{'at': 0, 'end': 1., 'text': 'What a shot!\n这一拍真精彩'},
                       {'at': 1., 'end': 2., 'text': 'Break point.\n破发点'},
                       {'at': 2., 'end': 3., 'text': 'She holds.\n保住发球局'}]},
        ],
    }

    def render(settings=None):
        return reel.render(settings or deepcopy(spec), tmp_path, voice='fixture', rate='+0%')

    return spec, tmp_path, render


def test_original_native_ass_bytes_and_timeline_are_ready_before_tracking(prepared_render):
    spec, out, render = prepared_render
    with pytest.raises(BeforeTracking):
        render()
    # Frozen from the original post-encoding native block with these same actual
    # marks, quote intervals, measured MP3 duration and cover/segment lengths.
    assert hashlib.sha256((out / 'subtitles.ass').read_bytes()).hexdigest() == 'e4f90307cfd31ad62fb1de9dbef23f4efaef14e014047a55ff72a3aef22feeb8'
    import json
    timeline = json.loads((out / 'audio_review_binding.json').read_text())
    assert timeline['timeline'] == {'cover_seconds': 1.2, 'offsets': [1.2, 5.2], 'lengths': [4., 3.]}
    assert not (out / 'render.json').exists()
    assert not (out / 'qc_attestation.json').exists()


@pytest.mark.parametrize('fault', ['cross-position-window', 'invalid-quote-end'])
def test_bad_caption_fails_before_tracking_and_encoding_without_success_proof(prepared_render, fault):
    spec, out, render = prepared_render
    if fault == 'cross-position-window':
        spec['segments'][1]['quote'][0]['end'] = 1.1
        # Still a valid nonoverlapping quote schedule; only the position crossing
        # is bad, so the real ASS writer must be the gate that rejects it.
        spec['segments'][1]['quote'][1]['at'] = 1.1
        expected, message = ValueError, 'crosses'
    else:
        spec['segments'][1]['quote'][-1]['end'] = 4.
        expected, message = reel.ReelError, '结束时间'
    with pytest.raises(expected, match=message):
        render(spec)
    assert not (out / 'render.json').exists()
    assert not (out / 'qc_attestation.json').exists()
    assert not list(out.glob('part_*.mp4'))


def test_native_name_protection_is_display_only_before_encoding(prepared_render):
    spec, out, render = prepared_render
    spec['cover']['matchup'] = [{'name_en': 'Marie Bouzkova'}, {'name_en': 'Maja Chwalinska'}]
    text = "Marie Bouzkova's shot.\n布兹科娃这一拍"
    spec['segments'][1]['quote'][0]['text'] = text
    with pytest.raises(BeforeTracking):
        render(spec)
    assert spec['segments'][1]['quote'][0]['text'] == text
    assert "Marie\u00a0Bouzkova's shot." in (out / 'subtitles.ass').read_text()
    # Unrelated cues keep their exact original timing and display.
    assert '0:00:06.20,0:00:07.20' in (out / 'subtitles.ass').read_text()


def test_name_guard_preserves_explicit_lines_and_word_boundaries():
    spec = {'cover': {'matchup': [{'name_en': 'Marie Bouzkova'}]}}
    original = 'NotMarie Bouzkovax and MARIE Bouzkova.\nMarie\nBouzkova\n中文 Marie Bouzkova'
    assert reel.protect_quote_player_names(original, spec) == (
        'NotMarie Bouzkovax and MARIE\u00a0Bouzkova.\nMarie\nBouzkova\n中文 Marie Bouzkova')


@pytest.mark.parametrize('orientation', [1, 6])
def test_cover_probe_preserves_exif_oriented_geometry(tmp_path, orientation):
    from PIL import Image
    photo = tmp_path / f'photo-{orientation}.jpg'
    exif = Image.Exif()
    exif[274] = orientation
    Image.new('RGB', (800, 1200), 'navy').save(photo, exif=exif)
    spec = {'slug': 'cover-probe-fixture', 'cover': {'portrait': {
        'image': str(photo), 'crop': [0, 0, .5, 1], 'zoom': 1.1}}}
    message = reel.cover_photo_problem(spec)
    # EXIF 5/6/7/8 rotate the physical dimensions before crop/zoom; the actual
    # error text and native enlargement threshold remain the existing contract.
    size = '600×800' if orientation in (5, 6, 7, 8) else '400×1200'
    assert message and f'裁完 {size}' in message and 'zoom 1.1' in message


def test_bad_cover_is_still_rejected_by_native_asset_gate(tmp_path):
    import reel_asset_gates
    photo = tmp_path / 'broken.jpg'
    photo.write_bytes(b'broken image')
    spec = {'slug': 'cover-probe-fixture', 'cover': {'portrait': {'image': str(photo)}}}
    # The geometry check historically declines unreadable pictures. This must
    # never turn into a successful decode / asset approval.
    assert reel.cover_photo_problem(spec) is None
    assert reel_asset_gates.image_load_problem(photo)
    photo.unlink()
    assert reel.cover_photo_problem(spec) == f'封面大图找不到：{photo}'


def test_default_caption_margin_uses_resolved_scoreboard_top(prepared_render, monkeypatch):
    import scoreboard_geometry
    spec, out, render = prepared_render
    spec['cover']['eyebrow'] = '赛场之上'
    spec['scorebox'] = [50, 900, 400, 1000]
    spec['segments'][0]['score_inset'] = True
    spec['segments'][1]['score_inset'] = False
    spec['segments'][1]['_score_inset_why'] = '整段原声字幕样例没有比分板'
    for raw in spec['segments']:
        raw.pop('subtitle_bottom', None)
        raw.pop('subtitle_bottom_windows', None)
    monkeypatch.setattr(reel, 'CROP_W', 810)
    monkeypatch.setattr(reel, 'scoreboard_profile', lambda *_a, **_k: 'us-open')
    resolved = []

    def resolve_masks(_sources, segments, *_a):
        # The native US Open resolver reserves 36 source pixels above the body
        # for its point header. Default ASS margins must use this landed frame,
        # not the initial spec search box.
        x0, y0, x1, y1 = segments[0].score_inset
        segments[0].score_inset = (x0, y0 - 36, x1, y1)
        resolved.append(segments[0].score_inset)

    monkeypatch.setattr(scoreboard_geometry, 'resolve_masks', resolve_masks)
    with pytest.raises(BeforeTracking):
        render(spec)
    assert resolved == [(50, 864, 400, 1000)]
    lines = (out / 'subtitles.ass').read_text().splitlines()
    style = next(x for x in lines if x.startswith('Style: TL,'))
    assert int(style.split(',')[-2]) == 992  # Initial search-box geometry: 1040.
    cues = [x for x in lines if x.startswith('Dialogue:')]
    assert cues and all(int(x.split(',', 9)[7]) == 312 for x in cues)  # Initial: 264.
    assert not (out / 'render.json').exists()
    assert not (out / 'qc_attestation.json').exists()
