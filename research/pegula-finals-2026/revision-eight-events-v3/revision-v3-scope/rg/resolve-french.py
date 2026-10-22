from pathlib import Path
from faster_whisper import WhisperModel,decode_audio
import json,gc
r=Path('/workspace/pegula-finals-production/revision-v3-scope/rg');src=r/'rg-r1-hoh-08EHKHtS6hg.mp4';a=decode_audio(str(src),sampling_rate=16000)
for mn in ['small','large-v3','large-v3-turbo']:
 m=WhisperModel(mn,device='cpu',compute_type='int8',cpu_threads=6)
 for st,en,tag in [(705.5,715,'complete-pa'),(708.0,711.4,'opening-only')]:
  ss,ii=m.transcribe(a[int(st*16000):int(en*16000)],language='fr',initial_prompt='Jessica Pegula. Kimberly Birrell. Roland-Garros.',word_timestamps=True,beam_size=5,condition_on_previous_text=False,vad_filter=False)
  out=[]
  for s in ss:out.append({'start':round(s.start+st,3),'end':round(s.end+st,3),'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'w':w.word,'start':round(w.start+st,3),'end':round(w.end+st,3),'p':round(w.probability,3)}for w in s.words]})
  d={'model':mn,'language':'fr','clip':[st,en],'source_sha256':'d4a53903e603dc459f0d49b2bad23a5876a66afd80758e392a6faa3d281121ca','prompt':'Jessica Pegula. Kimberly Birrell. Roland-Garros.','segments':out}
  (r/f'french-{tag}-{mn}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print(mn,tag,json.dumps(out,ensure_ascii=False),flush=True)
 del m;gc.collect()
