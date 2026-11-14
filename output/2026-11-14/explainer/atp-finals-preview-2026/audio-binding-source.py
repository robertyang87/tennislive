from pathlib import Path
import subprocess,json,hashlib
import numpy as np
from scipy.signal import correlate
O=Path('/workspace/atp-finals-2026');R=Path('/workspace/tennislive-sparse');D=R/'output/2026-11-14/explainer/atp-finals-preview-2026'
def decode(p):return np.frombuffer(subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(p),'-f','f32le','-ar','16000','-ac','1','pipe:1']),dtype='<f4')
film=O/'atp-finals-preview-2026.mp4';pcm=decode(film);t=json.loads((O/'final-timeline.json').read_text());rows=[]
for i,m in enumerate(t[1:-1]):
 ref=decode(O/f'voice_{i:02d}.mp3');start=m['start']+.65;lo=round((start-.12)*16000);hi=round((start+.12)*16000)+len(ref);x=pcm[lo:hi];score=correlate(x,ref,mode='valid',method='fft');k=int(np.argmax(score));actual=x[k:k+len(ref)];rho=float(np.dot(actual,ref)/(np.linalg.norm(actual)*np.linalg.norm(ref)));shift=(lo+k)/16000-start
 rows.append({'index':i,'start':start,'measured_offset_s':round(shift,6),'correlation':round(rho,6),'pass':rho>.97 and abs(shift)<.08})
ref=decode(R/'assets/brand/outro_story.mp4');start=t[-1]['start'];lo=round((start-.12)*16000);x=pcm[lo:];ref=ref[:int(3.9*16000)];score=correlate(x,ref,mode='valid',method='fft');k=int(np.argmax(score));a=x[k:k+len(ref)];rho=float(np.dot(a,ref)/(np.linalg.norm(a)*np.linalg.norm(ref)));rows.append({'index':'brand_outro','correlation':round(rho,6),'measured_offset_s':round((lo+k)/16000-start,6),'pass':rho>.97})
e={'schema':'tennislive.actual-audio-binding.v1','method':'independent decoded final PCM versus all exact input MP3s and frozen brand source; normalized waveform correlation; full utterances, no ASR prompt matching','film_sha256':hashlib.sha256(film.read_bytes()).hexdigest(),'all_pass':all(x['pass'] for x in rows),'entries':rows}
(D/'actual-audio-binding.json').write_text(json.dumps(e,ensure_ascii=False,indent=2));print(json.dumps(e,ensure_ascii=False,indent=2));assert e['all_pass']
