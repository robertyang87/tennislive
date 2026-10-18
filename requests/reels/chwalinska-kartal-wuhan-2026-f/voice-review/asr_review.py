"""Whole actual frozen utterance ASR: content evidence, never tone evidence."""
import argparse,datetime,hashlib,json,subprocess,sys,wave,fcntl
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--model',required=True);a=p.parse_args()
j=json.loads((a.out/'job.json').read_text());wav=a.out/'actual-utterances.wav';scope=a.out/'asr-input-map.json'
prepare_lock=(a.out/'asr-prepare.lock').open('a');fcntl.flock(prepare_lock,fcntl.LOCK_EX)
if not wav.exists():
    arrays=[];offset=0;rows=[]
    for b in j['bindings']:
        path=Path(b['bound_snapshot_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==b['actual_mp3_sha256']
        y=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ar','16000','-ac','1','-f','s16le','-']),dtype=np.int16)
        rows.append(dict(edit_id=b['edit_id'],start=offset/16000,end=(offset+len(y))/16000,text=b['text'],mp3_sha256=b['actual_mp3_sha256']))
        arrays.extend([y,np.zeros(8000,dtype=np.int16)]);offset+=len(y)+8000
    with wave.open(str(wav),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(np.concatenate(arrays).tobytes())
    scope.write_text(json.dumps(dict(source_bundle_sha256=j['bundle_sha256'],wav_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),utterances=rows,human_listening_claimed=False),ensure_ascii=False,indent=2)+'\n')
fcntl.flock(prepare_lock,fcntl.LOCK_UN);prepare_lock.close()
m=WhisperModel(a.model,device='cpu',compute_type='int8',cpu_threads=2)
with wave.open(str(wav),'rb') as w: samples=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
segments,info=m.transcribe(samples,language='zh',word_timestamps=True,vad_filter=False,beam_size=5,condition_on_previous_text=False)
dest=a.out/f'asr-{a.model}.json';rows=[]
for s in segments:
    rows.append(dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,no_speech_prob=s.no_speech_prob,words=[dict(start=w.start,end=w.end,text=w.word,probability=w.probability) for w in s.words or []]))
    data=dict(model=a.model,input_wav_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),bundle_sha256=j['bundle_sha256'],options=dict(language='zh',word_timestamps=True,vad_filter=False,beam_size=5,condition_on_previous_text=False,compute_type='int8',cpu_threads=2),segments=rows,status='partial',human_listening_claimed=False,tone_evidence=False)
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(s.text,flush=True)
data['status']='complete';data['recorded_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
