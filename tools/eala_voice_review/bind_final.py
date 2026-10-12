import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
import numpy as np
from scipy.signal import correlate,correlation_lags
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src')]
from tennislive.video import tts
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
OUT=Path(os.environ['EALA_VOICE_REVIEW_DIR'])
specpath=Path(sys.argv[1]);outdir=Path(sys.argv[2]);expected_film_sha=sys.argv[3];spec=json.loads(specpath.read_text());render=json.loads((outdir/'render.json').read_text());film=outdir/f"{spec['slug']}.mp4"
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pcm(p):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar','16000','-f','f32le','-']),dtype=np.float32).copy()
film_pcm=pcm(film);offset=float(render['cover_seconds']);items=[]
if isinstance(spec.get('cover'),dict) and spec['cover'].get('narration'):items.append(('封面',spec['cover']['narration'],outdir/'voice_cover.mp3',0,{}))
for i,s in enumerate(spec['segments']):
 if s.get('narration'):items.append((f'第 {i+1} 段',s['narration'],outdir/f'voice_{i:02}.mp3',int(offset*1000)/1000,s.get('voice')or{}))
 offset+=float(s['seconds'])if'seconds'in s else float(s['end'])-float(s['start'])
if spec.get('outro',True):items.append(('片尾',NARRATION,outdir/'voice_outro.mp3',int(offset*1000)/1000,{}))
rows=[]
for label,text,p,at,v in items:
 spoken=speakable(text);voice=render['narration_voice'];rate=v.get('rate')or render['narration_rate'];pitch=v.get('pitch')or'+0Hz';style=v.get('style')or'';degree=v.get('styledegree')or'';lead=float(v.get('lead_pause')or 0)
 key=tts.tts_content_key(spoken,voice,rate,pitch,style,degree,lead);cache=Path(os.environ.get('TENNISLIVE_TTS_CACHE',str(Path.home()/'.cache/tennislive-tts')))/f'{key}-edge-v2.zip'
 with zipfile.ZipFile(cache)as z:audio=z.read('audio.mp3');marksraw=z.read('marks.json');marks=json.loads(marksraw)
 assert p.read_bytes()==audio,f'Actual audio differs from native cache for {label}'
 snapshot=OUT/'actual-tts'/p.name;snapshot.parent.mkdir(exist_ok=True);snapshot.write_bytes(audio);m=snapshot.with_suffix('.marks.json');m.write_text(json.dumps(marks,ensure_ascii=False,indent=2)+'\n')
 x=pcm(p);start=round(at*16000);n=min(len(x),len(film_pcm)-start);x=x[:n];y=film_pcm[start:start+n]
 cc=correlate(y,x,mode='full',method='fft');lags=correlation_lags(len(y),len(x),mode='full');mask=np.abs(lags)<=960;lag=int(lags[mask][np.argmax(cc[mask])])
 if lag>=0:a=x[:n-lag];b=y[lag:]
 else:a=x[-lag:];b=y[:n+lag]
 voiced=np.abs(a)>.015*np.max(np.abs(a));a=a[voiced];b=b[voiced];r=float(np.corrcoef(a,b)[0,1]);gain=float(np.dot(a,b)/np.dot(a,a));res=float(np.sqrt(np.mean((b-gain*a)**2))/np.sqrt(np.mean((gain*a)**2)))
 words=p.with_suffix('.words.json');exactmarks=words.is_file()and words.read_bytes()==marksraw
 rows.append({'index':int(p.stem.split('_')[1]) if p.stem.startswith('voice_') and p.stem!='voice_cover' else None,'label':label,'display_text':text,'text':spoken,'voice':voice,'rate':rate,'pitch':pitch,'cache_key':key,'production_cache_path':str(cache),'actual_voice_path':str(p),'actual_mp3_sha256':sha(p),'actual_pcm16k_sha256':hashlib.sha256(pcm(p).tobytes()).hexdigest(),'production_cache_audio_identical':True,'actual_word_marks_exact_cache':exactmarks,'bound_snapshot_path':str(snapshot),'marks_snapshot_path':str(m),'mp3_duration_seconds':len(pcm(p))/16000,'timeline_offset_s':at,'mix_lag_ms':lag/16,'mix_pearson_r':r,'mix_fitted_gain':gain,'mix_relative_residual':res,'mixed_waveform_binding':'strong_match'if r>.98 and res<.2 else'unconfirmed'})
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=sample_rate,channels,channel_layout,codec_name','-of','json',str(film)]))['streams'][0]
fullpcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(film),'-map','0:a:0','-ac',str(info['channels']),'-ar',info['sample_rate'],'-f','f32le','-'])
report={'status':'actual_cache_and_final_mix_binding_only_not_pronunciation_pass','spec_sha256':sha(specpath),'render_json_sha256':sha(outdir/'render.json'),'film_sha256':sha(film),'film_bytes':film.stat().st_size,'native_full_mix_pcm':{'sha256':hashlib.sha256(fullpcm).hexdigest(),'bytes':len(fullpcm),'sample_format':'f32le','audio_stream':info},'bindings':rows,'all_mixed_waveforms_strong_match':all(x['mixed_waveform_binding']=='strong_match'for x in rows),'all_production_word_marks_match':all(x['actual_word_marks_exact_cache']for x in rows),'method':'Exact native ZIP audio bytes and paired marks; independently reconstructed adelay offsets from spec and render cover; AAC mono16k waveform correlation with max60ms codec shift and fitted gain/residual. MP3 hash cannot equal encoded AAC hash.'}
(OUT/'final-actual-bindings.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'film_sha256':report['film_sha256'],'count':len(rows),'all_mixed_waveforms_strong_match':report['all_mixed_waveforms_strong_match'],'all_production_word_marks_match':report['all_production_word_marks_match'],'mix':[{k:r[k]for k in['label','mix_pearson_r','mix_relative_residual','mixed_waveform_binding']}for r in rows]},ensure_ascii=False,indent=2))
