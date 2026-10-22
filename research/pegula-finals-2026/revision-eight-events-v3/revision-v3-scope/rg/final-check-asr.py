from pathlib import Path
from faster_whisper import WhisperModel,decode_audio
import json,gc
r=Path('/workspace/pegula-finals-production/revision-v3-scope/rg');src=r/'rg-r1-hoh-08EHKHtS6hg.mp4';a=decode_audio(str(src),sampling_rate=16000)
for mn,lang,start,end,label in [('medium.en','en',700.0,708.16,'body-subwindow-medium.en'),('large-v3','fr',693.2,716.0,'body-and-pa-large-v3-fr')]:
 m=WhisperModel(mn,device='cpu',compute_type='int8',cpu_threads=6)
 ss,ii=m.transcribe(a[int(start*16000):int(end*16000)],language=lang,word_timestamps=True,beam_size=5,condition_on_previous_text=False,vad_filter=False)
 out=[]
 for s in ss:out.append({'start':round(s.start+start,3),'end':round(s.end+start,3),'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'w':w.word,'start':round(w.start+start,3),'end':round(w.end+start,3),'p':round(w.probability,3)} for w in s.words]})
 d={'model':mn,'language':lang,'clip':[start,end],'source_sha256':'d4a53903e603dc459f0d49b2bad23a5876a66afd80758e392a6faa3d281121ca','prompt':None,'segments':out}
 (r/(label+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print(label,json.dumps(out,ensure_ascii=False),flush=True);del m;gc.collect()
