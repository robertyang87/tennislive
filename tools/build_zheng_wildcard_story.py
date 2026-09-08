#!/usr/bin/env python3
"""Use the same native explainer template as wawrinka-wildcard (August 27).

No alternate card compositor or CSS: all cards use explainer._slide_html, exactly as wawrinka-wildcard.
Requires repository assets, Playwright Chromium and the normal tennislive TTS deps.
"""
from pathlib import Path
import argparse, json, subprocess, sys, html, re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca()
from tennislive.video import explainer as E
E._ASS_FONT='Noto Sans SC'
ASSETS=ROOT/'assets/explainer/zheng-wildcards'

def diagram(c):
    # Episode-specific contents inside the existing Wawrinka SVG content slot.
    big=html.escape(c['big']); fs=min(82,760//max(1,len(c['big'])))
    rows=''.join(f'<text x="78" y="{310+i*76}" fill="#f4fbf7" font-size="30" font-weight="700">{html.escape(line)}</text>' for i,line in enumerate(c['lines']))
    return f'''<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
    <text x="450" y="48" text-anchor="middle" fill="#cfe6d8" font-size="26" font-weight="700">{html.escape(c['tag'].split('/')[-1].strip())}</text>
    <rect x="48" y="85" width="804" height="150" rx="14" fill="rgba(198,246,90,.10)" stroke="#c6f65a" stroke-width="2"/>
    <text x="450" y="180" text-anchor="middle" fill="#c6f65a" font-size="{fs}" font-weight="800">{big}</text>
    <rect x="48" y="265" width="804" height="265" rx="14" fill="rgba(143,214,168,.16)"/>{rows}
    </svg>'''

def evidence(filename):
    # Show the supplied account header and complete post text; omit app chrome below.
    uri=E._data_uri(ASSETS/filename)
    return f'<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg"><defs><clipPath id="post"><rect width="900" height="600" rx="14"/></clipPath></defs><image href="{uri}" width="900" height="1436" preserveAspectRatio="xMinYMin meet" clip-path="url(#post)"/></svg>'

def segments(data):
    out=[]
    for i,c in enumerate(data['cards'][:-1]):
        title=['中网外卡来了，武网怎么办？','赛事发卡，球员还要算额度','全年六次，正赛最多三次','已用两次，中网将是第三次','奥运冠军，也要对照豁免条款','同一份成绩，两道截止线','美网成绩，赶得上武网报名','武网如今也是强制参赛','五十六签，不等于前五十六','去年直入线，卡在第四十一','今年的正赛名单，尚未公布','你的猜想，规则上有条件成立','八强不是门槛，胜利增加选择'][i]
        label=c['tag'].split('/')[-1].strip()
        if i==0:
            out.append(E.ExplainerSegment(kind='cover',label='网球有故事',title='中网外卡来了，武网怎么办？',narration=c['narration'],image='assets/reel/zheng-us-open-2026-r4.jpg',credit='AP / Seth Wenig · 美网第四轮'))
            out.append(E.ExplainerSegment(kind='announcement',label='官宣',title='中网确认，她将出战正赛',narration='中网官宣，郑钦文确认参加今年正赛。她在报名截止时的排名不足以直接入围，这次拿到的是正赛外卡。北京的门打开了，可她今年常规正赛外卡只剩最后一次，武汉怎么办？',diagram=evidence('china-open-announcement.jpg'),credit='用户提供 · 中网ChinaOpen微博截图',points=('截止时排名不足以直接入围','本次凭正赛外卡出战中网')))
            out.append(E.ExplainerSegment(kind='poster',label='北京之约',title='北京确定了，武汉怎么进？',narration='北京这一站已经明确。接下来的问题是：她还剩多少次接正赛外卡的额度，武汉又能不能靠排名进去？先把规则里的两本账分开。',image='assets/explainer/zheng-wildcards/china-open-poster.jpg',credit='用户提供 · 2026中网郑钦文参赛海报'))
        else:
            out.append(E.ExplainerSegment(kind='rule',label=label,title=title,narration=c['narration'],diagram=diagram(c),credit=c['source'],points=()))
    return out

def runner(cmd,**kw):
    if cmd[0]=='ffmpeg':
        cmd=list(cmd)
        if '-preset' in cmd:cmd[cmd.index('-preset')+1]='ultrafast'
        cmd[1:1]=['-threads','2','-filter_complex_threads','1']
        if '-filter_complex' in cmd:
            j=cmd.index('-filter_complex')+1
            cmd[j]=re.sub(r"subtitles='([^']+)'",lambda m:m.group(0)+":fontsdir='"+str(ROOT/'assets/fonts')+"'",cmd[j])
        cmd[-1:-1]=['-threads','2']
    return subprocess.run(cmd,**kw)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--cards-only',action='store_true');a=ap.parse_args()
    out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'specs/explainers/zheng-china-wuhan-wildcards.json').read_text())
    beats=segments(data)
    # A shared page supports single-process Chromium without changing the template.
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    slides=[]
    with sync_playwright() as pw:
        browser=launch_chromium(pw)
        page=browser.new_page(viewport={'width':E.W,'height':E.H},device_scale_factor=2)
        for i,beat in enumerate(beats):
            html_path=out/f'slide_{i:02d}.html'
            html_path.write_text(E._slide_html(i,beat,topic='郑钦文的中国赛季',column='网球有故事'))
            page.goto(html_path.as_uri())
            page.wait_for_function("document.fonts.status === 'loaded' && Array.from(document.images).every(i=>i.complete)")
            path=out/f'slide_{i:02d}.jpg'
            page.screenshot(path=str(path),type='jpeg',quality=86)
            slides.append(path)
            print('Native card',i+1,flush=True)
        browser.close()
    from PIL import Image
    sheet=Image.new('RGB',(1080,360*((len(slides)+3)//4)),'#061c14')
    for i,p in enumerate(slides):sheet.paste(Image.open(p).resize((270,360)),((i%4)*270,(i//4)*360))
    sheet.save(out/'contact-sheet.jpg')
    (out/'narration.json').write_text(json.dumps([{'title':s.title,'narration':s.narration} for s in beats],ensure_ascii=False,indent=2))
    if a.cards_only:return
    audios=E.synthesize_narration(beats,out,rate='+22%')
    outro=ROOT/'assets/brand/outro_master.mp4'
    if not outro.is_file():raise FileNotFoundError('Native brand outro is required')
    E.assemble_explainer_video(slides,audios,out/'zheng-wildcards-template.mp4',captions=[s.narration for s in beats],outro=outro,runner=runner)
    print(out/'zheng-wildcards-template.mp4',flush=True)
if __name__=='__main__':main()
