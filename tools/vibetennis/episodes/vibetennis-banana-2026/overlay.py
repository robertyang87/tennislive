"""vibetennis EP14 不是补钾：字幕与出处叠加层（VT_LANG=zh|en）。

用法：python3 overlay.py <3D 母带.mp4 或 concat 列表.txt> <输出.mp4> <分段锚点.json ...>；python3 overlay.py still <静帧.jpg ...>
通用函数（字体、字幕框、品牌标、span）沿用 EP07；文案时间跟着 narration.json 的 at 走（plan.py 排定）。
3D 场景里已经有标签（尺寸、张力表、年代、弹道、扇形），这里只补**画面上没有的上下文**，统一放底部；英文版另把旁白译成英文字幕（docs/vibetennis.md §8）。
每一条都只讲 papers/vibetennis-banana-2026/sources.md 里核过、可上屏的内容；只采用审核台账中的强／中主张；数字带条件，弱主张不上屏。
"""
import skia, numpy as np, math, json, sys, subprocess, glob, os
W,H,FPS=1920,1080,30
HERE=os.path.dirname(os.path.abspath(__file__))
REPO=os.path.abspath(os.path.join(HERE,'../../../..'))
WORK=os.environ.get('VT_WORK',HERE)  # 渲染中间产物目录（r3d/seg、sfx/），默认就是本目录
def snap(t): return t
LANG=os.environ.get('VT_LANG','zh')
def tr(zh,en): return en if LANG=='en' else zh
if LANG=='en':
    SANS=skia.Typeface.MakeFromName('Inter',skia.FontStyle.Bold()); SANSR=skia.Typeface.MakeFromName('Inter',skia.FontStyle.Normal())
    MONO=skia.Typeface.MakeFromName('Noto Sans Mono',skia.FontStyle.Normal())
else:
    SANS=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Bold()); SANSR=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Normal())
    MONO=skia.Typeface.MakeFromName('Noto Sans Mono CJK SC',skia.FontStyle.Normal())
SERIF=skia.Typeface.MakeFromName('Noto Serif CJK SC',skia.FontStyle.Bold())
GOLD=(1.0,0.72,0.30); CYAN=(0.45,0.88,1.0); WHITE=(1,1,1); GRAY=(0.6,0.66,0.75)
FC={}
def F(tf,size):
    k=(id(tf),size)
    if k not in FC: f=skia.Font(tf,size); f.setSubpixel(True); FC[k]=f
    return FC[k]
def col(c,a): return skia.Color4f(c[0],c[1],c[2],max(0,min(1,a)))
def P(c,a=1,stroke=None,blur=0):
    p=skia.Paint(AntiAlias=True,Color=col(c,a))
    if stroke: p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke); p.setStrokeCap(skia.Paint.kRound_Cap)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle,blur))
    return p
def ease(x): x=max(0,min(1,x)); return x*x*(3-2*x)
def seg_runs(s):
    out=[]; hi=False; buf=''
    for ch in s:
        if ch in '【】':
            if buf: out.append((buf,hi))
            buf=''; hi=(ch=='【'); continue
        buf+=ch
    if buf: out.append((buf,hi))
    return out
def rich(c,s,x,y,size,a,tf=None,align='c',reveal=None,glow=True,base=WHITE):
    tf=tf or SANS; f=F(tf,size); runs=seg_runs(s)
    chars=[(ch,hi) for r,hi in runs for ch in r]
    w=sum(f.measureText(ch) for ch,_ in chars)
    x0=x-w/2 if align=='c' else (x-w if align=='r' else x)
    cx=x0; n=len(chars)
    for i,(ch,hi) in enumerate(chars):
        ca=a
        if reveal is not None: ca=a*ease((reveal-i*0.028)/0.22)
        dy=(1-ease((reveal-i*0.028)/0.22))*10 if reveal is not None else 0
        cc=GOLD if hi else base
        c.drawString(ch,cx,y+dy,f,P((0,0,0),ca*0.75,blur=size*0.18))
        if hi and glow: c.drawString(ch,cx,y+dy,f,P(GOLD,ca*0.55,blur=size*0.22))
        c.drawString(ch,cx,y+dy,f,P(cc,ca))
        cx+=f.measureText(ch)
    return w
def text(c,s,x,y,size,cc=WHITE,a=1,tf=None,align='c',glow=0,spacing=0):
    tf=tf or SANS; f=F(tf,size)
    if spacing:
        w=sum(f.measureText(ch) for ch in s)+spacing*(len(s)-1)
        cx=x-w/2 if align=='c' else (x-w if align=='r' else x)
        for ch in s:
            if glow: c.drawString(ch,cx,y,f,P(cc,a*glow,blur=size*0.25))
            c.drawString(ch,cx,y,f,P(cc,a)); cx+=f.measureText(ch)+spacing
        return w
    w=f.measureText(s); x0=x-w/2 if align=='c' else (x-w if align=='r' else x)
    if glow: c.drawString(s,x0,y,f,P(cc,a*glow,blur=size*0.25))
    c.drawString(s,x0,y,f,P(cc,a)); return w
def wrap_zh(s,size,maxw=930,tf=None):
    f=F(tf or SANS,size); lines=[]; cur=''
    tot=f.measureText(s.replace('【','').replace('】',''))
    if tot>maxw: n=math.ceil(tot/maxw); maxw=tot/n+size*1.2
    for ch in s:
        test=(cur+ch).replace('【','').replace('】','')
        if f.measureText(test)>maxw and ch not in '，。：；、”）】':
            lines.append(cur); cur=ch
        else: cur+=ch
    if cur: lines.append(cur)
    # carry open highlight across lines
    out=[]; openhi=False
    for l in lines:
        s2=('【' if openhi else '')+l
        o=s2.count('【'); cl=s2.count('】'); openhi = o>cl
        out.append(s2+('】' if openhi else ''))
    return out
def wrap_en(s,size,maxw=930,tf=None):
    import re as _re
    f=F(tf or SANS,size); strip=lambda x:x.replace('【','').replace('】','')
    s=_re.sub(r'【[^】]*】',lambda m:m.group(0).replace(' ','\u00a0'),s)
    s=_re.sub(r'(\d) (?=(cm|mm|ms|s|km/h|fps|%)\b)','\\1\u00a0',s)
    tot=f.measureText(strip(s))
    if tot>maxw: n=math.ceil(tot/maxw); maxw=tot/n+size*1.2
    lines=[]; cur=''
    for w in s.split(' '):
        test=(cur+' '+w) if cur else w
        if cur and f.measureText(strip(test))>maxw: lines.append(cur); cur=w
        else: cur=test
    if cur: lines.append(cur)
    out=[]; openhi=False
    for l in lines:
        s2=('【' if openhi else '')+l
        o=s2.count('【'); cl=s2.count('】'); openhi = o>cl
        out.append(s2+('】' if openhi else ''))
    return out
def wrap(s,size,maxw=930,tf=None):  # 文案里写了 \n 就按它分行（语义分行，别让自动折行把一个词拆开）
    return [l for p in s.split('\n') for l in (wrap_en if LANG=='en' else wrap_zh)(p,size,maxw,tf)]
def hudlabel(c,x,y,s,a,cc=CYAN,dx=60,dy=-60,size=28,align='l'):
    # leader line from anchor to label
    c.drawCircle(x,y,6,P(cc,a,stroke=2)); c.drawCircle(x,y,2.5,P(cc,a))
    lx,ly=x+dx,y+dy
    path=skia.Path(); path.moveTo(x,y); path.lineTo(lx,ly); path.lineTo(lx+(150 if align=='l' else -150)*0.4,ly)
    c.drawPath(path,P(cc,a*0.8,stroke=1.6))
    text(c,s,lx+(10 if align=='l' else -10),ly-10,size,cc,a,MONO,align=align,glow=0.4)
def bracketbox(c,x,y,w,h,a,cc=CYAN):
    k=18; p=P(cc,a,stroke=2)
    for (px,py,sx,sy) in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
        c.drawLine(px,py,px+sx*k,py,p); c.drawLine(px,py,px,py+sy*k,p)
    c.drawRect(skia.Rect.MakeXYWH(x,y,w,h),P((0.02,0.05,0.1),a*0.45))


def onscreen(v,m=90): return bool(v) and v[2] and m<v[0]<W-m and m<v[1]<H-m
def caption(c,t,s,d,txt,pl,an):
    a=min(1,(t-s)/0.25,(s+d+0.35-t)/0.35)
    if a<=0: return
    size=50; leader=None
    if pl[0]=='s':
        x,y,al=pl[1],pl[2],pl[3]; size=pl[4] if len(pl)>4 else size
    else:
        _,k,dx,dy,al,fx,fy=pl[:7]; size=pl[7] if len(pl)>7 else size; v=an.get(k)
        if onscreen(v): x,y=v[0]+dx,v[1]+dy; leader=(v[0],v[1])
        else: x,y=fx,fy
    ls=wrap(txt,size,maxw=1560)
    lh=size*1.42; ws=[F(SANS,size).measureText(l.replace('【','').replace('】','')) for l in ls]; bw=max(ws)
    lo=80+(bw if al==R else bw/2 if al==C else 0); hi=W-80-(0 if al==R else bw/2 if al==C else bw)
    x=max(lo,min(hi,x)); y=max(110+size,min(H-60-(len(ls)-1)*lh,y))
    bx=x-(bw if al==R else bw/2 if al==C else 0)
    c.drawRect(skia.Rect.MakeXYWH(bx-40,y-size*1.15,bw+80,lh*len(ls)+size*0.5),P((0,0,0),a*0.32,blur=36))
    if leader:
        lx,ly=leader
        if al==L: ex,ey=bx-18,y-size*0.45
        elif al==R: ex,ey=bx+bw+18,y-size*0.45
        else: ex,ey=x,(y-size*1.2 if ly<y else y+(len(ls)-1)*lh+18)
        c.drawCircle(lx,ly,7,P(CYAN,a,stroke=2)); c.drawCircle(lx,ly,2.5,P(CYAN,a))
        c.drawLine(lx,ly,ex,ey,P(CYAN,a*0.55,stroke=1.4))
    if al!=C:
        ax=bx-18 if al==L else bx+bw+18
        c.drawLine(ax,y-size*0.95,ax,y+(len(ls)-1)*lh+size*0.15,P(GOLD,a*0.85,stroke=3))
    for i,l in enumerate(ls):
        rich(c,l,x,y+i*lh,size,a,SANS,align=al,reveal=(t-s)*1.0-i*0.15)


# ---- top-left brand: official 网球时差 ball-clock icon + wordmark ----
# text size = old mark (22px); icon height = 22px; vertically centred on the
# top-right chip line (chip ink y59..86, centre 72.5); left margin mirrors chip right margin (182)
from PIL import Image as _PI
BRAND_X=182; BRAND_SIZE=22; BRAND_ICON=22; BRAND_GAP=9; BRAND_BASE=81
def _load_icon():
    im=_PI.open(os.path.join(REPO,'assets/logo/brand/account/icon-transparent-1024.png')).convert('RGBA')
    im=im.crop(im.split()[3].getbbox()).resize((BRAND_ICON,BRAND_ICON),_PI.LANCZOS)
    a=np.array(im).astype(np.float32); a[...,:3]*=a[...,3:4]/255.0
    return skia.Image.fromarray(np.ascontiguousarray(a.round().astype(np.uint8)),colorType=skia.kRGBA_8888_ColorType,alphaType=skia.kPremul_AlphaType)
_ICON=None
def brand(c):
    global _ICON
    if _ICON is None: _ICON=_load_icon()
    cy=BRAND_BASE-8  # ink centre of 22px CJK (ink -19..+3)
    y0=cy-BRAND_ICON/2
    c.drawCircle(BRAND_X+BRAND_ICON/2,cy,BRAND_ICON/2+1,P((0,0,0),0.45,blur=4))
    c.drawImageRect(_ICON,skia.Rect.MakeXYWH(BRAND_X,y0,BRAND_ICON,BRAND_ICON),skia.SamplingOptions(skia.FilterMode.kLinear),skia.Paint(AntiAlias=True))
    text(c,tr("网球时差","Tennis Jetlag"),BRAND_X+BRAND_ICON+BRAND_GAP,BRAND_BASE,BRAND_SIZE,WHITE,0.88,SANS,align='l',spacing=1)

L,R,C='l','r','c'
NAR=json.load(open(os.path.join(HERE,'narration.json')))
AT={l['file']:l['at'] for l in NAR['lines']}
def speak(f):
    wb=json.load(open(os.path.join(HERE,'voice',f+'.json'))); return AT[f]+wb[0]['off'], AT[f]+wb[-1]['off']+wb[-1]['dur']
ORDER=[l['file'] for l in NAR['lines']]
def span(f,off=0.0,until=None,pad=0.25):
    """字幕起止：从句子 f 开口后 off 秒起；until=None 到下一句开口前，数字＝持续秒数，句子名＝到那句开口前。
    第 2 版旁白只有 20 句、句间留白长，所以一句底下可以挂几条字幕，用 off 往后排。"""
    s,e=speak(f); s=s+off
    if isinstance(until,(int,float)): return s-0.1, until
    if until: e=speak(until)[0]-pad
    else:
        i=ORDER.index(f); e=(speak(ORDER[i+1])[0]-pad) if i+1<len(ORDER) else e+2.5
    return s-0.1, max(1.0,e-s+0.1)
TL=json.load(open(os.path.join(HERE,'r3d','timeline.json')))
TOP=('s',960,205,C,44); BOT=('s',960,965,C,44)
# (句子, 开口后几秒起, 持续[None=到下一句开口/秒数], 文案, 位置)
CAPS=[
('p1',0.3,None,tr("USDA FDC 173944：中等香蕉可食部约 118 g；约 27 g 碳水、14 g 糖、3 g 纤维、105 千卡","USDA FDC 173944: medium banana, ~118 g edible; about 27 g CHO, 14 g sugar, 3 g fibre, 105 kcal"),('s',960,1008,C,28)),
('p2',0.3,None,tr("同一份：钾 422 mg","Same entry: 422 mg potassium"),('s',960,1008,C,28)),
('p3',0.3,None,tr("Atkinson 等 2008 年国际表：香蕉 GI 均值 51±3（低 GI）。2021 表：过熟可到 57","Atkinson et al. 2008 international table: banana GI mean 51±3 (low). 2021 table: overripe may reach 57"),('s',960,1008,C,28)),
('k1',0.3,None,tr("Baker 2019：11 名休闲运动员，30°C、90 分钟骑车，中等强度。不是网球。","Baker 2019: 11 recreational athletes, 30°C, 90-min cycling, moderate intensity. Not tennis."),('s',960,1008,C,28)),
('k3',0.3,None,tr("Schwellnus 2004 / 2005 / 2009 / 2011：耐力赛队列与综述。不是网球。","Schwellnus 2004 / 2005 / 2009 / 2011: endurance cohorts and a review. Not tennis."),('s',960,1008,C,28)),
('g1',0.3,None,tr("网球场上没有查到肌糖原活检；指南把比赛中的碳水写成补贴糖原的燃料","No muscle-glycogen biopsy was found in tennis; guidelines describe in-match CHO as topping up glycogen"),('s',960,1008,C,28)),
('g2',0.3,None,tr("Vicente-Salar 等，2025，ITF/WTA/ATP 专家声明，IJSNEM 35:557–594，Table 3","Vicente-Salar et al., 2025, ITF/WTA/ATP expert statement, IJSNEM 35:557–594, Table 3"),('s',960,1008,C,28)),
('e1',0.3,None,tr("Vergauwen 等 1998，Med Sci Sports Exerc：13 名男选手，双盲交叉，0.7 g/kg/h","Vergauwen et al. 1998, Med Sci Sports Exerc: 13 men, double-blind crossover, 0.7 g/kg/h"),('s',960,1008,C,28)),
('e2',0.3,None,tr("McRae & Galloway 2012，IJSNEM：22 人，室内 2 小时；68±7% 对 66±7%，一发 65±9% 对 61±7%","McRae & Galloway 2012, IJSNEM: 22 players, 2 h indoors; 68±7% vs 66±7%, first serve 65±9% vs 61±7%"),('s',960,1008,C,28)),
('e3',0.3,None,tr("Mitchell 等 1992：12 名选手，3 小时比赛，7.5% 碳水饮料对水；血糖升高，表现无好处","Mitchell et al. 1992: 12 players, 3-h match, 7.5% CHO vs water; glucose up, no performance benefit"),('s',960,1008,C,28)),
('e4',0.3,None,tr("Nieman 等 2012，PLoS ONE：14 名男自行车手，75 km；Dole 资助；2.41±0.22 h 对 2.36±0.19 h","Nieman et al. 2012, PLoS ONE: 14 male cyclists, 75 km; Dole-funded; 2.41±0.22 h vs 2.36±0.19 h"),('s',960,1008,C,28)),
('e5',0.3,None,tr("检索未找到网球比赛中吃香蕉的随机对照","No randomised trial of bananas in tennis was found"),('s',960,1008,C,28)),
('c1',0.3,None,tr("6 g/100 mL × 450 mL = 27 g，按浓度算；与一根中等香蕉的碳水大约相当","6 g/100 mL × 450 mL = 27 g, by concentration; about the same CHO as a medium banana"),('s',960,1008,C,28)),
('c2',0.3,None,tr("美枣：USDA FDC 168191，一颗去核约 24 g，约 18 g 碳水","Medjool date: USDA FDC 168191, one pitted date ~24 g, about 18 g CHO"),('s',960,1008,C,28)),
('c3',0.3,None,tr("BBC Sport 文字直播，Tom Fordyce，2010 年温网男单半决赛，穆雷 4–6、第二盘 2–2 的一次换边","BBC Sport live text, Tom Fordyce, 2010 Wimbledon men's SF, Murray 4–6, 2–2 in the second, one changeover"),('s',960,1008,C,28)),
('n3',0.3,None,tr("更站得住的理由，是补糖。防抽筋还没有被证明。","The more defensible reason is carbohydrate. Preventing cramp has not been shown."),TOP),
]
CAPS=[(*span(f,o,u),txt,pl) for f,o,u,txt,pl in CAPS]
# 英文版：旁白译成英文字幕，跟着中文旁白的时间（docs/vibetennis.md §8）
EN={l['file']:l.get('en') for l in NAR['lines']}
SUBS=[(f,*speak(f)) for f in ORDER] if LANG=='en' else []
def sub(c,t):
    for i,(f,s0,e0) in enumerate(SUBS):
        e1=min(e0+0.5,SUBS[i+1][1]-0.1) if i+1<len(SUBS) else e0+1.5
        if s0-0.1<=t<e1 and EN.get(f):
            a=min(1,(t-s0+0.1)/0.2,(e1-t)/0.25); ls=wrap(EN[f],34,maxw=1640); lh=34*1.36; y0=928-(len(ls)-1)*lh
            bw=max(F(SANS,34).measureText(l) for l in ls)
            c.drawRect(skia.Rect.MakeXYWH(960-bw/2-36,y0-44,bw+72,lh*len(ls)+22),P((0,0,0),a*0.38,blur=30))
            for k,l in enumerate(ls): text(c,l,960,y0+k*lh,34,WHITE,a,SANS)
def sec_of(t):
    for s in TL['sections']:
        if s['t0']<=t<s['t1']: return s
    return TL['sections'][-1]
NOTE={  # 每段底部的出处
 'hook':tr("ITF《网球规则》2026 第 29 条：换边最多 90 秒，盘间最多 120 秒","ITF Rules of Tennis 2026, rule 29: 90 s at changeover, 120 s between sets"),
 'title':tr("肌糖原：耐力运动的经典燃料库（示意，不是网球活检）","Muscle glycogen: classic fuel store in endurance sport (schematic, not a tennis biopsy)"),
 'peel':tr("USDA FDC 173944 · Atkinson 等 2008 / 2021 国际 GI 表","USDA FDC 173944 · Atkinson et al. 2008 / 2021 international GI tables"),
 'salt':tr("Baker 2019（骑车，n=11）· Schwellnus 2004–2011（耐力赛，不是网球）","Baker 2019 (cycling, n=11) · Schwellnus 2004–2011 (endurance racing, not tennis)"),
 'fuel':tr("Vicente-Salar 等 2025，ITF/WTA/ATP 专家声明 Table 3 · ITF 规则第 29 条","Vicente-Salar et al. 2025, ITF/WTA/ATP expert statement Table 3 · ITF rule 29"),
 'proof':tr("Vergauwen 1998 · McRae 2012 · Mitchell 1992 · Nieman 2012（Dole 资助，不是网球）","Vergauwen 1998 · McRae 2012 · Mitchell 1992 · Nieman 2012 (Dole-funded, not tennis)"),
 'alt':tr("USDA FDC 173944 / 168191 · BBC Sport 文字直播（Fordyce，2010）","USDA FDC 173944 / 168191 · BBC Sport live text (Fordyce, 2010)"),
 'end':tr("更站得住的理由是补糖；防抽筋还没有被证明","The more defensible reason is carbohydrate; preventing cramp has not been shown")}
CHAP={'title':("01",tr("不是补钾","NOT POTASSIUM")),'peel':("02",tr("剖开","ANATOMY")),'salt':("03",tr("钾与抽筋","POTASSIUM")),'fuel':("04",tr("补糖窗口","FUELING")),
 'proof':("05",tr("试验","TRIALS")),'alt':("06",tr("对照","COMPARE")),'end':("07",tr("结论","CONCLUSION"))}
def chapter(c,t):  # 右上角章节标签
    s=sec_of(t)
    if s['name'] not in CHAP: return
    n,lab=CHAP[s['name']]; a=min(1,(t-s['t0'])/0.5,(s['t1']-t)/0.4)
    text(c,n+"  "+lab,W-182,BRAND_BASE,22,(0.85,0.9,1.0),a*0.85,SANS,align='r',spacing=1)
def draw(c,t,an):
    brand(c); chapter(c,t); s=sec_of(t); u=t-s['t0']; a=min(1,u/0.6,(s['t1']-t)/0.4)
    if s['name'] in NOTE: text(c,NOTE[s['name']],960,1050,18,GRAY,a*0.9,SANSR)
    if s['name']=='end' and u>2:
        text(c,tr("资料：USDA · ITF/WTA/ATP 2025 声明 · Vergauwen · McRae · Mitchell · Nieman · Schwellnus · Baker · BBC · 详见文案","Sources: USDA · ITF/WTA/ATP 2025 statement · Vergauwen · McRae · Mitchell · Nieman · Schwellnus · Baker · BBC · see caption"),960,1050,18,GRAY,min(1,(u-2)/0.5),SANSR)
    sub(c,t)
    for s0,d,txt,pl in CAPS:
        if s0<=t<s0+d+0.35: caption(c,t,s0,d,txt,pl,an)

def main(inp,out,anchors_files):
    an={}
    for fpath in anchors_files:
        for f,a in json.load(open(fpath)): an[f]=a
    dec=subprocess.Popen(['ffmpeg','-loglevel','error']+(['-f','concat','-safe','0'] if inp.endswith('.txt') else [])+['-i',inp,'-f','rawvideo','-pix_fmt','rgba','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgba','-s','%dx%d'%(W,H),'-r',str(FPS),'-i','-','-c:v','libx264','-preset','medium','-crf','19','-maxrate','30M','-bufsize','60M','-pix_fmt','yuv420p','-movflags','+faststart',out],stdin=subprocess.PIPE)
    f=int(os.environ.get('OV_F0','0')); n=W*H*4
    while True:
        buf=dec.stdout.read(n)
        if len(buf)<n: break
        arr=np.frombuffer(buf,np.uint8).reshape(H,W,4).copy()
        s=skia.Surface(arr); draw(s.getCanvas(),f/FPS,an.get(f,{}))
        enc.stdin.write(arr.tobytes()); f+=1
    enc.stdin.close(); enc.wait(); print('frames',f)
if __name__=='__main__':
    if sys.argv[1]=='still':
        from PIL import Image
        for p in sys.argv[2:]:
            t=float(os.path.basename(p)[2:9]); jp=p.replace('.jpg','.json'); an=json.load(open(jp)) if os.path.exists(jp) else {}
            arr=np.array(Image.open(p).convert('RGBA')); s=skia.Surface(arr); draw(s.getCanvas(),t,an)
            Image.fromarray(arr[...,:3]).save(p.replace('.jpg','_ov.jpg'),quality=90)
    else:
        main(sys.argv[1],sys.argv[2],sys.argv[3:])
