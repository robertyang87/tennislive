import json,subprocess,hashlib
from pathlib import Path
import numpy as np
O=Path(__import__('os').environ['EALA_VOICE_REVIEW_DIR']);rows=json.loads((O/'native-bindings.json').read_text())['bindings'];parts=[];samples=[];offset=0
for i,b in enumerate(rows):
 p=Path(b['bound_snapshot_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==b['actual_mp3_sha256'];x=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar','16000','-f','f32le','-']),dtype=np.float32);samples.append(x);parts.append({'edit_id':b['edit_id'],'formal_edit_id':b.get('formal_edit_id'),'text':b['text'],'actual_mp3_sha256':b['actual_mp3_sha256'],'native_mp3_path':str(p),'marks_snapshot_path':b['marks_snapshot_path'],'input_audio_start_s':offset/16000,'input_audio_end_s':(offset+len(x))/16000});offset+=len(x)
 if i<len(rows)-1:samples.append(np.zeros(6400,dtype=np.float32));offset+=6400
wav=O/'complete-native-speech.wav';subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','16000','-ac','1','-i','-','-c:a','pcm_s16le',str(wav)],input=np.concatenate(samples).tobytes(),check=True);r={'path':str(wav),'sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),'parts':parts,'method':'Exact complete native MP3 waveforms decoded16kmono; only400ms between sentences. No altered speech, no prompts, no old-period voice, no final-film claim.','human_listening_claimed':False};(O/'complete-speech-asr-input-manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r['sha256'],len(parts),offset/16000)
