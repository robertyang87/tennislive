"""vibetennis EP13 网中间矮：字幕与出处叠加层（VT_LANG=zh|en）。

用法：python3 overlay.py <3D 母带.mp4 或 concat 列表.txt> <输出.mp4> <分段锚点.json ...>；python3 overlay.py still <静帧.jpg ...>
通用函数（字体、字幕框、品牌标、span）沿用 EP07；文案时间跟着 narration.json 的 at 走（plan.py 排定）。
3D 场景里已经有标签（尺寸、张力表、年代、弹道、扇形），这里只补**画面上没有的上下文**，统一放底部；英文版另把旁白译成英文字幕（docs/vibetennis.md §8）。
每一条都只讲 papers/vibetennis-net-dip-2026/sources.md 里核过、可上屏的内容；单源数字不上屏。
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
('h1',0.3,None,tr("ITF《网球规则》2026 第 1 条：网柱处 1.07 米，中间 0.914 米，中间用不宽于 5 厘米的白色中央带拉紧","ITF Rules of Tennis 2026, rule 1: 1.07 m at the posts, 0.914 m at the centre, held down by a white strap ≤ 5 cm wide"),('s',960,1008,C,30)),
('s0',0.3,None,tr("ITF《场地设施指南》2020：建议张力 1.8–2.0 kN（±0.1）；USTA《Friend at Court》2026 换算约 400–450 磅","ITF Facilities Guide 2020: 1.8–2.0 kN (±0.1) recommended; USTA Friend at Court 2026: about 400–450 lb"),('s',960,1008,C,30)),
('s1',0.3,None,tr("没有测力计时的场上做法（USTA《Friend at Court》2026 注释 1.1）：先到 39 英寸（99.1 厘米），再收紧中央带到 36 英寸","Field method without a gauge (USTA Friend at Court 2026, comment 1.1): 39 in (99.1 cm) first, then tighten the strap to 36 in"),('s',960,1008,C,30)),
('y0',0.3,None,tr("1874 年的中间高度各家记载不一，这里不给具体数字","Sources disagree on the 1874 centre height, so no number is given"),('s',960,1008,C,30)),
('y1',0.3,None,tr("1877 年尺寸以温网官方 Compendium 为准：场地 78×27 英尺，网柱 5 英尺，中间 3 英尺 3 英寸","1877 figures from the official Wimbledon Compendium: 78×27 ft court, 5 ft posts, 3 ft 3 in centre"),('s',960,1008,C,30)),
('d2',0.3,None,tr("按浅 V 网形算（有单打支杆）：单打边线处约 104 厘米；真网在两支撑点之间还会略垂，实际可能略低","Shallow-V net model (singles sticks in): about 104 cm at the singles sideline; a real net sags a little more"),('s',960,1008,C,30)),
('m0',0.3,None,tr("模型见本集资料包 net_geometry.py；按模型算，不是鹰眼实测。80 km/h 余量更大，120 km/h 更紧","Model in net_geometry.py; computed, not Hawk-Eye measurements. More margin at 80 km/h, tighter at 120 km/h"),('s',960,1008,C,30)),
('m4',0.3,None,tr("Sackmann 2020-01-02，Tennis Abstract 记拍项目：2010 年代男子约 2700 场；非切削反手，中路 29.5%","Sackmann 2020-01-02, Tennis Abstract Match Charting: ~2,700 men's matches, 2010s; non-slice backhands, 29.5% middle"),('s',960,1008,C,30)),
('m5',0.3,None,tr("同一来源：反手位打出的沿线球，正反手合计；该位置所有球的非受迫性失误 11%","Same source: down-the-line shots from the backhand corner, both wings; 11% for every shot from that corner"),('s',960,1008,C,30)),
('k1',0.3,None,tr("ITF《网球规则》2026 第 1 条：双打网用于单打时，支杆中心在单打边线外 0.914 米","ITF Rules of Tennis 2026, rule 1: with a doubles net, singles sticks sit 0.914 m outside the singles sideline"),('s',960,1008,C,30)),
('n2',0.3,None,tr("评论区说说：你注意过中央带吗？","Tell us: had you ever noticed the centre strap?"),TOP),
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
 'hook':tr("ITF《网球规则》2026 第 1 条","ITF Rules of Tennis 2026, rule 1"),
 'title':tr("悬链线：伯努利、莱布尼茨、惠更斯，1691 · ITF《网球规则》2026 第 1 条","Catenary: Bernoulli, Leibniz, Huygens, 1691 · ITF Rules of Tennis 2026, rule 1"),
 'strap':tr("ITF《场地设施指南》2020 · USTA《Friend at Court》2026 · 静力学示意","ITF Facilities Guide 2020 · USTA Friend at Court 2026 · statics sketch"),
 'hist':tr("温网官方 Compendium · Halliday 1971 · Wilberforce《Lawn Tennis》· Heathcote（Badminton Library）","Wimbledon Compendium · Halliday 1971 · Wilberforce, Lawn Tennis · Heathcote (Badminton Library)"),
 'diag':tr("ITF《网球规则》2026 · 勾股定理 · 浅 V 网形模型（net_geometry.py）","ITF Rules of Tennis 2026 · Pythagoras · shallow-V net model (net_geometry.py)"),
 'margin':tr("net_geometry.py 真空弹道模型 · Sackmann，Tennis Abstract 2019 / 2020","net_geometry.py vacuum model · Sackmann, Tennis Abstract 2019 / 2020"),
 'sticks':tr("ITF《网球规则》2026 第 1 条 · net_geometry.py","ITF Rules of Tennis 2026, rule 1 · net_geometry.py")}
CHAP={'title':("01",tr("悬链线","CATENARY")),'strap':("02",tr("中央带","THE STRAP")),'hist':("03",tr("降网史","HISTORY")),'diag':("04",tr("勾股定理","PYTHAGORAS")),
 'margin':("05",tr("过网余量","MARGIN")),'sticks':("06",tr("单打支杆","SINGLES STICKS")),'end':("07",tr("结论","CONCLUSION"))}
def chapter(c,t):  # 右上角章节标签
    s=sec_of(t)
    if s['name'] not in CHAP: return
    n,lab=CHAP[s['name']]; a=min(1,(t-s['t0'])/0.5,(s['t1']-t)/0.4)
    text(c,n+"  "+lab,W-182,BRAND_BASE,22,(0.85,0.9,1.0),a*0.85,SANS,align='r',spacing=1)
def draw(c,t,an):
    brand(c); chapter(c,t); s=sec_of(t); u=t-s['t0']; a=min(1,u/0.6,(s['t1']-t)/0.4)
    if s['name'] in NOTE: text(c,NOTE[s['name']],960,1050,18,GRAY,a*0.9,SANSR)
    if s['name']=='end' and u>2:
        text(c,tr("资料：ITF 规则与设施指南 · USTA · 温网 Compendium · Tennis Abstract · 详见文案","Sources: ITF Rules & Facilities Guide · USTA · Wimbledon Compendium · Tennis Abstract · see caption"),960,1050,18,GRAY,min(1,(u-2)/0.5),SANSR)
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
