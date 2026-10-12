"""Real codec/source/voice-pair evidence; no mocked acoustic acceptance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import natural_quiet_audio as Q
from foreground_audio_gate import plan_hash
import render_inputs as RI


def encode(raw: np.ndarray, path: Path, *, codec='aac'):
    data = path.with_suffix('.f32')
    data.write_bytes(raw.astype('<f4').tobytes())
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','f32le','-ar','8000',
                    '-ac','1','-i',str(data),'-ar','48000','-c:a',codec,
                    '-b:a','192k',str(path)],check=True,timeout=30,
                   stdin=subprocess.DEVNULL,capture_output=True)


def seal(root, spec, film, offsets, lengths):
    source=root/'source_main.mp4'
    path=root/'spec.json';path.write_text(json.dumps(spec))
    entries=[]
    for i, seg in enumerate(spec['segments']):
        packet=root/f'packet-{i}.json'
        packet.write_text(json.dumps({'source_url':spec['sources']['main'],
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'method':'verified_source_captions','reviewer':'deterministic-PCM-test-fixture',
            'reviewed_at':datetime.now(timezone.utc).isoformat(),'status':'complete',
            'reviewed_from':seg['start'],'reviewed_to':seg['end'],
            'uncertain_spans':[],'foreground_english':[],
            'no_foreground_english_reason':'Generated deterministic ambience has no speech.'}))
        entries.append({'index':i,'transcript_path':packet.name,
                        'transcript_sha256':hashlib.sha256(packet.read_bytes()).hexdigest()})
    review=root/'data/audio_reviews'/f"{spec['slug']}.json"
    review.parent.mkdir(parents=True,exist_ok=True)
    review.write_text(json.dumps({'schema':'tennislive.foreground-audio-review.v1',
                                 'plan_sha256':plan_hash(spec),'segments':entries}))
    binding={'plan_sha256':plan_hash(spec),
             'review_sha256':hashlib.sha256(review.read_bytes()).hexdigest(),
             'sources':{'main':hashlib.sha256(source.read_bytes()).hexdigest()},
             'timeline':{'cover_seconds':0,'offsets':offsets,'lengths':lengths}}
    (root/'audio_review_binding.json').write_text(json.dumps(binding))
    (root/'subtitles.ass').write_text('[Events]\n')
    render={'narration_backend':'edge-tts','narration_voice':'zh-CN-YunjianNeural',
            'narration_rate':'+6%'}
    (root/'render.json').write_text(json.dumps(render))
    RI.record(path,root,film,root)


@pytest.fixture
def joined(tmp_path):
    rng=np.random.default_rng(73)
    source=np.convolve(rng.normal(size=32000),np.ones(5)/5,mode='same')
    source*=.0008/np.sqrt(np.mean(source**2))
    encode(source,tmp_path/'source_main.mp4')
    original=Q.pcm(tmp_path/'source_main.mp4')[6400:30400]
    film=tmp_path/'film.mp4';encode(original*.972,film)
    spec={'slug':'native-join','sources':{'main':'https://example.test/source'},
          'segments':[{'source':'main','start':.8,'end':1.93,'bed':'high'},
                      {'source':'main','start':1.93,'end':3.8,'bed':'high'}]}
    seal(tmp_path,spec,film,[0,1.13],[1.13,1.87])
    return spec,film,tmp_path,original


def test_actual_codec_continuous_join(joined):
    spec,film,root,_=joined
    assert Q.verified_native_ambience_seconds(spec,film,[1],root=root)==[1]


@pytest.mark.parametrize('failure',['wrong_gain','zero','source_gap','different_bed','changed_source'])
def test_continuous_join_does_not_waive_sound_identity(joined,failure):
    spec,film,root,original=joined
    lengths=[1.13,1.87]
    if failure=='wrong_gain':encode(original*.972*.3,film)
    elif failure=='zero':encode(np.zeros_like(original),film)
    elif failure=='source_gap':
        spec['segments'][1]['start']=1.94;lengths=[1.13,1.86]
    elif failure=='different_bed':spec['segments'][1]['bed']='low'
    else:
        source=root/'source_main.mp4'
        encode(Q.pcm(source)[::-1],source)
    seal(root,spec,film,[0,1.13],lengths)
    assert Q.verified_native_ambience_seconds(spec,film,[1],root=root)==[]


@pytest.fixture
def voiced_tail(tmp_path,monkeypatch):
    from build_match_reel import _tts_content_key
    rng=np.random.default_rng(92)
    source=np.convolve(rng.normal(size=40000),np.ones(5)/5,mode='same')
    source*=.002/np.sqrt(np.mean(source**2))
    encode(source,tmp_path/'source_main.mp4')
    voice=np.zeros(16000)
    voice[:10000]=.13*np.sin(2*np.pi*250*np.arange(10000)/8000)
    voice_path=tmp_path/'voice_00.mp3';encode(voice,voice_path,codec='libmp3lame')
    marks=[{'offset':0,'duration':11500000,'text':'测试'}]
    marks_path=voice_path.with_suffix('.words.json');marks_path.write_text(json.dumps(marks))
    # These are generated signal fixtures, not a claim that a human spoke Chinese.
    cache=tmp_path/'cache';cache.mkdir();monkeypatch.setenv('TENNISLIVE_TTS_CACHE',str(cache))
    key=_tts_content_key('测试','zh-CN-YunjianNeural','+6%','+0Hz','','',0.)
    pair=cache/f'{key}-edge-v2.zip'
    with zipfile.ZipFile(pair,'w') as bundle:
        bundle.writestr('audio.mp3',voice_path.read_bytes())
        bundle.writestr('marks.json',json.dumps(marks))
    original=Q.pcm(tmp_path/'source_main.mp4')[:40000]
    decoded_voice=Q.pcm(voice_path)
    mix=original*.36;mix[:len(decoded_voice)]+=decoded_voice
    film=tmp_path/'film.mp4';encode(mix,film)
    spec={'slug':'native-tail','sources':{'main':'https://example.test/source'},
          'segments':[{'source':'main','start':0,'end':5,'bed':'low','narration':'测试'}]}
    seal(tmp_path,spec,film,[0],[5])
    return spec,film,tmp_path,original,pair


def test_actual_codec_paired_complete_voice_and_weak_tail(voiced_tail):
    spec,film,root,_,_=voiced_tail
    assert Q.verified_native_ambience_seconds(spec,film,[2,3],root=root)==[2,3]
    assert Q.verified_native_ambience_seconds(spec,film,[0,1],root=root)==[]


@pytest.mark.parametrize('failure',['zero','wrong_bed_gain','wrong_voice_gain',
                                   'null_marks','missing_pair','premature_word_end','wrong_voice'])
def test_tail_proof_requires_actual_complete_paired_voice(voiced_tail,failure):
    spec,film,root,original,pair=voiced_tail
    voice=root/'voice_00.mp3';marks_path=voice.with_suffix('.words.json')
    decoded_voice=Q.pcm(voice)
    if failure in ('zero','wrong_bed_gain','wrong_voice_gain'):
        mix=original*(.12 if failure=='wrong_bed_gain' else .36)
        mix[:len(decoded_voice)]+=decoded_voice*(.3 if failure=='wrong_voice_gain' else 1)
        if failure=='zero':mix[16000:32000]=0
        encode(mix,film)
    elif failure=='missing_pair':pair.unlink()
    else:
        marks=json.loads(marks_path.read_text())
        if failure=='null_marks':marks=[]
        elif failure=='premature_word_end':marks[0]['duration']=23000000
        else:
            replacement=np.zeros(16000)
            replacement[:8000]=.13*np.sin(2*np.pi*650*np.arange(8000)/8000)
            encode(replacement,voice,codec='libmp3lame')
        marks_path.write_text(json.dumps(marks))
        with zipfile.ZipFile(pair,'w') as bundle:
            bundle.writestr('audio.mp3',voice.read_bytes());bundle.writestr('marks.json',json.dumps(marks))
    seal(root,spec,film,[0],[5])
    assert Q.verified_native_ambience_seconds(spec,film,[2,3],root=root)==[]


def test_quiet_window_floor_proxy_requires_every_actual_second_proved():
    assert Q.quiet_window_has_source_proof(251,252,{251})
    assert Q.quiet_window_has_source_proof(251,253,{251,252})
    assert not Q.quiet_window_has_source_proof(251,253,{251})
    assert not Q.quiet_window_has_source_proof(251,252,set())
    assert not Q.quiet_window_has_source_proof(251,251,{251})


def test_actual_eala_master_regression_when_available(monkeypatch):
    root=Path(__file__).resolve().parents[1]
    film=root/'output/2026-10-12/reel/eala-shi/eala-shi.mp4'
    if not film.is_file():pytest.skip('Actual owner master is a release asset, never a Git test fixture.')
    if hashlib.sha256(film.read_bytes()).hexdigest()!='dd60eef0078ca720037d4a9ce9543d157598d8d335503363d9f19e69c48b5b35':
        pytest.skip('Different production master; this immutable real-media regression does not apply.')
    monkeypatch.setenv('TENNISLIVE_TTS_CACHE', str(Path.home()/'.cache/tennislive-tts'))
    spec=json.loads((root/'specs/reels/eala-shi.json').read_text())
    assert Q.verified_native_ambience_seconds(spec,film,[48,208,211],root=root)==[48,208,211]
    assert 251 in Q.verified_seconds(spec,film,[251])


@pytest.fixture
def mixed_final_word(voiced_tail):
    """A complete signal utterance with a real quiet 40ms final sound."""
    spec, film, root, original, pair = voiced_tail
    raw = np.zeros(32000)
    raw[:16000] = .13 * np.sin(2*np.pi*250*np.arange(16000)/8000)
    raw[16000:16320] = .001 * np.sin(2*np.pi*250*np.arange(320)/8000)
    voice = root/'voice_00.mp3'
    encode(raw, voice, codec='libmp3lame')
    marks = [{'offset':0, 'duration':20350000, 'text':'测试'}]
    voice.with_suffix('.words.json').write_text(json.dumps(marks))
    with zipfile.ZipFile(pair,'w') as bundle:
        bundle.writestr('audio.mp3',voice.read_bytes())
        bundle.writestr('marks.json',json.dumps(marks))
    decoded = Q.pcm(voice)
    mix = original*.36
    mix[:len(decoded)] += decoded
    encode(mix,film)
    seal(root,spec,film,[0],[5])
    return spec,film,root,original,pair,decoded


def test_complete_codec_mix_keeps_the_quiet_final_word(mixed_final_word):
    spec,film,root,_,_,_=mixed_final_word
    assert Q.verified_native_ambience_seconds(spec,film,[2],root=root)==[2]


@pytest.mark.parametrize('failure',['deleted_final_sound','wrong_pair'])
def test_mixed_word_proof_rejects_deleted_sound_and_wrong_pair(mixed_final_word,failure):
    spec,film,root,original,pair,decoded=mixed_final_word
    if failure=='deleted_final_sound':
        truncated=decoded.copy();truncated[16000:]=0
        mix=original*.36;mix[:len(truncated)]+=truncated
        encode(mix,film)
    else:
        with zipfile.ZipFile(pair,'w') as bundle:
            bundle.writestr('audio.mp3',b'not the actual paired MP3')
            bundle.writestr('marks.json',(root/'voice_00.words.json').read_bytes())
    seal(root,spec,film,[0],[5])
    assert Q.verified_native_ambience_seconds(spec,film,[2],root=root)==[]


def test_actual_paolini_final_word_with_original_sound_when_available():
    movie=Path('/workspace/scratch/timed-662TF-JlyZY/final-original-sound-master.mp4')
    source=Path('/workspace/scratch/timed-662TF-JlyZY/662TF-JlyZY.mp4')
    voice=Path('/workspace/scratch/timed-cloud-artifact/voice_06.mp3')
    if not all(p.is_file()for p in(movie,source,voice)):
        pytest.skip('Actual master/source/utterance are external media, not Git fixtures.')
    if hashlib.sha256(movie.read_bytes()).hexdigest()!='3339af7058a8ccfb0c260dfe9c72ab6bf69f6bd309111b5ac47784c4c0b70d3c':
        pytest.skip('This immutable actual source/voice regression has another movie.')
    final,original,actual_voice=Q.pcm(movie),Q.pcm(source),Q.pcm(voice)
    at=round(118.16*Q.RATE)
    proof=Q._mixed_word_tail_match(original[at-640:at+Q.RATE+640],
        final[137*Q.RATE:138*Q.RATE],actual_voice,6.16,.36,
        {'word_end':6.155625,'acoustic_end':6.2,'native_channel_gain':1/np.sqrt(2)})
    assert proof is not None and proof['correlation']>.97
    assert proof['correlation']>proof['source_only_correlation']+.002
