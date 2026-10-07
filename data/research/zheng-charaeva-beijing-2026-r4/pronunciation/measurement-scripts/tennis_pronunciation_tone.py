import sys,json,numpy as np
sys.path.insert(0,'/tmp')
import tennis_pronunciation_adapter as ad
mp=ad.mp
mp.combined=lambda d:float(d['f0']) if np.isfinite(d['f0']) else float('nan')
out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation'
s='关注网球时差，时差归我，好球归你。'
for idx in [5,8]:
 r=mp.measure('差',s,['插','叉'],['岔','诧','汊'],'zh-CN-YunjianNeural','+6%',char='差',at=idx)
 r['method']='F0-only local semitone distances; same syllable cha differs only tone; MFCC DTW alignment preserved; complete utterance; leave-one-out calibration must pass'
 (out/'raw'/f'outro-f0-i{idx}-cha1-cha4.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(idx,r['verdict'],r['confidence'],r['score'],r['selftest_loo'],flush=True)
