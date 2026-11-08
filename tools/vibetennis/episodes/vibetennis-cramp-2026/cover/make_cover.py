"""vibetennis EP10 德约接发之王封面（不进视频）：沿用 B 版式（杂志信息图）——
两行问句（「接发之王」金色）＋四格时间轴＋大数字「第 7」（ATP 官方历史接发评分），主体退到一侧。
底图是 3D 场景无字模式（r3d/still_cover.js，notext=1）在 14.5 s：赛点正手接发出手前一瞬（来球拖着光迹，带中央球场看台，2026-11-07 重出）。
    tall：W=1440 H=1920 CAM="5.5,2.2,17.6,1.5,0.9,8.0"，再 Lanczos 放大到 2160×2880（swiftshader 在 2880 高时会出横带）
    wide：W=1920 H=1080 CAM="-3.0,2.4,19.5,-0.6,1.0,10.0"（人在画面右边，左边放字）
    vert：W=1080 H=1920 CAM="5.5,2.2,18.4,1.5,0.9,8.0"
  抽出来的图放 cover/raw/B_<tall|wide|vert>.jpg
    python3 cover/make_cover.py B tall|wide|vert <输出.jpg> [zh|en]
数字口径见 papers/vibetennis-djokovic-return-2026/sources.md：第 7＝ATP 官方生涯 Return Rating（1991 年起）；
0.2 s＝简单视觉反应（Woods 2015、Jain 2015）；0.15／0.19 s＝职业接发人落地／动拍（Mecheri 2019、Navia 2022）；八成＝回过发球线（Match Charting Project、ESPN）。
"""
import json, sys
from pathlib import Path
import numpy as np, skia
from PIL import Image
HERE=Path(__file__).resolve().parent; REPO=Path(__file__).resolve().parents[5]; RAW=HERE/'raw'
LANG=sys.argv[4] if len(sys.argv)>4 else 'zh'
def T(zh,en): return en if LANG=='en' else zh
SANS=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Bold()); SANSR=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Normal())
SERIF=skia.Typeface.MakeFromName('Noto Serif CJK SC',skia.FontStyle.Bold()); MONO=skia.Typeface.MakeFromName('Noto Sans Mono CJK SC',skia.FontStyle.Normal())
GOLD=(255,196,64); GOLD2=(255,214,110); CYAN=(110,220,255); MAG=(255,110,220); WHITE=(245,245,240); GRAY=(160,165,175)
def P(col,a=1,blur=0,stroke=0):
    p=skia.Paint(AntiAlias=True,Color=skia.Color4f(col[0]/255,col[1]/255,col[2]/255,a))
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle,blur))
    if stroke: p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke)
    return p
def F(tf,s): f=skia.Font(tf,s); f.setSubpixel(True); return f
def width(s,tf,size,sp=0): f=F(tf,size); return sum(f.measureText(ch)+sp for ch in s)-sp if sp else f.measureText(s)
def text(c,s,x,y,size,col,a=1,tf=SANS,align='l',sp=0,glow=0,shadow=0.6):
    f=F(tf,size); w=width(s,tf,size,sp); x0=x-(w if align=='r' else w/2 if align=='c' else 0)
    def run(p):
        if sp:
            xx=x0
            for ch in s: c.drawString(ch,xx,y,f,p); xx+=f.measureText(ch)+sp
        else: c.drawString(s,x0,y,f,p)
    if shadow: run(P((0,0,0),shadow,blur=size*0.12))
    if glow: run(P(col,glow,blur=size*0.25))
    run(P(col,a)); return w
def rich(c,parts,x,y,size,tf=SANS,align='l',glow=0.35):
    tot=sum(width(s,tf,size) for s,_ in parts); xx=x-(tot if align=='r' else tot/2 if align=='c' else 0)
    for s,col in parts: xx+=text(c,s,xx,y,size,col,1,tf,glow=glow if col!=WHITE else 0)
ICON=None
def brand(c,x=60,base=92,size=34,icon=44,gap=12):
    global ICON
    if ICON is None:
        im=Image.open(REPO/'assets/logo/brand/account/icon-transparent-1024.png').convert('RGBA'); im=im.crop(im.split()[3].getbbox()).resize((icon*2,icon*2),Image.LANCZOS)
        a=np.array(im).astype(np.float32); a[...,:3]*=a[...,3:4]/255.0
        ICON=skia.Image.fromarray(np.ascontiguousarray(a.round().astype(np.uint8)),colorType=skia.kRGBA_8888_ColorType,alphaType=skia.kPremul_AlphaType)
    cy=base-size*0.36; c.drawImageRect(ICON,skia.Rect.MakeXYWH(x,cy-icon/2,icon,icon),skia.SamplingOptions(skia.FilterMode.kLinear),skia.Paint(AntiAlias=True))
    text(c,T("网球时差","Tennis Jetlag"),x+icon+gap,base,size,GOLD,1,SANS,sp=1,shadow=0.5)
def grad(c,W,y0,y1,a0,a1):
    p=skia.Paint(Shader=skia.GradientShader.MakeLinear([(0,y0),(0,y1)],[skia.Color4f(0,0,0,a0),skia.Color4f(0,0,0,a1)])); c.drawRect(skia.Rect.MakeLTRB(0,y0,W,y1),p)
def hgrad(c,H,x0,x1,a0,a1):
    p=skia.Paint(Shader=skia.GradientShader.MakeLinear([(x0,0),(x1,0)],[skia.Color4f(0,0,0,a0),skia.Color4f(0,0,0,a1)])); c.drawRect(skia.Rect.MakeLTRB(x0,0,x1,H),p)
def dot(c,x,y,col,r=7): c.drawCircle(x,y,r*2.4,P(col,0.35,blur=10)); c.drawCircle(x,y,r,P(col,1))
def leader(c,x0,y0,x1,y1,col,a=0.85): c.drawLine(x0,y0,x1,y1,P(col,a,stroke=2.2))

Q2=lambda: [(T("凭什么叫他","Why the "),WHITE),(T("接发之王？","return king?"),GOLD)]
TL4=lambda: [("0.2 s",T("人的反应","Reaction")),("0.15 s",T("垫步落地","Split lands")),("0.19 s",T("开始动拍","Racket moves")),(T("约八成","~80%"),T("回过发球线","Deep returns"))]
def timeline(c,x0,x1,y,size=26):
    n=4; xs=[x0+(x1-x0)*i/(n-1) for i in range(n)]
    c.drawLine(x0,y,x1,y,P(GOLD,0.55,stroke=2.5))
    for x,(yr,lab) in zip(xs,TL4()):
        dot(c,x,y,GOLD,6); text(c,yr,x,y-22,size*0.95,GOLD2,1,MONO,align='c',shadow=0.4)
        text(c,lab,x,y+16+size,size,WHITE,0.95,SANS,align='c')
BIG=lambda: T("第 7","No. 7")
CAP=lambda: T("ATP 官方历史接发评分（1991 年起）：德约排第 7","ATP all-time Return Rating (since 1991): Djokovic is No. 7")
NOTE=lambda: T("ATP 官方榜单 · Mecheri 2019 · Navia 2022 · Match Charting Project","ATP leaderboards · Mecheri 2019 · Navia 2022 · Match Charting Project")
L1=lambda: T("官方榜单只排第 7，","Officially No. 7.")
def make(opt,kind,out):
    bg=np.array(Image.open(RAW/f'{opt}_{kind}.jpg').convert('RGBA')); H,W=bg.shape[:2]
    surf=skia.Surface(W,H); c=surf.getCanvas(); c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    s=W/1080 if kind!='wide' else 1.0
    c.save(); c.scale(s,s); w,h=W/s,H/s
    if kind=='wide':
        hgrad(c,h,0,1250,0.9,0.1); grad(c,w,0,160,0.5,0)
        brand(c,60,92,34,44)
        text(c,L1(),80,300,T(118,92),WHITE,1,SANS); rich(c,Q2(),80,430,T(118,92),align='l',glow=0)
        timeline(c,130,1030,580,26)
        text(c,BIG(),80,820,T(92,92),GOLD,1,SANS,glow=0.25); text(c,CAP(),84,870,28,WHITE,0.95,SANS); text(c,NOTE(),84,912,20,GRAY,0.95,MONO,shadow=0)
    else:
        yb=h-210   # 底部数字块：tall h=1440 → 1230，vert h=1920 → 1710
        grad(c,w,0,h*0.5,0.92,0.15); grad(c,w,h*0.62,h,0.1,0.92)
        brand(c)
        text(c,L1(),70,300,T(104,92),WHITE,1,SANS); rich(c,Q2(),70,430,T(104,92),align="l",glow=0)
        timeline(c,130,950,560,28)
        text(c,BIG(),70,yb,T(104,104),GOLD,1,SANS,glow=0.25); text(c,CAP(),74,yb+60,T(28,25),WHITE,0.95,SANS); text(c,NOTE(),74,yb+106,T(20,19),GRAY,0.95,MONO,shadow=0)
    c.restore()
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(out,quality=95); print(out)
if __name__=='__main__':
    make(sys.argv[1],sys.argv[2],sys.argv[3])
