from pathlib import Path
import json,subprocess,hashlib
from PIL import Image,ImageDraw
R=Path('/workspace/noskova-finals-production');s=json.load(open(R/'production/selections.json'))['selections'];o=R/'production/exact-point-proofs';o.mkdir(exist_ok=True);scoretime={'ao-r3':160.,'iw-sf':262.7,'madrid-r16':264.,'berlin-final':5982.7,'wimbledon-final':216.,'us-qf':167.12};records=[]
for k,t in scoretime.items():
 x=s[k];a=x['start'];b=x['end'];ss=[];co=Image.new('RGB',(810,1146),'#111');d=ImageDraw.Draw(co)
 for i in range(9):
  v=round(a+(b-a)*i/8,3);p=o/f'{k}-{v:.3f}.jpg';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(v),'-i',x['source_file'],'-frames:v','1','-vf','crop=810:1080:555:0,scale=540:720','-q:v','3',str(p)],check=True);im=Image.open(p);im.thumbnail((270,360));xx=i%3*270;yy=i//3*382;co.paste(im,(xx,yy));d.text((xx+3,yy+362),f'{k} {v:.3f}',fill='white');ss.append({'source_time':v,'image':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 cp=o/(k+'-crop9.jpg');co.save(cp,quality=94);sp=o/(k+'-original-scoreboard.jpg');subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',x['source_file'],'-frames:v','1','-q:v','2',str(sp)],check=True);records.append({'key':k,'source_sha256':x['source_sha256'],'start':a,'end':b,'cx':.5,'frame':'court','samples':ss,'contact':str(cp),'original_scoreboard':{'time':t,'path':str(sp),'sha256':hashlib.sha256(sp.read_bytes()).hexdigest()},'dense_terminal_contact':str(R/'production/visual'/(k+'-dead-contact.jpg')),'point_evidence':x['point_evidence'],'scope':'Actual source9 fixedcourt crop proof plus uncropped original scoreboard; not native watermark/subtitle preview or finalmovie QC.'})
(o/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n');print('Exact point9 proofs',len(records),flush=True)
