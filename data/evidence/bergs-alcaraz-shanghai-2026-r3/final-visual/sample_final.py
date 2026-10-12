from pathlib import Path
import sys,json,hashlib,subprocess,re,math
from PIL import Image,ImageDraw
film=Path(sys.argv[1]); expected=sys.argv[2]; out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
actual=hashlib.sha256(film.read_bytes()).hexdigest()
if actual!=expected:raise SystemExit('SHA mismatch: refusing to sample stale or changing film '+actual)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(film)],text=True))
v=next(x for x in probe['streams'] if x['codec_type']=='video');duration=float(probe['format']['duration']);fps=eval(v['avg_frame_rate'],{'__builtins__':{}})
ass=film.parent/'subtitles.ass';asshash=hashlib.sha256(ass.read_bytes()).hexdigest()
def sec(t):
 h,m,s=t.split(':');return int(h)*3600+int(m)*60+float(s)
samples=[]
for line in ass.read_text().splitlines():
 if line.startswith('Dialogue: '):
  f=line.split(',',9);start,end=sec(f[1]),sec(f[2]);samples.append({'t':(start+end)/2,'kind':'subtitle_midpoint','cue_start':start,'cue_end':end,'cue':f[9]})
for t in [0,.6,1.2,2,5,6.7,10,162.5,168.5,duration-17.35,duration-15,duration-12,duration-9,duration-6,duration-3,duration-.3,duration-.06]+list(range(0,math.floor(duration),5)):
 if 0<=t<duration:samples.append({'t':t,'kind':'continuity_or_geometry'})
frames={}
for s in samples:
 n=max(0,min(int(v.get('nb_frames',10**9))-1,round(s['t']*fps)));s['frame']=n;frames.setdefault(n,[]).append(s)
selected=sorted(frames)
def balanced(expressions):
 if len(expressions)==1:return expressions[0]
 mid=len(expressions)//2
 return '('+balanced(expressions[:mid])+'+'+balanced(expressions[mid:])+')'
vf="select='"+balanced([f'eq(n,{n})' for n in selected])+"'"
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(film),'-an','-vf',vf,'-fps_mode','vfr',str(out/'frame-%03d.png')],check=True)
manifest=[]
for i,n in enumerate(selected):
 f=out/f'frame-{i+1:03d}.png';manifest.append({'file':f.name,'frame':n,'t':round(n/fps,3),'annotations':frames[n],'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
for g in range((len(manifest)+11)//12):
 im=Image.new('RGB',(4*360,3*510),'#172020');dr=ImageDraw.Draw(im)
 for j,m in enumerate(manifest[g*12:(g+1)*12]):
  im.paste(Image.open(out/m['file']).resize((360,480)),((j%4)*360,(j//4)*510+30));dr.text(((j%4)*360+8,(j//4)*510+7),f"{m['file']} {m['t']:.2f}s",fill='white')
 im.save(out/f'sheet-{g+1:02d}.jpg',quality=95)
black=subprocess.run(['ffmpeg','-hide_banner','-i',str(film),'-an','-vf','blackdetect=d=0.1:pix_th=0.10:pic_th=0.98','-f','null','-'],capture_output=True,text=True,check=True)
(out/'blackdetect.log').write_text(black.stderr)
if hashlib.sha256(film.read_bytes()).hexdigest()!=expected:raise SystemExit('Film changed while sampled: evidence invalid')
report={'film':str(film),'film_sha256':expected,'film_bytes':film.stat().st_size,'probe':probe,'subtitles_ass_sha256':asshash,'sample_method':'actual film exact decoded frame indices at subtitle midpoints and5s cadence plus cold/stat/matchpoint/handshake/end','blackdetect_hits':re.findall(r'black_start:[^\n]+',black.stderr),'frames':manifest,'status':'frames extracted; visual interpretation pending'}
(out/'actual-film-sample-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sha':expected,'samples':len(manifest),'seconds':duration,'fps':fps,'blackdetect_hits':report['blackdetect_hits'],'out':str(out)}))
