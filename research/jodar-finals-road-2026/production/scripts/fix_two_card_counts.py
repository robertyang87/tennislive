import json,sys
from pathlib import Path
R=Path('/dev/shm/jodar-production/native');sys.path[:0]=[str(R/'src'),str(R/'tools')];from tennislive.video.transition_cards import render_clip
B=Path('/workspace/jodar-finals-production');p=B/'production/visual-sequence-manifest.json';rows=json.load(open(p));changed=[]
for row in rows:
 if row['id'] not in ['wimbledon_intro','montreal']:continue
 for j,shot in enumerate(row['shots']):
  if shot['kind']!='native_card':continue
  shot['title']=shot['title'].replace('先赢一盘','先赢1盘').replace('三盘负','3盘负');seconds=row['cuts'][j+1]-row['cuts'][j]+(.28 if j<len(row['shots'])-1 else .56)
  render_clip(shot['title'],Path(shot['path']),seconds=seconds,fps=25,kicker=shot['kicker'],size=(1080,1440))
 changed.append(row)
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');sys.path.insert(0,'/dev/shm/jodar-production');from visual_sequences import render
new=[render(row) for row in changed];ep=B/'production/visual-sequence-actual-inputs.json';old=json.load(open(ep));by={r['id']:r for r in new};ep.write_text(json.dumps([by.get(r['id'],r) for r in old],ensure_ascii=False,indent=2)+'\n')
p=B/'research/photos/narration-photo-binding.json';t=p.read_text();p.write_text(t.replace('先赢一盘\\n负于望月慎太郎','先赢1盘\\n负于望月慎太郎').replace('美网首轮\\n三盘负布云朝克特','美网首轮\\n3盘负布云朝克特'))
