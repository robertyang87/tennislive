"""vibetennis 第 4 集《费德勒只赢了 54% 的分，凭什么赢了八成多的比赛？》字幕与信息面板叠加层（中英两版，VT_LANG=zh|en）。

用法：python3 overlay.py <3D 母带.mp4> <输出.mp4> <分段锚点.json ...>；python3 overlay.py still <静帧.jpg ...>
通用函数（字体、引线字幕、品牌标）抄自第 2 集 overlay.py；文案、面板和数字是这一集的，出处见 papers/vibetennis-federer-54-percent-2026/sources.md。
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
        if NARR and y>=860: y=y-90   # 中文版底部有配音字幕：底部居中的锚定字幕整体上移
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




# ---------------- captions（锚在被讲的东西旁边；数字出处见 papers/vibetennis-federer-54-percent-2026/sources.md） ----------------
# place: ('s',x,y,align[,size]) 固定位置；('a',anchor,dx,dy,align,fx,fy[,size]) 引线连到 3D 元素，找不到就退回 fx,fy
L,R,C='l','r','c'
CAPS=[
# 00 开场
(0.35,2.0,tr("费德勒：职业生涯 【1526】 场单打","Federer: 【1,526】 singles matches"),('s',960,900,C,50)),
(2.6,1.9,tr("赢了 【1251】 场，胜率 【82%】","Won 【1,251】 — 【82%】"),('s',960,900,C,50)),
(4.7,1.25,tr("可每一分，他只赢了 【54%】","Yet he won only 【54%】 of points"),('s',960,900,C,50)),
(6.0,0.95,tr("只比一半多一点，凭什么？","Barely over half. So how?"),('s',960,210,C,58)),
# 01 理论大标题
(9.1,1.9,tr("答案藏在一个数学工具里","The answer is a piece of maths"),('s',960,250,C,46)),
# 02 一分：天平
(16.0,2.6,tr("把他打过的分，按每 100 分来看","Take his points, 100 at a time"),('s',960,190,C,46)),
(18.9,3.8,tr("每 100 分：【54 分】他赢，【46 分】他输","Every 100 points: he wins 【54】, loses 【46】"),('s',960,190,C,46)),
(23.0,2.6,tr("天平只歪了 【2.3°】","The scale tips just 【2.3°】"),('a','beam',60,-120,L,1200,300,46)),
(25.9,2.4,tr("几乎就是抛硬币","Almost a coin toss"),('a','coin',-40,-150,R,1500,300,46)),
(28.5,4.2,tr("「平均每两分，就要输掉一分。」","“When you lose every second point, on average, you learn not to dwell on every shot.”"),('s',960,880,C,44 if LANG=='zh' else 34)),
# 03 一局：比分河道
(33.6,3.3,tr("一局：先拿 4 分，还要领先 2 分","A game: first to 4 points, 2 clear"),('s',168,190,L,44)),
(37.1,3.6,tr("每个比分，都是一个【状态】","Every score is a 【state】"),('s',168,190,L,44)),
(40.9,3.5,tr("每一分只决定下一步：赢往右，输往左","Each point decides one step: win → right, lose → left"),('s',168,190,L,42)),
(44.6,3.6,tr("让 【1200 局】 都按「每分 54%」打一遍","Play 【1,200 games】 at 54% per point"),('s',168,190,L,44)),
(48.4,3.2,tr("河道越宽，走这条路的局越多","Wider channel = more games took that path"),('s',168,190,L,42)),
(51.8,3.0,tr("40 平：在平分和占先之间来回打转","Deuce: round and round, advantage and back"),('a','g3_3',-60,40,R,700,700,40)),
(55.0,3.6,tr("下一步只看【现在的比分】——这就是马尔可夫链","Next step depends only on 【the current score】 — a Markov chain"),('s',960,190,C,42)),
(58.8,2.2,tr("局数越多，比例越稳","More games, steadier ratio"),('s',960,190,C,44)),
(61.2,2.6,tr("54% 的一分 → 【60%】 的一局","54% per point → 【60%】 per game"),('s',960,190,C,54)),
# 04 套娃
(64.4,3.0,tr("把整整一局，缩成【一步】","Shrink a whole game into 【one step】"),('s',960,190,C,48)),
(68.0,3.5,tr("一盘：先拿 6 局、领先 2 局；6 平打抢七","A set: first to 6 games, 2 clear; tiebreak at 6–6"),('s',168,190,L,42)),
(71.8,3.6,tr("现在每一步，是 60% 的一局","Now each step is a 60% game"),('s',168,190,L,44)),
(75.8,3.6,tr("同一个规律，再放大一次","Same rule, amplified again"),('s',168,190,L,44)),
(79.8,2.6,tr("60% 的一局 → 【76%】 的一盘","60% per game → 【76%】 per set"),('s',960,190,C,54)),
(82.8,3.2,tr("再缩一层：五盘三胜","One more layer: best of five"),('s',960,190,C,48)),
(86.4,3.6,tr("每一步，是 76% 的一盘","Each step is a 76% set"),('s',168,190,L,44)),
(90.3,4.3,tr("76% 的一盘 → 【91%】 的五盘三胜（三盘两胜 【86%】）","76% per set → 【91%】 best of five (best of three: 【86%】)"),('s',960,190,C,44)),
# 05 S 曲线
(95.6,1.7,tr("三次放大，画在一张图上","Three amplifications, one chart"),('s',960,150,C,42)),
(97.4,1.5,tr("不放大：54% 还是 54%","No amplifier: 54% stays 54%"),('s',960,150,C,42)),
(99.1,1.8,tr("一局：更陡","A game: steeper"),('s',960,150,C,42)),
(101.1,4.0,tr("一盘、一场：一层比一层陡","A set, a match: steeper each layer"),('s',960,150,C,42)),
(105.6,2.8,tr("在 54% 处：60% → 76% → 91%","At 54%: 60% → 76% → 91%"),('s',960,150,C,42)),
(108.6,1.9,tr("退回 50%：谁也不占便宜","Back at 50%: nobody gains"),('s',960,150,C,42)),
(110.7,2.6,tr("每一分只多赢 【1%】","Win just 【1%】 more points"),('s',960,150,C,46)),
(113.5,3.1,tr("五盘三胜的胜率就从 50% 跳到 【63%】","Best-of-five win chance jumps from 50% to 【63%】"),('s',960,150,C,44)),
# 06 验证
(117.3,2.5,tr("这是推导。真实比赛也这样吗？","That's the theory. Does real tennis agree?"),('s',960,170,C,46)),
(120.0,3.1,tr("代入他真实的数据：发球每分赢 【约 70%】，接发 【约 40%】","Plug in his real numbers: 【~70%】 of serve points, 【~40%】 of return points"),('s',960,170,C,38)),
(123.3,3.0,tr("虚线：模型的预测","Dashed: the model's prediction"),('s',960,170,C,44)),
(126.5,4.1,tr("实心：真实统计（ATP 官方与第三方数据）","Solid: real stats (ATP and independent data)"),('s',960,170,C,42)),
(130.8,4.2,tr("每一项都差不到 【2 个百分点】","Every gap under 【2 percentage points】"),('s',960,170,C,46)),
(135.2,4.3,tr("层层放大，在真实比赛里成立","The amplifier holds in real matches"),('s',960,170,C,50)),
# 07 局限
(140.4,3.1,tr("可到了【整场】：模型算 86% 以上，他实际是 82%","But for 【whole matches】: model 86%+, reality 82%"),('s',960,170,C,42)),
(143.7,4.2,tr("研究发现，每一分并不完全独立：关键分上，发球方更难拿分","Research: points aren't fully independent — servers win fewer big points"),('s',960,170,C,38)),
(148.4,2.1,tr("2019 温网决赛","Wimbledon final, 2019"),('s',960,170,C,52)),
(150.6,3.0,tr("费德勒全场赢了 【218】 分，德约科维奇 【204】 分","Federer won 【218】 points, Djokovic 【204】"),('s',960,170,C,44)),
(153.8,3.0,tr("冠军，却是德约科维奇","The champion: Djokovic"),('s',960,170,C,50)),
(157.4,3.3,tr("第五盘 8-7，费德勒发球：两个冠军点","Fifth set, 8–7, Federer serving: two championship points"),('s',960,210,C,44)),
(160.9,1.7,tr("两个都没拿下","He lost both"),('s',960,880,C,56)),
(162.6,1.3,tr("分，并不平等","Not all points are equal"),('s',960,880,C,50)),
# 08 收束
(164.4,3.4,tr("他生涯打过的二十多万分","Over 200,000 points in his career"),('s',960,190,C,46)),
(172.6,3.4,tr("每一分只多 4 个百分点，一层层放大，就是天壤之别","Four points in a hundred, amplified layer by layer, make all the difference"),('s',960,880,C,42)),
(176.2,3.6,tr("你打球时，最放不下的是哪一分？","Which point can't you let go of?"),('s',960,880,C,50)),
]
SECT=[(0,7,"00",tr("问题","QUESTION")),(15.5,33,"01",tr("一分","A POINT")),(33,64,"02",tr("一局","A GAME")),(64,95,"03",tr("套娃","NESTING")),(95,117,"04",tr("放大曲线","AMPLIFIER")),
      (117,140,"05",tr("验证","CHECK")),(140,164,"06",tr("局限","LIMITS")),(164,180,"07",tr("一分","ONE POINT"))]
SRC=["Federer, R. (2024). Dartmouth Commencement Address, 9 June 2024",
"Newton, P. K. & Keller, J. B. (2005). Probability of Winning at Tennis I. Stud. Appl. Math. 114: 241–269",
"Klaassen, F. & Magnus, J. (2001). Are Points in Tennis i.i.d.? JASA 96: 500–509",
"Seneta, E. (2006). Markov and the creation of Markov chains",
"ATP career stats · Roland-Garros “Federer's career in figures” · Al Jazeera (2022)",
"Ultimate Tennis Statistics · Wimbledon 2019 men's final match statistics",
"",
tr("模型：每一分独立同分布；1200 / 800 / 600 局为按模型抽样的模拟对局","Model: points i.i.d.; 1,200 / 800 / 600 games are simulated samples"),
tr("赢局率约 58% 由 ATP 保发率与破发率推算","~58% games won derived from ATP hold and break rates")]
SCORE=['0','15','30','40']
def score_name(a,b):
    if a>=3 and b>=3:
        return tr("平分","Deuce") if a==b else (tr("占先","Adv") if a>b else tr("被占先","Adv out"))
    return f"{SCORE[a]}-{SCORE[b]}"
def secA(t,t0,t1,i=0.5,o=0.3): return max(0,min(1,(t-t0)/i,(t1-t)/o))
def onv(v,m=20): return onscreen(v,m)
def tag(c,x,y,s,a,cc=CYAN,size=22,align='c',tf=None):
    if a<=0: return
    tf=tf or MONO; f=F(tf,size); w=f.measureText(s); x0=x-w/2 if align=='c' else (x-w if align=='r' else x)
    c.drawRoundRect(skia.Rect.MakeXYWH(x0-10,y-size*1.05,w+20,size*1.5),6,6,P((0.02,0.05,0.1),a*0.6)); c.drawRoundRect(skia.Rect.MakeXYWH(x0-10,y-size*1.05,w+20,size*1.5),6,6,P(cc,a*0.8,stroke=1.2))
    text(c,s,x,y,size,cc,a,tf,align=align)
def pct(v,d=1): return ("%."+str(d)+"f%%")%(v*100)
def pool_hud(c,an,kw,kl,kn,wkey,lkey,a,label_w,label_l):
    w,l,n=an.get(kw,0),an.get(kl,0),an.get(kn,1); tot=w+l
    for key,cnt,col,lab in ((wkey,w,GOLD,label_w),(lkey,l,BLUE_C,label_l)):
        v=an.get(key)
        if not onv(v,10): continue
        x,y=v[0],v[1]-12
        text(c,lab,x,y-58,24,WHITE,a*0.85,SANS)
        text(c,(pct(cnt/tot) if tot>=40 else "—"),x,y-12,54,col,a,SANS,glow=0.5)
        text(c,tr("%d 局","%d games")%cnt if kn!='mn' or True else "",x,y+20,20,GRAY,a,MONO)
BLUE_C=(0.45,0.62,1.0)

# 中文版配音字幕：voice.py 写的时间表（每句按 TTS 词边界切成 ≤16 字的短句），屏幕用阿拉伯数字（TTS 稿写汉字）
NARR=[]
if LANG=='zh' and os.path.exists(os.path.join(HERE,'voice','schedule.json')):
    sys.path.insert(0,os.path.join(REPO,'src'))
    from tennislive.video.explainer import arabic_numerals
    for _l in json.load(open(os.path.join(HERE,'voice','schedule.json'))):
        for _p in _l['phrases']: NARR.append((_p['t0'],_p['t1'],arabic_numerals(_p['text'])))
def narr_sub(c,t):
    for i,(t0,t1,s) in enumerate(NARR):
        t1x=max(t1,t0+0.9)+0.15
        if i+1<len(NARR): t1x=min(t1x,NARR[i+1][0])
        if t0-0.05<=t<t1x:
            a=min(1,(t-t0+0.05)/0.12,(t1x-t)/0.12)
            f=F(SANS,40); w=f.measureText(s)
            c.drawRoundRect(skia.Rect.MakeXYWH(960-w/2-26,1002-44,w+52,62),12,12,P((0,0,0),a*0.42))
            text(c,s,960,1002,40,WHITE,a,SANS)
            return

def draw(c,t,an,hist):
    g=lambda k: an.get(k)
    brand(c)
    for t0,t1,n,lab in SECT:
        if t0<=t<t1:
            a=min(1,(t-t0)/0.6,(t1-t)/0.4)
            text(c,n,1630,82,26,GOLD,a,MONO,align='l',glow=0.5); c.drawLine(1672,62,1672,88,P(GOLD,a*0.6,stroke=2)); text(c,lab,1686,82,26,WHITE,a*0.85,SANS,align='l')
    # 00 开场：星系计数
    if t<2.5:
        a=secA(t,0.3,2.5); n=int(1526*min(1,max(0,(t-0.3)/1.3)))
        text(c,"%d"%n,960,820,40,WHITE,a,MONO,glow=0.4)
        text(c,tr("● 胜  ● 负","● won  ● lost"),960,980,22,GRAY,a*0.8,MONO)
    # 01 标题副标与关键词
    if 11.6<=t<15.2:
        a=secA(t,11.7,15.2); v=g('titleBot')
        y=(v[1] if onv(v,5) else 660)+24
        text(c,tr("MARKOV CHAIN · 1906","ANDREY MARKOV · 1906"),960,y,26,GOLD,a,MONO,spacing=6)
        for i,(zh,en,cc) in enumerate(((tr("比分＝状态","Score = state"),"",CYAN),(tr("每一分只决定下一步","Each point, one step"),"",(1,0.55,0.15)),(tr("层层放大","Amplified layer by layer"),"",GOLD))):
            ai=a*ease((t-12.4-i*0.5)/0.35); tag(c,960+(i-1)*380,y+90,zh,ai,cc,26,tf=SANS)
    # 02 天平计数
    if 17<=t<33:
        a=secA(t,17.2,33)
        for key,cnt,col,lab in (('panL',an.get('won',0),GOLD,tr("他赢","won")),('panR',an.get('lost',0),BLUE_C,tr("他输","lost"))):
            v=g(key)
            if onv(v,10): text(c,"%d"%cnt,v[0],v[1]+110,64,col,a,SANS,glow=0.5); text(c,lab,v[0],v[1]+146,22,GRAY,a,MONO)
        if 25.9<=t: v=g('coin'); aa=secA(t,26.2,33); 
        if 25.9<=t and onv(g('coin'),10): v=g('coin'); text(c,"50 : 50",v[0],v[1]+130,32,WHITE,aa*0.9,MONO)
        if 28.5<=t<33 and LANG=='zh': aa=secA(t,28.7,33); text(c,"“When you lose every second point, on average, you learn not to dwell on every shot.”",960,938-(90 if NARR else 0),22,GRAY,aa,MONO)
        if 28.5<=t<33: aa=secA(t,28.7,33); text(c,tr("—— 费德勒，2024 年达特茅斯学院毕业演讲","— Roger Federer, Dartmouth Commencement, 2024"),960,(974-(90 if NARR else 0)) if LANG=='zh' else 1040,20,GRAY,aa*0.8,SANSR)
    # 03 一局：比分节点与水库
    if 34<=t<64:
        a=secA(t,35.4,64)
        for a_ in range(4):
            for b_ in range(4):
                if a_+b_>6: continue
                v=g('g%d_%d'%(a_,b_))
                if onv(v,10) and not (a_==3 and b_==3): text(c,score_name(a_,b_),v[0]+28,v[1]+8,20,WHITE,a*0.8,MONO,align='l')
        for k,(a_,b_) in (('g3_3',(3,3)),('g4_3',(4,3)),('g3_4',(3,4))):
            v=g(k)
            if onv(v,10): text(c,score_name(a_,b_),v[0]+(30 if a_>=b_ else -30),v[1]+8,20,GOLD if a_>b_ else (WHITE if a_==b_ else BLUE_C),a*0.85,SANS if LANG=='zh' else MONO,align='l' if a_>=b_ else 'r')
        if t>=44: pool_hud(c,an,'gw','gl','gn','gWinTop','gLoseTop',a*ease((t-44.5)/0.6),tr("赢下这一局","game won"),tr("丢掉这一局","game lost"))
    # 04 套娃：一盘、一场的水库
    if 68.5<=t<82.6:
        a=secA(t,69,82.6); pool_hud(c,an,'sw','sl','sn','sWinTop','sLoseTop',a,tr("赢下这一盘","set won"),tr("丢掉这一盘","set lost"))
        v=g('s6_6')
        if onv(v,10): tag(c,v[0],v[1]+52,tr("6 平 · 抢七","6–6 · tiebreak"),a*0.9,WHITE,20)
        v=g('s0_0')
        if onv(v,10) and t<74: tag(c,v[0],v[1]-34,tr("这一步 = 一整局","one step = one game"),a*0.9,CYAN,20)
    if 86<=t<95:
        a=secA(t,86.5,95); pool_hud(c,an,'mw','ml','mn','mWinTop','mLoseTop',a,tr("赢下这一场","match won"),tr("输掉这一场","match lost"))
        v=g('m0_0')
        if onv(v,10) and t<90: tag(c,v[0],v[1]-40,tr("这一步 = 一整盘","one step = one set"),a*0.9,CYAN,20)
    # 05 S 曲线：坐标、曲线名、读数
    if 95.6<=t<117:
        a=secA(t,96,117)
        for v_ in (40,45,50,55,60):
            v=g('ax%d'%v_)
            if onv(v,5): text(c,"%d%%"%v_,v[0],v[1]+30,20,GRAY,a,MONO)
        for v_ in (0,50,100):
            v=g('ay%d'%v_)
            if onv(v,5): text(c,"%d%%"%v_,v[0]-8,v[1]+7,20,GRAY,a,MONO,align='r')
        v=g('ax50')
        if onv(v,5): text(c,tr("每一分的胜率 →","win % per point →"),v[0],v[1]+62,22,GRAY,a,SANSR)
        names=[tr("一分（不放大）","a point"),tr("一局","a game"),tr("一盘","a set"),tr("一场（五盘三胜）","a match (Bo5)")]
        cols=[(0.7,0.9,1.0),CYAN,(1,0.78,0.5),GOLD]; starts=[98.4,100.6,102.8,105.0]
        for i in range(4):
            v=g('cEnd%d'%i)
            if onv(v,5) and t>=starts[i]: text(c,names[i],v[0]+16,v[1]+8-(i==3)*16+(i==2)*10,22,cols[i],a*ease((t-starts[i])/0.4),SANS,align='l')
        p=an.get('p')
        if p is not None and t>=105.4:
            aa=a*ease((t-105.4)/0.5); x0,y0=1450,640
            bracketbox(c,x0-20,y0-40,330,250,aa)
            rows=[(tr("每一分","point"),an.get('cv0',p)),(tr("一局","game"),an.get('cv1',0)),(tr("一盘","set"),an.get('cv2',0)),(tr("一场","match"),an.get('cv3',0))]
            for i,(lab,vv) in enumerate(rows):
                text(c,lab,x0,y0+i*52,24,cols[i],aa,SANS,align='l'); text(c,pct(vv),x0+290,y0+i*52,30,cols[i],aa,MONO,align='r',glow=0.3 if i==3 else 0)
    # 06 验证：每根柱的名字、模型值、真实值
    if 121<=t<140:
        a=secA(t,121.3,140)
        labs=[tr("保发率","Service games held"),tr("破发率","Return games broken"),tr("赢局率","Games won")]
        model=[0.897,0.256,0.599]; real=[0.888,0.266,0.581]; realtxt=["88.8%","26.6%",tr("约 58%","~58%")]
        for i in range(3):
            vb,vm,vr=g('vb%d'%i),g('vm%d'%i),g('vr%d'%i)
            if onv(vb,5): text(c,labs[i],vb[0],vb[1]+40,26,WHITE,a,SANS)
            am=a*ease((t-121.5-i*0.9)/0.6)
            if onv(vm,5): text(c,tr("模型 ","model ")+pct(model[i]),vm[0]-70,vm[1]-14,22,CYAN,am,MONO,align='r')
            ar=a*ease((t-127.4-i*1.5)/0.5)
            if onv(vr,5) and ar>0: text(c,tr("真实 ","real ")+realtxt[i],vr[0]+70,vr[1]-14,24,GOLD,ar,MONO,align='l',glow=0.3)
            if onv(vr,5) and t>=130.8: ad=a*ease((t-131-i*0.3)/0.4); tag(c,vr[0],vr[1]-70,"Δ %.1f"%(abs(model[i]-real[i])*100),ad,(0.5,1,0.7),22)
        text(c,tr("真实值：ATP 官方、罗兰·加洛斯官网、Ultimate Tennis Statistics；赢局率由保发率与破发率推算","Real: ATP, Roland-Garros, Ultimate Tennis Statistics; games won derived from hold/break rates"),960,1036 if not NARR else 1064,20,GRAY,a,MONO if LANG=='en' else SANSR)
    # 07 局限
    if 140<=t<148:
        a=secA(t,140.4,148)
        vm,vr,vb=g('lm'),g('lr'),g('lb')
        if onv(vb,5): text(c,tr("赢下整场","Matches won"),vb[0],vb[1]+40,26,WHITE,a,SANS)
        if onv(vm,5): text(c,tr("模型 85.9%（三盘两胜）","model 85.9% (Bo3)"),vm[0]-90,vm[1]-10,22,(1,0.45,0.4) if t>143 else CYAN,a,MONO,align='r')
        if onv(vr,5) and t>=142.4: text(c,tr("真实 82.0%（1251 胜 275 负）","real 82.0% (1,251–275)"),vr[0]+90,vr[1]-10,24,GOLD,a*ease((t-142.4)/0.4),MONO,align='l')
        if t>=143.7: text(c,"Klaassen & Magnus (2001) · "+tr("481 场温网、近 9 万分","481 Wimbledon matches, ~90,000 points"),960,1036 if not NARR else 1064,20,GRAY,a,MONO if LANG=='en' else SANSR)
    if 148.4<=t<157:
        a=secA(t,148.8,157)
        for k,kb,name,key,col in (('ves0','ves0b',tr("费德勒","Federer"),'p0',GOLD),('ves1','ves1b',tr("德约科维奇","Djokovic"),'p1',BLUE_C)):
            v,vb=g(k),g(kb)
            if onv(vb,5): text(c,name,vb[0],vb[1]+40,28,WHITE,a,SANS); text(c,"%d"%an.get(key,0),vb[0],vb[1]+104,60,col,a,SANS,glow=0.4); text(c,tr("分","pts"),vb[0]+76,vb[1]+104,22,GRAY,a,MONO,align='l')
        if t>=153.8:
            v=g('ves1')
            if onv(v,5): tag(c,v[0],v[1]+40,tr("冠军","CHAMPION"),a*ease((t-154)/0.4),GOLD,26,tf=SANS)
        text(c,"7-6(5)  1-6  7-6(4)  4-6  13-12(3)",960,1036 if not NARR else 1064,24,GRAY,a,MONO)
    # 08 收束：引语原文
    if 168.6<=t<178.2:
        a=secA(t,169.2,178.2); v=g('oneBot'); y=(v[1] if onv(v,5) else 700)+40
        if LANG=='zh': text(c,"It's only a point.",960,y,30,WHITE,a*0.9,SERIF)
        text(c,tr("—— 费德勒","— Roger Federer"),960,y+46,22,GRAY,a*0.8,SANSR)
    if t>=180:
        a=min(1,(t-180)/0.6,(188-t)/0.5)
        text(c,tr("参考资料","References"),960,230,44,WHITE,a,SERIF); y=320
        for s in SRC:
            if s: text(c,s,300,y,22,GRAY if s[0]<='z' else WHITE,a,MONO if s[0]<='z' else SANSR,align='l')
            y+=50
    for s,d,txt,pl in CAPS:
        if pl and s<=t<s+d+0.35: caption(c,t,s,d,txt,pl,an)
    if NARR and t<180: narr_sub(c,t)

def main(inp,out,anchors_files):
    an={}
    for fpath in anchors_files:
        for f,a in json.load(open(fpath)): an[f]=a
    dec=subprocess.Popen(['ffmpeg','-loglevel','error']+(['-f','concat','-safe','0'] if inp.endswith('.txt') else [])+['-i',inp,'-f','rawvideo','-pix_fmt','rgba','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgba','-s','%dx%d'%(W,H),'-r',str(FPS),'-i','-','-c:v','libx264','-preset','medium','-crf','19','-maxrate','30M','-bufsize','60M','-pix_fmt','yuv420p','-movflags','+faststart',out],stdin=subprocess.PIPE)
    # VT_OVERRIDE="210:465:片段.mp4,..."：这几段帧换成另一份 3D（英文版的粒子大字），锚点同名 .anchors.json
    ovr=[]
    for item in filter(None,os.environ.get('VT_OVERRIDE','').split(',')):
        a0,a1,pth=item.split(':',2); ovr.append([int(a0),int(a1),subprocess.Popen(['ffmpeg','-loglevel','error','-i',pth,'-f','rawvideo','-pix_fmt','rgba','-'],stdout=subprocess.PIPE)])
        for ff,aa in json.load(open(pth+'.anchors.json')): an[ff]=aa
    hist=[]; f=0; n=W*H*4
    while True:
        buf=dec.stdout.read(n)
        if len(buf)<n: break
        for a0,a1,pr in ovr:
            if a0<=f<a1:
                b2=pr.stdout.read(n)
                if len(b2)==n: buf=b2
        arr=np.frombuffer(buf,np.uint8).reshape(H,W,4).copy()
        s=skia.Surface(arr); c=s.getCanvas(); draw(c,f/FPS,an.get(f,{}),hist)
        enc.stdin.write(arr.tobytes()); f+=1
    enc.stdin.close(); enc.wait(); print('frames',f)
if __name__=='__main__':
    if sys.argv[1]=='still':
        from PIL import Image
        for p in sys.argv[2:]:
            t=float(os.path.basename(p)[2:9]); an=json.load(open(p.replace('.jpg','.json')))
            arr=np.array(Image.open(p).convert('RGBA')); s=skia.Surface(arr); draw(s.getCanvas(),t,an,[])
            Image.fromarray(arr[...,:3]).save(p.replace('.jpg','_ov.jpg'),quality=90)
    else:
        main(sys.argv[1],sys.argv[2],sys.argv[3:])
