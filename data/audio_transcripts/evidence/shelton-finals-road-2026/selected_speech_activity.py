from pathlib import Path
import json,hashlib,datetime
from faster_whisper import decode_audio
from faster_whisper.vad import get_speech_timestamps,VadOptions
R=Path('/workspace/shelton-finals-production/research/audio')
res=[]
for ident,clip in [('sh26ao',[138.0,153.5]),('sh26dallas',[132.0,145.0]),('sh26munich',[158.5,172.4])]:
 p=Path('/dev/shm/shelton-sources')/(ident+'.mp4')
 with p.open('rb') as f:s=hashlib.file_digest(f,'sha256').hexdigest()
 start,end=clip;a=decode_audio(str(p),sampling_rate=16000)[int(start*16000):int(end*16000)]
 rows=[]
 for threshold in [.3,.5,.7]:
  regions=get_speech_timestamps(a,VadOptions(threshold=threshold,min_silence_duration_ms=150,speech_pad_ms=0))
  rows.append({'threshold':threshold,'regions':[[round(start+x['start']/16000,3),round(start+x['end']/16000,3)] for x in regions]})
 res.append({'id':ident,'source_sha256':s,'clip':clip,'activity':rows})
out={'method':'Actual local Silero speech activity support only; not auditory listening, not precise quiet syllable proof, not loudness or gain QC.','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':res}
(R/'early-speech-activity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
