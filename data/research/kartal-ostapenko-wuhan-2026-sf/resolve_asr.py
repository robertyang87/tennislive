import numpy as np,json,wave
from faster_whisper import WhisperModel
p='/workspace/research-kartal/source.wav'
with wave.open(p) as f:audio=np.frombuffer(f.readframes(f.getnframes()),dtype='int16').astype('float32')/32768
m=WhisperModel('large-v3-turbo',device='cpu',compute_type='int8',cpu_threads=8)
out=[]
for a,b in [(128,134),(129,136),(146,151),(238,245),(220,226)]:
 ss,_=m.transcribe(audio[int(a*16000):int(b*16000)],language='en',beam_size=5,word_timestamps=True,condition_on_previous_text=False,vad_filter=False)
 for s in ss:
  j={'window':[a,b],'start':a+s.start,'end':a+s.end,'text':s.text,'words':[{'w':w.word,'s':a+w.start,'e':a+w.end,'p':w.probability}for w in s.words]};out.append(j);print(json.dumps(j),flush=True)
open('/workspace/research-kartal/resolve-asr.json','w').write(json.dumps(out,indent=2))
