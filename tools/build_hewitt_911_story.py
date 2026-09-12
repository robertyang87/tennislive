#!/usr/bin/env python3
"""Render the 25th-anniversary story with the repository's native photo cards."""
from pathlib import Path
import argparse, json, subprocess, sys, html, re, os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca()
from tennislive.video import explainer as E

# Preserve the event name before the shared Chinese-number formatter.
_original_arabic_numerals=E.arabic_numerals
E.arabic_numerals=lambda text:_original_arabic_numerals(text.replace('九一一','EVENTNAME')).replace('EVENTNAME','九一一')

CREDITS={
 'sampras':'C. Newsom / AFP · L’Équipe',
 'action':'Tennis World USA · 2001年美网颁奖资料照',
 'street':'用户提供的历史照片 · 摄影者未核实',
 'trophy':'Jamie Squire / Allsport / Getty Images · Tennis.com',
 'press':'Jamie Squire / Allsport / Getty Images · Tennis.com',
 'wimbledon':'Clive Brunskill / Getty Images · Tennis.com',
 'newyork':'Carol M. Highsmith / Library of Congress · Public domain',
 'smoke':'Michael Foran · CC BY 2.0 · Flickr',
 'memorial':'Anthony Quintano · CC BY 2.0 · Flickr',
}

def runner(cmd,**kw):
    cmd=list(cmd)
    if cmd[0]=='ffmpeg':
        if '-preset' in cmd:cmd[cmd.index('-preset')+1]='veryfast'
        cmd[1:1]=['-threads','2','-filter_complex_threads','1']
        cmd[-1:-1]=['-threads','2']
    return subprocess.run(cmd,**kw)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True)
    ap.add_argument('--use-existing-audio',action='store_true');ap.add_argument('--cards-only',action='store_true');ap.add_argument('--assemble-only',action='store_true');ap.add_argument('--voice-only',action='store_true')
    a=ap.parse_args();out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'specs/explainers/hewitt-911-25.json').read_text())
    beats=[E.ExplainerSegment(kind='cover' if i==0 else 'photo',label=c['label'],title=c['title'],narration=c['narration'],image=f"assets/explainer/hewitt-911-25/{c['image']}.jpg",credit=CREDITS[c['image']],gloss=c['note']) for i,c in enumerate(data['cards'])]
    slides=[out/f'slide_{i:02d}.jpg' for i in range(len(beats))]
    if a.voice_only:
        E.synthesize_narration(beats,out,rate='+8%');return
    if not a.assemble_only:
        from playwright.sync_api import sync_playwright
        from tennislive.chromium import launch_chromium
        with sync_playwright() as pw:
            browser=launch_chromium(pw);page=browser.new_page(viewport={'width':E.W,'height':E.H},device_scale_factor=1)
            for i,(c,beat,path) in enumerate(zip(data['cards'],beats,slides)):
                h=E._slide_html(i,beat,topic='九一一25周年 · 休伊特的纽约告别',column=data['column'])
                # Preserve native typography and layout; remove old pill labels.
                css='''<style>
                body{font-family:'TL Sans SC','Noto Sans CJK SC',sans-serif}
                .chip,.kicker{background:transparent;color:#d8dbac;padding:0;border-radius:0;font-size:28px;letter-spacing:1px;font-weight:500}
                .copy{gap:24px;bottom:225px}
                .title{font-size:62px!important;white-space:normal;text-wrap:balance}
                .cover .title{font-size:88px!important;line-height:1.2}
                .gloss{font-family:'Noto Sans CJK SC',sans-serif;font-size:28px;line-height:1.5;font-weight:400;color:#cedbd4}
                .topic{font-family:'Noto Sans CJK SC',sans-serif;font-size:24px;font-weight:400;color:#c6d0cb}
                .brand{color:#f4f4ed}.brand-icon{width:46px;height:46px}
                .credit{position:absolute;left:70px;right:70px;bottom:46px;color:#aebbb4;font:18px 'Noto Sans CJK SC',sans-serif;z-index:6}
                .folio{position:absolute;right:70px;top:147px;font:24px 'Noto Sans CJK SC',sans-serif;color:#c6d0cb;z-index:6}
                .cover .hero{background-size:auto 1050px!important;background-position:50% 155px!important;background-repeat:no-repeat}
                .cover .copy{bottom:230px}.cover .kicker{font-size:30px}
                </style>'''
                h=h.replace('</head>',css+'</head>')
                if i==0:h=h.replace('>网球有故事</span>',f'>{html.escape(c["label"])}</span>')
                else:h=re.sub(r'(<span class="chip">)[^<]+',r'\g<1>'+html.escape(c['label']),h)
                extra=f'<div class="credit">{html.escape(beat.credit)}</div><div class="folio">{i+1:02d} / {len(beats):02d}</div>'
                h=h.replace('</body>',extra+'</body>');hp=out/f'slide_{i:02d}.html';hp.write_text(h)
                page.goto(hp.as_uri());page.wait_for_function("document.fonts.status==='loaded'")
                page.screenshot(path=str(path),type='jpeg',quality=95)
                print('card',i+1,flush=True)
            browser.close()
        from PIL import Image
        sheet=Image.new('RGB',(1080,360*((len(slides)+3)//4)),'#061c14')
        for i,p in enumerate(slides):sheet.paste(Image.open(p).resize((270,360)),((i%4)*270,(i//4)*360))
        sheet.save(out/'contact-sheet.jpg')
    (out/'narration.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    if a.cards_only:return
    audios=[out/f'voice_{i:02d}.mp3' for i in range(len(beats))] if a.use_existing_audio else E.synthesize_narration(beats,out,rate='+8%')
    E.assemble_explainer_video(slides,audios,out/'hewitt-911-25-dry.mp4',captions=[s.narration for s in beats],outro=ROOT/'assets/brand/outro_master.mp4',canvas_h=1440,runner=runner)
    print(out/'hewitt-911-25-dry.mp4',flush=True)

if __name__=='__main__':main()
