from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
import subprocess,json,math,sys,concurrent.futures,os,hashlib
R=Path('/workspace/davis-roster-worktree');O=Path('/workspace/scratch/davis-update-20261123/render');sys.path[:0]=[str(R/'src'),str(R/'tools')]
from tennislive.video import explainer as E
from tennislive.video.transition_cards import render_clip
S=json.loads((O/'story.json').read_text());F=json.loads((O/'facts.json').read_text());FPS=30;FADE=.5
SCRIPT_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
BG='#0b1426';WHITE='#f3f5ef';GOLD='#e4bf7a';MUTED='#a5b4c9';LIME='#d4ee71';PANEL='#14243d';LINE='#334762'
REG='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';DISPLAY=str(O/'brand/display.ttf')
logo=Image.open(O/'brand/logo.png').convert('RGBA');logo.thumbnail((54,54))
def txt(d,xy,t,size=40,fill=WHITE,anchor=None,bold=False,display=False,maxw=956):
 fp=DISPLAY if display else BOLD if bold else REG
 f=ImageFont.truetype(fp,size)
 while maxw and d.textlength(t,font=f)>maxw:
  size-=1;f=ImageFont.truetype(fp,size)
 assert size>=23,(t,size)
 d.text(xy,t,font=f,fill=fill,anchor=anchor)
def sec(p):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))
def run(args,log):
 safe=[]
 for arg in args:
  if arg=='-i':safe+=['-threads','1']
  safe.append(arg)
 with open(O/log,'w') as f:subprocess.run(['ffmpeg','-y','-nostdin','-v','error','-threads','2','-filter_complex_threads','1']+safe,stdout=f,stderr=f,check=True)
enc=['-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','30','-threads','2','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-movflags','+faststart']
def header(s,alpha=False):
 im=Image.new('RGBA',(1080,1440),(11,20,38,0) if alpha else BG);d=ImageDraw.Draw(im)
 d.rectangle((0,0,1080,254),fill=BG);d.rectangle((0,1205,1080,1440),fill=BG)
 im.alpha_composite(logo,(62,43))
 txt(d,(132,43),'网球时差 · 网球有故事',38,display=True);txt(d,(132,99),'2026 戴维斯杯 · 博洛尼亚',28,fill=MUTED)
 txt(d,(1018,118),s['chapter'],24,fill=LIME,anchor='rt',maxw=305)
 txt(d,(62,167),s['title'],51,display=True)
 meta=F['quarterfinals'][s['tie']]['h2h'] if s['kind']=='tie' else '截至2026.11.23核实阵容 · 个人赛前判断'
 txt(d,(62,220),meta,25,fill=GOLD)
 txt(d,(540,1245),s['insight'],35,fill=LIME,anchor='mm',bold=True,maxw=970)
 return im
def country_photo(n):
 p=Image.open(O/'photos'/f'{n}.jpg').convert('RGB')
 centers={'czechia':(.40,.4),'canada':(.30,.35),'italy':(.48,.38),'korea-rep':(.58,.3),'great-britain':(.5,.45),'germany':(.58,.4),'austria':(.5,.42),'spain':(.53,.35)}
 return ImageOps.fit(p,(1080,950),Image.Resampling.LANCZOS,centering=centers[n])
def overlay(s,n):
 im=header(s,True);d=ImageDraw.Draw(im)
 d.rectangle((0,1098,1080,1205),fill=(5,13,25,205))
 txt(d,(62,1114),F['teams'][n]['cn'],44,bold=True)
 suffix='戴维斯杯官方资料照'
 if s['kind']=='tie':suffix+='  ·  北京时间 '+F['quarterfinals'][s['tie']]['beijing']
 txt(d,(62,1173),suffix,25,fill=WHITE)
 return im
def bracket(s):
 im=header(s);d=ImageDraw.Draw(im);mode=s['mode'];picks=mode!='draw';teams=F['teams'];ties=F['quarterfinals']
 txt(d,(210,294),'1/4决赛',31,fill=MUTED,anchor='mm',bold=True);txt(d,(580,294),'半决赛预测' if picks else '半决赛',31,fill=MUTED,anchor='mm',bold=True);txt(d,(901,294),'决赛预测' if picks else '决赛',31,fill=MUTED,anchor='mm',bold=True,maxw=260)
 rows=[346,520,760,934]
 def box(x,y,w,t,gold=False,sz=37):
  d.rounded_rectangle((x,y,x+w,y+58),radius=10,fill=PANEL,outline=GOLD if gold else LINE,width=3 if gold else 2);txt(d,(x+w/2,y+27),t,sz,fill=GOLD if gold else WHITE,anchor='mm',bold=True,maxw=w-12)
 for i,(tie,y) in enumerate(zip(ties,rows)):
  for j,k in enumerate([tie['left'],tie['right']]):box(62,y+j*62,290,teams[k]['cn'],picks and k==tie['pick'])
  if mode=='draw':txt(d,(64,y+128),tie['beijing'],23,fill=MUTED,maxw=290)
  mid=y+60;target=[460,522,875,937][i];d.line((354,mid,392,mid,392,target,433,target),fill=GOLD if picks else LINE,width=3)
 upper=['捷克','意大利'] if picks else ['捷/加胜者','意/韩胜者'];lower=['德国','西班牙'] if picks else ['英/德胜者','奥/西胜者']
 for y,items,winner in [(431,upper,'意大利'),(846,lower,'西班牙')]:
  for j,name in enumerate(items):box(435,y+j*62,283,name,picks and name==winner,35)
  fy=640 if y==431 else 702;d.line((720,y+60,754,y+60,754,fy,782,fy),fill=GOLD if picks else LINE,width=3)
 for j,name in enumerate(['意大利','西班牙'] if picks else ['上半区胜者','下半区胜者']):box(784,611+j*62,238,name,picks and name=='西班牙' and mode=='final',32)
 if picks:
  txt(d,(540,1111),'冠军倾向：西班牙' if mode=='final' else '意大利 / 捷克 / 德国 / 西班牙',49,fill=GOLD,anchor='mm',display=True,maxw=970)
  txt(d,(540,1173),'金色为个人预测 · 尚未产生赛果',25,fill=MUTED,anchor='mm')
 else:txt(d,(540,1173),'所有时间均为北京时间 · 官方淘汰签表',25,fill=MUTED,anchor='mm')
 return im.convert('RGB')
shared={
 'format':('先拿到2分\n才能晋级','01 赛制',{'comparison':{'metric':'01 每轮对抗','nodes':[{'label':'单打','value':'2场','source':F['sources']['guide']},{'label':'必要时双打','value':'1场','source':F['sources']['guide']},{'label':'晋级所需','value':'2胜','source':F['sources']['guide']}]}}),
 'doubles':('最后那一分\n可能属于双打','03 关键变量',{'comparison':{'metric':'03 双打变量','nodes':[{'label':'德国组合｜戴杯战绩','value':'18胜2负','source':F['sources']['germany']},{'label':'英国两将｜分别随各自搭档','value':'大满贯3冠','source':F['sources']['gb_doubles']}]}}),
 'risk':('主力能否出场\n临场怎样排兵','赛前观察',{'comparison':{'metric':'公布阵容不等于确定首发','nodes':[{'label':'观察点1','value':'身体恢复','source':F['sources']['guide']},{'label':'观察点2','value':'实际出场','source':F['sources']['guide']}]}}),
}
timeline=[]
for i,s in enumerate(S['segments']):
 a=sec(O/f'voice_{i:02d}.mp3');dur=math.ceil((a+1.5)*FPS)/FPS;timeline.append({'index':i,'title':s['title'],'kind':s['kind'],'duration':dur,'audio_duration':a,'voice_delay':.65})
 cues=E.subtitle_cues(E.readable(s['narration']),a,boundaries=json.loads((O/f'voice_{i:02d}.words.json').read_text()),offset=.65)
 E.write_subtitles(cues,O/f'captions_{i:02d}.ass',height=1440,margin_v=1290)
 (O/f'cues_{i:02d}.json').write_text(json.dumps(cues,ensure_ascii=False))
 if s['kind']=='bracket':bracket(s).save(O/f'card_{i:02d}.jpg',quality=96)
 elif s['kind'] in ('photos','tie'):
  for j,n in enumerate(s['people']):
   country_photo(n).save(O/f'photo_{i:02d}_{j}.jpg',quality=97);ov=overlay(s,n);ov.save(O/f'overlay_{i:02d}_{j}.png')
   preview=Image.new('RGBA',(1080,1440),BG);preview.alpha_composite(country_photo(n).convert('RGBA'),(0,255));preview.alpha_composite(ov);preview.convert('RGB').save(O/f'card_{i:02d}_{j}.jpg',quality=96)
(O/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2)+'\n')
if '--graphics-only' in sys.argv:sys.exit()
def render(m):
 i=m['index'];s=S['segments'][i];dur=m['duration'];out=O/f'segment_{i:02d}.mp4'
 key=hashlib.sha256(json.dumps([SCRIPT_SHA,s,F,hashlib.sha256((O/f'voice_{i:02d}.mp3').read_bytes()).hexdigest()],ensure_ascii=False).encode()).hexdigest();receipt=O/f'segment_{i:02d}.render.json'
 if out.exists() and receipt.exists():
  prior=json.loads(receipt.read_text())
  if prior.get('key')==key and prior.get('sha256')==hashlib.sha256(out.read_bytes()).hexdigest():return
 args=[];filters=[];voice=O/f'voice_{i:02d}.mp3';kind=s['kind']
 if kind in shared:
  text,kicker,content=shared[kind];silent=O/f'native-card-{i:02d}.mp4'
  render_clip(text,silent,seconds=dur,fps=FPS,content=content,kicker=kicker,header={'brand':'网球时差 · 网球有故事','topic':'2026 戴维斯杯 · 赛前预测'})
  args=['-i',str(silent),'-i',str(voice)];vid='[0:v]setsar=1';ai=1
 elif kind=='bracket':
  args=['-loop','1','-framerate','30','-i',str(O/f'card_{i:02d}.jpg'),'-i',str(voice)];vid='[0:v]setsar=1';ai=1
 else:
  n=len(s['people'])
  for j in range(n):
   args+=['-loop','1','-framerate','30','-t',str(dur+.5),'-i',str(O/f'photo_{i:02d}_{j}.jpg'),'-loop','1','-framerate','30','-t',str(dur+.5),'-i',str(O/f'overlay_{i:02d}_{j}.png')]
   filters.append(f"[{j*2}:v]scale=2160:1900,zoompan=z='min(1.028,1+0.028*on/({dur}*30))':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x950:fps=30,pad=1080:1440:0:255:color=0x0b1426,setsar=1[b{j}];[b{j}][{j*2+1}:v]overlay=0:0:shortest=1[p{j}]")
  if n==2:
   filters.append(f'[p0][p1]xfade=transition=fade:duration=0.5:offset={dur/2-.25}[pv]');vid='[pv]null'
  else:vid='[p0]null'
  args+=['-i',str(voice)];ai=2*n
 filters+=[vid+f',fillborders=top=14:mode=smear,ass={O}/captions_{i:02d}.ass[v]',f'[{ai}:a]aresample=48000,aformat=channel_layouts=stereo,adelay=650:all=1,apad,atrim=0:{dur}[a]']
 run(args+['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-t',str(dur),'-frames:v',str(round(dur*FPS))]+enc+[str(out)],f'render_{i:02d}.log')
 receipt.write_text(json.dumps({'key':key,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'seconds':dur},indent=2)+'\n');print('Rendered',i,dur,flush=True)
if '--sample' in sys.argv:
 for k in (0,2,3):render(timeline[k])
 sys.exit()
# The shared browser engine uses sync Playwright: run its three clips on this
# thread, then overlap independent deterministic photographic encodes.
for m in timeline:
 if m['kind'] in shared:render(m)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(render,[m for m in timeline if m['kind'] not in shared]))
run(['-loop','1','-framerate','30','-i',str(O/'poster.jpg'),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','1.7']+enc+[str(O/'cover.mp4')],'cover.log')
run(['-i',str(O/'brand/outro.mp4'),'-vf','scale=1080:1440,fps=30,setsar=1','-t','4.117']+enc+[str(O/'outro.mp4')],'outro.log')
files=[O/'cover.mp4']+[O/f'segment_{i:02d}.mp4' for i in range(len(timeline))]+[O/'outro.mp4'];parts=[];ft=[];pos=0
for j,p in enumerate(files):
 length=sec(p);lead=0 if j==0 else FADE;tail=0 if j==len(files)-1 else FADE;interior=O/f'interior_{j:02d}.mp4'
 run(['-ss',str(lead),'-i',str(p),'-t',str(length-lead-tail),'-frames:v',str(round((length-lead-tail)*FPS))]+enc+[str(interior)],f'interior-{j}.log');parts.append(interior)
 ft.append({'start':pos,'duration':length,'file':p.name,'title':'封面' if j==0 else '品牌片尾' if j==len(files)-1 else S['segments'][j-1]['title']});pos+=length-(FADE if j<len(files)-1 else 0)
 if j<len(files)-1:
  trans=O/f'join_{j:02d}.mp4';f=f'[0:v]settb=1/30,setpts=PTS-STARTPTS[v0];[1:v]settb=1/30,setpts=PTS-STARTPTS[v1];[v0][v1]blend=all_expr=A*(1-T/0.5)+B*T/0.5[v];[0:a][1:a]amix=inputs=2:normalize=0[a]'
  run(['-ss',str(length-FADE),'-t','0.5','-i',str(p),'-t','0.5','-i',str(files[j+1]),'-filter_complex',f,'-map','[v]','-map','[a]','-t','0.5']+enc+[str(trans)],f'join-{j}.log');parts.append(trans)
(O/'concat.txt').write_text(''.join("file '"+str(p)+"'\n" for p in parts));(O/'final-timeline.json').write_text(json.dumps(ft,ensure_ascii=False,indent=2)+'\n')
# Video-only concatenation avoids cumulative AAC segment timestamp drift.
run(['-f','concat','-safe','0','-i',str(O/'concat.txt'),'-map','0:v:0','-c','copy',str(O/'video-only.mp4')],'concat.log')
duration=sum(round(sec(p)*FPS) for p in parts)/FPS
args=[];fl=[]
for i,m in enumerate(ft[1:-1]):
 args+=['-i',str(O/f'voice_{i:02d}.mp3')];fl.append(f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={round((m["start"]+.65)*1000)}:all=1,apad,atrim=0:{duration},asetpts=PTS-STARTPTS[a{i}]')
n=len(ft)-2;args+=['-i',str(O/'brand/outro.mp4')];fl.append(f'[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={round(ft[-1]["start"]*1000)}:all=1,apad,atrim=0:{duration},asetpts=PTS-STARTPTS[a{n}]');fl.append(''.join(f'[a{i}]' for i in range(n+1))+f'amix=inputs={n+1}:normalize=0,atrim=0:{duration}[a]')
run(args+['-filter_complex',';'.join(fl),'-map','[a]','-c:a','pcm_s16le','-ar','48000','-ac','2',str(O/'final-audio.wav')],'audio-assembly.log')
run(['-i',str(O/'video-only.mp4'),'-i',str(O/'final-audio.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-t',str(duration),'-movflags','+faststart',str(O/(S['slug']+'.mp4'))],'final-mux.log')
print('Ready',S['slug'],duration,flush=True)
