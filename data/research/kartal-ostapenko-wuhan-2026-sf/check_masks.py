import sys,json
from pathlib import Path
sys.path[:0]=['/workspace/tennislive/tools','/workspace/tennislive/src']
from probe_board import _decode
import wta_scoreboard as w
s=json.load(open('/workspace/tennislive/specs/reels/kartal-ostapenko-wuhan-2026-sf.json'));out=[]
for seg in s['segments']:
 if 'start'not in seg:continue
 a=seg['start'];b=seg['end'];bad=[];present=[];k=0
 for band in _decode(Path('/workspace/research-kartal/abL2j0xldOc.mp4'),(90,826,w.SCAN_W,154),a,b,25):
  t=round(a+k/25,3)
  try:
   g=w.frame_geometry(band,cap=460)
   if g:present.append(t)
  except RuntimeError as exc:bad.append(t)
  k+=1
 row={'segment':seg['_edit_id'],'bounds':[a,b],'frames':k,'bad_times':bad,'first_present':present[:1],'last_present':present[-1:]};out.append(row);print(json.dumps(row),flush=True)
Path('/workspace/research-kartal/mask-findings.json').write_text(json.dumps(out,indent=2))
