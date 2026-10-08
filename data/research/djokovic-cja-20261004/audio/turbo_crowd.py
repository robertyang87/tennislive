import argparse,hashlib,json,subprocess,tempfile,wave,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from faster_whisper import WhisperModel
p=Path(__file__).parent;source=Path('/workspace/djokovic-cja-research/source/cjaHThpISKk.mp4')
WINDOWS=[('turbo-crowd-250',248,257),('turbo-crowd-261',259,266.4),('turbo-crowd-oh',244,249)]
a=argparse.ArgumentParser();a.add_argument('--model',required=True);args=a.parse_args();model=WhisperModel('/workspace/eala-research/asr-models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf',device='cpu',compute_type='int8',cpu_threads=4,download_root='/workspace/eala-research/asr-models',local_files_only=True)
sha=hashlib.sha256(source.read_bytes()).hexdigest()
for key,start,end in WINDOWS:
 begin=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='djokovic-asr-') as temp:
  f=Path(temp)/'audio.wav';subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(f)],check=True)
  with wave.open(str(f),'rb') as w:samples=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768.
  segments,info=model.transcribe(samples,language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
  rows=[]
  for s in segments:rows.append({'start':round(s.start+start,3),'end':round(s.end+start,3),'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':round(w.start+start,3),'end':round(w.end+start,3),'word':w.word,'probability':w.probability} for w in s.words or []]})
  out={'schema':'tennislive.raw-asr-evidence.v1','source_url':'https://www.youtube.com/watch?v=cjaHThpISKk','source_path':str(source),'source_sha256':sha,'model':args.model,'device':'cpu','compute_type':'int8','vad_filter':False,'word_timestamps':True,'condition_on_previous_text':False,'requested_language':'en','language_why':'Independent fullsource auto-language passes both detected English 0.991/0.942 probability. This is a targeted pass after detection, not an initial assumption.','range_from':start,'range_to':end,'created_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-begin,2),'review_status':'raw_asr_only_not_certified','segments':rows}
  (p/'raw'/f'target-{key}-{args.model}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(args.model,key,[(r['start'],r['end'],r['text']) for r in rows],flush=True)
