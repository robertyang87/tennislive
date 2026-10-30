import skia, numpy as np, math, json, sys, subprocess, glob, os
W,H,FPS=1920,1080,30
BAR=2.1364; B0=0.46; bar=lambda k:B0+BAR*k
HERE=os.path.dirname(os.path.abspath(__file__))
REPO=os.path.abspath(os.path.join(HERE,'../../../..'))
WORK=os.environ.get('VT_WORK',HERE)  # 渲染中间产物目录（r3d/seg、sfx/），默认就是本目录
BEATS=np.load(os.path.join(HERE,'beats.npy'))
def snap(t):
    i=np.argmin(np.abs(BEATS-t)); return float(BEATS[i]) if abs(BEATS[i]-t)<0.3 else t
SANS=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Bold())
SANSR=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Normal())
SERIF=skia.Typeface.MakeFromName('Noto Serif CJK SC',skia.FontStyle.Bold())
MONO=skia.Typeface.MakeFromName('Noto Sans Mono CJK SC',skia.FontStyle.Normal())
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

# ---------------- captions (contextual placement, 16:9) ----------------
# place: ('s',x,y,align[,size])  fixed spot in negative space
#        ('a',anchor,dx,dy,align,fx,fy[,size])  anchored to a 3D element (leader line), fallback fx,fy
#        None -> carried by an on-screen HUD element instead
L,R,C='l','r','c'
CAPS=[
 (0.6,2.9,"一个时速 【200 公里】 的发球",('s',168,660,L)),
 (3.7,3.0,"在电视上看，像是飘过去的",('a','ball',60,-70,L,1180,420)),
 (7.0,5.6,"坐到场边——你可能连球都没看清",('s',1752,250,R,58)),
 (13.6,2.9,"奇怪的是，别的球好像反过来",('s',168,250,L)),
 (16.8,2.8,"坐上看台，足球像放慢了",('a','pitch',-260,-160,R,600,800)),
 (20.0,2.8,"电视里，却更快、更激烈",('s',960,190,C,58)),
 (23.0,2.8,"球还是那个球。变的是什么？",('s',960,560,C,70)),
 (26.4,2.4,"先看网球有多快",('s',1752,250,R)),
 (29.0,2.7,"底线到底线：【23.77 米】",('s',1752,330,R)),
 (31.9,3.0,"200 km/h 的发球，约 【0.4 秒】 落地",('a','bounce',-40,150,R,1752,860)),
 (35.0,2.0,"约 【0.7 秒】 到接发球的人面前",('s',1752,250,R)),
 (37.1,1.7,"——不到一次心跳",('s',1752,330,R)),
 (39.2,3.6,"电视的主机位，架在底线后方的高处",('a','c1',80,150,L,200,860)),
 (43.0,4.2,"ATP 制作手册：视线要擦过网顶，俯角约 【12°】",('a','nettop',60,170,L,900,860)),
 (47.7,3.5,"23.77 米的纵深，在镜头里只占约 【11°】",('s',1240,860,C)),
 (51.5,4.2,"远的那半场，还不到近半场的一半",('a','wedgeMidFar',120,-190,L,1300,330)),
 (56.2,2.9,"这样，两名球员和整片场地都在画面里",('s',560,420,R,44)),
 (59.3,2.9,"但球，几乎是正对着镜头来回飞",('s',1360,600,L,44)),
 (62.7,3.0,"作家华莱士写过：电视“压缩”了球场",('s',960,330,C)),
 (65.9,2.7,"而球速，恰恰藏在这段被压缩的长度里",('s',960,900,C)),
 (69.1,3.8,"大脑判断快慢，看的是球在你眼里扫过的角度",('s',1752,220,R,46)),
 (73.2,3.0,"离得越近、越是横着飞，扫得越快",('s',1752,300,R,46)),
 (76.5,2.8,"坐在场边，0.71 秒扫过约 【98°】",('a','seat',90,160,L,1100,820)),
 (79.8,2.4,"电视前：约 【19°/秒】",None),(82.4,2.6,"底线后高处的看台：约 【23°/秒】",None),(85.2,2.4,"坐在场边：约 【138°/秒】",None),
 (87.8,2.2,"同一个球，在你眼里快了约 【7 倍】",('s',1150,740,L)),
 (90.5,2.6,"大脑会帮你校正一部分距离",('s',1752,240,R)),
 (93.3,2.8,"可它校正不了一件事：眼睛追不上",('s',1752,320,R)),
 (96.3,2.2,"平滑追踪的舒适上限，约 【70°/秒】",None),
 (98.6,2.2,"超过它，眼球只能跳着追",('a','gaze',70,110,L,1300,800)),
 (101.2,2.8,"球像“消失”了一段——这就是“快”",('s',960,250,C,60)),
 (104.2,2.6,"而电视里的球，多在纵深方向前后飞",('s',168,880,L)),
 (107.0,2.3,"人眼对纵深运动，本来就更迟钝",('s',1752,880,R)),
 (109.7,2.4,"那足球为什么反过来？",('s',960,900,C,68)),
 (112.4,2.8,"看台上，你眼里是一整块 【105 米】 的球场",('s',168,250,L)),
 (115.4,2.4,"电视把镜头推近，画面里只剩约 【40 米】",('s',168,330,L)),
 (118.2,2.8,"1931 年，心理学家 J.F. Brown 发现",('s',168,250,L,46)),
 (121.2,3.4,"同样的速度，放进越大的“窗口”，看起来越慢",('a','pSmall',0,110,C,460,820,42)),
 (124.8,3.6,"窗口大 2 倍，要快约 【1.94 倍】 才显得一样快",('a','pBig',0,100,C,1210,960,42)),
 (128.9,3.4,"电视里，传球每秒走 【半个画面】",('a','win',-60,-150,R,700,420)),
 (132.5,4.4,"看台上，每秒只走 【1/5】 个球场",('a','pitch',60,200,L,1300,760)),
 (137.5,2.4,"电视压扁了网球的距离",('a','tennis',0,-190,C,300,400)),
 (140.1,2.4,"又缩小了足球的窗口",('a','football',0,-190,C,1650,400)),
 (142.7,2.0,"快和慢，不只在球",('s',960,470,C,56)),
 (144.9,2.8,"在你坐在哪里，隔着多大的窗口",('s',960,550,C,56)),
 (148.2,4.6,"我们看别人的生活，大多也是从底线后方的高处",('s',168,210,L,52)),
 (153.0,5.4,"隔着屏幕，每个回合都显得从容",('s',1752,300,R,52)),
 (158.9,3.0,"而你自己的日子，你一直坐在场边",('s',168,250,L,56)),
 (162.1,2.7,"每一球，都快得看不清",('s',168,335,L,56)),
]
CAPS=[(snap(s),d,t,p) for s,d,t,p in CAPS]
CHIPS=[(0,bar(12),"01","现象"),(bar(12),bar(18),"02","速度"),(bar(18),bar(32),"03","机位"),(bar(32),bar(42),"04","角度"),(bar(42),bar(51),"05","眼睛"),(bar(51),bar(64),"06","窗口"),(bar(64),bar(69),"07","结论"),(bar(69),bar(77),"08","回到生活")]
SRC=["David Foster Wallace (2006). Federer as Religious Experience. NYT",
"ATP 250 TV Production Manual (2023): Camera 1 sightline 12.09°",
"J.F. Brown (1931). Psychologische Forschung 14:199–232",
"H. Wallach (1939). On constancy of visual speed. Psych. Review",
"C.W. Tyler (1971). Science 174:958–961",
"Purves et al. Neuroscience — smooth pursuit ≈ 70°/s",
"Meyer, Lasker & Robinson (1985). Vision Research",
"Regan & Gray (2000). Trends in Cognitive Sciences",
"",
"角速度与发球时间按简化模型估算；",
"机位距离、座位与屏幕尺寸为示意假设"]
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
    text(c,"网球时差",BRAND_X+BRAND_ICON+BRAND_GAP,BRAND_BASE,BRAND_SIZE,WHITE,0.88,SANS,align='l',spacing=1)

def draw(c,t,an,hist):
    g=lambda k: an.get(k)
    brand(c)
    for t0,t1,n,lab in CHIPS:
        if t0<=t<t1:
            a=min(1,(t-t0)/0.6,(t1-t)/0.4)
            text(c,n,1630,82,26,GOLD,a,MONO,align='l',glow=0.5); c.drawLine(1672,62,1672,88,P(GOLD,a*0.6,stroke=2)); text(c,lab,1686,82,26,WHITE,a*0.85,SANS,align='l')
    if t<bar(3):
        a=min(1,(t-0.8)/0.8,(bar(3)-t)/0.4)
        if a>0: text(c,"200",160,560,230,GOLD,a,SANS,align='l',glow=0.6); text(c,"K M / H",640,560,40,WHITE,a*0.8,MONO,align='l',spacing=12)
    if bar(12)<=t<bar(18) and g('tb') is not None:
        tb=max(0,min(0.714,g('tb'))); a=min(1,(t-bar(12))/0.5,(bar(18)-t)/0.3)
        text(c,"%.3f"%tb,160,330,150,GOLD,a,SANS,align='l',glow=0.5); text(c,"S E C O N D S",166,385,26,WHITE,a*0.7,MONO,align='l',spacing=8)
        text(c,"慢放 ×0.12" if t<bar(15)+1.0 else "实时 ×1",166,435,28,CYAN,a*0.9,MONO,align='l')
        bf,bn=g('base_far'),g('base_near')
        if bf and bn and bf[2] and bn[2] and t>=snap(29.0):
            a2=a*ease((t-snap(29.0))/0.5)
            c.drawLine(bf[0],bf[1],bn[0],bn[1],P(GOLD,a2*0.9,stroke=3))
            for v in (bf,bn): c.drawCircle(v[0],v[1],6,P(GOLD,a2))
        if tb>=0.395 and onscreen(g('bounce'),20): b=g('bounce'); c.drawCircle(b[0],b[1],18,P(CYAN,a,stroke=2)); text(c,"0.40 s",b[0],b[1]-30,26,CYAN,a,MONO,glow=0.4)
    if bar(18)<=t<bar(22):
        a=min(1,(t-bar(18))/0.6,(bar(22)-t)/0.3)
        v=g('c1')
        if onscreen(v,20): text(c,"CAM 1",v[0],v[1]-70,26,CYAN,a,MONO,spacing=4,glow=0.4)
        if t>snap(43.0):
            a2=a*ease((t-snap(43.0))/0.5)
            bracketbox(c,1340,150,500,130,a2); text(c,"俯角 12.09°",1370,215,50,GOLD,a2,SANS,align='l',glow=0.5); text(c,"ATP 250 TV 制作手册 · 2023",1372,258,22,GRAY,a2,MONO,align='l')
    if bar(22)<=t<bar(26):
        a=min(1,(t-bar(22))/0.5,(bar(26)-t)/0.3); u=(t-bar(22))/(bar(26)-bar(22))
        v=g('c1'); bx,by=(v[0]+40,v[1]-300) if onscreen(v,20) else (120,120)
        bx=max(80,min(W-560,bx)); by=max(120,by)
        bracketbox(c,bx,by,480,220 if u>=0.5 else 110,a)
        text(c,"整片球场  10.7°",bx+28,by+72,44,GOLD,a,SANS,align='l',glow=0.5)
        if u>=0.5:
            a2=a*ease((u-0.5)/0.08); text(c,"近半场  7.4°",bx+28,by+135,34,GOLD,a2,SANS,align='l'); text(c,"远半场  3.3°",bx+28,by+190,34,CYAN,a2,SANS,align='l',glow=0.4)
        text(c,"示意：底线后 18 m · 高 7.3 m（按 12.09° 视线推算）",1240,1020,22,GRAY,a*0.9,MONO)
        for k,lab in (('far','远底线'),('net','网'),('near','近底线')):
            v=g(k)
            if onscreen(v,20): c.drawLine(v[0],v[1]+10,v[0],v[1]+34,P(WHITE,a*0.6,stroke=1.5)); text(c,lab,v[0],v[1]+68,24,WHITE,a*0.8,MONO)
    if bar(26)<=t<bar(29):
        a=min(1,(t-bar(26))/0.5,(bar(29)-t)/0.3); text(c,"CAM 1 · LIVE",960,180,26,CYAN,a,MONO,spacing=6,glow=0.4)
    if bar(29)<=t<bar(32):
        a=min(1,(t-bar(29)-0.8)/0.6,(bar(32)-t)/0.3)
        if a>0:
            text(c,"“This perspective … ‘foreshortens’ the court.”",960,200,44,WHITE,a,SERIF,glow=0.2)
            text(c,"— David Foster Wallace, NYT, 2006",960,250,22,GRAY,a,MONO)
    if bar(32)<=t<bar(37) and g('tb') is not None:
        a=min(1,(t-bar(32))/0.5,(bar(37)-t)/0.3); tb=g('tb')
        def ang(tt):
            L_=11.885; z=-L_+ (18*(tt/0.395)*(1.12-0.12*tt/0.395) if tt<0.395 else 18+6.8*min(1,(tt-0.395)/0.319)*(1.1-0.1*min(1,(tt-0.395)/0.319)))
            return math.degrees(math.atan2(z, math.hypot(10.115,2.0)))
        sw=ang(tb)-ang(0); text(c,"%d°"%round(sw),160,330,170,GOLD,a,SANS,align='l',glow=0.5); text(c,"S W E E P",166,385,26,WHITE,a*0.7,MONO,align='l',spacing=8)
        text(c,"t = %.2f s"%tb,166,435,28,CYAN,a,MONO,align='l')
        v=g('sweepLabel')
        if onscreen(v,20): text(c,"你 · 场边 6 m",v[0],v[1]-20,24,CYAN,a,MONO,glow=0.4)
    if bar(37)<=t<bar(42):
        a=min(1,(t-bar(37))/0.5,(bar(42)-t)/0.3)
        bracketbox(c,90,150,1020,500,a*0.9)
        text(c,"球在你眼里的平均角速度",130,215,30,GRAY,a,SANSR,align='l')
        rows=[("电视前 · 65 寸 · 2.5 m",19,snap(79.8),WHITE),("现场 · 底线后高处",23,snap(82.4),WHITE),("现场 · 场边",138,snap(85.2),GOLD)]
        y=290
        for name,v,t0,cc in rows:
            ab=a*ease((t-t0)/0.4); gr=ease((t-t0)/0.9)
            text(c,name,130,y,30,WHITE,ab,SANSR,align='l')
            wv=5.4*v*gr; c.drawRoundRect(skia.Rect.MakeXYWH(130,y+18,max(3,wv),32),6,6,P(cc,ab*0.9))
            if cc==GOLD: c.drawRoundRect(skia.Rect.MakeXYWH(130,y+18,max(3,wv),32),6,6,P(GOLD,ab*0.6,blur=14))
            text(c,"%d°/s"%v,130+wv+16,y+46,36,cc,ab,SANS,align='l'); y+=120
        if t>=snap(87.8): a7=a*ease((t-snap(87.8))/0.4); text(c,"× 7",1150,640,120,GOLD,a7,SANS,align='l',glow=0.6)
    if bar(42)<=t<bar(47):
        a=min(1,(t-bar(42))/0.6,(bar(47)-t)/0.3)
        b=g('ball')
        if b and b[2]: hist.append((b[0],b[1]))
        if len(hist)>8:
            k=len(hist)-1; kk=(k//6)*6-4; kk=max(0,min(k,kk)); gx,gy=hist[kk]
            if t>=snap(98.6):
                an['gaze']=[gx,gy,1]
                c.drawCircle(gx,gy,46,P(CYAN,a,stroke=3)); c.drawLine(gx-64,gy,gx-50,gy,P(CYAN,a,stroke=3)); c.drawLine(gx+50,gy,gx+64,gy,P(CYAN,a,stroke=3))
                text(c,"你的视线",gx,gy-62,24,CYAN,a,MONO)
        if t>=snap(96.3):
            a2=a*ease((t-snap(96.3))/0.4)
            bracketbox(c,100,150,760,170,a2)
            text(c,"平滑追踪舒适上限",130,205,28,WHITE,a2,SANSR,align='l'); text(c,"≈ 70°/s",130,280,60,CYAN,a2,SANS,align='l',glow=0.4)
            text(c,"场边的球",520,205,28,WHITE,a2,SANSR,align='l'); text(c,"138°/s",520,280,60,GOLD,a2,SANS,align='l',glow=0.5)
    if bar(47)<=t<bar(51):
        a=min(1,(t-bar(47))/0.5,(bar(51)-t)/0.3)
        if t>=snap(107.0):
            a2=a*ease((t-snap(107.0))/0.4); bracketbox(c,560,150,800,150,a2)
            text(c,"纵深运动灵敏度 ≈ 横向的 1/3",960,222,42,GOLD,a2,SANS,glow=0.4); text(c,"Tyler · Science · 1971（双眼立体运动阈值）",960,272,22,GRAY,a2,MONO)
    if bar(51)<=t<bar(55):
        a=min(1,(t-bar(51))/0.5,(bar(55)-t)/0.3)
        for k,lab in (('tennis','网球场 · 23.77 m'),('football','足球场 · 105 m')):
            v=g(k)
            if onscreen(v,20): hudlabel(c,v[0],v[1],lab,a,GOLD if k=='football' else CYAN,50,-90,26)
    if bar(55)<=t<bar(60):
        a=min(1,(t-bar(55))/0.5,(bar(60)-t)/0.3)
        if t>snap(121.0): text(c,"J.F. BROWN · 1931",168,170,30,GRAY,a*ease((t-snap(121.0))/0.5),MONO,align='l',spacing=6)
        for k,lab in (('pSmallTop','窗口 ×1'),('pBigTop','窗口 ×2')):
            v=g(k)
            if onscreen(v,10): text(c,lab,v[0],v[1]-22,28,CYAN,a,MONO,glow=0.3)
        v=g('pBig')
        if t>=snap(124.8) and v and v[2]:
            top=g('pBigTop'); cy=(v[1]+top[1])/2 if top else v[1]-300
            a2=a*ease((t-snap(124.8))/0.4); text(c,"×1.94",v[0],cy+30,120,GOLD,a2,SANS,glow=0.6)
            text(c,"暗室 · 7 人平均（明亮环境约 ×1.57）",v[0],cy+90,22,GRAY,a2,MONO)
    if bar(60)<=t<bar(64):
        a=min(1,(t-bar(60))/0.5,(bar(64)-t)/0.3)
        v=g('win')
        if onscreen(v,20): text(c,"电视画面 ≈ 40 m",v[0],v[1]+60,24,GOLD,a,MONO,glow=0.4)
        bracketbox(c,100,150,820,170,a)
        text(c,"电视",130,205,28,WHITE,a,SANSR,align='l'); text(c,"0.5 画面/秒",130,280,52,GOLD,a,SANS,align='l',glow=0.4)
        text(c,"看台",520,205,28,WHITE,a,SANSR,align='l'); text(c,"0.19 球场/秒",520,280,52,CYAN,a,SANS,align='l',glow=0.3)
        text(c,"假设：20 m/s 传球",960,1030,22,GRAY,a,MONO)
    if bar(64)<=t<bar(69):
        a=min(1,(t-bar(64))/0.5,(bar(69)-t)/0.3)
        for k,lab,cc in (('tennis','距离 · 被压扁',CYAN),('football','窗口 · 被缩小',GOLD)):
            v=g(k)
            if onscreen(v,20): text(c,lab,v[0],v[1]+110,26,cc,a,MONO,glow=0.4)
        if t>=snap(144.9): a2=a*ease((t-snap(144.9))/0.5); text(c,"角度 · 距离 · 窗口",960,900,72,WHITE,a2,SERIF,glow=0.4)
    if bar(77)<=t<bar(82):
        lt=t-bar(77); a=min(1,(bar(82)-t)/0.8)
        rich(c,"致每一个隔着屏幕，",960,330,68,a,SERIF,reveal=lt-0.4)
        rich(c,"觉得别人都很从容的人：",960,430,68,a,SERIF,reveal=lt-1.4)
        rich(c,"【他们的球，也快得看不清。】",960,600,76,a,SERIF,reveal=lt-3.4)
    if t>=bar(82):
        a=min(1,(t-bar(82))/0.6)
        text(c,"参考资料",960,250,44,WHITE,a,SERIF); y=340
        for s in SRC:
            if s: text(c,s,560,y,24,GRAY if not s[0]>'z' else WHITE,a,MONO if s[0]<='z' else SANSR,align='l')
            y+=50
    for s,d,txt,pl in CAPS:
        if pl and s<=t<s+d+0.35: caption(c,t,s,d,txt,pl,an)

def main(inp,out,anchors_files):
    an={}
    for fpath in anchors_files:
        for f,a in json.load(open(fpath)): an[f]=a
    dec=subprocess.Popen(['ffmpeg','-loglevel','error','-i',inp,'-f','rawvideo','-pix_fmt','rgba','-'],stdout=subprocess.PIPE)
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
