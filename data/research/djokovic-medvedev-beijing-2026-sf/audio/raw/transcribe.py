import json, sys, time, wave
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel

root = Path('/workspace/scratch/lgrd3-audio')
model_name = sys.argv[1] if len(sys.argv) > 1 else 'small.en'
t0=time.time()
model=WhisperModel(model_name,device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(root/'models'))
print('MODEL READY',model_name,flush=True)
with wave.open(str(root/'source.wav')) as wf:
    audio=np.frombuffer(wf.readframes(wf.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
segments,info=model.transcribe(audio,language='en',beam_size=5,word_timestamps=True,vad_filter=True,condition_on_previous_text=False)
rows=[]
for s in segments:
    row={'start':s.start,'end':s.end,'text':s.text.strip(),'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words]}
    rows.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    (root/f'asr-{model_name}.json').write_text(json.dumps({'model':model_name,'method':'faster-whisper int8 CPU, language=en, beam_size=5, word_timestamps=True, vad_filter=True, condition_on_previous_text=False','duration':info.duration,'duration_after_vad':info.duration_after_vad,'elapsed_s':time.time()-t0,'segments':rows},ensure_ascii=False,indent=2)+'\n')
print('COMPLETE',time.time()-t0,flush=True)
