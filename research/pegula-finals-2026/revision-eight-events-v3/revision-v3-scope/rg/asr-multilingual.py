from pathlib import Path
from faster_whisper import WhisperModel,decode_audio
import json,hashlib,gc
r=Path('/workspace/pegula-finals-production/revision-v3-scope/rg');src=r/'rg-r1-hoh-08EHKHtS6hg.mp4';a=decode_audio(str(src),sampling_rate=16000)[int(696*16000):int(721.37*16000)]
for mn in ['small','large-v3-turbo']:
 m=WhisperModel(mn,device='cpu',compute_type='int8',cpu_threads=4)
 ss,ii=m.transcribe(a,word_timestamps=True,beam_size=5,condition_on_previous_text=False,vad_filter=False)
 out=[]
 for s in ss:out.append({'start':round(s.start+696,2),'end':round(s.end+696,2),'text':s.text,'words':[{'w':w.word,'s':round(w.start+696,2),'e':round(w.end+696,2),'p':round(w.probability,3)} for w in s.words]})
 d={'model':mn,'language':ii.language,'language_probability':ii.language_probability,'clip':[696,721.37],'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'prompt':None,'segments':out}
 (r/f'hoh-terminal-multilingual-{mn}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print(mn,ii.language,ii.language_probability,json.dumps(out,ensure_ascii=False),flush=True);del m;gc.collect()
