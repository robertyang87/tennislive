import json,sys,time,wave
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
root=Path('/workspace/scratch/lgrd3-audio')
model_name=sys.argv[1] if len(sys.argv)>1 else 'small.en'
with wave.open(str(root/'source.wav')) as wf:
    audio=np.frombuffer(wf.readframes(wf.getnframes()),np.int16).astype(np.float32)/32768.
model_path=str(root/'models'/'medium.en') if model_name=='medium.en' else model_name
model=WhisperModel(model_path,device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(root/'models'))
windows=[(0,23),(23,33),(40,48),(87,97),(120,128),(129,137),(160,168),(190,200),(217,222),(227,235),(234,245),(255,263),(266,273),(308,316),(334,340),(342,350),(351,357),(355.5,367),(368,381),(380,389.979)]
if model_name=='medium.en':
    windows=[(355.5,367),(368,381),(23,33),(129,137),(308,316),(334,340),(342,350),(351,357),(87,97),(190,200),(255,263),(227,235),(120,128),(40,48),(160,168),(217,222),(266,273),(234,245)]
rows=[]
for start,end in windows:
    segs,info=model.transcribe(audio[int(start*16000):int(end*16000)],language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
    window={'from':start,'to':end,'segments':[]}
    for s in segs:
        row={'start':round(s.start+start,3),'end':round(s.end+start,3),'text':s.text.strip(),'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':round(w.start+start,3),'end':round(w.end+start,3),'word':w.word,'probability':w.probability} for w in s.words]}
        window['segments'].append(row)
    rows.append(window)
    print(json.dumps(window),flush=True)
    (root/f'asr-windows-{model_name}.json').write_text(json.dumps({'model':model_name,'method':'faster-whisper int8 CPU, language=en, beam_size=5, word_timestamps=True, vad_filter=False, condition_on_previous_text=False; windows use original source absolute timestamps','windows':rows},ensure_ascii=False,indent=2)+'\n')
print('COMPLETE',flush=True)
