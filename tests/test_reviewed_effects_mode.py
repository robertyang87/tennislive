import copy,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
import reviewed_effects_mode as mode
import narrated_audio_mode as narrated
import build_match_reel as build

def candidate():
 return {'slug':mode.SLUG,'original_audio_mode':mode.MODE,'owner_approval':mode.APPROVAL,'sources':{k:'https://www.youtube.com/watch?v='+v for k,v in mode.IDS.items()},'segments':[{'source':'s2','start':1.,'end':2.,'narration':'中文旁白'},{'source':'s1','start':132.4,'end':145.7}]}

def test_owner_scope_and_old_modes_unchanged():
 s=candidate();assert mode.enabled(s);assert not narrated.enabled(s)
 for mutation in [lambda x:x.update(slug='other'),lambda x:x.update(owner_approval=narrated.APPROVAL),lambda x:x['segments'][0].update(mute=True),lambda x:x['segments'][1].update(end=145.8),lambda x:x['segments'][1].update(narration='中文'),lambda x:x.update(music={'file':'x'})]:
  x=copy.deepcopy(s);mutation(x)
  with pytest.raises(ValueError):mode.enabled(x)
 assert not mode.enabled({'segments':[]})
 assert '[0:a]volume=' in build.duck_filtergraph(['[1:a]anull[v0]'],['[v0]'])
 assert 'anullsrc' not in build.duck_filtergraph(['[1:a]anull[v0]'],['[v0]'],reviewed_bed='[2:a]anull[bed];')

def fixture_manifest(tmp_path,monkeypatch):
 original=tmp_path/'raw.wav';effects=tmp_path/'effects.wav'
 for path,hz in [(original,800),(effects,300)]:
  subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={hz}:sample_rate=48000:duration=146','-c:a','pcm_s16le',str(path)],check=True)
 monkeypatch.setattr(mode,'HASHES',{k:mode.sha(original) for k in mode.IDS})
 rows={}
 for k in mode.IDS:
  transcript=tmp_path/(k+'.json');transcript.write_text(json.dumps({'effects_sha256':mode.sha(effects),'status':'complete','uncertain_spans':[],'method':'asr_cross_checked','reviewer':'synthetic fixture','reviewed_at':'2026-10-03T00:00:00Z','reviewed_from':0,'reviewed_to':146,'foreground_speech':[],'no_foreground_speech_reason':'Synthetic tones contain no speech','asr_results':[{'model':'fixture-a'},{'model':'fixture-b'}]}))
  rows[k]={'source_sha256':mode.sha(original),'effects_path':'data/audio_effects/rna10/'+k+'.wav','effects_url':mode.EFFECTS_RELEASE+k+'.wav','effects_sha256':mode.sha(effects),'algorithm':'synthetic test fixture only','model_sha256':'a'*64,'status':'reviewed','reviewer':'test fixture','reviewed_at':'2026-10-03T00:00:00Z','ball_impacts_preserved':True,'speech_review':{'method':'asr_cross_checked','transcript_path':transcript.name,'sha256':mode.sha(transcript),'uncertain_spans':[]}}
 for k in mode.IDS:
  destination=tmp_path/'data/audio_effects/rna10'/f'{k}.wav';destination.parent.mkdir(parents=True,exist_ok=True);destination.hardlink_to(effects)
 manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'schema':'tennislive.reviewed-effects.v1','slug':mode.SLUG,'owner_approval':mode.APPROVAL,'sources':rows}))
 s=candidate();s['audio_effects_review']=manifest.name
 return s,{k:original for k in mode.IDS},manifest

def test_real_mix_uses_effects_and_exact_raw_not_concat(tmp_path,monkeypatch):
 s,sources,_=fixture_manifest(tmp_path,monkeypatch)
 inputs,graph,windows=mode.bed_graph(s,sources,[1.,4.],0,root=tmp_path)
 assert windows[0]['kind']=='processed_effects' and windows[1]['kind']=='raw'
 assert 'apad' not in graph
 output=tmp_path/'mixed.wav'
 subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',graph,'-map','[bed]','-t','19','-ac','1','-ar','8000','-c:a','pcm_f32le',str(output)],check=True)
 pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-f','f32le','-']),dtype='<f4')
 def rms(a,b):return np.sqrt(np.mean(pcm[int(a*8000):int(b*8000)]**2))
 assert rms(1.1,1.9)>.03 and rms(4.1,17.2)>.03
 assert rms(0,.9)==0 and rms(2.1,3.9)==0
 assert len(pcm)/8000==pytest.approx(17.3,abs=.01)
 for a,b,hz in [(1.1,1.9,300),(4.1,4.9,800)]:
  part=pcm[int(a*8000):int(b*8000)];peak=np.argmax(np.abs(np.fft.rfft(part)));frequency=peak*8000/len(part);assert abs(frequency-hz)<3

def test_manifest_blocks_unreviewed_or_changed_effects(tmp_path,monkeypatch):
 s,sources,path=fixture_manifest(tmp_path,monkeypatch)
 doc=json.loads(path.read_text());doc['sources']['s1']['status']='pending';path.write_text(json.dumps(doc))
 with pytest.raises(ValueError):mode.manifest(s,root=tmp_path,sources=sources)
 doc['sources']['s1']['status']='reviewed';doc['sources']['s2']['speech_review']['uncertain_spans']=[{'start':1,'end':2}];path.write_text(json.dumps(doc))
 with pytest.raises(ValueError):mode.manifest(s,root=tmp_path,sources=sources)

def test_foreground_gate_still_requires_exact_raw_packet(tmp_path):
 import foreground_audio_gate as foreground
 s=candidate()
 with pytest.raises(ValueError,match='waiting_audio_review'):
  foreground.require(s,root=tmp_path)
 review_dir=tmp_path/'data/audio_reviews';review_dir.mkdir(parents=True)
 packet={'source_url':s['sources']['s1'],'source_sha256':mode.HASHES['s1'],'method':'asr_cross_checked','reviewer':'synthetic gate fixture','status':'complete','reviewed_at':'2026-10-03T00:00:00Z','reviewed_from':132.4,'reviewed_to':145.7,'foreground_english':[],'no_foreground_english_reason':'Synthetic fixture only','uncertain_spans':[]}
 p=review_dir/'raw.json';p.write_text(json.dumps(packet))
 review={'schema':foreground.SCHEMA,'plan_sha256':foreground.plan_hash(s),'segments':[{'index':1,'transcript_path':str(p.relative_to(tmp_path)),'transcript_sha256':mode.sha(p)}]}
 (review_dir/(mode.SLUG+'.json')).write_text(json.dumps(review))
 assert foreground.require(s,root=tmp_path)==[]
 packet['uncertain_spans']=[{'start':134,'end':135}];p.write_text(json.dumps(packet));review['segments'][0]['transcript_sha256']=mode.sha(p);(review_dir/(mode.SLUG+'.json')).write_text(json.dumps(review))
 with pytest.raises(ValueError,match='不确定'):
  foreground.require(s,root=tmp_path)

def test_ball_bed_is_not_ducked_by_narration(tmp_path):
 graph=build.duck_filtergraph(['[1:a]anull[v0]'],['[v0]'],reviewed_bed='[0:a]volume=0.72[bed];')
 assert 'sidechaincompress' not in graph
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=300:sample_rate=48000:duration=1','-f','lavfi','-i','sine=frequency=2000:sample_rate=48000:duration=1','-filter_complex',graph,'-map','[out]','-ac','1','-ar','48000','-f','f32le','-'])
 pcm=np.frombuffer(raw,dtype='<f4');spectrum=np.abs(np.fft.rfft(pcm));assert spectrum[300]/spectrum[2000]==pytest.approx(.72,rel=.01)

def test_exact_release_download_only_and_sha_fail_closed(tmp_path,monkeypatch):
 import io
 content=b'real test bytes';expected=hashlib.sha256(content).hexdigest();calls=[]
 row={'effects_url':mode.EFFECTS_RELEASE+'s1.wav','effects_path':'data/audio_effects/rna10/s1.wav','effects_sha256':expected}
 path=tmp_path/row['effects_path']
 def response(url,timeout):calls.append(url);return io.BytesIO(content)
 monkeypatch.setattr(mode,'urlopen',response)
 mode.archived_effect('s1',row,path,download=False);assert not calls and not path.exists()
 mode.archived_effect('s1',row,path,download=True);assert calls==[row['effects_url']] and path.read_bytes()==content
 calls.clear();path.unlink();bad=dict(row,effects_url='https://example.com/s1.wav')
 with pytest.raises(ValueError,match='固定'):mode.archived_effect('s1',bad,path,download=True)
 assert not calls and not path.exists()
 bad=dict(row,effects_sha256='0'*64)
 with pytest.raises(ValueError,match='SHA'):mode.archived_effect('s1',bad,path,download=True)
 assert not path.exists() and not list(path.parent.glob('*.partial'))

def test_many_delayed_mp3_voices_and_finite_beds_mux_aac(tmp_path):
 voice=tmp_path/'voice.mp3';bed=tmp_path/'bed.wav'
 for path in (voice,bed):
  subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=500:sample_rate=48000:duration=0.6',str(path)],check=True)
 inputs=[];chains=[];labels=[];filters=[];voices=[]
 for i in range(15):
  inputs.extend(['-i',str(bed)]);chains.append(f'[{i}:a]asetpts=PTS-STARTPTS,adelay={i*100}|{i*100}[b{i}]');labels.append(f'[b{i}]')
 chains.append(''.join(labels)+'amix=inputs=15:normalize=0:dropout_transition=0,volume=0.72[bed]')
 for i in range(15):
  inputs.extend(['-i',str(voice)]);filters.append(f'[{i+15}:a]adelay={i*250}|{i*250}[v{i}]');voices.append(f'[v{i}]')
 graph=build.duck_filtergraph(filters,voices,reviewed_bed=';'.join(chains)+';')
 assert 'asetpts=N/SR/TB[out]' in graph and 'apad' not in graph
 output=tmp_path/'mixed.m4a';subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',graph,'-map','[out]','-c:a','aac','-ar','48000',str(output)],check=True)
 length=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(output)]));assert 4.0<length<4.2
