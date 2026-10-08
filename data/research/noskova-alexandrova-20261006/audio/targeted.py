import wave,json,numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
root=Path(__file__).parent
with wave.open(str(root/'source.wav')) as w:audio=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768.
m=WhisperModel('medium.en',device='cpu',compute_type='int8',cpu_threads=4,download_root=str(root/'models'))
rows=[]
for a,b in [(12,19.72),(56.4,73.92),(80,87),(168,174.84),(179,195.4),(215,221),(276,299.08)]:
 ss,inf=m.transcribe(audio[int(a*16000):int(b*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
 row={'start':a,'end':b,'segments':[{'start':s.start+a,'end':s.end+a,'text':s.text,'words':[{'start':w.start+a,'end':w.end+a,'word':w.word,'probability':w.probability} for w in s.words]} for s in ss]};rows.append(row);print(row,flush=True)
 (root/'asr-targeted-medium.en.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
