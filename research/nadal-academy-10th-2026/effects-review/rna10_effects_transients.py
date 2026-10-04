import json,pathlib,subprocess,time
import numpy as np,soundfile as sf
from scipy.signal import find_peaks
r=pathlib.Path('/workspace/scratch');spec=json.loads((r/'rna10-selected-spec.json').read_text());ids=json.loads((r/'rna10-sources.json').read_text());out=[]
for n in range(1,8):
 p=r/'rna10-effects'/f's{n}.wav'
 while not p.exists():time.sleep(3)
 while True:
  try:meta=next(x for x in json.loads((p.parent/'processing.json').read_text()) if x['source']==f's{n}');break
  except (FileNotFoundError,StopIteration,json.JSONDecodeError):time.sleep(3)
 y,sr=sf.read(p);x=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(r/'rna10-media'/f'{ids[f"rna10-source-{n}"]}.mp4'),'-vn','-ar','48000','-ac','1','-f','f32le','-']),dtype='<f4')
 for a,b in sorted(set((s['start'],s['end']) for s in spec['segments'] if s['source']==f's{n}')):
  if n==1 and a>=132.4 and b<=145.7:continue
  xx=x[int(a*sr):int(b*sr)];yy=y[int(a*sr):int(b*sr)];N=min(len(xx),len(yy))//480;xx=xx[:N*480].reshape(N,480);yy=yy[:N*480].reshape(N,480)
  ex=np.sqrt(np.mean(xx*xx,axis=1));ey=np.sqrt(np.mean(yy*yy,axis=1));peaks,_=find_peaks(ex,distance=20,prominence=np.median(ex)*.6);peaks=sorted(peaks,key=lambda k:ex[k],reverse=True)[:12]
  vals=[]
  for k in sorted(peaks):
   lo=max(0,k-5);hi=min(N,k+6);vals.append({'time':round(a+k*.01,2),'effect_to_original_peak_db':round(float(20*np.log10((ey[k]+1e-9)/(ex[k]+1e-9))),2),'original_contrast_db':round(float(20*np.log10((ex[k]+1e-9)/(np.median(ex[lo:hi])+1e-9))),2),'effect_contrast_db':round(float(20*np.log10((ey[k]+1e-9)/(np.median(ey[lo:hi])+1e-9))),2)})
  row={'source':f's{n}','start':a,'end':b,'effect_sha256':meta['effects_sha256'],'rms_ratio_db':float(20*np.log10((np.sqrt(np.mean(yy**2))+1e-9)/(np.sqrt(np.mean(xx**2))+1e-9))),'transient_candidates':vals,'limitation':'Energy transients are not semantically identified ball hits; no listening performed.'};out.append(row);(r/'rna10-effects-transients.json').write_text(json.dumps(out,indent=2))
