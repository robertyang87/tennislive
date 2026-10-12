import sys,json,pathlib,subprocess,hashlib,datetime
import numpy as np
from faster_whisper import WhisperModel
source=pathlib.Path(sys.argv[1]);name=sys.argv[2];output=pathlib.Path(sys.argv[3]);ranges=json.loads(sys.argv[4]);rows=[];results=[]
samples=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-map','0:a:0','-ac','1','-ar','16000','-f','f32le','-']),dtype=np.float32)
m=WhisperModel(name,device='cpu',compute_type='int8',cpu_threads=3,local_files_only=True)
d=dict(schema='actual-local-targeted-asr.v1',source_path=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),model=name,device='cpu',compute_type='int8',normalization='none; original amplitude',vad_filter=False,beam_size=5,word_timestamps=True,condition_on_previous_text=False,initial_prompt=None,human_listening_claimed=False,windows=ranges,window_results=results,segments=rows,run_status='running')
for a,b in ranges:
 segs,info=m.transcribe(samples[int(a*16000):int(b*16000)],language='en',vad_filter=False,beam_size=5,word_timestamps=True,condition_on_previous_text=False)
 current=[]
 for s in segs:
  row=dict(window=[a,b],start=a+s.start,end=a+s.end,text=s.text,no_speech_prob=s.no_speech_prob,avg_logprob=s.avg_logprob,words=[dict(start=a+w.start,end=a+w.end,word=w.word,probability=w.probability) for w in s.words]);current.append(row);rows.append(row);print(f'{a+s.start:.2f}–{a+s.end:.2f} {s.text}',flush=True)
 results.append(dict(window=[a,b],duration=info.duration,utterance_count=len(current),status='actual_decode_complete'))
 d['recorded_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();output.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('WINDOW COMPLETE',a,b,flush=True)
d['run_status']='complete';output.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('COMPLETE',flush=True)
