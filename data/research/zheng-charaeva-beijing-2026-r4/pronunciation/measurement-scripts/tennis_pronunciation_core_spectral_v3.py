import sys,json,numpy as np,hashlib
from pathlib import Path
sys.path.insert(0,'/tmp');import tennis_pronunciation_adapter as ad
mp=ad.mp;out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation'
for tag,name in [('bei4-pi1-pairedrefs','native-bei-pairedrefs.json'),('shao3-shao4','native-cleanrefs-u05-i23-shao3-shao4-rhyme-2d826b17dc3a.json'),('chang3-chang2','native-cleanrefs-u06-i24-chang3-chang2-dce91d5c813f.json')]:
 b=json.loads((out/'raw'/name).read_text());idx=b['index'];tracks={};feats={};wins={};waves={}
 for k,ap in b['audio'].items():
  txt=b['sentence'] if k=='ORIG' else b['sentence'][:idx]+k[-1]+b['sentence'][idx+1:];marks=json.loads(Path(ap.replace('.mp3','.json')).read_text());s,e,tok=mp.char_window(txt,marks,idx)
  y=mp.load_wav(Path(ap));f=mp.features(y);t=np.arange(len(f['st']))*.01
  # phonetic core excludes voiced preceding token and different consonant initials;
  # middle35..85% plus50ms boundary compensation, /ei/ distinct from /i/.
  a=s+.35*(e+.05-s);z=s+.85*(e+.05-s);ix=np.flatnonzero((t>=a)&(t<=z));feats[k]=f;wins[k]=ix;waves[k]=y[int(a*mp.SR):int(z*mp.SR)];tracks[k]={'wordboundary':[s,e,tok],'core_s':[a,z],'frames':ix.tolist()}
 allspec=np.vstack([f['spec'][f['rms']>.1*np.max(f['rms'])] for f in feats.values()]);mu=allspec.mean(0);sd=allspec.std(0)+1e-6;vec={k:((f['spec'][wins[k]]-mu)/sd).mean(0) for k,f in feats.items()}
 A=[k for k in vec if k.startswith('A:')];B=[k for k in vec if k.startswith('B:')]
 def d(a,b):return float(np.linalg.norm(vec[a]-vec[b]))
 def score(k):
  da=min((d(k,x) for x in A if x!=k),default=float('nan'));db=min((d(k,x) for x in B if x!=k),default=float('nan'));v=(db-da)/(db+da);return {'d_intended':da,'d_wrong':db,'score':v,'got':'correct' if v>=.2 else 'misread' if v<=-.2 else 'uncertain'}
 loo={k:{'expected':'correct' if k in A else 'misread',**score(k)} for k in A+B};passed=all(v['expected']==v['got'] for v in loo.values());orig=score('ORIG')
 r={'sentence':b['sentence'],'text_sha256':b['text_sha256'],'index':idx,'audio':b['audio'],'native_orig_mp3_sha256':hashlib.sha256(Path(b['audio']['ORIG']).read_bytes()).hexdigest(),'method':'WordBoundary phonetic vowel core middle35..85%, end+50ms compensation; standardized MFCC+delta mean, double-sided reference LOO; no F0 mixed into segmental contrast','tracks':tracks,'selftest_loo':loo,'selftest_pass':passed,'original':orig,'verdict':orig['got'] if passed else 'unreliable','confidence':'medium' if passed else None}
 (out/'raw'/f'native-vowel-core-{tag}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(tag,r['verdict'],orig,loo,flush=True)
