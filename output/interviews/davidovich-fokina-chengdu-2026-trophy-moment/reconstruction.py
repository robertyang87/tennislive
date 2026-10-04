from pathlib import Path
import json,subprocess,asyncio,certifi
certifi.where=lambda:'/etc/ssl/certs/ca-certificates.crt'
import edge_tts
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent; R=D.parents[1]/'tennislive';S=D.parent/'9u2kSI8md88.mp4';F=R/'assets/fonts';CN=R/'assets/asiad-2026-draws/NotoSansCJKsc-Regular.otf'; SM=F/'SmileySans-Oblique.ttf'
def run(a): subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error']+a,check=True)
def dur(p):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))
rows=[(441.41,443.21,'But the smile says it all.','但他的笑容已经说明了一切'),(444.35,447.81,'After losing his first five Tour-level finals,','此前五次巡回赛决赛都失利'),(448.27,450.35,'he’s now won two in a row.','如今他已连续两次决赛夺冠'),(451.27,453.97,'And this one came having not played a match','而这次夺冠之前 他已有'),(453.97,455.57,'for two and a half months.','两个半月没有参加比赛'),(455.83,458.45,'What a week it has been for the Spaniard.','对他来说 这是难忘的一周'),(458.59,460.77,'He is the champion in Chengdu.','他就是成都站的冠军'),(467.59,470.73,'Just an absolute incredible effort','这样的表现实在不可思议'),(470.73,472.67,'and he absolutely deserved that.','这个冠军他当之无愧'),(472.89,474.61,'He played so well from the start.','从一开始 他就打得非常出色')]
(D/'lines.json').write_text(json.dumps([dict(source_start=s,source_end=e,en=en,zh=zh) for s,e,en,zh in rows],ensure_ascii=False,indent=2))
def text(dr,s,xy,size,color='#f4fbf7',display=False,stroke=0,anchor=None):dr.text(xy,s,font=ImageFont.truetype(str(SM if display else CN),size),fill=color,stroke_width=stroke,stroke_fill='#000000',anchor=anchor)
def stripes(dr):
 for i,c in enumerate(['#c6f65a','#37e29a','#ff5a6a','#4bb8ff']):dr.rectangle((i*270,0,(i+1)*270,10),fill=c)
lay=Image.new('RGBA',(1080,1440));dr=ImageDraw.Draw(lay);dr.rectangle((0,0,1080,150),fill=(6,20,15,235));stripes(dr)
text(dr,'赛后开麦｜成都捧杯时刻',(540,20),54,display=True,anchor='mt');text(dr,'达维多维奇·福基纳  2026成都站冠军',(540,93),32,anchor='mt');text(dr,'网球时差',(540,1365),26,anchor='mt',stroke=1);lay.save(D/'layout.png')
ass='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1440\nWrapStyle: 2\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: EN,Inter,44,&H00FFFFFF,&H00FFFFFF,&H60000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,200,1\nStyle: ZH,Noto Sans CJK SC,54,&H00FFFFFF,&H00FFFFFF,&H60000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,145,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
def ts(x):return f'{int(x//3600)}:{int(x//60)%60:02d}:{x%60:05.2f}'
for s,e,en,zh in rows:
 for style,tx in [('EN',en),('ZH',zh)]:ass+=f'Dialogue: 0,{ts(s-441)},{ts(e-441)},{style},,0,0,0,,{tx}\n'
(D/'subtitles.ass').write_text(ass)
enc=['-r','25','-c:v','libx264','-pix_fmt','yuv420p','-preset','fast','-crf','20','-threads','4','-c:a','aac','-b:a','192k','-ar','48000','-ac','2']
# Install complete Chinese font to avoid the repository subset missing glyphs.
fontdir=Path.home()/'.local/share/fonts';fontdir.mkdir(parents=True,exist_ok=True)
import shutil
shutil.copy(CN,fontdir/CN.name);subprocess.run(['fc-cache','-f'],check=True)
run(['-ss','441','-t','35.5','-i',str(S),'-loop','1','-i',str(D/'layout.png'),'-filter_complex',f"[0:v]delogo=x=90:y=825:w=1050:h=215:enable='between(t,10.5,20.5)',crop=810:1080:555:0,scale=1080:1440,setsar=1[v];[v][1:v]overlay=0:0,subtitles={D}/subtitles.ass:fontsdir={F}[out]",'-map','[out]','-map','0:a','-t','35.5']+enc+[str(D/'body.mp4')])
run(['-ss','463','-i',str(S),'-frames:v','1',str(D/'cover-source.jpg')]);im=Image.open(D/'cover-source.jpg').convert('RGB').crop((555,0,1365,1080)).resize((1080,1440));dr=ImageDraw.Draw(im);stripes(dr)
text(dr,'网球时差 · 赛后开麦',(70,44),42,display=True,stroke=3);text(dr,'成都站冠军 · 达维多维奇·福基纳',(70,108),32,stroke=3);text(dr,'四救盘点',(70,1090),94,'#c6f65a',True,3);text(dr,'终于笑着捧杯',(70,1210),94,display=True,stroke=3);im.save(D/'poster.jpg',quality=95)
end=Image.new('RGB',(1080,1440),'#06140f');dr=ImageDraw.Draw(end);stripes(dr);text(dr,'赛后开麦',(120,100),40,'#c6f65a',True);text(dr,'从五次决赛失利\n到连续两次捧杯',(120,420),40);text(dr,'四救盘点\n捧起成都冠军',(120,585),76,display=True);text(dr,'你更记得抢七逆转\n还是赛后这一刻',(120,890),54,'#c6f65a',True);text(dr,'网球时差',(120,1300),32);end.save(D/'endcard.png')
words='四次挽救盘点，捧起成都冠军。从五次决赛失利，到连续两次捧杯。你更记得抢七逆转，还是赛后这一刻？'
asyncio.run(edge_tts.Communicate(words,'zh-CN-YunjianNeural',rate='+12%').save(str(D/'endcard-voice.mp3')))
run(['-loop','1','-i',str(D/'poster.jpg'),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','1.8']+enc+[str(D/'cover.mp4')])
t=dur(D/'endcard-voice.mp3')+.45
run(['-loop','1','-i',str(D/'endcard.png'),'-i',str(D/'endcard-voice.mp3'),'-af','apad','-t',str(t)]+enc+[str(D/'endcard.mp4')])
run(['-i',str(R/'assets/brand/outro_master.mp4')]+enc+[str(D/'brand-outro.mp4')])
inputs=[]
for f in ['cover.mp4','body.mp4','endcard.mp4','brand-outro.mp4']:inputs+=['-i',str(D/f)]
chain=''.join(f'[{i}:v]setsar=1,setpts=PTS-STARTPTS[v{i}];[{i}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}];' for i in range(4))+''.join(f'[v{i}][a{i}]' for i in range(4))+'concat=n=4:v=1:a=1[v][a]'
out=D/'赛后开麦-成都捧杯时刻-v2.mp4';run(inputs+['-filter_complex',chain,'-map','[v]','-map','[a]']+enc+['-movflags','+faststart',str(out)])
import hashlib
(D/'rebuild-manifest.json').write_text(json.dumps({'kind':'reconstructed_new_version','not_original_library_bytes':True,'source':'https://github.com/robertyang87/tennislive/releases/download/source-9u2kSI8md88/9u2kSI8md88.mp4','source_window':[441,476.5],'crop':{'x':555,'cx':.5,'track':False},'duration':dur(out),'size':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'pieces':{f:dur(D/f) for f in ['cover.mp4','body.mp4','endcard-voice.mp3','endcard.mp4','brand-outro.mp4']},'voice':words,'audio':'commentator original plus voiced endcard and real brand master','qc_status':'awaiting_actual_inspection'},ensure_ascii=False,indent=2))
