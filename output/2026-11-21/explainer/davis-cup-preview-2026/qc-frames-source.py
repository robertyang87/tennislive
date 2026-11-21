from pathlib import Path
from PIL import Image,ImageDraw
import json,subprocess,math
O=Path('/workspace/davis-cup-preview-2026');T=json.loads((O/'final-timeline.json').read_text());S=json.loads((O/'story.json').read_text());rows=[];proof=[]
for j,m in enumerate(T):
 points=[min(4,m['duration']/2)]
 if 0<j<len(T)-1 and len(S['segments'][j-1].get('people',[]))==2:points=[m['duration']*.25,m['duration']*.75]
 for k,off in enumerate(points):
  t=m['start']+off;p=O/f'final-frame-{j:02d}-{k}.jpg'
  subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-ss',str(t),'-i',str(O/'davis-cup-preview-2026.mp4'),'-frames:v','1','-vf','scale=270:360',str(p)],check=True)
  rows.append(p);proof.append({'chapter':j,'time':round(t,3),'title':m['title'],'file':p.name})
im=Image.new('RGB',(270*6,385*math.ceil(len(rows)/6)),'#0b1426');d=ImageDraw.Draw(im)
for j,p in enumerate(rows):
 im.paste(Image.open(p),((j%6)*270,(j//6)*385));d.text(((j%6)*270+6,(j//6)*385+363),f'{j}: {proof[j]["time"]}s',fill='white')
im.save(O/'final-contact.jpg',quality=95);(O/'visual-review-index.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print('Actual final-film frames',len(rows))
