import sys,json,numpy as np,hashlib
from pathlib import Path
sys.path.insert(0,'/tmp');import tennis_pronunciation_adapter as ad
mp=ad.mp;out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation'
for name,tag in [('native-fa-f0-34ab0a3e1f7e.json','fa1-fa4'),('native-cleanrefs-u06-i24-chang3-chang2-dce91d5c813f.json','chang3-chang2')]:
 b=json.loads((out/'raw'/name).read_text());idx=b['index'];tracks={};vec={}
 for k,ap in b['audio'].items():
  text=b['sentence'] if k=='ORIG' else b['sentence'][:idx]+k[-1]+b['sentence'][idx+1:]
  marks=json.loads(Path(ap.replace('.mp3','.json')).read_text());s,e,tok=mp.char_window(text,marks,idx);f=mp.features(mp.load_wav(Path(ap)));t=np.arange(len(f['st']))*.01
  # End +50ms compensates word-boundary reporting ahead of the vowel end.
  # Use all pitch-valid frames in target, latter 40% (minimum3); excludes voiceless initial and pitch onset transition.
  ix=np.flatnonzero((t>=s+.04)&(t<=e+.05)&np.isfinite(f['st']));tail=ix[-max(3,int(np.ceil(len(ix)*.4))):]
  z=f['st'][tail]-np.nanmedian(f['st']);slope=float(np.median([(z[j]-z[i])/(t[tail[j]]-t[tail[i]]) for i in range(len(z)) for j in range(i+1,len(z))]))
  vec[k]=slope;tracks[k]={'wordboundary':[s,e,tok],'all_pitchvalid_times':t[ix].tolist(),'tail_times':t[tail].tolist(),'tail_semitones':z.tolist(),'robust_slope_st_per_s':slope}
 A=[k for k in vec if k.startswith('A:')];B=[k for k in vec if k.startswith('B:')]
 def score(k):
  da=min((abs(vec[k]-vec[a]) for a in A if a!=k),default=float('nan'));db=min((abs(vec[k]-vec[a]) for a in B if a!=k),default=float('nan'));v=(db-da)/(db+da)
  return {'d_intended':da,'d_wrong':db,'score':v,'got':'correct' if v>=.2 else 'misread' if v<=-.2 else 'uncertain'}
 loo={k:{'expected':'correct' if k in A else 'misread',**score(k)} for k in A+B if len(A)>1 or k in B};passed=all(v['expected']==v['got'] for v in loo.values());orig=score('ORIG');r={'sentence':b['sentence'],'text_sha256':b['text_sha256'],'voice':b['voice'],'rate':b['rate'],'index':idx,'audio':b['audio'],'native_orig_mp3_sha256':hashlib.sha256(Path(b['audio']['ORIG']).read_bytes()).hexdigest(),'method':'Exact native production; target WordBoundary onset+40ms..end+50ms; last40% of valid pitch frames, minimum3; Theil-Sen pitch slope in semitones/s; multiple references two-sided LOO (fa has only one intended ref and limits confidence)','tracks':tracks,'selftest_loo':loo,'selftest_pass':passed,'original':orig,'verdict':orig['got'] if passed else 'unreliable','confidence':'low' if len(A)==1 and passed else 'medium' if passed else None}
 (out/'raw'/f'native-tail-slope-{tag}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(tag,r['verdict'],r['confidence'],orig,loo,vec,flush=True)
