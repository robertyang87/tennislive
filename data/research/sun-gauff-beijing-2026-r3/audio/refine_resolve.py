import json,sys,time,hashlib,subprocess,numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
n=sys.argv[1]; root=Path('/workspace/tennislive/data/research/sun-gauff-beijing-2026-r3/audio');src=Path('/workspace/scratch/sun-gauff/Wg6m85wS3Ps.mp4')
model=WhisperModel(n,device='cpu',compute_type='int8',cpu_threads=4,download_root='/workspace/scratch/sun-gauff/asr-models')
windows=[(128,140),(212,219),(241,250),(101,108),(81,87)]
rows=[]
for a,b in windows:
 audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss',str(a),'-t',str(b-a),'-i',str(src),'-f','f32le','-ac','1','-ar','16000','-']),dtype=np.float32)
 seg,info=model.transcribe(audio,language='en',word_timestamps=True,beam_size=5,vad_filter=False,condition_on_previous_text=False)
 data=[]
 for s in seg:
  row={'start':s.start+a,'end':s.end+a,'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':w.start+a,'end':w.end+a,'word':w.word,'probability':w.probability} for w in s.words]};data.append(row)
  print(n,a,b,f'{s.start+a:.2f} {s.end+a:.2f}',s.text,flush=True)
 rows.append({'reviewed_from':a,'reviewed_to':b,'segments':data})
 (root/f'{n}-resolve.json').write_text(json.dumps({'model':n,'source_sha256':hashlib.file_digest(src.open('rb'),'sha256').hexdigest(),'windows':rows},ensure_ascii=False,indent=2)+'\n')
print('DONE',flush=True)
