import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,'/tmp');import tennis_pronunciation_adapter as ad
mp=ad.mp;out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation'
for idx in [5,8]:
 base=json.loads((out/'raw'/f'outro-i{idx}-chai1-combined.json').read_text());curves={};tracks={};feats={};windows={}
 for k,ap in base['audio'].items():
  tts=base['sentence'] if k=='ORIG' else base['sentence'][:idx]+k[-1]+base['sentence'][idx+1:]
  marks=json.load(open(ap.replace('.mp3','.json')));s,e,tok=mp.char_window(tts,marks,idx)
  f=mp.features(mp.load_wav(Path(ap)));times=np.arange(len(f['st']))*.01;ix=np.flatnonzero(np.isfinite(f['st']));runs=np.split(ix,np.where(np.diff(ix)>1)[0]+1)
  runs=[r for r in runs if len(r)>=4 and times[r[0]]>=s+.04 and times[r[0]]<=e+.08]
  if not runs:print('no nucleus',idx,k,s,e,flush=True);continue
  r=runs[0];r=r[times[r]<=e+.05];tail=r[int(len(r)*.6):] # tail40% reveals a vs ai vowel ending
  if len(tail)<2:tail=r[-2:]
  feats[k]=f;windows[k]=tail
  tracks[k]={'wordboundary':[s,e,tok],'nucleus_window':[float(times[r[0]]),float(times[r[-1]])],'tail_window':[float(times[tail[0]]),float(times[tail[-1]])],'mfcc_tail':f['spec'][tail].tolist()}
 allspec=np.vstack([f['spec'][f['rms']>.1*np.max(f['rms'])] for f in feats.values()]);sd=allspec.std(0)+1e-6;mu=allspec.mean(0)
 for k,f in feats.items():curves[k]=((f['spec'][windows[k]]-mu)/sd).mean(0)
 A=['A:插','A:叉'];B=['B:钗','B:拆']
 def d(a,b):return float(np.linalg.norm(curves[a]-curves[b]))
 def score(k):
  da=min((d(k,a) for a in A if a!=k),default=float('nan'));db=min((d(k,b) for b in B if b!=k),default=float('nan'));v=(db-da)/(db+da)
  return {'d_intended':da,'d_wrong':db,'score':v,'got':'correct' if v>=.2 else 'misread' if v<=-.2 else 'uncertain'}
 if not all(k in curves for k in A+B+['ORIG']):continue
 loo={k:{'expected':'correct' if k in A else 'misread',**score(k)} for k in A+B};passed=all(x['expected']==x['got'] for x in loo.values());orig=score('ORIG')
 r={'sentence':base['sentence'],'voice':base['voice'],'rate':base['rate'],'index':idx,'method':'independent sustained voiced nucleus: use complete voiced runs, reject run started before target onset+40ms to avoid preceding时; nucleus onset<=WordBoundary end+80ms, entire voiced run clipped at boundary end+50ms to exclude following归 even when Praat bridges voiced consonant; last40% MFCC+delta vowel signature distinguishes monophthong cha from chai diphthong ending; shared full-utterance standardization; paired leave-one-out required','tracks':tracks,'selftest_loo':loo,'selftest_pass':passed,'original':orig,'verdict':orig['got'] if passed else 'unreliable','audio':base['audio']}
 (out/'raw'/f'outro-bounded-nucleus-vowel-i{idx}-chai1.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(idx,r['verdict'],orig,loo,flush=True)
