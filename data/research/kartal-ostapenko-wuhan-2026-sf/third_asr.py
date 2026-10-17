from faster_whisper import WhisperModel
import json,time
from pathlib import Path
m=WhisperModel('large-v3-turbo',device='cpu',compute_type='int8',cpu_threads=8)
r=[]
for a,b in [(65,105),(115,170),(208,257)]:
 segs,info=m.transcribe(__import__('numpy').frombuffer(Path('/workspace/research-kartal/source.wav').read_bytes()[78:],dtype='int16').astype('float32')/32768,language='en',beam_size=5,word_timestamps=True,clip_timestamps=[a,b],condition_on_previous_text=False,vad_filter=False)
 for s in segs:
  q={'start':s.start,'end':s.end,'text':s.text,'words':[{'w':w.word,'s':w.start,'e':w.end,'p':w.probability}for w in s.words]};r.append(q);print(json.dumps(q),flush=True)
 Path('/workspace/research-kartal/large-v3-turbo.json').write_text(json.dumps(r,indent=2))
