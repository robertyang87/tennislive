import wave,json,numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
root=Path(__file__).parent
with wave.open(str(root/'source.wav')) as w:audio=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768.
m=WhisperModel('large-v3',device='cpu',compute_type='int8',cpu_threads=4,download_root='/workspace/scratch/noskova-asr-models')
rows=[]
for a,b in [(56.4,62),(67,74),(179,186),(215,220)]:
 ss,inf=m.transcribe(audio[int(a*16000):int(b*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
 row={'start':a,'end':b,'segments':[{'start':s.start+a,'end':s.end+a,'text':s.text,'words':[{'start':w.start+a,'end':w.end+a,'word':w.word,'probability':w.probability} for w in s.words]} for s in ss]};rows.append(row);print(row,flush=True)
 (root/'asr-targeted-large-v3.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
