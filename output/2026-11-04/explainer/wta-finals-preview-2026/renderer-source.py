from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,math,concurrent.futures,hashlib,sys
from tennislive.video import explainer as E
O=Path('/workspace/wta-finals-video-v2');R=Path('/workspace/tennis-preview');S=json.loads((O/'story.json').read_text())['segments'];FPS=30;FADE=.5
# This episode defaults to the owner's requested clean lower-left corner.
NO_SCOREBOARDS='--with-scoreboards' not in sys.argv
C={'bg':'#0b1426','panel':'#14243d','line':'#2c405c','white':'#f3f5ef','muted':'#a5b4c9','gold':'#e4bf7a','lime':'#d4ee71'}
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';DISPLAY=str(R/'assets/fonts/SmileySans-Oblique.ttf')
logo=Image.open(R/'assets/logo/brand/account/icon-transparent-1024.png').convert('RGBA');logo.thumbnail((64,64))
def font(size,bold=False,display=False):return ImageFont.truetype(DISPLAY if display else BOLD if bold else FONT,size)
def text(d,xy,t,size=40,fill=None,anchor=None,bold=False,display=False,maxw=None):
 f=font(size,bold,display)
 while maxw and d.textlength(t,font=f)>maxw:
  size-=1;f=font(size,bold,display)
 d.text(xy,t,font=f,fill=fill or C['white'],anchor=anchor,stroke_width=0)
 return size

def art(s,event='',idx=0):
 im=Image.new('RGBA',(1080,1440),C['bg']);d=ImageDraw.Draw(im)
 # Original account branding: only the column name is removed.
 stops=[(205,249,76),(80,216,155),(243,105,105),(90,177,246)]
 for x in range(1080):
  p=x/1079*3;i=min(2,int(p));a=p-i;c=tuple(round(stops[i][j]*(1-a)+stops[i+1][j]*a) for j in range(3));d.line((x,0,x,10),fill=c,width=1)
 im.alpha_composite(logo,(61,43));text(d,(143,38),'网球时差',48,display=True)
 text(d,(143,101),'2026 WTA年终总决赛',29,bold=True)
 text(d,(1018,62),'历史交锋' if s['kind']=='h2h' else s.get('chapter','赛前预测'),28,C['lime'],anchor='rt')
 if s['kind']=='h2h':
  text(d,(62,173),s['title'],52,bold=True,maxw=956)
  text(d,(62,255),f'组内全部对阵  /  {idx:02d} — 06',25,C['muted'])
  for n,(left,score,right,note) in enumerate(s['rows']):
   y=343+n*326;d.rounded_rectangle((54,y,1026,y+273),radius=18,fill=C['panel'],outline=C['line'],width=2)
   d.rectangle((54,y+20,59,y+253),fill=C['gold'])
   text(d,(237,y+102),left,44,anchor='mm',bold=True,maxw=302)
   text(d,(844,y+102),right,44,anchor='mm',bold=True,maxw=302)
   text(d,(540,y+43),'总交锋',22,C['muted'],anchor='mm')
   text(d,(540,y+110),score,108,C['gold'],anchor='mm',bold=True,maxw=242)
   d.line((82,y+183,998,y+183),fill=C['line'],width=1)
   text(d,(540,y+223),note,29,C['white'],anchor='mm',maxw=916)
  text(d,(62,1044),s['insight'],37,C['lime'],bold=True,maxw=956)
  text(d,(62,1127),'数据：WTA / TennisExplorer · 截至 2026.11.04',25,C['muted'])
  text(d,(62,1172),'口径：不含赛前退赛、表演赛；比赛中伤退计入并注明',25,C['muted'],maxw=956)
 else:
  name=s['title'].split('｜')[0]
  text(d,(62,151),name,62,display=True,maxw=956)
  text(d,(62,213),s.get('stats','11.08—11.15 · 印第安维尔斯 · 每组前2晋级') if s.get('chapter')!='个人预测' else s.get('insight',''),29,C['gold'],bold=True,maxw=956)
  d.rectangle((0,255,1080,1204),fill=(0,0,0,0))
  d.rectangle((0,1148,1080,1205),fill=(6,14,27,195))
  text(d,(540,1176),event,27,C['white'],anchor='mm',maxw=980)
  insight=s.get('insight2') or s.get('insight','')
  text(d,(540,1240),insight,35,C['lime'],anchor='mm',bold=True,maxw=956)
 return im

def sec(p):
 args=['-select_streams','v:0','-show_entries','stream=duration'] if Path(p).suffix=='.mp4' else ['-show_entries','format=duration']
 return float(subprocess.check_output(['ffprobe','-v','error']+args+['-of','csv=p=0',str(p)]))
def run(cmd,log):
 with open(log,'w') as f:subprocess.run(cmd,stdout=f,stderr=f,check=True)
base=['ffmpeg','-y','-v','error','-threads','2','-filter_complex_threads','1']
enc=['-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-r',str(FPS),'-threads','2','-c:a','aac','-b:a','128k','-ar','24000','-ac','1','-movflags','+faststart']
manifest=[]
for i,s in enumerate(S):
 a=sec(O/f'voice_{i:02d}.mp3');dur=math.ceil((a+1.3)*FPS)/FPS
 m=dict(index=i,title=s['title'],kind=s['kind'],audio_duration=a,duration=dur,voice_delay=.35)
 if s['kind']=='h2h':m['clips']=[]
 elif i==0:
  L=(dur+2*FADE)/3
  m['clips']=[dict(source=k,start=t,end=t+L,event=e,kind='aftermath') for k,t,e in [('ao-final',185.0,'2026 澳网决赛｜莱巴金娜 vs 萨巴伦卡'),('cincinnati-final',247.0,'2026 辛辛那提决赛｜高芙 vs 佩古拉'),('wimbledon-final',208.4,'2026 温网决赛｜诺斯科娃 vs 穆霍娃')]]
 elif i==14:
  L=(dur+3*FADE)/4
  m['clips']=[dict(source=k,start=t,end=t+L,event=e,kind='aftermath') for k,t,e in [('ningbo-final',257.05,'2026 宁波决赛｜莱巴金娜'),('cincinnati-final',247.0,'2026 辛辛那提决赛｜高芙'),('indian-wells-final',257.0,'2026 印第安维尔斯决赛｜萨巴伦卡'),('adelaide-final',263.0,'2026 阿德莱德决赛｜安德烈耶娃')]]
 elif i==15:
  m['clips']=[dict(source=k,start=t,end=t+length,event=event,kind=kind) for k,t,length,event,kind in [('ao-final',179.5,14.2,'2026 澳网决赛｜莱巴金娜 vs 萨巴伦卡','complete_point_and_aftermath'),('indian-wells-final',257.0,6.0,'2026 印第安维尔斯决赛｜萨巴伦卡 vs 莱巴金娜','aftermath'),('ningbo-final',267.0,dur+1.0-20.2,'2026 宁波决赛｜莱巴金娜 vs 费尔南德斯','aftermath')]]
 else:
  starts={7:248.0,8:230.0,9:189.5,10:235.6,11:254.8,12:219.92,13:238.0};t=starts[i]
  m['clips']=[dict(source=s['source'],start=t,end=t+dur,event=s['event'],kind='complete_point_and_aftermath')]
  if i==13 and '--refresh-narration' in sys.argv:
   m['clips'][0]['end']=t+json.loads((O/'approved-timeline-with-scores.json').read_text())[i+1]['duration']
 manifest.append(m)
 cues=E.subtitle_cues(E.readable(s['narration']),a,boundaries=json.loads((O/f'voice_{i:02d}.words.json').read_text()),offset=.35)
 E.write_subtitles(cues,O/f'captions_{i:02d}.ass',height=1440,margin_v=1284)
 # Chinese captions keep native geometry; a single sentence may wrap to two lines.
 if s['kind']=='h2h':art(s,idx=i).convert('RGB').save(O/f'card_{i:02d}.jpg',quality=96)
 else:
  for n,c in enumerate(m['clips']):art(s,c['event']).save(O/f'overlay_{i:02d}_{n}.png')
(O/'timeline.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))

def render(m):
 i=m['index'];dur=m['duration'];s=S[i];out=O/f'segment_{i:02d}.mp4';cmd=list(base);filters=[]
 if NO_SCOREBOARDS:
  dur=json.loads((O/'approved-timeline-with-scores.json').read_text())[i+1]['duration']
 if '--resume' in sys.argv and out.exists() and out.stat().st_size>1000 and abs(sec(out)-dur)<0.08:
  print('retained checked segment',i,flush=True);return str(out)
 if s['kind']=='h2h':
  cmd+=['-loop','1','-framerate',str(FPS),'-i',str(O/f'card_{i:02d}.jpg'),'-i',str(O/f'voice_{i:02d}.mp3')]
  filters+=[f'[0:v]setsar=1,ass={O}/captions_{i:02d}.ass[v]',f'[1:a]adelay=350,apad,atrim=0:{dur},asetpts=PTS-STARTPTS[a]']
 else:
  for c in m['clips']:cmd+=['-ss',str(c['start']),'-t',str(c['end']-c['start']),'-i',str(O/'sources'/(c['source']+'.mp4'))]
  n=len(m['clips'])
  for j in range(n):cmd+=['-loop','1','-framerate',str(FPS),'-i',str(O/f'overlay_{i:02d}_{j}.png')]
  cmd+=['-i',str(O/f'voice_{i:02d}.mp3')]
  boards={'ningbo-final':(90,830,426,151,257.36),'cincinnati-final':(90,830,426,151,248.44),'wimbledon-final':(181,46,440,92,224.0),'indian-wells-final':(90,830,464,167,252.16),'adelaide-final':(90,830,426,151,264.68),'rome-final':(90,830,464,151,234.96),'doha-final':(90,830,426,151,258.56),'ao-final':(99,904,520,129,194.0)}
  for j,c in enumerate(m['clips']):
   x,y,w,h,until=boards[c['source']];enabled=max(0,until-c['start'])
   crop_top='crop=iw:ih-140:0:140,' if c['source']=='wimbledon-final' else ''
   if NO_SCOREBOARDS:
    # Remove the inset and its backing. Clean only the original broadcast board
    # remaining at the crop edge, keeping the established fixed framing.
    clean='' if c['source']=='wimbledon-final' or not enabled else f'delogo=x={x-4}:y={y-4}:w={w+8}:h={h+8}:enable=\'lt(t,{enabled})\','
    filters += [f'[{j}:v]fps={FPS},settb=1/{FPS},setpts=PTS-STARTPTS,{clean}{crop_top}scale=-2:950,crop=1080:950:(iw-ow)/2:0,pad=1080:1440:0:255:color=0x0b1426,setsar=1[b{j}]',f'[b{j}][{n+j}:v]overlay=0:0:shortest=1,format=yuv420p,fps={FPS},settb=1/{FPS}[c{j}]']
   else:
    filters+=[f'[{j}:v]fps={FPS},settb=1/{FPS},setpts=PTS-STARTPTS,split=2[main{j}][score{j}]',f'[main{j}]{crop_top}scale=-2:950,crop=1080:950:(iw-ow)/2:0,pad=1080:1440:0:255:color=0x0b1426,setsar=1,drawbox=x=0:y=960:w=510:h=188:color=0x0b1426:t=fill:enable=\'lt(t,{enabled})\'[b{j}]',f'[score{j}]crop={w}:{h}:{x}:{y},scale=450:-2,setsar=1[board{j}]',f'[b{j}][board{j}]overlay=22:978:enable=\'lt(t,{enabled})\'[boxed{j}]',f'[boxed{j}][{n+j}:v]overlay=0:0:shortest=1,format=yuv420p,fps={FPS},settb=1/{FPS}[c{j}]']
  label='c0';offset=0
  for j in range(1,n):
   offset+=m['clips'][j-1]['end']-m['clips'][j-1]['start']-FADE
   filters += [f'[{label}][c{j}]xfade=transition=fade:duration={FADE}:offset={offset},fps={FPS},settb=1/{FPS}[x{j}]'];label=f'x{j}'
  final_pad=f'tpad=stop_mode=clone:stop_duration=0.2,trim=end_frame={round(dur*FPS)},' if NO_SCOREBOARDS else ''
  filters +=[f'[{label}]{final_pad}ass={O}/captions_{i:02d}.ass[v]',f'[{2*n}:a]adelay=350,apad,atrim=0:{dur},asetpts=PTS-STARTPTS[a]']
 cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-t',str(dur)]+enc+[str(out)]
 run(cmd,O/f'render_{i:02d}.log');print('rendered',i,dur,flush=True);return str(out)

if '--graphics-only' in sys.argv:
 print('graphics ready');sys.exit()
if '--sample' in sys.argv:
 for k in (1,7):render(manifest[k])
 sys.exit()
if '--repair' in sys.argv:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,[manifest[k] for k in (0,7,8,10,11,12,14,15)]))
 sys.exit()
if '--remove-scoreboards' in sys.argv:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,[m for m in manifest if m['kind']=='video']))
 sys.exit()
if '--repair-residuals' in sys.argv:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,[manifest[k] for k in (0,8,12,13,14)]))
 sys.exit()
if '--finish-scoreboard-cleanup' in sys.argv:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,[manifest[k] for k in (7,10,11,14)]))
 sys.exit()
if '--render-muchova-voice' in sys.argv:
 render(manifest[13]);sys.exit()
if '--assemble-only' not in sys.argv:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,manifest))
# Standardize approved cover and the existing account-only native outro.
cover=O/'cover.mp4';run(base+['-loop','1','-framerate',str(FPS),'-i','/workspace/wta-finals-2026/wta-finals-eight-player-cover.png','-f','lavfi','-i','anullsrc=r=24000:cl=mono','-vf','scale=1080:1440:force_original_aspect_ratio=increase,crop=1080:1440,setsar=1','-t','2.2']+enc+[str(cover)],O/'render-cover.log')
outro=O/'outro.mp4';run(base+['-i','/workspace/wta-finals-2026/outro.mp4','-vf',f'scale=1080:1440,fps={FPS},setsar=1','-t','4.117']+enc+[str(outro)],O/'render-outro.log')
files=[cover]+[O/f'segment_{i:02d}.mp4' for i in range(len(S))]+[outro]
# Render joins one at a time to keep memory bounded, then concatenate with stream copy.
# A join consists of a0.5s tail/head dissolve; stable interiors retain their encoded bytes.
parts=[];timeline=[];pos=0.0
for j,p in enumerate(files):
 length=sec(p);lead=0 if j==0 else FADE;tail=0 if j==len(files)-1 else FADE
 interior=O/f'interior_{j:02d}.mp4'
 if not interior.exists() or interior.stat().st_mtime < p.stat().st_mtime or abs(sec(interior)-(length-lead-tail))>0.005:
  run(base+['-ss',str(lead),'-i',str(p),'-t',str(length-lead-tail),'-frames:v',str(round((length-lead-tail)*FPS))]+enc+[str(interior)],O/f'join-interior-{j}.log')
 parts.append(interior)
 timeline.append(dict(file=str(p),start=pos,duration=length,title='approved cover' if j==0 else 'account outro' if j==len(files)-1 else S[j-1]['title']))
 pos+=length-(FADE if j<len(files)-1 else 0)
 if j<len(files)-1:
  nxt=files[j+1];transition=O/f'join_{j:02d}.mp4'
  f=f'[0:v]settb=1/{FPS},setpts=PTS-STARTPTS[v0];[1:v]settb=1/{FPS},setpts=PTS-STARTPTS[v1];[v0][v1]blend=all_expr=A*(1-T/{FADE})+B*T/{FADE}[v];[0:a][1:a]acrossfade=d={FADE}:c1=tri:c2=tri[a]'
  # Two0.5s heads are blended into0.5s; audio amix uses the same overlap, avoiding timeline drift.
  f=f'[0:v]settb=1/{FPS},setpts=PTS-STARTPTS[v0];[1:v]settb=1/{FPS},setpts=PTS-STARTPTS[v1];[v0][v1]blend=all_expr=A*(1-T/{FADE})+B*T/{FADE}[v];[0:a][1:a]amix=inputs=2:normalize=0[a]'
  if not transition.exists() or transition.stat().st_mtime < max(p.stat().st_mtime,nxt.stat().st_mtime):
   run(base+['-ss',str(length-FADE),'-t',str(FADE),'-i',str(p),'-t',str(FADE),'-i',str(nxt),'-filter_complex',f,'-map','[v]','-map','[a]','-t',str(FADE)]+enc+[str(transition)],O/f'join-{j}.log')
  parts.append(transition)
(O/'final-timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
concat=O/'concat.txt';concat.write_text(''.join("file '"+str(p)+"'\nduration "+str(sec(p))+"\n" for p in parts))
film=O/'wta-finals-2026-h2h-form-prediction.mp4'
total=sum(sec(p) for p in parts)
audio_cmd=list(base);audio_filters=[]
for j,m in enumerate(manifest):
 audio_cmd+=['-i',str(O/f'voice_{j:02d}.mp3')]
 delay=round((timeline[j+1]['start']+.35)*1000)
 audio_filters.append(f'[{j}:a]adelay={delay},apad,atrim=0:{total}[a{j}]')
audio_cmd+=['-i','/workspace/wta-finals-2026/outro.mp4']
audio_filters.append(f'[{len(manifest)}:a]adelay={round(timeline[-1]["start"]*1000)},apad,atrim=0:{total}[a{len(manifest)}]')
audio_filters.append(''.join(f'[a{j}]' for j in range(len(manifest)+1))+f'amix=inputs={len(manifest)+1}:normalize=0,atrim=0:{total}[a]')
run(audio_cmd+['-filter_complex',';'.join(audio_filters),'-map','[a]','-ar','24000','-ac','1','-c:a','pcm_s16le',str(O/'final-audio.wav')],O/'final-audio.log')
reuse_audio=NO_SCOREBOARDS and '--refresh-narration' not in sys.argv
audio_input=O/'previous-with-scoreboards.mp4' if reuse_audio else O/'final-audio.wav'
audio_codec=['-c:a','copy'] if reuse_audio else ['-c:a','aac','-b:a','128k','-ar','24000','-ac','1']
run(['ffmpeg','-y','-v','warning','-f','concat','-safe','0','-i',str(concat),'-i',str(audio_input),'-map','0:v:0','-map','1:a:0','-c:v','copy']+audio_codec+['-t',str(total),'-movflags','+faststart',str(film)],O/'concat.log')
start=float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=start_time','-of','csv=p=0',str(film)]))
if start>0.00001:
 aligned=O/'aligned-final.mp4'
 run(['ffmpeg','-y','-v','error','-itsoffset',str(-start),'-i',str(film),'-i',str(film),'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(aligned)],O/'align.log')
 aligned.replace(film)
print('FILM READY',film,'seconds',sec(film),'bytes',film.stat().st_size,flush=True)
