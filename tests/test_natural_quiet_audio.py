"""Actual PCM/AAC evidence; no mocked acoustic acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import natural_quiet_audio as Q
from foreground_audio_gate import plan_hash


def test_waveform_requires_original_and_gain():
    source = np.random.default_rng(42).normal(0, .0008, 9280)
    final = source[640:8640] * .972
    assert Q.matching_quiet(source, final)
    assert not Q.matching_quiet(source, np.zeros(8000))
    assert not Q.matching_quiet(source, final * .3)
    assert not Q.matching_quiet(np.zeros(9280), final)
    assert not Q.matching_quiet(source[::-1], final)
    assert not Q.matching_quiet(source * 100, final * 100)


@pytest.fixture
def encoded(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required for real codec evidence')
    raw = tmp_path / 'source.f32'
    rng = np.random.default_rng(3)
    # Bandlimited ambience survives AAC like an actual room/court noise floor.
    signal = np.convolve(rng.normal(size=32000), np.ones(5)/5, mode='same')
    signal *= .0008 / np.sqrt(np.mean(signal**2))
    raw.write_bytes(signal.astype('<f4').tobytes())
    source = tmp_path / 'source_main.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','8000','-ac','1',
                    '-i',str(raw),'-ar','48000','-c:a','aac','-b:a','192k',str(source)],check=True)
    film = tmp_path / 'film.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-af','volume=0.972',
                    '-c:a','aac','-b:a','192k',str(film)],check=True)
    spec = {'slug':'test','primary':'main','sources':{'main':'https://example.test/a'},
            'segments':[{'source':'main','start':0,'end':4,'bed':'high',
                         '_digital_silence_why':'Reviewed serve preparation',
                         '_digital_silence_windows':[[.5,3.5]]}]}
    binding = {'plan_sha256':plan_hash(spec),'sources':{'main':hashlib.sha256(source.read_bytes()).hexdigest()},
               'timeline':{'offsets':[0],'lengths':[4]}}
    (tmp_path/'audio_review_binding.json').write_text(json.dumps(binding))
    return spec, film


def test_real_aac_and_closed_boundaries(encoded):
    spec, film = encoded
    assert Q.verified_seconds(spec, film, [0,1,2,3]) == [1,2]
    spec['segments'][0].pop('_digital_silence_windows')
    assert Q.verified_seconds(spec, film, [1,2]) == []


def test_wrong_source_hash(encoded):
    spec, film = encoded
    with (film.parent/'source_main.mp4').open('ab') as stream:
        stream.write(b'changed source identity')
    assert Q.verified_seconds(spec, film, [1]) == []


@pytest.mark.parametrize('field,value', [('mute',True),('narration','speech'),('speed',.5)])
def test_nonplain_audio_refused(encoded, field, value):
    spec, film = encoded
    spec['segments'][0][field] = value
    assert Q.verified_seconds(spec, film, [1]) == []


def test_actual_missing_or_silent_landed_audio(encoded):
    spec, film = encoded
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anullsrc=r=48000:cl=mono',
                    '-t','4','-c:a','aac',str(film)],check=True)
    assert Q.verified_seconds(spec, film, [1]) == []


def test_real_codec_unexpected_attenuation_still_fails(encoded):
    spec, film = encoded
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(film.parent/'source_main.mp4'),
                    '-af','volume=0.2','-c:a','aac','-b:a','192k',str(film)],check=True)
    assert Q.verified_seconds(spec, film, [1]) == []


def test_why_alone_cannot_authorize(encoded):
    spec, film = encoded
    spec['segments'][0].pop('_digital_silence_why')
    assert Q.verified_seconds(spec, film, [1]) == []


@pytest.mark.parametrize('field,value', [('_digital_silence_windows', [[0,4]]),
                                        ('_digital_silence_why', 'Changed review')])
def test_post_render_declaration_change_rejected(encoded, field, value):
    spec, film = encoded
    assert Q.verified_seconds(spec, film, [1]) == [1]
    spec['segments'][0][field] = value
    assert Q.verified_seconds(spec, film, [1]) == []


def test_unducked_mix_cannot_use_ducked_gain(encoded):
    spec, film = encoded
    spec['outro'] = False
    assert Q.verified_seconds(spec, film, [1]) == []
    # Cover narration actually activates the renderer's ducked mixing branch.
    spec['cover'] = {'narration':'Real voice supplied to renderer'}
    assert Q.verified_seconds(spec, film, [1]) == [1]


def test_no_windows_preserves_legacy_plan_hash():
    spec = {'slug':'legacy','segments':[{'start':0,'end':4,'bed':'high',
                                      '_digital_silence_why':'legacy explanation'}]}
    row = {'start':0,'end':4,'bed':'high'}
    legacy = {'slug':'legacy','source_url':None,'sources':None,
              'source_audio':None,'segments':[row]}
    expected = hashlib.sha256(json.dumps(legacy,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    assert plan_hash(spec) == expected
    spec['segments'][0]['_digital_silence_windows'] = [[1,2]]
    assert plan_hash(spec) != expected


def test_real_aac_fade_near_segment_start_matches_but_crossing_fails(encoded):
    spec, film = encoded
    # Segment starts at output .95: candidate [1,2) begins .05 into its
    # .2-second audio fade. Use real encoding, delay and amplitude envelope.
    source = film.parent/'source_main.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),
                    '-af','atrim=start=0.8:end=3.8,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.2,volume=0.972,adelay=950',
                    '-c:a','aac','-b:a','192k',str(film)],check=True)
    seg = spec['segments'][0]
    seg['start'], seg['end'] = .8, 3.8
    seg['_digital_silence_windows'] = [[.8,3.8]]
    binding = json.loads((film.parent/'audio_review_binding.json').read_text())
    binding['plan_sha256'] = plan_hash(spec)
    binding['timeline']['offsets'] = [.95]
    (film.parent/'audio_review_binding.json').write_text(json.dumps(binding))
    assert Q.verified_seconds(spec, film, [1]) == [1]
    # [0,1) crosses the leading segment boundary; [3,4) crosses its end.
    # Neither may borrow another segment's audio even with a broad window.
    assert Q.verified_seconds(spec, film, [0,3]) == []


def test_real_aac_exact_boundary_float_cancellation(encoded):
    spec, film = encoded
    source = film.parent / 'source_main.mp4'
    # The regression concerns source/time mapping, not an adelay filter.
    # Decode the actual source independently, retain .4–3.4 seconds at the
    # renderer's gain, prepend one second, then encode real AAC. This avoids
    # the filter-construction subprocess that stalled on CI, without mocking
    # source identity, the codec, waveform/gain checks or boundary rejection.
    decoded_source = subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source), '-vn',
         '-ac', '1', '-ar', '8000', '-f', 'f32le', '-'],
        check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=30)
    original = np.frombuffer(decoded_source.stdout, dtype='<f4')
    assert len(original) >= 27200
    retained = original[3200:27200] * .972
    raw = film.parent / 'mapped.f32'
    raw.write_bytes(np.concatenate((np.zeros(8000), retained)).astype('<f4').tobytes())
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y',
                    '-f', 'f32le', '-ar', '8000', '-ac', '1', '-i', str(raw),
                    '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', str(film)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=30)
    decoded = Q.pcm(film)
    assert 4 * Q.RATE <= len(decoded) <= 4 * Q.RATE + 256
    assert np.max(np.abs(decoded[:Q.RATE - 640])) == 0
    seg = spec['segments'][0]
    seg['start'], seg['end'] = .4, 3.4
    seg['_digital_silence_windows'] = [[.4, 3.4]]
    binding = json.loads((film.parent / 'audio_review_binding.json').read_text())
    binding['plan_sha256'] = plan_hash(spec)
    binding['timeline']['offsets'] = [1.0]
    (film.parent / 'audio_review_binding.json').write_text(json.dumps(binding))
    assert .4 + 1 - 1 < .4  # Actual cancellation that used to reject this cut.
    assert Q.verified_seconds(spec, film, [1]) == [1]
    assert Q.verified_seconds(spec, film, [0, 4]) == []


@pytest.fixture
def reviewed_codec_mix(encoded, tmp_path):
    """A genuine AAC mix and immutable native review/manifest chain."""
    from datetime import datetime, timezone
    import render_inputs as RI
    _, film = encoded
    source = tmp_path / 'source_main.mp4'
    original = Q.pcm(source)
    selected = original[6400:26400]
    times = np.arange(len(selected)) / Q.RATE
    selected = selected * np.clip(times / .18, 0, 1) * .972
    # Card has actual tone audio at its beginning, then a deliberate quiet hold.
    card = np.zeros(12000)
    card[:3200] = .1 * np.sin(2*np.pi*300*np.arange(3200)/Q.RATE)
    raw = tmp_path / 'reviewed-mix.f32'
    raw.write_bytes(np.concatenate((card, selected)).astype('<f4').tobytes())
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','f32le',
                    '-ar','8000','-ac','1','-i',str(raw),'-ar','48000',
                    '-c:a','aac','-b:a','192k',str(film)],check=True,timeout=30)
    spec = {'slug':'reviewed-fixture','sources':{'main':'https://example.test/a'},
            'segments':[{'title_card':True,'seconds':1.5,'narration':'测试证据卡'},
                        {'source':'main','start':.8,'end':3.3,'bed':'high'}]}
    spec_path = tmp_path/'spec.json'
    spec_path.write_text(json.dumps(spec))
    packet = tmp_path/'packet.json'
    packet.write_text(json.dumps({'source_url':spec['sources']['main'],
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'method':'verified_source_captions','reviewer':'generated-PCM-test-fixture',
        'reviewed_at':datetime.now(timezone.utc).isoformat(),'status':'complete',
        'reviewed_from':.8,'reviewed_to':3.3,'uncertain_spans':[],
        'foreground_english':[],
        'no_foreground_english_reason':'Deterministic generated noise contains no speech.'}))
    review = tmp_path/'data/audio_reviews/reviewed-fixture.json'
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({'schema':'tennislive.foreground-audio-review.v1',
        'plan_sha256':plan_hash(spec),'segments':[{'index':1,
        'transcript_path':'packet.json','transcript_sha256':hashlib.sha256(packet.read_bytes()).hexdigest()}]}))
    binding = {'plan_sha256':plan_hash(spec),'review_sha256':hashlib.sha256(review.read_bytes()).hexdigest(),
               'sources':{'main':hashlib.sha256(source.read_bytes()).hexdigest()},
               'timeline':{'cover_seconds':0,'offsets':[0,1.5],'lengths':[1.5,2.5]}}
    (tmp_path/'audio_review_binding.json').write_text(json.dumps(binding))
    (tmp_path/'subtitles.ass').write_text('[Events]\n')
    RI.record(spec_path,tmp_path,film,tmp_path)
    return spec, film, tmp_path


def test_complete_review_real_codec_card_join_and_full_second(reviewed_codec_mix):
    spec, film, root = reviewed_codec_mix
    assert Q.verified_reviewed_mix_seconds(spec,film,[1,2],root=root) == [1,2]
    # Existing declared-window behavior is unchanged: there are no declarations.
    assert Q.verified_seconds(spec,film,[1,2]) == []


def test_reviewed_waveform_rejects_wrong_gain_silence_noise_and_fade():
    rng = np.random.default_rng(17)
    source = np.convolve(rng.normal(size=9280),np.ones(5)/5,mode='same')
    source *= .0008 / np.sqrt(np.mean(source**2))
    envelope = np.clip((np.arange(8000)/8000-.5)/.18,0,1)
    landed = source[640:8640] * envelope * .972
    assert Q._reviewed_mix_match(source,landed,envelope,.972)
    assert not Q._reviewed_mix_match(source,landed*.3,envelope,.972)
    assert not Q._reviewed_mix_match(source,np.zeros(8000),envelope,.972)
    assert not Q._reviewed_mix_match(source[::-1],landed,envelope,.972)
    # A missing fade cannot pass merely by fitting the constant-volume tail.
    no_fade = source[640:8640] * (envelope > 0) * .972
    assert not Q._reviewed_mix_match(source,no_fade,envelope,.972)


@pytest.mark.parametrize('changed', ['film','source','binding','packet','declaration'])
def test_reviewed_mix_requires_unchanged_authenticated_chain(reviewed_codec_mix,changed):
    spec,film,root=reviewed_codec_mix
    if changed == 'declaration':
        spec['segments'][1]['_digital_silence_windows']=[[.8,3.3]]
    else:
        path={'film':film,'source':root/'source_main.mp4',
              'binding':root/'audio_review_binding.json','packet':root/'packet.json'}[changed]
        with path.open('ab') as stream:stream.write(b'changed')
    assert Q.verified_reviewed_mix_seconds(spec,film,[1,2],root=root) == []


@pytest.mark.parametrize('field,value', [('mute',True),('narration','speech'),
    ('speed',.5),('music',{'file':'unreviewed'}),('source_audio',{'main':'unreviewed'})])
def test_reviewed_mix_rejects_non_native_plain_audio(reviewed_codec_mix,field,value):
    spec,film,root=reviewed_codec_mix
    if field in ('music','source_audio'):spec[field]=value
    else:spec['segments'][1][field]=value
    assert Q.verified_reviewed_mix_seconds(spec,film,[1,2],root=root) == []


def test_reviewed_mix_never_accepts_video_to_video_boundary(reviewed_codec_mix):
    spec,film,root=reviewed_codec_mix
    # No synthesized/changed metadata can make this raw boundary a card.
    spec['segments'][0]={'source':'main','start':0,'end':1.5}
    assert Q.verified_reviewed_mix_seconds(spec,film,[1],root=root) == []
