import json,sys
from pathlib import Path
R=Path('/dev/shm/jodar-production/native');sys.path[:0]=[str(R/'tools'),str(R/'src')]
import build_match_reel as reel
from preview_reel_captions import render_frames
specpath=R/'specs/reels/jodar-finals-road-2026.json';spec=json.load(open(specpath));out=Path('/dev/shm/jodar-production/native-captions-countfix' if '--cards-only' in sys.argv else '/dev/shm/jodar-production/native-captions');out.mkdir(exist_ok=True)
paths={'australian-open-r2':'jd26ao.mp4','roland-garros-qf':'ifZ07lICjz8.mp4','washington-final':'-4AXzTrC9Ls.mp4','us-open-r1':'jd26uso.mp4','shanghai-final':'402fnpRkS3c.mp4'}
for key,name in paths.items():
 p=out/f'source_{key}.mp4'
 if not p.exists():p.symlink_to(Path('/dev/shm/jodar-production/sources')/name)
reel.apply_tts_backend(spec)
def callback(**kwargs):
 cues=kwargs['cues'];segs=kwargs['segments'];cursor=kwargs['cover_secs'];starts={}
 for i,s in enumerate(segs):starts[i]=cursor;cursor+=s.length
 ids=[]
 for index in [0,1,3,4,5,7,8,10,12,13,15,16,17,18]:
  valid=[(j+1,c) for j,c in enumerate(cues) if starts[index]<=c[0]<starts[index]+segs[index].length]
  if valid:ids.append(max(valid,key=lambda x:len(x[1][2]))[0])
 times=[starts[i]+1 for i in [2,6,9,11,14]]+[starts[7]+7,starts[10]+7,starts[16]+2,starts[14]+.62]
 return render_frames(**kwargs,maximum=24,cue_ids=() if '--cards-only' in sys.argv else tuple(ids),at=(starts[7]+7,starts[10]+7) if '--cards-only' in sys.argv else tuple(times),spec_path=specpath)
print(reel.render(spec,out,voice='zh-CN-YunjianNeural',rate='+6%',preview_callback=callback,tts_bundle_in=Path('/dev/shm/jodar-production/jodar-tts-bundle.zip')))
