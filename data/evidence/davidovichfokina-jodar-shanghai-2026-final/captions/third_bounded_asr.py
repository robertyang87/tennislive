import sys,json,subprocess,time,hashlib
from pathlib import Path
sys.path.insert(0,'/workspace/scratch/asr-tools')
import numpy as np
from faster_whisper import WhisperModel
out=Path('/workspace/scratch/fokina-final-captions')
root=Path('/workspace/scratch/whisper-models')
model_dir=root/'models--Systran--faster-whisper-base.en'
snapshot=model_dir/'snapshots'/(model_dir/'refs/main').read_text().strip()
print('loading local snapshot',snapshot,flush=True)
m=WhisperModel(str(snapshot),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True,download_root=str(model_dir))
windows=[('percentage',47.68,55.04),('set_close',118.66,130.66),('athleticism',191.98,200.22),('at_bay',309.62,316.38),('foot_event',400.50,407.80)]
res=[]
for name,start,end in windows:
 b=subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i','/workspace/scratch/fokina-requested-source/source.mp4','-t',str(end-start),'-ac','1','-ar','16000','-f','f32le','-'],check=True,stdout=subprocess.PIPE).stdout
 audio=np.frombuffer(b,dtype=np.float32)
 segments,info=m.transcribe(audio,language='en',beam_size=5,word_timestamps=True,condition_on_previous_text=False,vad_filter=False,initial_prompt=None)
 rec={'id':name,'source_start':start,'source_end':end,'audio_sha256':hashlib.sha256(b).hexdigest(),'audio_samples':len(audio),'segments':[]}
 for s in segments:
  rec['segments'].append({'start':round(start+s.start,3),'end':round(start+s.end,3),'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'w':w.word,'s':round(start+w.start,3),'e':round(start+w.end,3),'p':w.probability} for w in (s.words or [])]})
 res.append(rec)
 (out/'base.en-bounded-raw.json').write_text(json.dumps({'model':'base.en','snapshot':str(snapshot),'settings':{'device':'cpu','compute_type':'int8','cpu_threads':2,'beam_size':5,'word_timestamps':True,'condition_on_previous_text':False,'vad_filter':False,'initial_prompt':None,'local_files_only':True},'source_sha256':'805bfda10e11ffccc9f1ecc03db4af4661c5ead00d4858d4625c70618737c975','windows':res},ensure_ascii=False,indent=2)+'\n')
 print(name,json.dumps(rec['segments'],ensure_ascii=False),flush=True)
