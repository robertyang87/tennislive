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
 'street':'2001年纽约街头资料照',
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
    beats=[E.ExplainerSegment(kind='cover' if i==0 else 'photo',label=c['label'],title=c['title'],narration=c['narration'],image=f"assets/explainer/hewitt-911-25/{c['image']}.jpg",credit=CREDITS[c['image']],points=c['points']) for i,c in enumerate(data['cards'])]
    slides=[out/f'slide_{i:02d}.jpg' for i in range(len(beats))]
    if a.voice_only:
        E.synthesize_narration(beats,out,rate='+8%');return
    if not a.assemble_only:
        from playwright.sync_api import sync_playwright
        from tennislive.chromium import launch_chromium
        with sync_playwright() as pw:
            browser=launch_chromium(pw);page=browser.new_page(viewport={'width':E.W,'height':E.H},device_scale_factor=2)
            for i,(c,beat,path) in enumerate(zip(data['cards'],beats,slides)):
                h=E._slide_html(i,beat,topic='九一一25周年 · 休伊特的纽约告别',column=data['column'])
                photo_dates={'street':'纽约 · 2001年9月','sampras':'美网颁奖 · 2001年9月9日','trophy':'美网 · 2001年9月9日','action':'美网颁奖 · 2001年9月9日','press':'纽约发布会 · 2001年9月10日','newyork':'纽约 · 2001年资料照','smoke':'纽约 · 2001年9月11日','wimbledon':'温网颁奖 · 2002年7月7日','memorial':'纽约纪念之光 · 2014年资料照'}
                stamp=html.escape(photo_dates[c['image']])
                h=h.replace('</body>',f'<div style="position:absolute;bottom:28px;left:70px;color:#cfe6d8;font-size:20px;text-shadow:0 2px 6px #061c14">{stamp}</div></body>')
                hp=out/f'slide_{i:02d}.html';hp.write_text(h)
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
    E.assemble_explainer_video(slides,audios,out/'hewitt-911-25-dry.mp4',captions=[s.narration for s in beats],outro=ROOT/'assets/brand/outro_master.mp4',canvas_h=1920,runner=runner)
    print(out/'hewitt-911-25-dry.mp4',flush=True)

if __name__=='__main__':main()
