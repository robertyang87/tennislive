"""vibetennis 拍线篇（三部曲①）封面（不进视频）：照 EP03/EP06 定稿的版式——黑夜星空底、发光主体、顶部一行问句（关键词金色）、
金色大标题＋一行等宽英文小字、底部一行关键数据（带范围）＋一行金色出处。
底图是 3D 场景的无字模式（r3d/still_cover.js，notext=1），三个方案：
  A 意面拍（50.0 s，红，主线横线滑开）  B 聚酯线撞击（84.0 s）  C 发球上网柱状图（126.0 s）
    tall：W=2160 H=2880（C 另加 CAM="0,2.0,25,0,1.6,0"）
    wide：A CAM="4.16,1.0,7.6,2.97,0,-1.35"  B CAM="5.0,1.2,7.6,2.5,0.2,-1.65"  C CAM="3,1.0,18,3,2.0,0"
  抽出来的图放 cover/raw/<方案>_<tall|wide>.jpg
    python3 cover/make_cover.py A|B|C tall|wide <输出.jpg> [zh|en]
数字口径：73.1% → 6.2% 是温网男子单打发球上网占比（去掉 ACE），1990–99 对 2020–26，Match Charting Project 逐分自算
（papers/vibetennis-strings-2026/data/mcp_serve_volley_trend_result.txt）；意面拍转速约 2 倍、1978 年被禁见 sources.md。
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

VIO=(200,170,255); BLUE=(150,200,255); RED=(255,120,100)
def make(opt,kind,out):
    bg=np.array(Image.open(RAW/f'{opt}_{kind}.jpg').convert('RGBA')); H,W=bg.shape[:2]
    surf=skia.Surface(W,H); c=surf.getCanvas(); c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    s=W/1080 if kind!='wide' else 1.0
    c.save(); c.scale(s,s); w,h=W/s,H/s
    Q=[(T("是","Did the "),WHITE),(T("线","strings"),GOLD),(T("，改变了网球吗？"," change tennis?"),WHITE)]
    TITLE=T("拍 线 四 代","STRINGS"); SUB=T("GUT · NYLON · POLY · HYBRID","GUT · NYLON · POLY · HYBRID")
    DATA={'A':T("意面拍：转速约是普通球拍的 2 倍，1978 年被禁","Spaghetti racket: ~2x spin, banned in 1978"),
          'B':T("线滑开、千分之一秒内弹回：这才是转的来源","Strings slide, then snap back within 1 ms"),
          'C':T("温网男子发球上网：1990 年代 73.1% → 2020 年以来 6.2%","Wimbledon men serve-and-volley: 73.1% → 6.2%")}[opt]
    SRC=T("牛顿碰撞定律 · 库仑摩擦定律 · 麦克斯韦弛豫时间","Newton · Coulomb · Maxwell")
    if opt=='C':
        SRC=T("Match Charting Project 逐分自算 · 去掉 ACE · 志愿者标注","Match Charting Project · aces excluded · volunteer-charted")
    if kind=='wide':
        hgrad(c,h,860,1920,0,0.85); grad(c,w,0,200,0.6,0); grad(c,w,880,1080,0,0.6); hgrad(c,h,0,240,0.5,0)
        brand(c,60,92,34,44)
        X=1400; rich(c,Q,X,250,50,align='c',glow=0.5)
        text(c,TITLE,X,470,T(118,124),GOLD,1,SERIF,align='c',sp=T(18,30),glow=0.45)
        text(c,SUB,X,520,22,GRAY,0.9,MONO,align='c',sp=6,shadow=0)
        text(c,DATA,X,610,T(30,28),WHITE,0.95,SANS,align='c')
        text(c,SRC,X,662,T(26,22),GOLD2,1,MONO,align='c',glow=0.3)
    else:
        grad(c,w,0,430,0.7,0); grad(c,w,1040,h,0,0.88); hgrad(c,h,0,200,0.45,0); hgrad(c,h,880,1080,0,0.45)
        brand(c)
        rich(c,Q,540,215,T(62,56),align='c',glow=0.5)
        text(c,TITLE,540,1200,T(112,120),GOLD,1,SERIF,align='c',sp=T(26,40),glow=0.45)
        text(c,SUB,540,1247,22,GRAY,0.9,MONO,align='c',sp=6,shadow=0)
        text(c,DATA,540,1318,T(30,28),WHITE,0.95,SANS,align='c')
        text(c,SRC,540,1372,T(25,22),GOLD2,1,MONO,align='c',glow=0.3)
    c.restore()
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(out,quality=95); print(out)
if __name__=='__main__':
    make(sys.argv[1],sys.argv[2],sys.argv[3])
