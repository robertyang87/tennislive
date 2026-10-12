import sys,json,pathlib,wave,hashlib,datetime,subprocess
import numpy as np
from faster_whisper import WhisperModel
source=pathlib.Path(sys.argv[1]); model_name=sys.argv[2]; target=pathlib.Path(sys.argv[3]); target.parent.mkdir(parents=True,exist_ok=True)
source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
m=WhisperModel(model_name,device='cpu',compute_type='int8',cpu_threads=3,local_files_only=True)
samples=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-map','0:a:0','-ac','1','-ar','16000','-f','f32le','-']),dtype=np.float32)
segments, info=m.transcribe(samples,language='en',vad_filter=True,beam_size=5,word_timestamps=True,condition_on_previous_text=False)
rows=[]
for s in segments:
 row=dict(start=s.start,end=s.end,text=s.text,no_speech_prob=s.no_speech_prob,avg_logprob=s.avg_logprob,words=[dict(start=w.start,end=w.end,word=w.word,probability=w.probability) for w in s.words]);rows.append(row)
 print(f'{s.start:.2f}–{s.end:.2f} {s.text}',flush=True)
 target.write_text(json.dumps(dict(schema='actual-local-asr.v1',model=model_name,faster_whisper_version='1.2.1',device='cpu',compute_type='int8',language='en',vad_filter=True,beam_size=5,word_timestamps=True,condition_on_previous_text=False,source_path=str(source),source_sha256=source_sha,recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),human_listening_claimed=False,run_status='actual_prefix_checkpoint',segments=rows),ensure_ascii=False,indent=2))
d=json.loads(target.read_text());d['run_status']='complete';d['max_transcribed_end']=max((x['end'] for x in rows),default=0);target.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('COMPLETE',flush=True)
