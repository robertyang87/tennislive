from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,hashlib
r=Path('/workspace/pegula-finals-production/revision-v3-scope/rg');src=r/'rg-r1-hoh-08EHKHtS6hg.mp4';label=Path('/workspace/tennislive/assets/reel/pegula-finals-2026/context-rg-r1.png');proof=r/'final-proof';proof.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
labelim=Image.open(label).convert('RGBA');labelim=labelim.resize((648,228),Image.Resampling.LANCZOS)
records={}
for kind,ts in [('point',[693.2,695.4,695.8,697.2,699.2,701.2,703.2,705.4,708.16]),('label',[round(704.4+i*3/8,3)for i in range(9)])]:
 rec=[];contact=Image.new('RGB',(1080,1530),'#111')
 for i,t in enumerate(ts):
  orig=proof/f'{kind}-{i:02d}-source-{t:.3f}.png';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(src),'-frames:v','1',str(orig)],check=True)
  im=Image.open(orig).crop((555,0,1365,1080)).resize((1080,1440),Image.Resampling.LANCZOS).convert('RGBA');crop=proof/f'{kind}-{i:02d}-crop.png';im.convert('RGB').save(crop)
  if kind=='label':im.alpha_composite(labelim,(386,151))
  out=proof/f'{kind}-{i:02d}-overlay.png';im.convert('RGB').save(out);thumb=im.convert('RGB').resize((360,480));contact.paste(thumb,((i%3)*360,(i//3)*510));ImageDraw.Draw(contact).text(((i%3)*360+6,(i//3)*510+484),f'{t:.3f}s {kind}',fill='white');rec.append({'time':t,'original':str(orig),'original_sha256':sha(orig),'crop':str(crop),'crop_sha256':sha(crop),'overlay':str(out),'overlay_sha256':sha(out)})
  if kind=='point'and i==1:Image.open(orig).crop((0,830,650,1050)).save(proof/'matchpoint-scoreboard-original.png')
 contact.save(proof/f'{kind}-contact.jpg',quality=95);records[kind]=rec
(proof/'manifest.json').write_text(json.dumps({'source_sha256':sha(src),'label_png':str(label),'label_sha256':sha(label),'geometry':{'source_crop':[555,0,810,1080],'canvas':[1080,1440],'inset':[386,151,648,228]},'method':'actual extracted source pixels plus existing PNG alpha; source geometry precheck only, not native final-film QC','samples':records},indent=2))
