import json,pathlib,subprocess,time,sys,hashlib
import numpy as np,soundfile as sf
from faster_whisper import WhisperModel
root=pathlib.Path('/workspace/scratch'); mode=sys.argv[1]
m=WhisperModel(mode,device='cpu',compute_type='int8',cpu_threads=2)
spec=json.loads((root/'rna10-selected-spec.json').read_text());ids=json.loads((root/'rna10-sources.json').read_text());rows=[]
for n in range(1,8):
 p=root/'rna10-effects'/f's{n}.wav'
 while not p.exists():time.sleep(3)
 # writer exports wav then processing digest; require completed record
 while True:
  try:
   proc=json.loads((p.parent/'processing.json').read_text());meta=next(x for x in proc if x['source']==f's{n}');break
  except (FileNotFoundError,StopIteration,json.JSONDecodeError):time.sleep(3)
 ranges=sorted(set((s['start'],s['end']) for s in spec['segments'] if s['source']==f's{n}'))
 for a,b in ranges:
  windows=[(a,b)]
  if n==1:
   windows=[]
   if a<132.4:windows.append((a,min(b,132.4)))
   if b>145.7:windows.append((max(a,145.7),b))
  for a,b in windows:
   if b<=a:continue
   w=root/f'effect-check-{n}-{a}.wav'
   subprocess.run(['ffmpeg','-v','error','-y','-ss',str(a),'-i',str(p),'-t',str(b-a),'-ar','16000','-ac','1',str(w)],check=True)
   seg,info=m.transcribe(str(w),beam_size=5,vad_filter=True,condition_on_previous_text=False,word_timestamps=True)
   row={'source':f's{n}','start':a,'end':b,'model':mode,'effects_sha256':meta['effects_sha256'],'language':info.language,'language_probability':info.language_probability,'segments':[{'start':s.start+a,'end':s.end+a,'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':x.start+a,'end':x.end+a,'word':x.word,'probability':x.probability} for x in s.words]} for s in seg]}
   rows.append(row);(root/f'rna10-effects-{mode}-asr.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(row,ensure_ascii=False),flush=True)
