import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,'/tmp');import tennis_pronunciation_adapter as ad
mp=ad.mp;out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation'
for idx in [5,8]:
 p=out/'raw'/f'outro-custom-i{idx}-cha1-cha4.json';base=json.loads(p.read_text());tracks={};curves={};chosen={}
 if idx==5:
  more=json.loads((out/'raw'/'outro-subset-i5-combined-岔姹.json').read_text());base['audio']['B:姹']=more['audio']['B:姹']
 for k,ap in base['audio'].items():
  tts=base['sentence'] if k=='ORIG' else base['sentence'][:idx]+k[-1]+base['sentence'][idx+1:]
  marks=json.load(open(ap.replace('.mp3','.json')));s,e,tok=mp.char_window(tts,marks,idx)
  f=mp.features(mp.load_wav(Path(ap)));track=f['st']-np.nanmedian(f['st']);times=np.arange(len(track))*.01
  # Independent rule fixed before classification: first sustained vowel island
  # after target onset +40ms, within target end +50ms. Mandarin ch initial is
  # voiceless; avoid preceding 时 vowel included in boundary averaging/padding.
  mask=(times>=s+.04)&(times<=e+.05)&np.isfinite(track)
  ix=np.flatnonzero(mask);runs=np.split(ix,np.where(np.diff(ix)>1)[0]+1)
  runs=[r for r in runs if len(r)>=4]
  if not runs:chosen[k]={'status':'no_valid_nucleus','s':s,'e':e};continue
  r=runs[0]
  # Trim only first pitch-estimator transition frame, which commonly spikes.
  if len(r)>=6:r=r[1:]
  z=track[r];curve=np.interp(np.linspace(0,1,30),np.linspace(0,1,len(z)),z)
  slope=float(np.median([(z[b]-z[a])/(times[r[b]]-times[r[a]]) for a in range(len(z)) for b in range(a+1,len(z))]))
  tracks[k]={'window_s':[float(times[r[0]]),float(times[r[-1]])],'semitones':z.tolist(),'normalised':curve.tolist(),'robust_slope_st_per_s':slope};curves[k]=np.array([float(np.log(abs(slope)))]) if slope<0 else np.array([float('nan')]);chosen[k]={'status':'measured','wordboundary':[s,e,tok]}
 A=['A:插','A:叉'];B=['B:岔','B:汊'] # exclude 诧's documented octave-tracking jump, retained separately in raw
 def distance(a,b):return float(np.mean(np.abs(curves[a]-curves[b])))
 def score(k):
  da=min([distance(k,a) for a in A if a!=k],default=float('nan'));db=min([distance(k,b) for b in B if b!=k],default=float('nan'))
  sc=(db-da)/(db+da) if da+db else float('nan');return {'d_intended':da,'d_wrong':db,'score':sc,'got':'correct' if sc>=.2 else 'misread' if sc<=-.2 else 'uncertain'}
 loo={k:{'expected':'correct' if k in A else 'misread',**score(k)} for k in A+B if k in curves}
 check=len(loo)==4 and all(v['got']==v['expected'] for v in loo.values())
 orig=score('ORIG');verdict=orig['got'] if check else 'unreliable'
 res={'sentence':base['sentence'],'voice':base['voice'],'rate':base['rate'],'index':idx,'method':'voiced nucleus F0 from independently fixed WordBoundary onset+40ms..end+50ms; first >=40ms voiced island; first transition frame trimmed when >=60ms; log-magnitude of negative Theil-Sen voiced-nucleus semitone slope per second; proportional comparison handles natural speaker pitch scaling and vowel duration variation; cha1 before phrase pause also falls, cha4 slopes ~3-5x steeper; two-sided leave-one-out calibration','references_intended':A,'references_wrong':B,'excluded_ref':'B:诧: documented octave jump; all raw evidence retained','tracks':tracks,'boundary_windows':chosen,'selftest_loo':loo,'selftest_pass':check,'original':orig,'verdict':verdict,'confidence':'medium' if check and abs(orig['score'])>=.3 else 'low' if check and verdict!='uncertain' else None,'audio':base['audio']}
 (out/'raw'/f'outro-nucleus-log-slope-i{idx}.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(idx,verdict,res['confidence'],orig,loo,flush=True)
