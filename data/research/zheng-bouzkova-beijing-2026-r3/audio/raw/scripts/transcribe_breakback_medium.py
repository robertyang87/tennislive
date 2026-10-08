from pathlib import Path
from dataclasses import asdict
import json,subprocess,time
import numpy as np
from faster_whisper import WhisperModel
R=Path('/workspace/scratch/zheng-bouzkova');src=R/'main-source/source.mp4'
a=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(src),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1']),dtype=np.float32).copy()
model=WhisperModel('medium.en',device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(R/'asr-models'))
results=[]
for window in [{'edit_id':'breakback_review','start':128,'end':138}]:
 start=max(0,window['start']-2);end=min(len(a)/16000,window['end']+2)
 ss,info=model.transcribe(a[round(start*16000):round(end*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
 segments=[]
 for s in ss:
  d=asdict(s);d['start']+=start;d['end']+=start
  for w in d.get('words') or []:w['start']+=start;w['end']+=start
  segments.append(d);print(window['edit_id'],f"{d['start']:.2f}–{d['end']:.2f}",d['text'],flush=True)
 results.append({'window':window,'decoded_start':start,'decoded_end':end,'segments':segments})
 (R/'asr-breakback-medium.en.json').write_text(json.dumps({'model':'medium.en','vad_filter':False,'word_timestamps':True,'source_sha256':'71228364152bda28488fd6918e6e2e7b58e493d6c75ba5b44485e4695aa81941','windows':results},ensure_ascii=False,indent=2))
