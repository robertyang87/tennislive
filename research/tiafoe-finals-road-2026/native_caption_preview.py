import json,sys
from pathlib import Path
from functools import partial
R=Path('/dev/shm/tiafoe-production/native');sys.path[:0]=[str(R/'tools'),str(R/'src')]
import build_match_reel as reel
from preview_reel_captions import render_frames
B=Path('/workspace/tiafoe-finals-production');specpath=R/'specs/reels/tiafoe-finals-road-2026.json';spec=json.load(open(specpath));race_only='--race-only' in sys.argv;out=Path('/dev/shm/tiafoe-production/native-race-v2' if race_only else '/dev/shm/tiafoe-production/native-captions-v2');out.mkdir(exist_ok=True)
paths={'halle-final':'/dev/shm/tiafoe-production/media-early/tf26halle.mp4','acapulco-final':'/workspace/cobolli-research/media-a/4459713-native.mp4','wimbledon-r3':'/dev/shm/tiafoe-production/sources/tf26wimmp.mp4','cincinnati-final':'/workspace/fils-finals-production/research/media-late/RAAXKA85t3g.mp4','us-open-qf':'/dev/shm/tiafoe-production/sources/tf26usqf.mp4','us-open-sf':'/dev/shm/tiafoe-production/sources/tf26ussf.mp4'}
for key,path in paths.items():
 p=out/f'source_{key}.mp4'
 if not p.exists():p.symlink_to(path)
reel.apply_tts_backend(spec)
# Explicit bounded samples use real voice cue times, plus onsets and long scores.
def callback(**kwargs):
 cues=kwargs['cues'];segs=kwargs['segments'];cursor=kwargs['cover_secs'];starts={}
 for i,s in enumerate(segs):starts[i]=cursor;cursor+=s.length
 ids=[]
 for index in ([19] if race_only else [0,4,5,12,14,19]):
  valid=[(j+1,c) for j,c in enumerate(cues) if starts[index]<=c[0]<starts[index]+segs[index].length]
  if valid:ids.append(max(valid,key=lambda x:len(x[1][2]))[0])
 times=[] if race_only else [starts[i]+1 for i in [3,6,8,11,13,15]]
 return render_frames(**kwargs,maximum=16,cue_ids=tuple(ids),at=tuple(times),spec_path=specpath)
print(reel.render(spec,out,voice='zh-CN-YunjianNeural',rate='+6%',preview_callback=callback,tts_bundle_in=Path('/dev/shm/tiafoe-production/tiafoe-tts-bundle.zip')))
