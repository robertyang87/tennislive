from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,io,json
root=Path('/workspace/rybakina-finals-production');jobs=[('ao-highlights',163.35,179.6),('indian-wells-final',245.6,262),('rg-r2',2,14.3),('us-final',152,167)]
for name,a,b in jobs:
 ts=[round(a+i,2) for i in range(int(b-a)+1)];rows=(len(ts)+3)//4;out=Image.new('RGB',(1280,204*rows),(5,12,17));d=ImageDraw.Draw(out)
 for i,t in enumerate(ts):
  z=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-ss',str(t),'-i',str(root/'sources'/f'{name}.mp4'),'-frames:v','1','-vf','scale=320:180','-f','image2pipe','-vcodec','mjpeg','-']);im=Image.open(io.BytesIO(z));x=i%4*320;y=i//4*204;out.paste(im,(x,y+24));d.text((x+3,y+3),f'source {t:.2f}s / seg {t-a:.2f}s',fill='white')
 p=root/'research/evidence'/('card-safe-'+name+'.jpg');out.save(p,quality=92);print(str(p),flush=True)
