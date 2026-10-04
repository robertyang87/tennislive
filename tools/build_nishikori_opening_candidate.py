from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
from render_story_info_band import render
from render_title_card import build as title_html
from playwright.sync_api import sync_playwright
OUT=ROOT/'work/nishikori-career-farewell/opening';OUT.mkdir(parents=True,exist_ok=True)
CAREER=ROOT/'work/nishikori-career-farewell/career.mp4';X=Path('/workspace/scratch/usopen-x-true-champion.mp4');TOKYO=Path('/workspace/scratch/tokyo-official-x-thanks.mp4');VOICE=ROOT/'work/nishikori-career-farewell/audio/opening.mp3'
def run(a,log=None):
 r=subprocess.run(a,capture_output=True,text=True)
 if log:log.write_text(r.stderr)
 if r.returncode:raise RuntimeError('command failed, local log available')
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def crop(src,cx=.5,cy=.5):
 v=next(s for s in probe(src)['streams'] if s['codec_type']=='video');w,h=v['width'],v['height'];cw=min(w,int(h*.75))//2*2;ch=min(h,int(w/.75))//2*2;xx=int(max(0,min(w-cw,cx*w-cw/2)))//2*2;yy=int(max(0,min(h-ch,cy*h-ch/2)))//2*2;return f'crop={cw}:{ch}:{xx}:{yy},scale=1080:1440:flags=lanczos,setsar=1,setpts=PTS-STARTPTS',[xx,yy,cw,ch]
render('生涯纪录','12座冠军','奥运铜牌',OUT/'stats.png',metric='最高第4',variant='stat')
html=title_html('锦织圭的来路',kicker='网球有故事',size=(1080,1440));(OUT/'title.html').write_text(html)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1080,'height':1440},device_scale_factor=1);page.set_content(html,wait_until='load');page.wait_for_function('document.fonts.status === "loaded"');page.wait_for_timeout(300);page.screenshot(path=str(OUT/'title.png'));b.close()
firstcrop,box=crop(X)
run(['ffmpeg','-y','-hide_banner','-ss','35.6','-t','6.35','-i',str(X),'-vf',firstcrop,'-r','25','-c:v','libx264','-threads','3','-preset','veryfast','-crf','19','-c:a','aac','-ar','48000','-b:a','192k','-af','asetpts=PTS-STARTPTS','-t','6.35',str(OUT/'00-original.mp4')],OUT/'first-encode.log')
shots=[(CAREER,34,38,.5,.5,'2008 Delray trophy'),(CAREER,74,78,.5,.5,'2012 Tokyo trophy'),(CAREER,850.15,853.25,.48,.5,'2019 Brisbane trophy'),(TOKYO,7,12,.5,.35,'2026 Tokyo farewell reactions')];audit=[];parts=[]
for i,(src,start,end,cx,cy,identity) in enumerate(shots):
 vf,box=crop(src,cx,cy);part=OUT/f'vo-{i:02d}.mp4';run(['ffmpeg','-y','-v','error','-ss',str(start),'-t',str(end-start),'-i',str(src),'-vf',vf,'-r','25','-c:v','libx264','-threads','3','-preset','veryfast','-crf','19','-an',str(part)]);parts.append(part);audit.append({'identity':identity,'source':str(src),'source_start':start,'source_end':end,'crop':box,'medal_identity':False})
(OUT/'vo-concat.txt').write_text('\n'.join("file '"+str(p)+"'" for p in parts)+'\n');run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(OUT/'vo-concat.txt'),'-c','copy',str(OUT/'vo-footage.mp4')])
run(['ffmpeg','-y','-v','error','-i',str(OUT/'vo-footage.mp4'),'-i',str(VOICE),'-loop','1','-i',str(OUT/'stats.png'),'-filter_complex_threads','1','-filter_complex',"[0:v]setpts=PTS-STARTPTS[v];[2:v]scale=500:-1[c];[v][c]overlay=520:65:enable='lt(t,3.85)':eof_action=repeat[out]",'-map','[out]','-map','1:a:0','-t','16.032','-r','25','-c:v','libx264','-threads','3','-preset','veryfast','-crf','19','-c:a','aac','-ar','48000','-b:a','192k',str(OUT/'01-narration.mp4')])
run(['ffmpeg','-y','-v','error','-loop','1','-i',str(OUT/'title.png'),'-ss','24','-t','1.8','-i',str(TOKYO),'-t','1.8','-map','0:v:0','-map','1:a:0','-vf','scale=1080:1440,setsar=1','-r','25','-c:v','libx264','-threads','3','-preset','veryfast','-crf','19','-c:a','aac','-ar','48000','-b:a','192k','-af','afade=t=out:st=1.25:d=0.55',str(OUT/'02-title.mp4')])
files=[OUT/'00-original.mp4',OUT/'01-narration.mp4',OUT/'02-title.mp4'];offsets=[];offset=0
for f in files:
 d=float(probe(f)['format']['duration']);offsets.append(offset);offset+=d
(OUT/'concat.txt').write_text('\n'.join("file '"+str(p)+"'" for p in files)+'\n');run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-c','copy',str(OUT/'opening-unsubtitled.mp4')])
base=(ROOT/'work/nishikori-career-farewell/sample-bilingual/commentary.ass').read_text().split('[Events]')[0]+'[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
def tm(t):
 n=round(t*100);return f'{n//360000}:{n//6000%60:02d}:{n//100%60:02d}.{n%100:02d}'
lines=[];quotes=[(36.05,37.7,"It's out!",'出界了！'),(38.1,38.95,'Unbelievable!','难以置信！'),(39.3,41.95,'And Nishikori has his greatest day.','锦织圭迎来了他最辉煌的一天。')]
for s,e,en,zh in quotes:
 for style,text,y in [('English',en,1284),('Chinese',zh,1326)]:lines.append(f'Dialogue: 0,{tm(s-35.6)},{tm(e-35.6)},{style},,0,0,0,,{{\\an2\\pos(540,{y})}}'+text)
# Chinese captions aligned to actual synthesis WordBoundary offsets.
marks=json.loads((VOICE.parent/'opening-marks.json').read_text());groups=[(0,2,'十二座冠军'),(3,4,'世界第四'),(5,8,'一枚奥运铜牌'),(9,15,'他赢过费德勒、纳达尔和德约科维奇'),(16,24,'也把亚洲男子网球带进了大满贯决赛'),(25,30,'今天，把时间拨回十八岁'),(31,36,'重新走一遍锦织圭的来路')];spoken_audit=[]
for a,b,text in groups:
 s=marks[a]['offset']/1e7;e=(marks[b]['offset']+marks[b]['duration'])/1e7+.10;s+=offsets[1];e+=offsets[1];lines.append(f'Dialogue: 0,{tm(s)},{tm(e)},Chinese,,0,0,0,,{{\\an2\\pos(540,1326)}}'+text);spoken_audit.append({'start':s,'end':e,'text':text,'method':'opening WordBoundary 100ns ticks'})
(OUT/'opening.ass').write_text(base+'\n'.join(lines)+'\n')
run(['ffmpeg','-y','-hide_banner','-i',str(OUT/'opening-unsubtitled.mp4'),'-vf',f'ass={OUT}/opening.ass:fontsdir={ROOT}/assets/fonts','-r','25','-c:v','libx264','-threads','3','-preset','veryfast','-crf','20','-c:a','copy','-movflags','+faststart',str(OUT/'opening-candidate.mp4')],OUT/'subtitle-encode.log')
json.dump({'status':'opening_candidate_not_final_film','duration':float(probe(OUT/'opening-candidate.mp4')['format']['duration']),'width':1080,'height':1440,'fps':25,'first_original_source':str(X),'first_source_window':[35.6,41.95],'first_limit':'Only historical point final shot and celebration, not complete service-to-point footage','first_audio':'real source English commentary; no VO overlap','VO_source':str(VOICE),'VO_start':offsets[1],'VO_duration':16.032,'VO_captions':spoken_audit,'footage':audit,'title_start':offsets[2],'title_audio':'Tokyo official applause 24–25.8s faded out; no synthetic player quote','ASR_listening_review':False,'voice_human_listening_review':False,'medal_visual':'No Olympic medal footage used; summary record card states career medal independently of trophy images','subtitle_style':'English1284 Chinese1326 native real fonts','visual_review':'pending actual frames'},open(OUT/'manifest.json','w'),ensure_ascii=False,indent=2)
print('complete',offset)
