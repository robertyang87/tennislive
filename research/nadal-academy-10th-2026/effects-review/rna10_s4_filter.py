import numpy as np,soundfile as sf,pathlib,hashlib,json
from scipy.signal import butter,sosfilt
r=pathlib.Path('/workspace/scratch/rna10-effects');x,sr=sf.read(r/'s4.wav');y=x.copy();sos=butter(4,2200,btype='highpass',fs=sr,output='sos');regions=[]
for a,b in [(79.7,81.1),(98.7,99.9)]:
 lo=int(a*sr);hi=int(b*sr);pad=int(.1*sr);v=sosfilt(sos,x[max(0,lo-pad):hi])[lo-max(0,lo-pad):];w=np.ones(hi-lo);fade=int(.02*sr);w[:fade]=np.linspace(0,1,fade);w[-fade:]=np.linspace(1,0,fade);y[lo:hi]=x[lo:hi]*(1-w)+v*w
 regions.append({'start':a,'end':b,'rms_before':float(np.sqrt(np.mean(x[lo:hi]**2))),'rms_after':float(np.sqrt(np.mean(y[lo:hi]**2))),'peak_before':float(np.max(np.abs(x[lo:hi]))),'peak_after':float(np.max(np.abs(y[lo:hi]))),'nonzero_samples':int(np.count_nonzero(y[lo:hi]))})
p=r/'s4-v2.wav';sf.write(p,y,sr,subtype='PCM_24');out={'algorithm':'4th-order Butterworth highpass 2200Hz local effects only;20ms linear crossfade to original effects at each edge; no full-frequency mute','input_sha256':hashlib.file_digest((r/'s4.wav').open('rb'),'sha256').hexdigest(),'output_sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'regions':regions};(r/'s4-v2-processing.json').write_text(json.dumps(out,indent=2));print(out)
