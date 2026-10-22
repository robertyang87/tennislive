from pathlib import Path
import json,hashlib,subprocess,concurrent.futures
from PIL import Image,ImageDraw
R=Path('/workspace/noskova-finals-production/revision-madrid-tail/native-joined');m=json.load(open(R/'join-manifest.json'));o=R/'grid';o.mkdir(exist_ok=True);times=[round(6.84+i*.04,2)for i in range(37)]+[8.64,9.44,10.24];src=Path(m['file'])
def f(t):
 p=o/f'{t:.2f}.jpg';subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',str(t),'-i',str(src),'-frames:v','1','-q:v','3',str(p)],check=True);return {'mini_time':t,'equivalent_global_time':round(m['global_time_offset']+t,3),'source_if_before_join':round(m['source_start']+t,3)if t<m['mini_join_time']else None,'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=4)as p:rows=list(p.map(f,times))
for n,off in enumerate(range(0,len(rows),18)):
 subset=rows[off:off+18];out=Image.new('RGB',(1080,((len(subset)+5)//6)*270),(20,20,20));d=ImageDraw.Draw(out)
 for i,r in enumerate(subset):
  im=Image.open(r['file']);im.thumbnail((180,240));x=i%6*180;y=i//6*270;out.paste(im,(x,y+30));d.text((x+3,y+3),str(r['mini_time']),fill='white')
 out.save(R/f'join-contact-{n}.jpg',quality=93)
(R/'grid-manifest.json').write_text(json.dumps({'kind':'actualtargetnative_join_framegrid_not_finalmovie','join_manifest_sha256':hashlib.sha256((R/'join-manifest.json').read_bytes()).hexdigest(),'samples':rows},indent=2)+'\n');print('Actual joined frames',len(rows))
