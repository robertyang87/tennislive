#!/usr/bin/env python3
"""Render the approved NCAA story with the existing explainer typography and brand.

The official NCAA footage is archival 2021 and labelled as such. The US Open
web-page video was rejected after visual inspection: its scoreboard did not
support the page's 2026 identity. Never substitute that video for this year's SF.
"""
import argparse
import concurrent.futures
import html
import json
import os
import re
import xml.etree.ElementTree as ET
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tennislive.video import explainer as E

ASSETS = ROOT / 'assets/explainer/shelton-ncaa'
WORK = ROOT / 'work/shelton-ncaa'
# These bundled subset files expose this legacy family to libass. Browser CSS
# aliases them separately. "Noto Sans SC" silently falls back to Latin-only fonts.
E._ASS_FONT = 'Noto Sans SC Thin'
LIME, WHITE, MUTED = '#c6f65a', '#f2faf5', '#bad5c8'


def run(cmd):
    if cmd[0] == 'ffmpeg':
        cmd = [cmd[0], '-xerror', '-nostdin', *cmd[1:]]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2400:])
    return r


def seconds(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)]).stdout)


def txt(x, y, text, size=30, color=WHITE, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="700" text-anchor="{anchor}">{html.escape(str(text))}</text>'


def box(x, y, w, h, color='#193e30'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{color}"/>'


def pic(name, x, y, w, h):
    path = ASSETS / (name + '.jpg') if name != 'shelton' else ROOT / 'assets/reel/shelton-tiafoe-us-open-2026-sf.jpg'
    return f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><image href="{E._data_uri(path)}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/></svg>'


def diagram(beat, index, frame=None):
    visual = beat['visual']
    v = ''
    if visual == 'ncaa':
        v += txt(0, 36, 'NCAA · 2021 全国团体决赛', 28, MUTED)
        v += f'<image href="{E._data_uri(frame)}" x="0" y="70" width="900" height="506"/>'
    elif visual == 'timeline':
        v += pic('florida', 0, 0, 900, 290)
        for i, (year, text) in enumerate([('2021','全国团体冠军'),('2022','全国单打冠军'),('2026','美网决赛')]):
            x = i * 300
            v += txt(x+150, 390, year, 68, LIME, 'middle') + txt(x+150, 447, text, 28, WHITE, 'middle')
        v += '<path d="M60 510H840" stroke="#75ceef" stroke-width="4"/>'
        for x in [150,450,750]:v += f'<circle cx="{x}" cy="510" r="9" fill="{LIME}"/>'
    elif visual == 'structure':
        v += pic('florida',0,0,900,220)
        for i, (a,b) in enumerate([('大学校队','代表学校出战'),('联盟赛事','校际竞争'),('全国锦标赛','团体和个人冠军')]):
            x=i*304;v+=box(x,275,288,218)+txt(x+144,340,a,33,LIME,'middle')+txt(x+144,410,b,25,WHITE,'middle')
        v+=txt(450,558,'组织关系示意 · 非职业晋级制度',24,MUTED,'middle')
    elif visual == 'divisions':
        v+=pic('florida',0,0,900,195)
        for i,(a,b,c) in enumerate([('D1','高投入项目集中','本期聚焦'),('D2','体育与学业结合','可提供体育奖学金'),('D3','强调学生体验','不提供体育奖学金')]):
            x=i*304;v+=box(x,240,288,280)+txt(x+144,330,a,80,LIME,'middle')+txt(x+144,400,b,25,WHITE,'middle')+txt(x+144,465,c,23,MUTED,'middle')
        v+=txt(450,570,'组别不是年级，也不是球员等级',28,LIME,'middle')
    elif visual in ('doubles','singles','decider'):
        v+=txt(450,45,'D1 常见团体赛制 · 示意',29,MUTED,'middle')
        if visual=='doubles':
            for j in range(3):
                x=20+j*300;v+=box(x,100,260,250)+f'<rect x="{x+35}" y="145" width="190" height="150" fill="#22547b" stroke="#d7e8dc" stroke-width="3"/><path d="M{x+35} 220h190" stroke="#fff" stroke-width="3"/>'+txt(x+130,325,f'双打 {j+1}',25,WHITE,'middle')
            v+=txt(450,445,'先赢两场',46,WHITE,'middle')+txt(450,535,'团队只加 1 分',64,LIME,'middle')
        elif visual=='singles':
            for j in range(6):
                x=20+(j%3)*300;y=95+(j//3)*190
                v+=box(x,y,260,165)+txt(x+130,y+48,f'第 {j+1} 单打',26,WHITE,'middle')+txt(x+130,y+125,'1 分',60,LIME,'middle')
            v+=txt(450,555,'1 分双打 + 6 分单打 = 7 分',40,WHITE,'middle')
        else:
            v+=txt(450,240,'3 : 3',156,LIME,'middle')+txt(450,350,'最后一场单打',44,WHITE,'middle')+txt(450,450,'先到 4 分的学校获胜',42,LIME,'middle')+txt(450,565,'假设比分 · 非2021决赛实际赛果',25,MUTED,'middle')
    elif visual in ('support','aid','aid_new','calendar','limits','bridge','accelerator'):
        v+=pic('florida',0,0,900,235)
        rows={
          'support':[('训练','教练 · 队友 · 场地'),('身体','体能 · 康复支持'),('成长','持续训练与比赛')],
          'aid':[('体育奖学金','部分球员获得'),('学校预算','各校不同'),('D3','不提供体育奖学金')],
          'aid_new':[('2025 改革','参与新规则的 D1 学校'),('可提供范围扩大','不等于人人全额资助'),('实际待遇','以学校方案为准')],
          'calendar':[('课堂','课程 · 作业'),('球队','训练 · 选拔'),('客场','比赛 · 出行')],
          'limits':[('入队','本身存在选拔'),('转职业','依然面临竞争'),('明星案例','不代表平均结果')],
          'bridge':[('大学成绩','校队及全国赛事'),('参赛机会','衔接职业赛事'),('职业排名','靠职业赛赢球积分')],
          'accelerator':[('成绩条件','大学排名或NCAA单打成绩'),('提供支持','挑战赛参赛机会'),('不会赠送','胜场和职业积分')]
        }[visual]
        for i,(a,b) in enumerate(rows):
            y=275+i*95;v+=box(0,y,900,77)+txt(25,y+50,a,28,LIME)+txt(870,y+50,b,29,WHITE,'end')
        if visual in ('bridge','accelerator'):v+=txt(450,591,'ATP × ITA · 大学通往职业的桥',23,MUTED,'middle')
    elif visual=='isner':
        v+=pic('isner',35,30,210,210)+txt(310,110,'约翰·伊斯内尔',51,LIME)+txt(310,183,'佐治亚大学 · 2004—2007',31,WHITE)
        for i,(a,b) in enumerate([('4 年','大学校队'),('TOP 10','职业世界前十'),('温网','2018 单打四强')]):
            x=i*304;v+=box(x,300,288,230)+txt(x+144,395,a,58,LIME,'middle')+txt(x+144,465,b,26,WHITE,'middle')
        v+=txt(450,580,'左上为佐治亚大学校徽',23,MUTED,'middle')
    else:
        raise ValueError(visual)
    root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 740">'+v+'</svg>')
    for node in root:
        tag=node.tag.rsplit('}',1)[-1]
        for key in ('y','cy','height'):
            if key in node.attrib:node.set(key,str(float(node.get(key))*1.23))
        if tag=='text':
            size=float(node.get('font-size','30'))
            if size<=44:node.set('font-size',str(round(size*1.25)))
        elif tag=='path':node.set('transform','scale(1 1.23)')
        elif tag=='svg':
            vb=node.get('viewBox').split();vb[3]=str(float(vb[3])*1.23);node.set('viewBox',' '.join(vb))
            for child in node:
                if 'height' in child.attrib:child.set('height',str(float(child.get('height'))*1.23))
        if visual=='ncaa' and tag=='image':
            node.set('y','65');node.set('height','675');node.set('preserveAspectRatio','xMidYMid slice')
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    return ET.tostring(root,encoding='unicode')


def make_cards(spec, out):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    # Reuse the existing native template. No new global CSS or brand system.
    with sync_playwright() as pw:
        exe=os.environ.get('TENNISLIVE_CHROMIUM')
        local=Path('/root/.cache/ms-playwright/chromium_headless_shell-1161/chrome-linux/headless_shell')
        if not exe and local.is_file():exe=str(local)
        browser=pw.chromium.launch(executable_path=exe,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1080,'height':1440},device_scale_factor=1)
        for i,b in enumerate(spec['beats']):
            v=b['visual'];photo='';frame=None
            if v in ('usopen','closing'):photo='assets/reel/shelton-tiafoe-us-open-2026-sf.jpg'
            elif v in ('florida','collins','rinderknech','tian'):photo=f'assets/explainer/shelton-ncaa/{v}.jpg'
            elif v=='ncaa':
                frame=out/f'frame_{i:02d}.jpg'
                run(['ffmpeg','-v','error','-ss',str(b['start']),'-i',str(WORK/'ncaa-2021.mp4'),'-frames:v','1','-y',str(frame)])
            sg=E.ExplainerSegment(kind='photo',label=b['label'],title=b['title'],narration=b['narration'],image=photo,diagram='' if photo else diagram(b,i,frame),points=())
            markup=E._slide_html(i+1,sg,topic='谢尔顿与美国大学网球',column='网球有故事')
            clean_label=re.sub(r'^\d+\s*', '', b['label'])
            markup=re.sub(r'<span class="chip">[^<]*</span>', '<span class="chip">'+html.escape(clean_label)+'</span>', markup)
            markup=markup.replace('</style>', '.diagram-wrap{top:190px}.diagram-wrap>svg{width:960px}.scrim--diagram{background:linear-gradient(180deg,transparent 0%,transparent 69%,rgba(6,28,20,.94) 100%)}.chip{font-size:36px;letter-spacing:1px}.copy{gap:24px}</style>')
            if photo:
                photo_css='.hero:not(.blurbg){top:190px;bottom:auto;height:790px;background-size:cover!important;background-position:center!important}'
                if v=='usopen':photo_css='.hero:not(.blurbg){inset:0;height:1440px;background-size:cover!important;background-position:center!important}'
                markup=markup.replace('</style>',photo_css+'</style>')
            # Explicit small archive identifiers avoid presenting old images as this year's action.
            archive={'florida':'2022 · NCAA单打冠军','collins':'柯林斯 · 职业赛资料图','rinderknech':'林德克内希 · 职业赛资料图','tian':'2023 · NCAA女单冠军','closing':'2026 · 美网半决赛','usopen':'2026 · 美网半决赛'}.get(v,'')
            if archive:markup=markup.replace('</body>',f'<div style="position:absolute;top:160px;left:70px;color:#e9f5ed;font-size:25px;text-shadow:0 2px 6px #000">{archive}</div></body>')
            path=out/f'card_{i:02d}.html';path.write_text(markup)
            page.goto(path.as_uri());page.wait_for_function("document.fonts.status==='loaded' && Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)")
            page.screenshot(path=str(out/f'card_{i:02d}.png'))
            print('Card',i+1,flush=True)
        cover=E.ExplainerSegment(kind='cover',label='网球有故事',title=spec['hook'].replace('\n',' '),narration='',image='assets/reel/shelton-tiafoe-us-open-2026-sf.jpg')
        markup=E._slide_html(0,cover,topic='谢尔顿 · 美国大学网球',column='网球有故事')
        markup=markup.replace(html.escape(cover.title),'先打大学联赛<br>再闯美网决赛')
        markup=markup.replace('</style>','.cover .title{font-size:94px!important}.cover .copy{bottom:230px}</style>')
        (out/'cover.html').write_text(markup);page.goto((out/'cover.html').as_uri());page.wait_for_function("document.fonts.status==='loaded'");page.screenshot(path=str(out/'cover.png'))
        browser.close()
    sheet=Image.new('RGB',(1080,360*6),'#061c14')
    for i in range(24):sheet.paste(Image.open(out/f'card_{i:02d}.png').resize((270,360)),((i%4)*270,(i//4)*360))
    sheet.save(out/'contact-sheet.jpg')


def encode_beat(iv,spec,out):
    i,b=iv;audio=out/f'voice_{i:02d}.mp3';d=seconds(audio);duration=d+0.22
    cues=E.subtitle_cues(E.speakable(b['narration']),d,boundaries=json.loads(audio.with_suffix('.words.json').read_text()),offset=0.08)
    sub=out/f'sub_{i:02d}.ass';E.write_subtitles(cues,sub,height=1440,margin_v=1284)
    # One native card is a backdrop; the source video is composited into its reserved photo slot.
    cmd=['ffmpeg','-v','error','-threads','2','-filter_complex_threads','1','-loop','1','-framerate','25','-i',str(out/f'card_{i:02d}.png'),'-i',str(audio)]
    fc='[0:v]format=yuv420p[base];'
    if b['visual']=='ncaa':
        cmd+=['-ss',str(b['start']),'-i',str(WORK/'ncaa-2021.mp4')]
        # These windows fit in the validated 0–326s region; never loop a winning point.
        if b['start']+duration>326:raise ValueError('Archival window overrun')
        fc+='[2:v]scale=960:720:force_original_aspect_ratio=increase:flags=lanczos,crop=960:720,setsar=1,setpts=PTS-STARTPTS[foot];[base][foot]overlay=60:259[card];'
        fc+='[2:a]volume=0.06,atrim=duration='+str(duration)+',asetpts=PTS-STARTPTS[amb];[1:a]adelay=80|80,apad,atrim=duration='+str(duration)+'[voice];[voice][amb]amix=inputs=2:normalize=0,alimiter=limit=0.95[a];'
    else:
        # Animate only the photo panel; brand, archive label, chip and title
        # stay at their native coordinates. Never scale a composed card.
        if b['visual'] in ('closing','florida','collins','rinderknech','tian'):
            fc+="[base]split=2[fixed][photo];[photo]crop=1080:790:0:190,scale=1124:822,crop=1080:790:x='22+8*sin(t/6)':y='16+6*sin(t/7)'[movingphoto];[fixed][movingphoto]overlay=0:190[card];"
        else:fc+='[base]null[card];'
        fc+='[1:a]adelay=80|80,apad,atrim=duration='+str(duration)+',alimiter=limit=0.95[a];'
    if i==0:
        cmd+=['-loop','1','-framerate','25','-i',str(out/'cover.png')]
        fc+="[card][2:v]overlay=0:0:enable='lt(t,2.4)'[opening];"
    subtitle_input='opening' if i==0 else 'card'
    fc+=f"[0:v]crop=1080:12:0:0[brandbar];[{subtitle_input}][brandbar]overlay=0:0[branded];"
    fc+=f"[branded]subtitles='{sub}':fontsdir='{ROOT/'assets/fonts'}'[v]"
    cmd+=['-filter_complex',fc,'-map','[v]','-map','[a]','-t',str(duration),'-r','25','-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-threads','2','-y',str(out/f'part_{i:02d}.mp4')]
    run(cmd)
    actual=seconds(out/f'part_{i:02d}.mp4')
    if abs(actual-duration)>0.12:
        raise RuntimeError(f'Incomplete segment {i}: {actual} != {duration}')
    print('Encoded',i+1,round(duration,2),flush=True)
    return {'index':i,'seconds':duration,'narration_seconds':d,'visual':b['visual'],'subtitle_cues':cues}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cards-only',action='store_true');ap.add_argument('--assemble-only',action='store_true');a=ap.parse_args()
    out=WORK/'render';out.mkdir(parents=True,exist_ok=True)
    # Reconstruct externally hosted media rather than committing movie files.
    import requests
    for entry in json.loads((ASSETS/'credits.json').read_text()):
        dest=ASSETS/entry['file']
        if not dest.is_file():
            response=requests.get(entry['image_url'],timeout=60)
            response.raise_for_status();dest.write_bytes(response.content)
    if not (WORK/'ncaa-2021.mp4').is_file():
        media=json.loads((ASSETS/'media-sources.json').read_text())['ncaa_2021']
        run(['ffmpeg','-v','error','-i',media['media_url'],'-map','0:v:0','-map','0:a:0','-c','copy','-y',str(WORK/'ncaa-2021.mp4')])
    spec=json.loads((ROOT/'specs/explainers/shelton-ncaa-story.json').read_text())
    if not a.assemble_only:make_cards(spec,out)
    if a.cards_only:return
    from tennislive.localca import trust_local_proxy_ca
    trust_local_proxy_ca()
    from tennislive.video.tts import tts_one
    def narrate(iv):
        i,b=iv;path=out/f'voice_{i:02d}.mp3'
        marks=tts_one(E.speakable(b['narration']).replace('二零二二年','2022年'),path,spec['voice'],spec['rate'],'+0Hz')
        path.with_suffix('.words.json').write_text(json.dumps(marks,ensure_ascii=False))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(narrate,enumerate(spec['beats'])))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        results=list(pool.map(lambda iv:encode_beat(iv,spec,out),enumerate(spec['beats'])))
    outro=out/'outro.mp4'
    run(['ffmpeg','-v','error','-i',str(ROOT/'assets/brand/outro_master.mp4'),'-vf','scale=1080:1440:flags=lanczos,setsar=1','-r','25','-c:v','libx264','-preset','veryfast','-crf','23','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-threads','2','-y',str(outro)])
    concat=out/'concat.txt';concat.write_text('\n'.join("file '"+str(out/f'part_{i:02d}.mp4')+"'" for i in range(len(results)))+"\nfile '"+str(outro)+"'\n")
    final=out/'shelton-ncaa-story.mp4';run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(concat),'-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-c:a','aac','-b:a','160k','-ar','48000','-movflags','+faststart','-y',str(final)])
    expected=sum(seconds(out/f'part_{i:02d}.mp4') for i in range(len(results)))+seconds(outro)
    if abs(seconds(final)-expected)>0.15:raise RuntimeError('Final concat was truncated')
    (out/'render.json').write_text(json.dumps({'slug':spec['slug'],'duration':seconds(final),'width':1080,'height':1440,'beats':results,'qc_status':'pending_visual_audio_review'},ensure_ascii=False,indent=2))
    print(final,flush=True)


if __name__=='__main__':main()
