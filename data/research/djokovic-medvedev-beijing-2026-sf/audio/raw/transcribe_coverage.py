import json,wave
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
root=Path('/workspace/scratch/lgrd3-audio')
with wave.open(str(root/'source.wav')) as wf:
    audio=np.frombuffer(wf.readframes(wf.getnframes()),np.int16).astype(np.float32)/32768.
model=WhisperModel('small.en',device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,download_root=str(root/'models'))
windows=[(46.28,61.43),(61.43,76.58),(31.74,46.28),(76.58,87),(95.32,120),(135,149),(149,161),(165.88,180),(180,191.68),(199.08,217),(221.2,227),(233.16,245),(245,255),(261.5,273.2),(273.2,289),(289,309),(314.52,334.5),(339.22,344.48),(379.96,389.979)]
rows=[]
for start,end in windows:
    segs,info=model.transcribe(audio[int(start*16000):int(end*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False,no_speech_threshold=.5)
    row={'from':start,'to':end,'segments':[]}
    for s in segs:
        row['segments'].append({'start':round(s.start+start,3),'end':round(s.end+start,3),'text':s.text.strip(),'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':round(w.start+start,3),'end':round(w.end+start,3),'word':w.word,'probability':w.probability} for w in s.words]})
    rows.append(row)
    print(json.dumps(row),flush=True)
    (root/'asr-coverage-small.en.json').write_text(json.dumps({'model':'small.en','method':'faster-whisper; int8 CPU 2threads; beam_size5; no VAD; no_speech_threshold .5; selected-window complement plus whole planned narration window','windows':rows},ensure_ascii=False,indent=2)+'\n')
print('COMPLETE',flush=True)
