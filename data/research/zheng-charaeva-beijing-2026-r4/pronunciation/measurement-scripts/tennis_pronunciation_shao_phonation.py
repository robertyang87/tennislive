import sys,json,numpy as np,hashlib
from pathlib import Path
sys.path.insert(0,'/tmp');import tennis_pronunciation_adapter as ad
mp=ad.mp;out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation';b=json.loads((out/'raw'/'native-cleanrefs-u05-i23-shao3-shao4-rhyme-2d826b17dc3a.json').read_text());idx=b['index'];tracks={};vec={}
for k,ap in b['audio'].items():
 txt=b['sentence'] if k=='ORIG' else b['sentence'][:idx]+k[-1]+b['sentence'][idx+1:];marks=json.loads(Path(ap.replace('.mp3','.json')).read_text());s,e,tok=mp.char_window(txt,marks,idx);f=mp.features(mp.load_wav(Path(ap)));t=np.arange(len(f['st']))*.01
 a=s+.35*(e+.05-s);z=s+.85*(e+.05-s);ix=np.flatnonzero((t>=a)&(t<=z));rms=f['rms'][ix];base=np.percentile(f['rms'][f['rms']>.1*np.max(f['rms'])],75);v=float(np.log(np.mean(rms)/base));vec[k]=v;tracks[k]={'wordboundary':[s,e,tok],'core_s':[a,z],'core_rms':rms.tolist(),'utterance_voiced_rms75':float(base),'log_mean_core_to_utterance_rms':v}
A=[k for k in vec if k.startswith('A:')];B=[k for k in vec if k.startswith('B:')]
def score(k):
 da=min((abs(vec[k]-vec[x]) for x in A if x!=k),default=float('nan'));db=min((abs(vec[k]-vec[x]) for x in B if x!=k),default=float('nan'));v=(db-da)/(db+da);return {'d_intended':da,'d_wrong':db,'score':v,'got':'correct' if v>=.2 else 'misread' if v<=-.2 else 'uncertain'}
loo={k:{'expected':'correct' if k in A else 'misread',**score(k)} for k in A+B};passed=all(v['expected']==v['got'] for v in loo.values());orig=score('ORIG');r={'sentence':b['sentence'],'text_sha256':b['text_sha256'],'index':idx,'audio':b['audio'],'native_orig_mp3_sha256':hashlib.sha256(Path(b['audio']['ORIG']).read_bytes()).hexdigest(),'method':'Exact production acoustic comparative phonation: vowel middle35..85%, end+50ms compensation; log target mean RMS normalized by per-full-utterance voiced-frame RMS75; compare third-tone low creaky vowel against fourth-tone fully voiced vowel, paired LOO; independent references嫂/扫 share ao3 with different initial excluded; intensity cue alone limits confidence','tracks':tracks,'selftest_loo':loo,'selftest_pass':passed,'original':orig,'verdict':orig['got'] if passed else 'unreliable','confidence':'low' if passed else None}
(out/'raw'/'native-shao-phonation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(r['verdict'],orig,loo,vec,flush=True)
