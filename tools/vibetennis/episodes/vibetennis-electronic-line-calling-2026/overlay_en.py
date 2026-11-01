"""vibetennis 第 2 集《电子司线，真的准吗？》英文版叠加层（品牌 Tennis Jetlag）——由 overlay.py 逐句翻译而来，画面与时间轴不变。

用法：python3 overlay.py <3D 母带.mp4> <输出.mp4> <分段锚点.json ...>；python3 overlay.py still <静帧.jpg ...>
通用函数（字体、引线字幕、品牌标）抄自第 1 集 overlay.py；文案与面板是这一集的。
"""
import skia, numpy as np, math, json, sys, subprocess, glob, os
W,H,FPS=1920,1080,30
HERE=os.path.dirname(os.path.abspath(__file__))
REPO=os.path.abspath(os.path.join(HERE,'../../../..'))
WORK=os.environ.get('VT_WORK',HERE)  # 渲染中间产物目录（r3d/seg、sfx/），默认就是本目录
# 第 2 集没有 BGM（授权未定），时间轴按秒排，不吸附节拍
def snap(t): return t
SANS=skia.Typeface.MakeFromName('Inter',skia.FontStyle.Bold())
SANSR=skia.Typeface.MakeFromName('Inter',skia.FontStyle.Normal())
SERIF=skia.Typeface.MakeFromName('Noto Serif CJK SC',skia.FontStyle.Bold())
MONO=skia.Typeface.MakeFromName('Noto Sans Mono',skia.FontStyle.Normal())
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
def wrap(s,size,maxw=930,tf=None):
    # English: break on spaces (balanced line lengths), keep 【】 highlights across lines
    f=F(tf or SANS,size); strip=lambda x:x.replace('【','').replace('】','')
    tot=f.measureText(strip(s))
    if tot>maxw: n=math.ceil(tot/maxw); maxw=tot/n+size*1.2
    lines=[]; cur=''
    import re as _re
    s=_re.sub(r'【[^】]*】',lambda m:m.group(0).replace(' ','\u00a0'),s)
    s=_re.sub(r'(\d) (?=(cm|mm|ms|s|km/h|fps)\b)','\\1\u00a0',s)
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
    ls=wrap(txt,size,maxw=1050)
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
    text(c,"Tennis Jetlag",BRAND_X+BRAND_ICON+BRAND_GAP,BRAND_BASE,BRAND_SIZE,WHITE,0.88,SANS,align='l',spacing=1)


# ---------------- captions（锚在被讲的东西旁边；出处见 papers/vibetennis-electronic-line-calling-2026/sources.md） ----------------
# place: ('s',x,y,align[,size]) 固定在留白处；('a',anchor,dx,dy,align,fx,fy[,size]) 用引线连到 3D 元素，找不到就退回 fx,fy
L,R,C='l','r','c'
CAPS=[
 # 01 回放
 (1.0,4.4,"Electronic line-calling replay: this ball touched the line",('s',168,900,L)),
 (6.6,3.6,"But was this oval actually filmed?",('a','land',-90,-230,R,1300,300)),
 (10.9,2.3,"Take Hawk-Eye: 【no — it's calculated】",('s',960,880,C,56)),
 (13.3,1.9,"Rule: any contact with the line is IN",('s',960,880,C,46)),
 # 02 相机
 (15.5,2.3,"How is it calculated?",('s',960,540,C,64)),
 (18.2,3.8,"Wimbledon: 【12 cameras】 per court",('s',168,250,L)),
 (22.4,4.6,"Each camera watches only its own patch",('s',1752,250,R)),
 (28.4,3.4,"Every frame: first find the 【ball centre】",('a','ball',70,-110,L,1200,400)),
 (32.1,2.6,"Each camera does this on its own",('s',168,880,L)),
 # 03 定位
 (35.7,3.4,"You judge distance with two eyes",('a','eyeL',-60,150,R,700,820)),
 (39.4,3.3,"Where the two lines of sight meet — that's the cup",('a','cup',40,-150,L,1200,300)),
 (43.4,3.2,"It uses 【12】",('s',168,250,L,60)),
 (46.9,3.8,"Lines of sight meet = one 【3D point】 in the air",('a','ball',80,-150,L,1100,300)),
 (51.0,3.4,"One frame, one point",('a','ball',80,140,L,1100,800)),
 (54.6,3.0,"Join the points: a 【trajectory】",('s',168,880,L)),
 (57.9,2.0,"But can a ball that fast be caught?",('s',960,880,C,58)),
 # 04 帧率
 (60.6,3.6,"Per the maker: up to 【340 frames per second】",('s',168,250,L)),
 (64.4,3.6,"About 【2.94 ms】 between frames",('s',168,330,L)),
 (68.2,3.8,"A 200 km/h ball has already flown about 【16 cm】",('a','g1',-40,-170,R,1500,330,46)),
 (72.4,4.3,"And the ball touches the ground for only about 【4.7 ms】",('s',1752,250,R)),
 (77.0,3.8,"The whole bounce: 【one or two frames, at most】",('s',1752,330,R)),
 (81.2,3.3,"The bounce itself has to be calculated",('s',960,880,C,58)),
 # 05 落地
 (85.6,3.2,"On landing, the ball squashes",('s',168,250,L)),
 (89.2,4.6,"Dropped straight down: contact up to about 【4.2 cm】",('a','ringR',90,-180,L,1200,300)),
 (96.4,3.6,"Landing at an angle: it squashes and slides forward",('s',168,250,L)),
 (100.6,4.4,"In experiments, the footprint stretched about 【10 cm】",('a','fpEnd',60,-170,L,1300,300)),
 (105.4,4.2,"The system never measures the footprint — it's 【modelled】",('a','sys',40,170,L,1100,860)),
 # 06 球印
 (110.6,3.0,"What about the mark on the court?",('s',960,540,C,60)),
 (114.0,4.6,"On clay, the mark can be 【larger than the real contact】",('a','clayEdge',80,90,L,1300,880)),
 (118.9,4.4,"On hard courts, it can be 【smaller than the real contact】",('a','hardEdge',80,-90,L,1300,260)),
 (123.6,2.6,"The mark can't be trusted either",('s',168,540,L,58)),
 (126.4,3.4,"Yet Roland-Garros still checks the mark",('a','clay',-120,-160,R,760,300)),
 # 07 精度
 (130.6,2.6,"So it's calculated — but how accurately?",('s',960,880,C,56)),
 (133.8,4.6,"2006 testing: mean error 【2.6 mm】",('s',168,250,L)),
 (138.8,4.4,"Today's top certification is graded in millimetres",('s',168,250,L)),
 (143.6,4.6,"Test balls more than 5 mm from the line: 【100% correct】 required",('s',168,250,L,46)),
 (148.6,3.6,"From bounce to the OUT call: about 【0.15 s】",('s',168,250,L)),
 (152.6,2.4,"And the human eye?",('s',960,880,C,62)),
 # 08 人眼
 (155.6,4.6,"Line judges' uncertainty: about 【1.4 cm】 on sidelines",('s',168,250,L,46)),
 (164.4,4.8,"Baselines and service lines are hardest: about 【3.2 cm】",('s',168,250,L)),
 (170.0,4.2,"ATP 2006–07: 【39%】 of challenged calls were wrong",('s',168,250,L,46)),
 (174.6,2.8,"And within 5 mm?",('s',960,880,C,60)),
 # 09 局限
 (180.6,3.4,"Within 5 mm: the standard's 【permitted error】",('s',168,250,L)),
 (184.2,2.6,"The court itself matters too",('s',168,250,L)),
 (187.4,3.8,"A surface just 1 mm uneven",('a','dotB',-60,-170,R,700,300)),
 (191.4,2.6,"shifts a fast serve's landing by 【3–4 mm】",('a','dotA',60,-170,L,1200,300)),
 (194.4,5.2,"The fuzz touches before the ball (mostly negligible)",('s',168,250,L,46)),
 # 10 人的角色
 (200.4,2.6,"So what's left for humans?",('s',960,880,C,58)),
 (203.2,3.2,"In or out: ELC decides — 【no video review】",('a','ljChair',60,-170,L,1100,300,46)),
 (206.6,3.6,"6 more cameras watch for foot faults (US Open, Linz setups)",('s',168,250,L,44)),
 (210.4,3.6,"Foot faults: machine watches, a human decides and triggers the call (Linz)",('a','booth',60,-150,L,700,300,42)),
 (214.4,3.4,"Wimbledon 2025: the system was switched off for a game by mistake",('s',168,250,L)),
 (218.0,3.8,"Three calls were missed — on the third, the point was replayed",('a','ump',-60,-170,R,1500,300,44)),
]
CAPS=[(snap(s),d,t,p) for s,d,t,p in CAPS]
SECT=[(0,15,"01","REPLAY"),(15,35,"02","CAMERAS"),(35,60,"03","LOCATING"),(60,85,"04","FRAME RATE"),(85,110,"05","THE BOUNCE"),(110,130,"06","BALL MARKS"),(130,155,"07","ACCURACY"),(155,180,"08","HUMAN EYE"),(180,200,"09","LIMITS"),(200,222,"10","HUMAN ROLE")]
SRC=["ITF (2026). Electronic Line-Calling Systems: Evaluation Procedures, Rev. 28.1",
"Hawk-Eye Innovations (2016). Electronic Line Calling Technology: How it works",
"Sony. Hawk-Eye — cameras running at up to 340 frames per second",
"R. Cross (2014). The footprint of a tennis ball. Sports Engineering 17",
"G. Mather (2008). Proc. R. Soc. B 275: 1645–1651",
"BBC Sport (2025-07) · CNBC (2023-09) · Tennisnet (2020-11) · AELTC (2025-07-06)",
"",
"'Calculated' refers to Hawk-Eye; some systems claim to capture the bounce directly (vendor claim)",
"Frame gap and 16 cm estimated at 340 fps; camera positions and footprint shape are illustrative"]
TB=1.05
def dim(c,a0,a1,label,a,cc=GOLD,off=-40,size=30):
    """两点之间的尺寸线 + 标注（2D）"""
    if not (a0 and a1 and a0[2] and a1[2]): return
    x0,y0,x1,y1=a0[0],a0[1]+off,a1[0],a1[1]+off
    c.drawLine(x0,y0,x1,y1,P(cc,a,stroke=2.5))
    for x,y in ((x0,y0),(x1,y1)): c.drawLine(x,y-14,x,y+14,P(cc,a,stroke=2.5))
    text(c,label,(x0+x1)/2,(y0+y1)/2-18,size,cc,a,SANS,glow=0.5)
def secA(t,t0,t1,i=0.5,o=0.3): return max(0,min(1,(t-t0)/i,(t1-t)/o))

def draw(c,t,an,hist):
    g=lambda k: an.get(k)
    brand(c)
    for t0,t1,n,lab in SECT:
        if t0<=t<t1:
            a=min(1,(t-t0)/0.6,(t1-t)/0.4)
            text(c,n,1630,82,26,GOLD,a,MONO,align='l',glow=0.5); c.drawLine(1672,62,1672,88,P(GOLD,a*0.6,stroke=2)); text(c,lab,1686,82,26,WHITE,a*0.85,SANS,align='l')
    # 01 回放：转播回放的样子
    if t<10.6:
        a=secA(t,0.3,10.6)
        c.drawRoundRect(skia.Rect.MakeXYWH(168,150,190,52),8,8,P((0.85,0.1,0.15),a*0.9)); text(c,"REPLAY",263,188,30,WHITE,a,MONO,spacing=4)
        v=g('land')
        if 5.4<t and onscreen(v,20):
            a2=a*ease((t-5.6)/0.3)
            c.drawRoundRect(skia.Rect.MakeXYWH(v[0]+120,v[1]-260,200,120),12,12,P((0.05,0.55,0.25),a2*0.9))
            text(c,"IN",v[0]+220,v[1]-170,84,WHITE,a2,SANS)
    # 02 相机编号 + 球心十字
    if 17<=t<28:
        a=secA(t,17,28)
        for i in range(12):
            v=g('cam%d'%i); ai=a*ease((t-15-0.6-i*0.35)/0.4)
            if onscreen(v,20) and ai>0: text(c,"CAM %02d"%(i+1),v[0],v[1]-34,20,CYAN,ai,MONO,glow=0.4)
    if 28<=t<35:
        a=secA(t,28,35); v=g('ball')
        if onscreen(v,20):
            x,y=v[0],v[1]; r=28
            c.drawCircle(x,y,r,P(GOLD,a,stroke=2)); 
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)): c.drawLine(x+dx*(r+6),y+dy*(r+6),x+dx*(r+22),y+dy*(r+22),P(GOLD,a,stroke=2))
            text(c,"x %d · y %d"%(round(x),round(y)),x+r+30,y+r+30,20,GOLD,a,MONO,align='l')
    # 03 视线计数 / 帧点
    if 43<=t<60:
        a=secA(t,43.3,60); n=g('nrays') or 0
        bracketbox(c,1340,150,460,130,a); text(c,"Lines of sight",1370,205,28,WHITE,a,SANSR,align='l'); text(c,"× %d"%n,1370,262,52,GOLD,a,SANS,align='l',glow=0.5)
        if t>=50.5: text(c,"1 frame · 1 point",1560,262,28,CYAN,a*ease((t-50.5)/0.4),MONO,align='l')
    # 04 帧率：时间轴
    if 60<=t<85:
        a=secA(t,60.4,85)
        text(c,"Estimated at 340 fps · 200 km/h ≈ 55.6 m/s",960,1030,22,GRAY,a,MONO)
        if 64.2<=t<72.2:
            dim(c,g('g0'),g('g1'),"≈16 cm",a*ease((t-64.2)/0.4),GOLD,-20,30)
        if t>=72.2:
            a2=a*ease((t-72.2)/0.5); x0,x1,y=360,1560,800; ms=12.0; px=lambda m:x0+(x1-x0)*m/ms
            c.drawRect(skia.Rect.MakeXYWH(x0-30,y-120,x1-x0+60,200),P((0,0,0),a2*0.45,blur=20))
            c.drawLine(x0,y,x1,y,P(WHITE,a2*0.7,stroke=2))
            for m in range(0,13): c.drawLine(px(m),y-6,px(m),y+6,P(WHITE,a2*0.5,stroke=1.5)); text(c,"%d"%m,px(m),y+36,20,GRAY,a2,MONO)
            text(c,"ms",x1+50,y+36,22,GRAY,a2,SANSR)
            cs=0.6+2.6*(0.5-0.5*math.cos(min(1,max(0,(t-73.0)/7.0))*math.pi*2)); ce=cs+4.72   # 落地时刻相对快门在滑动：有时罩住一帧，有时两帧
            nf=sum(1 for k in range(6) if cs<=k*2.94<=ce)
            c.drawRect(skia.Rect.MakeLTRB(px(cs),y-40,px(ce),y-8),P(GOLD,a2*0.35)); text(c,"Ball on ground ≈ 4.7 ms",(px(cs)+px(ce))/2,y-56,26,GOLD,a2,SANS,glow=0.4)
            k=0
            while k*2.94<=ms:
                fx=px(k*2.94); hit=cs<=k*2.94<=ce
                c.drawLine(fx,y-90,fx,y+8,P(CYAN if not hit else GOLD,a2*(1 if hit else 0.6),stroke=3 if hit else 2))
                k+=1
            text(c,"Each vertical line = one frame (2.94 ms apart)",x0,y-100,22,CYAN,a2,MONO,align='l')
            text(c,"%d frame%s captured"%(nf,"" if nf==1 else "s"),x1,y-100,30,GOLD,a2,SANS,align='r',glow=0.5)
    # 05 尺寸线
    if 89<=t<96: dim(c,g('ringL'),g('ringR'),"≈4.2 cm",secA(t,89.2,96),GOLD,60,32)
    if 100.4<=t<106: dim(c,g('fpStart'),g('fpEnd'),"≈10 cm",secA(t,100.6,106),GOLD,70,32)
    if 96<=t<110: text(c,"Experiment: 21 m/s horizontal · 6.8 m/s vertical (Cross 2014)",960,1030,22,GRAY,secA(t,96.3,110),MONO)
    if 105<=t<110:
        a=secA(t,105.4,110); v=g('sys')
        if onscreen(v,20): text(c,"Modelled footprint",v[0],v[1]-30,24,CYAN,a,MONO,glow=0.4)
    # 06 球印图例
    if 114<=t<130:
        a=secA(t,114,130)
        bracketbox(c,120,880,400,110,a); c.drawLine(150,935,210,935,P(CYAN,a,stroke=3)); text(c,"Dashed = real contact",226,944,26,WHITE,a,SANSR,align='l')
        text(c,"ITF ELC evaluation procedures §2.2",320,975,18,GRAY,a,MONO)
    # 07 精度
    if 133.6<=t<139:
        a=secA(t,133.8,139); text(c,"2.6",1300,600,170,GOLD,a,SANS,align='l',glow=0.6); text(c,"MM · 2006 ITF test (Hawk-Eye 2016)",1306,650,22,WHITE,a*0.8,MONO,align='l')
    if 140<=t<180:
        a=secA(t,140,180)
        bracketbox(c,1340,700,440,170,a)
        c.drawRect(skia.Rect.MakeXYWH(1370,740,40,26),P((0.05,0.5,0.25),a)); text(c,"5–100 mm off the line: 100% correct",1424,762,24,WHITE,a,SANSR,align='l')
        c.drawRect(skia.Rect.MakeXYWH(1370,790,40,26),P((0.9,0.5,0.1),a)); text(c,"±5 mm: permitted error",1424,812,24,WHITE,a,SANSR,align='l')
        text(c,"ITF procedures 28.1 · Gold level",1560,852,18,GRAY,a,MONO)
        for k,lab in (('z100','100 mm'),('zm100','100 mm')):
            v=g(k)
            if onscreen(v,10): text(c,lab,v[0],v[1]-14,20,(0.5,1,0.7),a,MONO)
    if 148.4<=t<152.6:
        a=secA(t,148.6,152.6); u=min(1,(t-148.6)/1.2); cx,cy=1560,470
        c.drawCircle(cx,cy,80,P(WHITE,a*0.25,stroke=6)); 
        arc=skia.Path(); arc.addArc(skia.Rect.MakeXYWH(cx-80,cy-80,160,160),-90,360*u); c.drawPath(arc,P(GOLD,a,stroke=6))
        text(c,"0.15 s",cx,cy+14,40,GOLD,a,SANS,glow=0.4); text(c,"Bounce → OUT",cx,cy+120,24,WHITE,a*0.8,SANSR)
    # 08 人眼
    if 155<=t<180:
        a=secA(t,155.6,180)
        text(c,"Mather 2008 · 15 ATP events · 2006–07 · positional uncertainty is a model parameter",960,1030,22,GRAY,a,MONO)
        v=g('edgeTop')
        if onscreen(v,10) and t<174: text(c,"Human-eye uncertainty band",v[0],v[1]-20,26,(0.5,0.75,1.0),a,SANS,glow=0.3)
    if 170<=t<174.6:
        a=secA(t,170,174.6); u=min(1,(t-170)/1.6)
        bracketbox(c,1260,300,520,220,a); text(c,"%d"%round(1473*u),1290,390,72,WHITE,a,SANS,align='l'); text(c,"challenges",1290,430,24,GRAY,a,SANSR,align='l')
        text(c,"%d%%"%round(39.3*u),1560,390,72,GOLD,a,SANS,align='l',glow=0.5); text(c,"overturned",1560,430,24,GRAY,a,SANSR,align='l')
    # 09 局限
    if 187<=t<194: a=secA(t,187.4,194); text(c,"Exaggerated for clarity",1752,1030,24,GRAY,a,MONO,align='r'); text(c,"Cross 2014",168,1030,22,GRAY,a,MONO,align='l')
    if 194<=t<200:
        a=secA(t,194.4,200); v=g('fibre')
        if onscreen(v,10): hudlabel(c,v[0],v[1],"Fuzz touches first",a,(1,0.45,0.45),80,60,26)
    # 10 挑战被划掉 / 按钮
    if 203<=t<206.4:
        a=secA(t,203.2,206.4); bracketbox(c,1200,850,640,170,a); text(c,"Video review · in/out",1520,922,36,WHITE,a*0.6,SANS)
        c.drawLine(1350,904,1690,926,P((1,0.35,0.35),a,stroke=4))
        text(c,"Reviewable: double bounces, touches, net calls, etc.",1520,972,22,WHITE,a*0.9,SANSR)
        text(c,"US Open since 2023 · Wimbledon since 2026",1520,1004,20,GRAY,a,MONO)
    # 11 收束
    if 222.6<=t<236:
        lt=t-222.6; a=min(1,(236-t)/0.8)
        rich(c,"It isn't infallible,",960,340,68,a,SERIF,reveal=lt-0.6)
        rich(c,"but it cut the error from 【centimetres】",960,445,68,a,SERIF,reveal=lt-2.2)
        rich(c,"to 【millimetres】.",960,550,68,a,SERIF,reveal=lt-3.6)
        if lt>6.5: rich(c,"Which electronic call have you refused to accept?",960,720,46,a*ease((lt-6.5)/0.8),SANS,glow=False)
    if t>=236:
        a=min(1,(t-236)/0.6,(244.2-t)/0.5)
        text(c,"References",960,230,44,WHITE,a,SERIF); y=320
        for s in SRC:
            if s: text(c,s,380,y,24,GRAY if s[0]<='z' else WHITE,a,MONO if s[0]<='z' else SANSR,align='l')
            y+=52
    for s,d,txt,pl in CAPS:
        if pl and s<=t<s+d+0.35: caption(c,t,s,d,txt,pl,an)

def main(inp,out,anchors_files):
    an={}
    for fpath in anchors_files:
        for f,a in json.load(open(fpath)): an[f]=a
    dec=subprocess.Popen(['ffmpeg','-loglevel','error']+(['-f','concat','-safe','0'] if inp.endswith('.txt') else [])+['-i',inp,'-f','rawvideo','-pix_fmt','rgba','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgba','-s','%dx%d'%(W,H),'-r',str(FPS),'-i','-','-c:v','libx264','-preset','medium','-crf','21','-maxrate','28M','-bufsize','56M','-pix_fmt','yuv420p','-movflags','+faststart',out],stdin=subprocess.PIPE)
    hist=[]; f=0; n=W*H*4
    while True:
        buf=dec.stdout.read(n)
        if len(buf)<n: break
        arr=np.frombuffer(buf,np.uint8).reshape(H,W,4).copy()
        s=skia.Surface(arr); c=s.getCanvas(); draw(c,f/FPS,an.get(f,{}),hist); 
        enc.stdin.write(arr.tobytes()); f+=1
    enc.stdin.close(); enc.wait(); print('frames',f)
if __name__=='__main__':
    if sys.argv[1]=='still':
        # still mode: overlay onto existing r3d stills
        from PIL import Image
        for p in sys.argv[2:]:
            t=float(os.path.basename(p)[2:9]); an=json.load(open(p.replace('.jpg','.json')))
            arr=np.array(Image.open(p).convert('RGBA')); s=skia.Surface(arr); draw(s.getCanvas(),t,an,[])
            Image.fromarray(arr[...,:3]).save(p.replace('.jpg','_ov.jpg'),quality=90)
    else:
        main(sys.argv[1],sys.argv[2],sys.argv[3:])
