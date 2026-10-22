from pathlib import Path
import sys,json,gc
sys.path.insert(0,'/workspace/tennislive/tools')
from source_asr import transcribe,shift,sha256
r=Path('/workspace/pegula-finals-production/revision-v3-scope/rg');src=r/'rg-r1-hoh-08EHKHtS6hg.mp4'
for model in ['small.en','medium.en']:
 for label,a,b in [('body',693.20,708.16),('point-end',705.8,709.2),('clean-reaction',714.40,721.20)]:
  ss,d=transcribe(src,model,a,b);out={'model':model,'source_sha256':sha256(src),'clip':[a,b],'segments':shift(ss,a),'prompt':None}
  (r/f'selected-{label}-{model}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(label,model,json.dumps(out['segments'],ensure_ascii=False),flush=True);gc.collect()
