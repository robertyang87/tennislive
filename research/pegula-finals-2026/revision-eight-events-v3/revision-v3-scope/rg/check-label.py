from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,hashlib
r=Path('/workspace/pegula-finals-production/revision-v3-scope/rg');src=r/'rg-r1-hoh-08EHKHtS6hg.mp4';p=Path('/workspace/tennislive/assets/reel/pegula-finals-2026/context-rg-r1.png');png=Image.open(p).convert('RGBA');png=png.resize((648,round(png.height*648/png.width)),Image.Resampling.LANCZOS)
ts=[693.2,694.0,694.8,695.4,696,696.6,697.2,697.8,698.4,699,699.6,700.2,700.8,701.4,702,702.6,703.2,703.8,704.4,705,705.6,706.2,706.8,707.4,708.0]
items=[]
for i,t in enumerate(ts):
 p1=r/f'label-source-{t:.2f}.png';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(src),'-frames:v','1','-vf','crop=810:1080:555:0,scale=1080:1440',str(p1)],check=True)
 im=Image.open(p1).convert('RGBA');im.alpha_composite(png,(386,151));p2=r/f'label-overlay-{t:.2f}.png';im.convert('RGB').save(p2);items.append({'source_time':t,'source_crop':str(p1),'overlay':str(p2)})
for j in range(0,len(items),9):
 group=items[j:j+9];o=Image.new('RGB',(1800,1200),'#111111')
 for k,x in enumerate(group):
  im=Image.open(x['overlay']).crop((200,50,1080,600)).resize((600,375));o.paste(im,((k%3)*600,(k//3)*400));ImageDraw.Draw(o).text(((k%3)*600+6,(k//3)*400+377),f"{x['source_time']:.2f}s actualPNG alpha overlay upperROI",fill='white')
 o.save(r/f'label-overlay-contact-{j//9+1}.jpg',quality=94)
(r/'label-overlay-manifest.json').write_text(json.dumps({'png':str(p),'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'geometry':{'x':386,'y':151,'width':648,'height':png.height},'method':'Exactfixed3:4sourcegeometry+actualtransparentPNG atfullopacity;not nativefade/font/movieQC','samples':items},indent=2))
