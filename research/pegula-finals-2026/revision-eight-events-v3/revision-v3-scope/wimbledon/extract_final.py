from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,hashlib,json
p=Path('/workspace/pegula-finals-production/revision-v3-scope/wimbledon');src=p/'2rtc9kSjmPM.mp4';d=p/'final-evidence';d.mkdir(exist_ok=True);times=[187.0,187.2,187.4,187.6,187.8,188.,188.4,188.8,189.2,197.,198.,199.,200.,204.,206.,208.,210.,212.,213.2];rows=[]
for t in times:
 f=d/f'source-{t:07.2f}.jpg';subprocess.run(['ffmpeg','-loglevel','error','-ss',str(t),'-i',str(src),'-frames:v','1','-y',str(f)],check=True);rows.append({'source_time':t,'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
for b in range((len(rows)+11)//12):
 im=Image.new('RGB',(1920,1080),(0,0,0));dr=ImageDraw.Draw(im)
 for j,r in enumerate(rows[b*12:b*12+12]):
  pic=Image.open(r['file']).resize((480,270));x=(j%4)*480;y=(j//4)*360;im.paste(pic,(x,y+25));dr.text((x+5,y+5),f"source {r['source_time']:.2f}",fill='yellow')
 im.save(d/f'contact-{b+1}.jpg',quality=95)
(d/'frames.json').write_text(json.dumps(rows,indent=2)+'\n');print('done')
