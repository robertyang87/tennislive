from pathlib import Path
import json,subprocess,hashlib,sys
import numpy as np
from scipy.signal import correlate

O=Path('/workspace/davis-cup-preview-2026'); V=O/'audio-fix'; RATE=48000
def decode(p):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(p),'-ar',str(RATE),'-ac','2','-f','f32le','pipe:1']),dtype='<f4').reshape(-1,2)

film=Path(sys.argv[1]); output=Path(sys.argv[2]); actual=decode(film)
timeline=json.loads((O/'final-timeline.json').read_text())
sources=[(i,O/f'voice_{i:02d}.mp3',round((m['start']+.65)*1000)/1000) for i,m in enumerate(timeline[1:-1])]
sources.append(('brand_outro',O/'brand/outro.mp4',round(timeline[-1]['start']*1000)/1000))
expected=np.zeros_like(actual); entries=[]; windows=[]
for name,path,start in sources:
    ref=decode(path); offset=round(start*RATE); end=min(len(actual),offset+len(ref)); expected[offset:end]+=ref[:end-offset]; windows.append((start,start+len(ref)/RATE))
    lo=max(0,offset-round(.08*RATE)); hi=min(len(actual),offset+len(ref)+round(.08*RATE)); block=actual[lo:hi]; channels=[]
    # Brand ends close to the movie end; use the complete audible phrase
    # through3.9s, beyond the final voiced syllable, for offset measurement.
    target=ref[:min(len(ref),round(3.9*RATE))] if name=='brand_outro' else ref
    for c in range(2):
        corr=correlate(block[:,c],target[:,c],mode='valid',method='fft'); k=int(np.argmax(corr)); sample=block[k:k+len(target),c]
        rho=float(np.dot(sample,target[:,c])/(np.linalg.norm(sample)*np.linalg.norm(target[:,c]))); shift=(lo+k)/RATE-start
        channels.append({'channel':c,'correlation':round(rho,6),'offset_s':round(shift,6),'pass':rho>.97 and abs(shift)<.04})
    entries.append({'index':name,'start':start,'channels':channels,'pass':all(x['pass'] for x in channels)})

cover=actual[:round(1.7*RATE)]; cover_peaks=np.max(np.abs(cover),axis=0)
intro_silent=bool(np.all(cover_peaks<.0001))
relative_errors=[]
envelope_errors=[]
block_size=RATE//50  # 20ms on the exact48kHz output sample clock.
block_count=len(actual)//block_size
for c in range(2):
    relative_errors.append(float(np.linalg.norm(actual[:,c]-expected[:,c])/np.linalg.norm(expected[:,c])))
    got=np.sqrt(np.mean(actual[:block_count*block_size,c].reshape(-1,block_size)**2,axis=1))
    want=np.sqrt(np.mean(expected[:block_count*block_size,c].reshape(-1,block_size)**2,axis=1))
    envelope_errors.append(float(np.linalg.norm(got-want)/np.linalg.norm(want)))
# AAC changes high-frequency phase even when speech is unaltered. Use20ms
# energy envelopes for absence/extra-copy checking; waveform correlation
# above independently checks each complete utterance in each output channel.
# Raw waveform differences remain visible diagnostics, not a PCM-equality claim.
reconstruction_ok=bool(max(envelope_errors)<.04)
gaps=[windows[i+1][0]-windows[i][1] for i in range(len(windows)-1)]
no_overlap=min(gaps)>.15
result={'schema':'tennislive.actual-audio-binding.v1','method':'Independent two-channel final-PCM audit against every exact frozen input placed at its intended time. Full-film20ms RMS-envelope reconstruction rejects additional speech copies outside intended placement; complete-utterance waveform correlation checks both channels separately; no human listening claimed.','film_sha256':hashlib.sha256(film.read_bytes()).hexdigest(),'entries':entries,'cover_silence':{'until_s':1.7,'peak_per_channel':cover_peaks.tolist(),'pass':intro_silent},'complete_mix_reconstruction':{'sample_rate':RATE,'rms_window_ms':20,'rms_envelope_relative_error_per_channel':envelope_errors,'max_rms_envelope_relative_error':.04,'raw_waveform_relative_error_diagnostic':relative_errors,'pass':reconstruction_ok},'scheduled_speech_gaps':{'minimum_s':min(gaps),'all_gaps_s':gaps,'pass':no_overlap},'all_pass':all(e['pass'] for e in entries) and intro_silent and reconstruction_ok and no_overlap}
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='entries'},ensure_ascii=False,indent=2),flush=True)
if '--expect-fail' in sys.argv:assert result['all_pass'] is False and intro_silent is False
else:assert result['all_pass'], 'Actual stereo final-film mix did not pass'
