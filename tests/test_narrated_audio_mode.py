import copy
import json
import subprocess
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
import narrated_audio_mode as mode
import build_match_reel as build
import foreground_audio_gate as foreground


def candidate(slug='nishikori-tiafoe-tokyo-2026-r1'):
 rec=mode.APPROVED[slug]
 return {'slug':slug,'source_url':'https://github.com/robertyang87/tennislive/releases/download/'+rec['asset'],
  'original_audio_mode':mode.MODE,'owner_approval':mode.APPROVAL,'cover':{'eyebrow':'赛场之上'},
  'segments':[{'start':a,'end':b,'cx':.5,'narration':'中文本人旁白' if i==0 else ''} for i,(a,b) in enumerate(rec['windows'])]}

@pytest.mark.parametrize('slug',list(mode.APPROVED))
def test_only_three_known_sources_and_windows(slug):
 spec=candidate(slug)
 assert mode.enabled(spec)
 assert foreground.require(spec)==[]
 assert build.cold_open_problem(spec) is None
 assert build.unvoiced_quote_problem(spec) is None
 for mutation in [lambda s:s.update(slug='another-film'),lambda s:s.update(source_url='https://example.com/a.mp4'),
  lambda s:s.update(owner_approval='yes'),lambda s:s.update(music={'file':'a.mp3'}),
  lambda s:s.update(source_audio='other.mp3'),lambda s:s['segments'][0].update(quote='Unverified\n未核准'),
  lambda s:s['segments'][0].update(start=s['segments'][0]['start']-.1),
  lambda s:s['segments'][0].update(narration=''),lambda s:s['segments'][0].update(cx=.6)]:
  altered=copy.deepcopy(spec);mutation(altered)
  with pytest.raises(ValueError):mode.enabled(altered)

def test_defaults_stay_strict():
 spec=candidate();spec.pop('original_audio_mode');spec.pop('owner_approval')
 assert not mode.enabled(spec)
 assert build.cold_open_problem(spec)
 with pytest.raises(ValueError):foreground.require(spec,root=Path('/nonexistent'))
 normal=build.duck_filtergraph(['[1:a]anull[v0]'],['[v0]'])
 assert '[0:a]volume=0.72[bed]' in normal
 assert 'anullsrc' not in normal
 assert build.MUTE_FLOOR==.05

def test_plan_hash_changes_with_mode():
 spec=candidate();old=copy.deepcopy(spec);old.pop('original_audio_mode');old.pop('owner_approval')
 assert foreground.plan_hash(old)!=foreground.plan_hash(spec)

def test_source_binding_rejects_changed_bytes(tmp_path):
 path=tmp_path/'source.mp4';path.write_bytes(b'incorrect')
 with pytest.raises(ValueError):mode.enabled(candidate(),sources={'':path})

def test_real_mix_removes_source_tone_and_preserves_voice_and_zero_pauses(tmp_path):
 graph=build.duck_filtergraph(['[1:a]adelay=1000|1000[v0]'],['[v0]'],mute_original=True)
 assert '[0:a]' not in graph and 'anullsrc' in graph
 film=tmp_path/'film.mp4'
 subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=997:sample_rate=48000:duration=6',
 '-f','lavfi','-i','sine=frequency=443:sample_rate=48000:duration=1',
 '-filter_complex',graph,'-map','[out]','-t','6','-c:a','aac','-b:a','192k',str(film)],check=True)
 pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(film),'-ac','1','-ar','8000','-f','f32le','-']),dtype='<f4')
 assert np.max(np.abs(pcm[:6400]))<1e-5
 assert np.max(np.abs(pcm[24000:]))<1e-5
 assert np.sqrt(np.mean(pcm[9000:15000]**2))>.01
 # Known 997Hz original source is absent, 443Hz narrator surrogate is present.
 chunk=pcm[9000:15000];freq=np.fft.rfftfreq(len(chunk),1/8000);spectrum=np.abs(np.fft.rfft(chunk))
 assert spectrum[np.argmin(abs(freq-443))] > 100*spectrum[np.argmin(abs(freq-997))]
 original_hash=mode.audio_packet_hash(film)
 remux=tmp_path/'remux.mp4'
 subprocess.run(['ffmpeg','-v','error','-i',str(film),'-c','copy',str(remux)],check=True)
 assert mode.audio_packet_hash(remux)==original_hash

def test_schema_fields_and_projection_are_render_inputs():
 assert {'original_audio_mode','owner_approval'}<=set(build._REAL_FIELDS['spec'])
 import render_inputs
 spec=candidate()
 assert 'original_audio_mode' in json.dumps(render_inputs.project(spec))


def test_pcm_verified_tts_padding_is_not_missing_original_audio(tmp_path,monkeypatch):
 film=tmp_path/'film.mp4';film.write_bytes(b'placeholder')
 (tmp_path/'audio_review_binding.json').write_text('{}')
 verified=[]
 monkeypatch.setattr(mode,'verify_mix',lambda spec,film,binding:verified.append(True))
 assert mode.declared_pause_seconds(candidate(),film,[-99,-25,-91,-99],after=2)==[2,3]
 assert verified==[True]

def test_missing_tts_is_never_accepted_as_planned_silence(tmp_path,monkeypatch):
 film=tmp_path/'film.mp4';film.write_bytes(b'placeholder')
 (tmp_path/'audio_review_binding.json').write_text('{}')
 def fail(*args):raise ValueError('missing real narration')
 monkeypatch.setattr(mode,'verify_mix',fail)
 with pytest.raises(ValueError,match='missing real narration'):
  mode.declared_pause_seconds(candidate(),film,[-99]*100,after=2)
