from pathlib import Path
from PIL import Image,ImageDraw
import json
b=Path('/workspace/pegula-finals-production');p=b/'native-preview-labels-late-fresh-v3b';req=json.loads((b/'revision-v3-scope/preview-labels-late-fresh-v3b-requested.json').read_text())['samples'];imgs=sorted(p.glob('caption-*.png'))
for batch in range((len(imgs)+3)//4):
 out=Image.new('RGB',(1080,1480),(10,20,30));d=ImageDraw.Draw(out)
 for j,f in enumerate(imgs[batch*4:batch*4+4]):
  n=int(f.stem.split('-')[-1])-1;im=Image.open(f).convert('RGB').resize((540,720));x=(j%2)*540;y=(j//2)*740;out.paste(im,(x,y+20));why='/'.join(z['why'] for z in req[n]['reasons']);d.text((x+5,y+3),f'{f.name} {req[n]["id"]} {why}',fill='white')
 out.save(p/f'review-contact-{batch+1:02}.jpg',quality=95)
print('actual_native_PNGs',len(imgs))
