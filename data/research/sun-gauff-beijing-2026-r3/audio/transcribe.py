import json,sys,time,hashlib,subprocess,numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
model_name=sys.argv[1]
root=Path('/workspace/tennislive/data/research/sun-gauff-beijing-2026-r3/audio')
source=Path('/workspace/scratch/sun-gauff/Wg6m85wS3Ps.mp4')
t0=time.time()
print('Loading',model_name,flush=True)
model=WhisperModel(model_name,device='cpu',compute_type='int8',cpu_threads=4,download_root='/workspace/scratch/sun-gauff/asr-models')
print('Transcribing',model_name,flush=True)
audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-f','f32le','-ac','1','-ar','16000','-']),dtype=np.float32)
segments,info=model.transcribe(audio,language='en',word_timestamps=True,beam_size=5,vad_filter=True,condition_on_previous_text=False)
rows=[]
for segment in segments:
    row={'start':segment.start,'end':segment.end,'text':segment.text,'avg_logprob':segment.avg_logprob,'no_speech_prob':segment.no_speech_prob,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in segment.words]}
    rows.append(row)
    print(f'{segment.start:.2f} {segment.end:.2f} {segment.text}',flush=True)
packet={'model':model_name,'source_path':str(source),'source_sha256':hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),'elapsed_seconds':time.time()-t0,'language':info.language,'language_probability':info.language_probability,'duration':info.duration,'duration_after_vad':info.duration_after_vad,'segments':rows}
(root/f'{model_name}-full.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
print('DONE',model_name,time.time()-t0,flush=True)
