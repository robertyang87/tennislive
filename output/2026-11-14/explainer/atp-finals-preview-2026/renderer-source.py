from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
import subprocess,json,math,concurrent.futures,sys
sys.path[:0]=['/workspace/tennislive-sparse/src','/workspace/tennislive-sparse/tools']
from tennislive.video import explainer as E
R=Path('/workspace/tennislive-sparse');O=Path('/workspace/atp-finals-2026');S=json.loads((O/'story.json').read_text())['segments'];FPS=30;FADE=.5
C={'bg':'#0b1426','panel':'#14243d','line':'#2c405c','white':'#f3f5ef','muted':'#a5b4c9','gold':'#e4bf7a','lime':'#d4ee71'}
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';DISPLAY=str(R/'assets/fonts/SmileySans-Oblique.ttf')
logo=Image.open(R/'assets/logo/brand/account/icon-transparent-1024.png').convert('RGBA');logo.thumbnail((64,64))
NAMES={'zverev':'兹维列夫','shelton':'谢尔顿','alcaraz':'阿尔卡拉斯','medvedev':'梅德韦德夫','fils':'菲斯','jodar':'霍达尔','tiafoe':'蒂亚福','cobolli':'科博利'}
def font(size,bold=False,display=False):return ImageFont.truetype(DISPLAY if display else BOLD if bold else FONT,size)
def text(d,xy,t,size=40,fill=None,anchor=None,bold=False,display=False,maxw=956):
 f=font(size,bold,display)
 while maxw and d.textlength(t,font=f)>maxw:
  size-=1;f=font(size,bold,display)
 if size<22:raise ValueError(('too small',t,size))
 d.text(xy,t,font=f,fill=fill or C['white'],anchor=anchor)
 return size

def art(s,idx=0):
 im=Image.new('RGBA',(1080,1440),C['bg']);d=ImageDraw.Draw(im)
 stops=[(205,249,76),(80,216,155),(243,105,105),(90,177,246)]
 for x in range(1080):
  p=x/1079*3;i=min(2,int(p));a=p-i;c=tuple(round(stops[i][j]*(1-a)+stops[i+1][j]*a) for j in range(3));d.line((x,0,x,10),fill=c)
 im.alpha_composite(logo,(61,43));text(d,(143,38),'网球时差',48,display=True);text(d,(143,101),'2026 ATP年终总决赛',29,bold=True)
 text(d,(1018,62),'历史交锋' if s['kind']=='h2h' else s.get('chapter','赛前预测'),28,C['lime'],anchor='rt')
 if s['kind']=='h2h':
  text(d,(62,173),s['title'],52,bold=True);text(d,(62,255),f'组内全部对阵  /  {idx:02d} — 06',25,C['muted'])
  for n,(left,score,right,note) in enumerate(s['rows']):
   y=343+n*326;d.rounded_rectangle((54,y,1026,y+273),radius=18,fill=C['panel'],outline=C['line'],width=2);d.rectangle((54,y+20,59,y+253),fill=C['gold'])
   text(d,(237,y+102),left,44,anchor='mm',bold=True,maxw=302);text(d,(844,y+102),right,44,anchor='mm',bold=True,maxw=302)
   text(d,(540,y+43),'总交锋',22,C['muted'],anchor='mm');text(d,(540,y+110),score,108,C['gold'],anchor='mm',bold=True,maxw=242)
   d.line((82,y+183,998,y+183),fill=C['line']);text(d,(540,y+223),note,29,anchor='mm',maxw=916)
  text(d,(62,1044),s['insight'],37,C['lime'],bold=True)
  text(d,(62,1127),'ATP 官方交锋 · 截至 2026.11.14',25,C['muted']);text(d,(62,1172),'巡回赛级别单打 · 年终赛前数据',25,C['muted'])
 else:
  text(d,(62,151),s['title'],54,display=True)
  text(d,(62,219),s['insight'] if idx==15 else '11.15—11.22 · 都灵 · 每组前2晋级' if idx<15 else '个人赛前判断 · 不等于已确定赛果',28,C['gold'],bold=True)
  d.rectangle((0,255,1080,1204),fill=(0,0,0,0))
  d.rectangle((0,1148,1080,1205),fill=(6,14,27,200))
  event=s.get('event','2026赛季资料照片')
  if idx in (0,15,16):event='2026 ATP年终总决赛 · 赛前预测'
  text(d,(540,1176),event,27,anchor='mm',maxw=1000)
  text(d,(540,1240),s.get('insight2') or s['insight'],35,C['lime'],anchor='mm',bold=True)
  # Individual predictions are labeled within their portrait tiles.
 return im

def photo(n,size):
 p=Image.open(O/'photos'/f'{n}.jpg').convert('RGB')
 if n=='medvedev':p=p.crop((0,0,int(p.width*.52),p.height))
 # Medvedev is on the left of the actual Almaty ceremony photograph.
 cx=.22 if n=='medvedev' else .94 if n=='jodar' else .5
 return ImageOps.fit(p,size,Image.Resampling.LANCZOS,centering=(cx,.4))
def photo_bg(s):
 im=Image.new('RGB',(1080,1440),C['bg']);names=s['people'];n=len(names)
 if n==1:im.paste(photo(names[0],(1080,950)),(0,255))
 elif n==2:
  for j,nm in enumerate(names):im.paste(photo(nm,(540,950)),(540*j,255))
 else:
  for j,nm in enumerate(names):im.paste(photo(nm,(540,475)),((j%2)*540,255+(j//2)*475))
 d=ImageDraw.Draw(im)
 if n==4:
  for j,nm in enumerate(names):
   x=(j%2)*540;y=255+(j//2)*475
   d.rectangle((x,y+376,x+540,y+438),fill=C['bg']);text(d,(x+270,y+407),NAMES[nm],38,anchor='mm',bold=True,maxw=500)
 return im

def sec(p):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))
def run(cmd,log):
 with open(log,'w') as f:subprocess.run(cmd,stdout=f,stderr=f,check=True)
base=['ffmpeg','-y','-nostdin','-v','error','-threads','2','-filter_complex_threads','1']
enc=['-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-r',str(FPS),'-threads','2','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-movflags','+faststart']
manifest=[]
for i,s in enumerate(S):
 a=sec(O/f'voice_{i:02d}.mp3');clip=s.get('end',0)-s.get('start',0);dur=math.ceil(max(a+1.5,clip+.5)*FPS)/FPS
 m=dict(index=i,title=s['title'],kind=s['kind'],audio_duration=a,duration=dur,voice_delay=.65);manifest.append(m)
 cues=E.subtitle_cues(E.readable(s['narration']),a,boundaries=json.loads((O/f'voice_{i:02d}.words.json').read_text()),offset=.65)
 E.write_subtitles(cues,O/f'captions_{i:02d}.ass',height=1440,margin_v=1290)
 (O/f'cues_{i:02d}.json').write_text(json.dumps(cues,ensure_ascii=False))
 overlay=art(s,idx=i)
 if s['kind']=='h2h':overlay.convert('RGB').save(O/f'card_{i:02d}.jpg',quality=96)
 elif s['kind']=='photos':
  bg=photo_bg(s).convert('RGBA');bg.alpha_composite(overlay);bg.convert('RGB').save(O/f'card_{i:02d}.jpg',quality=96)
 else:overlay.save(O/f'overlay_{i:02d}.png')
(O/'timeline.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
# Solo photographic cover, using the actual reviewed Paris final photograph.
cover=photo('alcaraz',(1080,1440)).convert('RGBA');d=ImageDraw.Draw(cover)
# Only the bottom title zone receives a light readability gradient.
grad=Image.new('RGBA',cover.size);gd=ImageDraw.Draw(grad)
for y in range(1000,1440):gd.line((0,y,1080,y),fill=(5,13,25,int(210*(y-1000)/440)))
cover.alpha_composite(grad);cover.alpha_composite(logo,(62,45));d=ImageDraw.Draw(cover)
text(d,(146,43),'网球时差',52,display=True);text(d,(62,1138),'ATP年终预测',92,bold=True);text(d,(62,1260),'冠军，我选阿卡',92,C['lime'],bold=True);text(d,(62,1375),'12组交锋 × 8人状态 · 2026.11.14',29)
cover.convert('RGB').save(O/'poster.jpg',quality=96)
if '--graphics-only' in sys.argv:sys.exit()
def render(m):
 i=m['index'];s=S[i];dur=m['duration'];out=O/f'segment_{i:02d}.mp4'
 if out.exists() and abs(sec(out)-dur)<.08:return
 if s['kind']=='video':
  clip=s['end']-s['start']
  cmd=base+['-ss',str(s['start']),'-t',str(clip),'-i',str(O/'sources'/(s['source']+'.mp4')),'-loop','1','-framerate',str(FPS),'-i',str(O/f'overlay_{i:02d}.png'),'-i',str(O/f'voice_{i:02d}.mp3')]
  # Keep the court centre fixed. The original native logo lies outside this crop.
  f=f'[0:v]fps={FPS},crop=iw:trunc(ih*0.82/2)*2:0:0,scale=-2:950,crop=1080:950:(iw-ow)/2:0,pad=1080:1440:0:255:color=0x0b1426,setsar=1,tpad=stop_mode=clone:stop_duration={dur-clip+1}[b];[b][1:v]overlay=0:0:shortest=1,ass={O}/captions_{i:02d}.ass[v];[2:a]adelay=650|650,apad,atrim=0:{dur}[a]'
 else:
  cmd=base+['-loop','1','-framerate',str(FPS),'-i',str(O/f'card_{i:02d}.jpg'),'-i',str(O/f'voice_{i:02d}.mp3')]
  f=f'[0:v]setsar=1,ass={O}/captions_{i:02d}.ass[v];[1:a]adelay=650|650,apad,atrim=0:{dur}[a]'
 cmd+=['-filter_complex',f,'-map','[v]','-map','[a]','-t',str(dur)]+enc+[str(out)]
 run(cmd,O/f'render_{i:02d}.log');print('rendered',i,dur,flush=True)
if '--sample' in sys.argv:
 for k in (1,7):render(manifest[k])
 sys.exit()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(render,manifest))
# Encode the exact account outro and short cover to the same stream parameters.
cv=O/'cover.mp4';run(base+['-loop','1','-framerate',str(FPS),'-i',str(O/'poster.jpg'),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','1.7']+enc+[str(cv)],O/'cover.log')
outro=O/'outro.mp4';run(base+['-i',str(R/'assets/brand/outro_story.mp4'),'-vf','scale=1080:1440,fps=30,setsar=1','-t','4.117']+enc+[str(outro)],O/'outro.log')
files=[cv]+[O/f'segment_{i:02d}.mp4' for i in range(len(S))]+[outro]
parts=[];timeline=[];pos=0
for j,p in enumerate(files):
 length=sec(p);lead=0 if j==0 else FADE;tail=0 if j==len(files)-1 else FADE
 interior=O/f'interior_{j:02d}.mp4'
 run(base+['-ss',str(lead),'-i',str(p),'-t',str(length-lead-tail),'-frames:v',str(round((length-lead-tail)*FPS))]+enc+[str(interior)],O/f'join-interior-{j}.log')
 parts.append(interior);timeline.append(dict(start=pos,duration=length,file=p.name,title='封面' if j==0 else '品牌片尾' if j==len(files)-1 else S[j-1]['title']))
 pos+=length-(FADE if j<len(files)-1 else 0)
 if j<len(files)-1:
  transition=O/f'join_{j:02d}.mp4'
  f=f'[0:v]settb=1/{FPS},setpts=PTS-STARTPTS[v0];[1:v]settb=1/{FPS},setpts=PTS-STARTPTS[v1];[v0][v1]blend=all_expr=A*(1-T/{FADE})+B*T/{FADE}[v];[0:a][1:a]amix=inputs=2:normalize=0[a]'
  run(base+['-ss',str(length-FADE),'-t',str(FADE),'-i',str(p),'-t',str(FADE),'-i',str(files[j+1]),'-filter_complex',f,'-map','[v]','-map','[a]','-t',str(FADE)]+enc+[str(transition)],O/f'join-{j}.log');parts.append(transition)
(O/'final-timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
concat=O/'concat.txt';concat.write_text(''.join("file '"+str(p)+"'\n" for p in parts))
film=O/'atp-finals-preview-2026.mp4'
run(['ffmpeg','-y','-nostdin','-v','warning','-f','concat','-safe','0','-i',str(concat),'-map','0:v:0','-map','0:a:0','-c','copy','-movflags','+faststart',str(film)],O/'concat.log')
print('FILM READY',film,'seconds',sec(film),'bytes',film.stat().st_size,flush=True)
