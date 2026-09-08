#!/usr/bin/env python3
"""Data-driven card episode; reuse tennislive TTS, word timing and video assembly.

Pillow card compositor makes this episode runnable without a browser download.
Run: PYTHONPATH=src python tools/build_zheng_wildcard_story.py --outdir /tmp/zheng-story
The input is editorially frozen at 2026-09-08; recheck entries before republishing.
"""
from pathlib import Path
import argparse, json, subprocess, os, sys
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageOps
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca()
from tennislive.video import explainer as E
E._ASS_FONT = "Noto Sans SC"
BG='#061c14'; FG='#f4f4e8'; LIME='#d5f35a'; MUTED='#a7bdb1'
@lru_cache(maxsize=128)
def font(n,bold=True):
    return ImageFont.truetype(str(ROOT/'assets/fonts'/('NotoSansSC-Bold-sub.ttf' if bold else 'NotoSansSC-Regular-sub.ttf')),n)
def text(d,xy,s,n=42,color=FG,bold=True):
    s=s.replace("｜", " | ").replace("／", " / ")
    x,y=xy
    fallback=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',n)
    for line in s.split('\n'):
        xx=x
        for ch in line:
            f=fallback if ch in '–→≠①②③／｜' else font(n,bold)
            d.text((xx,y),ch,font=f,fill=color)
            xx+=d.textlength(ch,font=f)
        y+=n+30
def fit(d,s,width,n=42):
    while d.textlength(s,font=font(n))>width: n-=1
    return n

def card(i,c,out,total):
    im=Image.new('RGB',(1080,1440),BG)
    if c.get('photo'):
        photo=Image.open(ROOT/'assets/reel/zheng-us-open-2026-r4.jpg').convert('RGB')
        photo=ImageOps.fit(photo,(1080,1000),centering=(.5,.25))
        im.paste(photo,(0,0))
        shade=Image.new('RGBA',im.size,(0,0,0,0)); sd=ImageDraw.Draw(shade)
        for y in range(1440):
            a=160 if y<100 else int(max(0,min(255,(y-430)/470*255)))
            sd.line((0,y,1080,y),fill=(6,28,20,a))
        im=Image.alpha_composite(im.convert('RGBA'),shade).convert('RGB')
    d=ImageDraw.Draw(im)
    text(d,(64,38),'网球时差  /  网球有故事',30)
    d.line((64,96,1016,96),fill=LIME,width=3)
    # Keep y=1260–1340 clear for the engine's timed subtitles.
    ty=860 if c.get('photo') else 260
    text(d,(64,ty-65),c['tag'],29,LIME)
    text(d,(64,ty),c['title'],82 if c.get('photo') else 74)
    if not c.get('photo'):
        d.rounded_rectangle((64,530,1016,805),radius=24,fill='#173c2b',outline='#416544',width=2)
        text(d,(100,565),'规则 / 事实',26,MUTED)
        text(d,(100,637),c['big'],fit(d,c['big'],880,88),LIME)
        for k,line in enumerate(c['lines']):
            yy=885+k*105
            d.ellipse((67,yy+20,77,yy+30),fill=LIME)
            text(d,(100,yy),line,fit(d,line,885,39))
    else:
        text(d,(64,1135),c['lines'][0],fit(d,c['lines'][0],950,37),LIME)
    text(d,(64,1200),c['source'],fit(d,c['source'],950,23),MUTED,False)
    text(d,(64,1360),'ZHENG QINWEN  /  2026',22,MUTED)
    text(d,(913,1354),f'{i+1:02d} / {total:02d}',25,MUTED)
    d.rectangle((64,1420,64+int(952*(i+1)/total),1425),fill=LIME)
    path=out/f'slide_{i:02d}.jpg';im.save(path,quality=95);return path

def runner(cmd,**kw):
    if cmd[0]=='ffmpeg':
        cmd=list(cmd)
        if '-preset' in cmd:cmd[cmd.index('-preset')+1]='ultrafast'
        cmd[1:1]=['-threads','2','-filter_complex_threads','1']
        if '-filter_complex' in cmd:
            import re
            j=cmd.index('-filter_complex')+1
            cmd[j]=re.sub(r"subtitles='([^']+)'",lambda m:m.group(0)+":fontsdir='"+str(ROOT/'assets/fonts')+"'",cmd[j])
        cmd[-1:-1]=['-threads','2']
    return subprocess.run(cmd,**kw)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--cards-only',action='store_true');a=ap.parse_args()
    data=json.loads((ROOT/'specs/explainers/zheng-china-wuhan-wildcards.json').read_text());out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    from fontTools.ttLib import TTFont
    cmap=TTFont(str(ROOT/'assets/fonts/NotoSansSC-Bold-sub.ttf')).getBestCmap()
    content=''.join(c['title']+c['big']+''.join(c['lines'])+c['tag']+c['source'] for c in data['cards'])
    missing=sorted(set(ch for ch in content if ord(ch)>127 and ord(ch) not in cmap))
    if set(missing)-set('–→≠①②③／｜'): raise RuntimeError('Missing font glyphs: '+''.join(missing))
    slides=[card(i,c,out,len(data['cards'])) for i,c in enumerate(data['cards'])]
    preview=Image.new('RGB',(1080,360*((len(slides)+3)//4)),BG)
    for i,p in enumerate(slides):preview.paste(Image.open(p).resize((270,360)),((i%4)*270,(i//4)*360))
    preview.save(out/'contact-sheet.jpg',quality=90)
    (out/'narration.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    if a.cards_only:return
    segments=[E.ExplainerSegment(kind='fact',label=c['tag'],title=c['title'],narration=c['narration']) for c in data['cards']]
    print('Narrating',len(segments),'cards',flush=True)
    audios=E.synthesize_narration(segments,out,rate='+22%')
    print('Rendering video',flush=True)
    E.assemble_explainer_video(slides,audios,out/'zheng-wildcards.mp4',captions=[c['narration'] for c in data['cards']],runner=runner)
    print(out/'zheng-wildcards.mp4',flush=True)
if __name__=='__main__':main()
