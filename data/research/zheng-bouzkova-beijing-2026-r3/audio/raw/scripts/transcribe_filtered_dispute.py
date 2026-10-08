import subprocess,json
from pathlib import Path
from dataclasses import asdict
import numpy as np
from faster_whisper import WhisperModel
r=Path('/workspace/scratch/zheng-bouzkova');source=r/'main-source/source.mp4'
filtergraph='highpass=f=120,lowpass=f=4000,volume=6dB'
a=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss','128','-i',str(source),'-t','10','-vn','-af',filtergraph,'-ac','1','-ar','16000','-f','f32le','pipe:1']),dtype=np.float32).copy()
model=WhisperModel('turbo',device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(r/'asr-models'))
ss,info=model.transcribe(a,language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
result=[]
for s in ss:
 d=asdict(s);d['start']+=128;d['end']+=128
 for w in d['words']:w['start']+=128;w['end']+=128
 result.append(d);print(d['text'],flush=True)
(r/'asr-breakback-filtered-turbo.json').write_text(json.dumps({'model':'large-v3-turbo','filter':filtergraph,'source_start':128,'source_end':138,'source_sha256':'71228364152bda28488fd6918e6e2e7b58e493d6c75ba5b44485e4695aa81941','vad_filter':False,'initial_prompt':None,'segments':result},ensure_ascii=False,indent=2))
