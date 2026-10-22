from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,hashlib
p=Path('/workspace/pegula-finals-production/revision-v3-scope/wimbledon');src=p/'2rtc9kSjmPM.mp4';d=p/'crop-proof';d.mkdir(exist_ok=True);rows=[];ims=[]
for i in range(9):
 t=187.36+(212.4-187.36)*i/8;f=d/f'crop-{i:02}.jpg';subprocess.run(['ffmpeg','-loglevel','error','-ss',str(t),'-i',str(src),'-frames:v','1','-vf','crop=810:1080:555:0,scale=1080:1440','-y',str(f)],check=True);rows.append({'source_time':round(t,3),'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()});im=Image.open(f).resize((360,480));ImageDraw.Draw(im).text((5,5),f'{t:.3f}',fill='yellow',stroke_width=1,stroke_fill='black');ims.append(im)
im=Image.new('RGB',(1080,1440));[im.paste(x,((i%3)*360,(i//3)*480)) for i,x in enumerate(ims)];im.save(d/'contact.jpg',quality=95);(d/'manifest.json').write_text(json.dumps({'kind':'actual_source_fixed_crop_not_native_final_composite','cx':.5,'crop':[555,0,810,1080],'canvas':[1080,1440],'samples':rows},indent=2)+'\n');print('done9')
