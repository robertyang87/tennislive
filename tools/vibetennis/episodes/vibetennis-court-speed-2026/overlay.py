"""vibetennis 第 5 集《同一个球，四块地》字幕与数据叠加层（中英两版，VT_LANG=zh|en）。

用法：python3 overlay.py <3D 母带.mp4 或 concat 列表.txt> <输出.mp4> <分段锚点.json ...>；python3 overlay.py still <静帧.jpg ...>
通用函数（字体、引线字幕、品牌标）抄自第 4 集；文案时间跟着 narration.json 的 at 走（plan.py 排定），
数字出处见 papers/vibetennis-court-speed-2026/sources.md。
"""
import skia, numpy as np, math, json, sys, subprocess, glob, os
W,H,FPS=1920,1080,30
HERE=os.path.dirname(os.path.abspath(__file__))
REPO=os.path.abspath(os.path.join(HERE,'../../../..'))
WORK=os.environ.get('VT_WORK',HERE)  # 渲染中间产物目录（r3d/seg、sfx/），默认就是本目录
# 第 2 集没有 BGM（授权未定），时间轴按秒排，不吸附节拍
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
def wrap(s,size,maxw=930,tf=None): return (wrap_en if LANG=='en' else wrap_zh)(s,size,maxw,tf)
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
    text(c,tr("网球时差","Tennis Jetlag"),BRAND_X+BRAND_ICON+BRAND_GAP,BRAND_BASE,BRAND_SIZE,WHITE,0.88,SANS,align='l',spacing=1)

L,R,C='l','r','c'
NAR=json.load(open(os.path.join(HERE,'narration.json')))
AT={l['file']:l['at'] for l in NAR['lines']}
def speak(f):
    wb=json.load(open(os.path.join(HERE,'voice',f+'.json'))); return AT[f]+wb[0]['off'], AT[f]+wb[-1]['off']+wb[-1]['dur']
ORDER=[l['file'] for l in NAR['lines']]
def span(f,until=None,pad=0.25):
    s,e=speak(f)
    if until: e=speak(until)[0]-pad
    else:
        i=ORDER.index(f); e=(speak(ORDER[i+1])[0]-pad) if i+1<len(ORDER) else e+2.5
    return s-0.1, max(1.0,e-s+0.1)
TL=json.load(open(os.path.join(HERE,'r3d','timeline.json')))
# ---------------- 文案（锚在被讲的东西旁边） ----------------
# (句子, 截止到哪一句开口[None=下一句], 文案, 位置)
CAPS=[
('h0',None,tr("同一颗球 · 同样的速度 · 红土 / 草地 / 硬地","Same ball · same speed · clay / grass / hard"),('s',960,200,C,46)),
('h1',None,tr("弹出来，是三个不同的球","Three surfaces, three different bounces"),('s',960,200,C,46)),
('h2',None,tr("一年四个大满贯，像四种比赛","Four Slams a year — four different games"),('s',960,200,C,48)),
('s0',None,tr("法网 · 菲利普·夏蒂埃球场 · 【红土】","Roland-Garros · Court Philippe-Chatrier · 【clay】"),('s',168,900,L,42)),
('s1',None,tr("温网 · 中心球场 · 【草地】","Wimbledon · Centre Court · 【grass】"),('s',168,900,L,42)),
('s2',None,tr("澳网 · 罗德·拉沃尔球场 / 美网 · 阿瑟·阿什球场 · 都是【硬地】，却不是同一种","AO · Rod Laver / US Open · Arthur Ashe · both 【hard】, but not the same"),('s',168,900,L,40)),
('s3',None,tr("同一群球员，换一块地，打法就要跟着变","Same players, different ground, different game"),('s',960,940,C,44)),
# ('q0',None,tr("地面，凭什么能左右一场比赛？","How can the ground change a match?"),('s',960,540,C,60)),  # 改由 3D 粒子聚字（scene.js setMorph）
('p0',None,tr("落地，只有几毫秒","A bounce lasts a few milliseconds"),('s',960,200,C,46)),
('p1',None,tr("① 底部先往前【滑】","① The bottom 【slides】 forward"),('a','slo_contact',-60,90,R,700,800,44)),
('p2',None,tr("② 摩擦往回拖：够大就被【咬住】，不够就一路【滑】","② Friction drags back: enough → it 【grips】; not enough → it 【slides】 through"),('a','slo_fr',-40,-90,R,700,320,44)),
('p3',None,tr("→ 决定离地时还剩多少【水平速度】","→ sets how much 【horizontal speed】 is left"),('s',960,200,C,44)),
('p4',None,tr("弹性：地面把球往上【顶回去】多少","Restitution: how hard the ground 【pushes back up】"),('a','slo_nr',60,-40,L,1300,320,44)),
('p5',None,tr("快不快，主要看两个数：【摩擦】和【弹性】","Pace comes down to two numbers: 【friction】 and 【restitution】"),('s',960,200,C,46)),
('p6',None,tr("国际网联场地速度评级：【摩擦】越大、【弹】得越高 → 越慢","ITF court pace rating: more 【friction】, higher 【bounce】 → slower"),('s',960,200,C,44)),
('n0',None,tr("红土：球斜着落地时，摩擦系数最高可达 【0.9】","Clay: friction up to 【0.9】 at low angles"),('a','lane_RG_hit',-40,-150,R,700,300,46)),
('n1',None,tr("细沙 → 对鞋：像【滚珠】，能滑步","Fine grit → under shoes: 【ball bearings】"),('s',960,200,C,44)),
('n2',None,tr("细沙 → 对球：像【砂纸】，把球拖住","Fine grit → on the ball: 【sandpaper】"),('s',960,200,C,44)),
('n3',None,tr("砸出小坑，被顶得更高（竖直弹性约 【0.85】）","It digs a dent and kicks up (vertical restitution ≈ 【0.85】)"),('a','lane_RG',40,-80,L,1200,300,42)),
('n4',None,tr("温网草地：摩擦只有 【0.5–0.6】，又低又快","Wimbledon grass: friction only 【0.5–0.6】 — low and fast"),('a','lane_WIM',40,-90,L,1200,300,44)),
('d0',None,tr("理论 vs 比赛数据","Theory vs match data"),('s',960,975,C,50)),
('d1',None,tr("1991 年以来 ATP 技术统计 · 给四大满贯算【发球指数】","ATP match stats since 1991 · a 【serve index】 for each Slam"),('s',960,975,C,42)),
('d2',None,tr("指数 > 1：这里的 ACE，比按球员平时水平预计的【更多】","Index > 1: 【more aces】 than the players’ usual level predicts"),('s',960,975,C,44)),
('d3',None,tr("近十年（2015–2026）","Last decade (2015–2026)"),('s',960,975,C,44)),
('r1',None,tr("论摩擦，温网草地最快；按 ACE 算，近十年最占便宜的是【澳网】","By friction, Wimbledon grass is fastest; by aces, 【the AO】 leads"),('s',960,975,C,42)),
('r2',None,tr("「低角度更快的场地，高角度不一定更快」—— Cross, 2003","“A court faster at low angles isn’t necessarily faster at high ones” — Cross, 2003"),('s',960,975,C,38)),
('k0',None,tr("澳网和美网：为什么也不一样快？","AO vs US Open: why aren’t they equally fast?"),('s',960,975,C,46)),
('k1',None,tr("硬地 ＝ 刷在地面上的几层【丙烯酸涂层】，像油漆","A hard court = layers of 【acrylic coating】, like paint"),('a','acr_layers',40,-60,L,300,800,42)),
('k2',None,tr("快慢，看最上面那层漆里掺的【沙子】","Pace comes from the 【sand】 in the top coat"),('s',960,975,C,44)),
('k3',None,tr("美网面层厂家 Laykold：大而有棱角的沙 → 中速；细而圆的沙 → 中快","US Open supplier Laykold: big angular sand → medium; fine round sand → medium-fast"),('s',960,975,C,36)),
('k4',None,tr("澳网用 GreenSet 的涂层，每年还能改变粗糙程度","The AO uses GreenSet’s coating — its grit can be tuned year to year"),('s',960,975,C,40)),
('k5',None,tr("2021：德约说「15 年来最快」；赛事方：赛前检测和上一年差不多","2021: Djokovic — fastest in his 15 years; organisers — tests similar to last year"),('s',960,975,C,36)),
('k6',None,tr("发球指数：2020 年 【1.02】 → 2021 年 【1.19】","Serve index: 【1.02】 in 2020 → 【1.19】 in 2021"),('s',960,975,C,44)),
('r3',None,tr("传言：温网 2001 年换了草种，变慢了","The story: Wimbledon slowed after a 2001 grass change"),('s',960,200,C,44)),
('r4',None,tr("温网官方：改为 100% 黑麦草是为耐磨，「不影响场地的体感速度」","Wimbledon: 100% ryegrass for durability, “without affecting the perceived speed”"),('s',960,200,C,38)),
('r5',None,tr("我们的数据：看不出温网变慢","Our data: no sign Wimbledon slowed"),('s',960,200,C,44)),
('r6',None,tr("法网 · 发球指数 · 2015–2025","Roland-Garros · serve index · 2015–2025"),('s',960,200,C,44)),
('r7',None,tr("2020：挪到 9–10 月 · 换用新的比赛用球","2020: moved to Sept–Oct · new match ball"),('a','yr_2020',40,-70,L,1200,300,42)),
('r8',None,tr("2020：【0.60】，近十年最低","2020: 【0.60】 — lowest in a decade"),('a','yr_2020',40,-70,L,1200,300,46)),
('r9',None,tr("温网官方：阴冷潮湿时，球「更重、更慢」","Wimbledon: on cold, damp days the ball feels “heavier and slower”"),('s',960,200,C,40)),
('e0',None,tr("快慢：地面、球、天气，一起决定","Pace: surface, ball and weather together"),('s',960,200,C,50)),
# ('e1',None,tr("球场的地面，也是比赛的一方","The ground is a player too"),('s',960,540,C,64)),  # 改由 3D 粒子聚字（scene.js setMorph）
('e2',None,tr("你在哪种场地上，打得最顺手？","Which surface suits your game?"),('s',960,940,C,48)),
]
CAPS=[(span(f,u)[0],span(f,u)[1],txt,pl) for f,u,txt,pl in CAPS]
def sec_of(t):
    for s in TL['sections']:
        if s['t0']<=t<s['t1']: return s
    return TL['sections'][-1]
LANE_LAB={'RG':tr('红土','Clay'),'WIM':tr('草地','Grass'),'AO':tr('硬地','Hard')}
LANE_COL={'RG':(1,0.6,0.35),'WIM':(0.55,1,0.6),'AO':(0.45,0.8,1)}
PIL=[('RG',tr('法网','RG'),0.75),('USO',tr('美网','USO'),1.02),('WIM',tr('温网','WIM'),1.09),('AO',tr('澳网','AO'),1.12)]
RGY={2015:0.755,2016:0.793,2017:0.823,2018:0.818,2019:0.743,2020:0.597,2021:0.842,2022:0.737,2023:0.635,2024:0.715,2025:0.721}
CHAP={'hook':("01",tr("现象","PHENOMENON")),'venues':("02",tr("四大满贯","THE SLAMS")),'q':("03",tr("机制","MECHANISM")),'slow':("03",tr("机制","MECHANISM")),
 'clay':("03",tr("机制","MECHANISM")),'grass':("03",tr("机制","MECHANISM")),'data':("04",tr("证据","EVIDENCE")),'rev1':("04",tr("证据","EVIDENCE")),
 'hard':("05",tr("硬地","HARD COURTS")),'aoy':("05",tr("硬地","HARD COURTS")),'rev2':("06",tr("反常","ANOMALIES")),'rev3':("06",tr("反常","ANOMALIES")),'end':("07",tr("结论","CONCLUSION"))}
def chapter(c,t):  # 右上角章节标签（第 3、4 集同款）
    for s in TL['sections']:
        if s['t0']<=t<s['t1'] and s['name'] in CHAP:
            n,lab=CHAP[s['name']]; prev=[x for x in TL['sections'] if x['t1']<=s['t0']+1e-6]; t0=s['t0']
            while prev and prev[-1]['name'] in CHAP and CHAP[prev[-1]['name']][0]==n: t0=prev[-1]['t0']; prev=prev[:-1]
            nxt=[x for x in TL['sections'] if x['t0']>=s['t1']-1e-6]; t1=s['t1']
            while nxt and nxt[0]['name'] in CHAP and CHAP[nxt[0]['name']][0]==n: t1=nxt[0]['t1']; nxt=nxt[1:]
            a=max(0,min(1,(t-t0)/0.6,(t1-t)/0.4))
            text(c,n,1630,82,26,GOLD,a,MONO,align='l',glow=0.5); c.drawLine(1672,62,1672,88,P(GOLD,a*0.6,stroke=2)); text(c,lab,1686,82,26,WHITE,a*0.85,SANS,align='l')
import math
def reticle(c,x,y,t,a,lab):  # 全息瞄准环：两圈反向转的刻度＋十字＋标签（慢镜咬住时锁定接触点）
    for r,sp,n in ((78,0.9,24),(104,-0.5,36)):
        for i in range(n):
            ang=i/n*2*math.pi+t*sp; L=10 if i%6==0 else 5
            c.drawLine(x+math.cos(ang)*r,y+math.sin(ang)*r,x+math.cos(ang)*(r+L),y+math.sin(ang)*(r+L),P(CYAN,a*(0.9 if i%6==0 else 0.45),stroke=2))
    c.drawCircle(x,y,60,P(CYAN,a*0.35,stroke=1.5))
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)): c.drawLine(x+dx*20,y+dy*20,x+dx*44,y+dy*44,P(CYAN,a*0.8,stroke=2))
    text(c,lab,x+120,y-84,22,CYAN,a,SANS,align='l',glow=0.4)
CITYLAB={'AO':(tr("1 月","JAN"),tr("墨尔本 · 澳网","Melbourne · AO"),(0.45,0.8,1.0)),'RG':(tr("5–6 月","MAY–JUN"),tr("巴黎 · 法网","Paris · Roland-Garros"),(1.0,0.6,0.35)),
 'WIM':(tr("6–7 月","JUN–JUL"),tr("伦敦 · 温网","London · Wimbledon"),(0.55,1.0,0.6)),'USO':(tr("8–9 月","AUG–SEP"),tr("纽约 · 美网","New York · US Open"),(0.5,0.62,1.0))}
def altimeter(c,an):  # 卫星简报式的高度读数（Lemo-Opuscar「Satellite Briefing」：仪表只放屏幕角落）
    alt=an.get('globe_alt')
    if not alt: return
    c.drawRect(skia.Rect.MakeXYWH(1560,930,320,96),P((0.02,0.04,0.08),0.75)); c.drawLine(1560,930,1880,930,P(WHITE,0.6,stroke=2))
    text(c,tr("轨道高度","ALTITUDE"),1580,962,18,(0.7,0.78,0.9),0.9,SANS,align='l',spacing=2); text(c,f"{alt:,} km",1580,1008,40,WHITE,1,MONO,align='l')
def citylabels(c,an):
    for k,(m,lab,col) in CITYLAB.items():
        v=an.get('city_'+k); on=an.get('city_on_'+k,0)
        if on and on>0.02 and onscreen(v,40):
            dx,dy={'AO':(46,0),'USO':(46,0),'RG':(56,62),'WIM':(-56,-56)}[k]; al='l' if dx>0 else 'r'  # 巴黎和伦敦只隔 340 km：一个标右下、一个标左上，别叠在一起
            c.drawLine(v[0],v[1],v[0]+dx*0.8,v[1]+dy-26,P(col,on*0.8,stroke=1.5))
            text(c,lab,v[0]+dx,v[1]+dy-30,36,WHITE,on,SANS,align=al,glow=0.4); text(c,m,v[0]+dx,v[1]+dy+8,26,col,on*0.95,MONO,align=al)  # 所有者 2026-11-02：每个点标「城市 · 赛事」，字放大
MARK=(1.0,0.84,0.0); MRED=(1.0,0.32,0.28)
def mline(c,x0,y0,x1,y1,a,cc=MARK,w=6):  # 马克笔线：深色描边＋亮色主线
    c.drawLine(x0,y0,x1,y1,P((0,0,0),a*0.55,stroke=w+5)); c.drawLine(x0,y0,x1,y1,P(cc,a,stroke=w))
def card(c,x,y,zh,en,a,cc=MARK):  # 画板标签：黑卡片＋左侧色条＋中文＋小号英文
    f=skia.Font(SANS,34); w=max(f.measureText(zh),200)+48
    c.drawRect(skia.Rect.MakeXYWH(x,y,w,86),P((0.04,0.05,0.07),a*0.88)); c.drawRect(skia.Rect.MakeXYWH(x,y,7,86),P(cc,a))
    text(c,zh,x+24,y+44,34,WHITE,a,SANS,align='l'); text(c,en,x+24,y+72,16,(0.75,0.8,0.88),a*0.9,SANSR,align='l',spacing=2)
def tele(c,t,an):
    m=an.get('tele_mode')
    if not m: return
    k=an.get('tele_k',0); fid=an.get('tele_freeze',0)
    tag={'rewind':"◀◀  "+tr("倒带","REWIND"),'slow':"▶ ½  "+tr("慢放","SLOW"),'freeze':"||  "+tr("定格","FREEZE")}.get(m)
    if tag: c.drawRect(skia.Rect.MakeXYWH(40,118,210,44),P((0.04,0.05,0.07),0.8)); text(c,tag,58,149,24,MARK if m!='rewind' else WHITE,1,MONO,align='l')
    if m=='rewind':
        for i in range(4):
            y=(t*900+i*277)%1080; c.drawRect(skia.Rect.MakeXYWH(0,y,1920,10+i*3),P(WHITE,0.35))
        text(c,"◀◀",960,560,150,WHITE,0.9,SANS,glow=0.4); text(c,tr("倒带","REWIND"),960,650,40,WHITE,0.9,SANS,spacing=6)
    if m!='freeze': return
    h,rx,rz=an.get('tele_hit'),an.get('tele_rx'),an.get('tele_rz')
    if fid==1 and h and rx and rz:
        ax=math.hypot(rx[0]-h[0],rx[1]-h[1]); az=math.hypot(rz[0]-h[0],rz[1]-h[1]); rect=skia.Rect.MakeLTRB(h[0]-ax,h[1]-az,h[0]+ax,h[1]+az)
        c.drawArc(rect,-90,360*ease(k),False,P((0,0,0),0.5,stroke=11)); c.drawArc(rect,-90,360*ease(k),False,P(MARK,1,stroke=6))
        if k>0.6: card(c,h[0]+ax+40,h[1]-140,tr("细沙像砂纸，把球拖住","Grit drags the ball"),"CLAY · FRICTION μ≈0.9",min(1,(k-0.6)/0.3))
    if fid in (2,3) and h:
        g,o=an.get('tele_gx'),an.get('tele_out')
        if g and o:
            a1=math.degrees(math.atan2(g[1]-h[1],g[0]-h[0])); a2=math.degrees(math.atan2(o[1]-h[1],o[0]-h[0])); r=170
            mline(c,h[0],h[1],h[0]+(g[0]-h[0])*1.6,h[1]+(g[1]-h[1])*1.6,1,WHITE,3)
            L=ease(k); mline(c,h[0],h[1],h[0]+(o[0]-h[0])*L,h[1]+(o[1]-h[1])*L,1)
            da=((a1-a2+180)%360)-180; c.drawArc(skia.Rect.MakeLTRB(h[0]-r,h[1]-r,h[0]+r,h[1]+r),a2,da*ease(k),False,P(MARK,1,stroke=4))
            deg=24 if fid==2 else 16  # 模型：入射 16°；红土咬住 → 23.9°，草地（μ0.55、e0.72）一路滑 → 15.8°
            mx=(h[0]+o[0])/2; cx=min(max(mx-170,40),1420)
            if k>0.5: card(c,cx,max(h[1],o[1])+70,tr(f"出射角 ≈ {deg}°（模型）",f"Exit angle ≈ {deg}° (model)"),"CLAY · BOUNCES HIGHER" if fid==2 else "GRASS · SKIDS LOW & FAST",min(1,(k-0.5)/0.3),MARK if fid==2 else (0.55,1,0.6))
        if fid==3:
            pts=[an.get('tele_ghost%d'%q) for q in range(9)]
            for q in range(8):
                p0,p1=pts[q],pts[q+1]
                if p0 and p1 and q%2==0: mline(c,p0[0],p0[1],p1[0],p1[1],0.85*ease(k),(1.0,0.6,0.35),4)
            if pts[8] and k>0.5: text(c,tr("红土 ≈ 24°","Clay ≈ 24°"),pts[8][0]+20,pts[8][1]-10,26,(1.0,0.6,0.35),min(1,(k-0.5)/0.3),SANS,align='l')
def draw(c,t,an):
    brand(c); chapter(c,t); citylabels(c,an); altimeter(c,an); tele(c,t,an); s=sec_of(t)
    if s['kind']=='slow' and AT['p2']<=t<AT['p3']:
        v=an.get('slo_reticle')
        if onscreen(v,10): reticle(c,v[0],v[1],t,min(1,(t-AT['p2'])/0.4,(AT['p3']-t)/0.4),tr("接触点 · 锁定","CONTACT · LOCKED"))
    s=sec_of(t); k=s['kind']; u=t-s['t0']; a=min(1,u/0.5,(s['t1']-t)/0.4)
    if k in ('lanes_all','lane_RG','lane_WIM') and not an.get('globe_alt'):  # 切到地球后泳道已隐藏，别留下飘着的「红土/草地/硬地」
        for ln in ('RG','WIM','AO'):
            v=an.get('lane_'+ln)
            if onscreen(v,40): hudlabel(c,v[0],v[1],LANE_LAB[ln],a*0.9,LANE_COL[ln],dx=30,dy=-50,size=26)
    if k in ('pillars','pillars_hi'):
        text(c,tr("1 片 ＝ 0.05　·　每第 10 片换成黄铜","1 disc = 0.05  ·  every 10th disc in brass"),60,1000,22,(0.85,0.75,0.45),a*0.9,SANS,align='l')
        hi=('WIM','AO') if k=='pillars_hi' else None
        for key,lab,val in PIL:
            v=an.get('pil_'+key)
            if onscreen(v,20):
                aa=a*(0.35 if hi and key not in hi else 1)
                text(c,lab,v[0],v[1]-46,30,WHITE,aa,SANS)
                text(c,f"{val:.2f}",v[0],v[1]-6,40,GOLD if (hi and key in hi) else CYAN,aa,MONO,glow=0.4)
        v=an.get('pil_ref')
        if onscreen(v,10): text(c,tr("1.00 = 平时水平","1.00 = usual"),v[0]+10,v[1]-10,22,GRAY,a,SANS,align='l')
        text(c,tr("发球指数 ＝ 实际 ACE ÷ 按发球人、接发人当年水平算出的期望值；数据：Sackmann 公开数据，ATP 男单","Serve index = actual aces ÷ expected from each server’s and returner’s season; data: Sackmann, ATP men"),960,1062,18,GRAY,a*0.9,SANSR)
    if k=='acryl' and t>=AT['k2']:
        for key,lab in (('acr_coarse',tr('大、有棱角 → 抓住绒毛 → 慢','Big, angular → grabs the felt → slower')),('acr_fine',tr('细、圆 → 抓得少 → 快','Fine, round → less grip → faster'))):
            v=an.get(key)
            if onscreen(v,20): text(c,lab,min(max(v[0],300),1620),max(v[1],170),30,GOLD if key=='acr_coarse' else CYAN,a,SANS,glow=0.3)  # 夹在安全区内，别顶到章节标签
    if k=='ao_years':
        for y in range(2015,2027):
            v=an.get('ay_%d'%y); vb=an.get('ayb_%d'%y); hl=(y in (2020,2021) and t>=AT['k6']-0.2)
            val={2015:1.124,2016:1.222,2017:1.156,2018:1.074,2019:1.191,2020:1.020,2021:1.189,2022:1.090,2023:1.076,2024:1.094,2025:1.103,2026:1.064}[y]
            if onscreen(v,10): text(c,f"{val:.2f}",v[0],v[1],26,GOLD if hl else WHITE,a,MONO)
            if onscreen(vb,10): text(c,str(y),vb[0],vb[1]+30,24,GOLD if hl else GRAY,a,SANS)
        text(c,tr("澳网发球指数（2020 年起 GreenSet 涂层）","AO serve index (GreenSet coating from 2020)"),960,1062,20,GRAY,a*0.9,SANSR)
    if k=='years':
        for y,val in RGY.items():
            v=an.get('yr_%d'%y); vb=an.get('yrb_%d'%y)
            hl=(y==2020 and t>=AT['r8']); 
            if onscreen(v,10): text(c,f"{val:.2f}",v[0],v[1],26,(1,0.35,0.35) if hl else WHITE,a,MONO)
            if onscreen(vb,10): text(c,str(y),vb[0],vb[1]+30,24,(1,0.35,0.35) if hl else GRAY,a,SANS)
    if k=='outro' and u>D_OUT(s)-5.0:
        text(c,tr("资料：Cross, Sports Engineering 2003 / Physics Today 2008 · 温网官方场地资料 · ITF 场地分级 · Sackmann ATP 数据","Sources: Cross, Sports Engineering 2003 / Physics Today 2008 · Wimbledon grounds fact sheet · ITF · Sackmann ATP data"),960,1040,18,GRAY,min(1,(u-(D_OUT(s)-5.0))/0.5),SANSR)
    for s0,d,txt,pl in CAPS:
        if s0<=t<s0+d+0.35: caption(c,t,s0,d,txt,pl,an)
def D_OUT(s): return s['t1']-s['t0']

def main(inp,out,anchors_files):
    an={}
    for fpath in anchors_files:
        for f,a in json.load(open(fpath)): an[f]=a
    dec=subprocess.Popen(['ffmpeg','-loglevel','error']+(['-f','concat','-safe','0'] if inp.endswith('.txt') else [])+['-i',inp,'-f','rawvideo','-pix_fmt','rgba','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgba','-s','%dx%d'%(W,H),'-r',str(FPS),'-i','-','-c:v','libx264','-preset','medium','-crf','19','-maxrate','30M','-bufsize','60M','-pix_fmt','yuv420p','-movflags','+faststart',out],stdin=subprocess.PIPE)
    f=int(os.environ.get('OV_F0','0')); n=W*H*4  # OV_F0：只渲一段补丁时，输入第 0 帧对应的全片帧号
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
            t=float(os.path.basename(p)[2:9]); an=json.load(open(p.replace('.jpg','.json')))
            arr=np.array(Image.open(p).convert('RGBA')); s=skia.Surface(arr); draw(s.getCanvas(),t,an)
            Image.fromarray(arr[...,:3]).save(p.replace('.jpg','_ov.jpg'),quality=90)
    else:
        main(sys.argv[1],sys.argv[2],sys.argv[3:])
