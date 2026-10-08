from pathlib import Path
from dataclasses import asdict
import hashlib,json,time,gc,importlib.metadata,subprocess
import numpy as np
from faster_whisper import WhisperModel
ROOT=Path('/workspace/scratch/zheng-bouzkova')
source=ROOT/'wta-brightcove-720p.mp4'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1']),dtype=np.float32).copy()
for name in ['base.en','small.en']:
 dest=ROOT/f'asr-720p-{name}.json'
 started=time.time()
 print(f'Loading {name}',flush=True)
 model=WhisperModel(name,device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(ROOT/'asr-models'))
 loaded=time.time()
 segments,info=model.transcribe(audio,language='en',beam_size=5,word_timestamps=True,vad_filter=True,condition_on_previous_text=False)
 results=[]
 for seg in segments:
  results.append(asdict(seg))
  print(f'{name} {seg.start:.2f}-{seg.end:.2f}: {seg.text}',flush=True)
 words=[w for seg in results for w in (seg.get('words') or [])]
 result={'source':str(source),'source_sha256':source_hash,'source_duration':info.duration,'model':name,'engine':'faster-whisper','engine_version':importlib.metadata.version('faster-whisper'),'device':'cpu','compute_type':'int8','cpu_threads':4,'beam_size':5,'word_timestamps':True,'vad_filter':True,'condition_on_previous_text':False,'language':info.language,'language_probability':info.language_probability,'duration_after_vad':info.duration_after_vad,'load_seconds':loaded-started,'transcribe_seconds':time.time()-loaded,'segments':results,'words':words,'review_method':'actual model inference; no human listening review claimed'}
 dest.write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(f'Saved {dest}: {len(results)} segments {len(words)} words',flush=True)
 del model;gc.collect()
