import json,wave
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
root=Path('/workspace/scratch/lgrd3-audio')
with wave.open(str(root/'source.wav')) as wf:
    audio=np.frombuffer(wf.readframes(wf.getnframes()),np.int16).astype(np.float32)/32768.
model=WhisperModel(str(root/'models'/'medium.en'),device='cpu',compute_type='int8',cpu_threads=4,num_workers=1)
windows=[(149,161),(180,190),(339.22,343.8),(76.58,87),(165.88,180),(273.2,289),(289,309),(314.52,334.5),(379.96,389.979)]
rows=[]
for start,end in windows:
    segs,info=model.transcribe(audio[int(start*16000):int(end*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=True,condition_on_previous_text=False,no_speech_threshold=.5)
    row={'from':start,'to':end,'duration_after_vad':info.duration_after_vad,'segments':[]}
    for s in segs:
        row['segments'].append({'start':round(s.start+start,3),'end':round(s.end+start,3),'text':s.text.strip(),'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':round(w.start+start,3),'end':round(w.end+start,3),'word':w.word,'probability':w.probability} for w in s.words]})
    rows.append(row)
    print(json.dumps(row),flush=True)
    (root/'asr-gaps-medium.en.json').write_text(json.dumps({'model':'medium.en','method':'faster-whisper; int8 CPU 4threads; beam_size5; VAD enabled; no_speech_threshold .5; secondary independent checks of non-commentary decoding hypotheses','windows':rows},ensure_ascii=False,indent=2)+'\n')
print('COMPLETE',flush=True)
