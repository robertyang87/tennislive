from pathlib import Path
from dataclasses import asdict
import hashlib,json,time,gc,subprocess,sys
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.vad import get_speech_timestamps,VadOptions
ROOT=Path('/workspace/scratch/zheng-bouzkova'); source=Path(sys.argv[1]); prefix=sys.argv[2]
audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1']),dtype=np.float32).copy()
islands=get_speech_timestamps(audio,VadOptions(min_silence_duration_ms=1000,speech_pad_ms=450))
(ROOT/f'asr-{prefix}-vad-islands.json').write_text(json.dumps([{'start':s['start']/16000,'end':s['end']/16000} for s in islands],indent=2))
for name in ['base.en','small.en']:
 model=WhisperModel(name,device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(ROOT/'asr-models'))
 started=time.time();results=[]
 for index,chunk in enumerate(islands):
  start,end=chunk['start'],chunk['end'];offset=start/16000
  segments,info=model.transcribe(audio[start:end],language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
  for seg in segments:
   d=asdict(seg);d['start']+=offset;d['end']+=offset;d['island']=index
   for word in d.get('words') or []:word['start']+=offset;word['end']+=offset
   results.append(d);print(name,index,f"{d['start']:.2f}-{d['end']:.2f}",d['text'],flush=True)
 payload={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_duration':len(audio)/16000,'model':name,'engine':'faster-whisper','device':'cpu','compute_type':'int8','cpu_threads':4,'beam_size':5,'method':'Each actual Silero VAD speech island independently decoded, no concatenation; source timestamp offset restored; no human listening claimed','vad_options':{'min_silence_duration_ms':1000,'speech_pad_ms':450},'segments':results,'words':[w for s in results for w in s.get('words') or []],'seconds':time.time()-started}
 print(f'Completed {name}: {len(results)} segments in {time.time()-started:.1f}s',flush=True)
 (ROOT/f'asr-{prefix}-islands-{name}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2));del model;gc.collect()
