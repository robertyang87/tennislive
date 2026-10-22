from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,hashlib
p=Path('/workspace/pegula-finals-production/revision-v3-scope/wimbledon');src=p/'2rtc9kSjmPM.mp4';probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(src)]));(p/'ffprobe.json').write_text(json.dumps(probe,indent=2)+'\n');(p/'source-sha256.txt').write_text(hashlib.sha256(src.read_bytes()).hexdigest()+'\n');d=p/'tail-scan';d.mkdir(exist_ok=True);subprocess.run(['ffmpeg','-loglevel','error','-ss','158','-i',str(src),'-vf','fps=1/2,scale=480:270','-frames:v','40','-y',str(d/'frame-%03d.jpg')],check=True);fs=sorted(d.glob('frame*.jpg'));im=Image.new('RGB',(1920,300*((len(fs)+3)//4)))
for i,f in enumerate(fs):
 pic=Image.open(f);ImageDraw.Draw(pic).text((4,4),f'approx {158+i*2:.1f}',fill='yellow',stroke_width=1,stroke_fill='black');im.paste(pic,((i%4)*480,(i//4)*300))
im.save(p/'tail-scan-contact.jpg',quality=95);print('sha',hashlib.sha256(src.read_bytes()).hexdigest(),'frames',len(fs))
