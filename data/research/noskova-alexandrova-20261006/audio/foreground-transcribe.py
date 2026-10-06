import json,wave,time,numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
root=Path(__file__).parent
s=json.load(open('/workspace/tennislive/specs/reels/noskova-alexandrova.json'))
with wave.open(str(root/'source.wav')) as w:audio=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768.
for name in ['medium.en','large-v3']:
 m=WhisperModel(name,device='cpu',compute_type='int8',cpu_threads=4,download_root='/workspace/scratch/noskova-asr-models');rows=[]
 for i,r in enumerate(s['segments']):
  if 'source' not in r:continue
  a,b=r['start'],r['end'];a=161.9 if i==8 else a;ss,info=m.transcribe(audio[int(a*16000):int(b*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=True,condition_on_previous_text=False)
  row={'index':i,'from':a,'to':b,'vad_duration':info.duration_after_vad,'segments':[{'start':float(z.start+a),'end':float(z.end+a),'text':z.text.strip(),'avg_logprob':z.avg_logprob,'words':[{'start':float(w.start+a),'end':float(w.end+a),'word':w.word,'probability':float(w.probability)} for w in z.words]} for z in ss]};rows.append(row);print(name,i,row,flush=True)
  (root/f'foreground-fullwindows-{name}.json').write_text(json.dumps({'model':name,'method':'actual exact selected source windows, VAD, beam5, no previous context','rows':rows},ensure_ascii=False,indent=2))
