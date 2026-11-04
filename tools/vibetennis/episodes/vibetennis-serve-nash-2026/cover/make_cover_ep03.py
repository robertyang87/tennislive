"""vibetennis 第 6 集封面（不进视频）——所有者 2026-11-04 选「最开始那个」（方案 A：两条发球轨迹分叉），并要「看看 ep03 的封面设计」：
照 EP03（topspin-magnus）定稿那张的版式重排：黑夜星空底、正中一个发光的主体、顶部一行问句（关键词金色）、
中下字距拉开的金色大标题＋一行等宽英文小字、底部一行关键数据＋一行金色出处；主体旁挂带引线的数据标签。
底图是 3D 场景的封面模式（不出 3D 问句、专用机位，两条轨迹和两个落点都进画面）：
    (cd r3d && COVER=1 CAM="&cx=-3&tx=-2.5&cy=3&cz=13" W=2160 H=2880 PORT=8771 OUT=stills_coverA node still_cover.js 3.4)  → tall
    (cd r3d && COVER=1 CAM="&cx=-2.5&tx=-5&cy=2.4&cz=7&ty=1.2" W=1920 H=1080 PORT=8771 OUT=stills_coverA node still_cover.js 3.4) → wide
（两张各自改名 tall.jpg/json、wide.jpg/json）
    python3 cover/make_cover_ep03.py tall|wide|story <输出.jpg> [zh|en]
"""
import json, sys
from pathlib import Path
import numpy as np, skia
from PIL import Image
HERE=Path(__file__).resolve().parent; REPO=Path(__file__).resolve().parents[5]; RAW=HERE.parent/'r3d'/'stills_coverA'
LANG=sys.argv[3] if len(sys.argv)>3 else 'zh'
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
def make(kind,out):
    bg=np.array(Image.open(RAW/f'{kind}.jpg').convert('RGBA')); an=json.load(open(RAW/f'{kind}.json')); H,W=bg.shape[:2]
    surf=skia.Surface(W,H); c=surf.getCanvas(); c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    s=W/1080 if kind!='wide' else 1.0
    c.save(); c.scale(s,s); w,h=W/s,H/s
    def pt(k): return an[k][0]/s, an[k][1]/s
    tw,tt=pt('tgtWide'),pt('tgtT')
    if kind=='wide':
        hgrad(c,h,960,1920,0,0.85); grad(c,w,0,200,0.6,0); grad(c,w,880,1080,0,0.6); hgrad(c,h,0,240,0.5,0)
        brand(c,60,92,34,44)
        dot(c,*tt,MAG,5); leader(c,tt[0]-8,tt[1]+6,tt[0]-70,tt[1]+60,MAG); text(c,T("中路  64.7%","T  64.7%"),tt[0]-78,tt[1]+86,30,MAG,1,SANS,align='r',glow=0.4)
        dot(c,*tw,CYAN,5); leader(c,tw[0]+8,tw[1]+6,tw[0]+70,tw[1]+60,CYAN); text(c,T("外角  65.0%","Wide  65.0%"),tw[0]+78,tw[1]+86,30,CYAN,1,SANS,glow=0.4)
        X=1460; rich(c,[(T("发球，该往","Serve: which "),WHITE),(T("哪边","side"),GOLD),(T("发？","?"),WHITE)],X,250,50,align='c',glow=0.5)
        text(c,T("纳 什 均 衡","NASH"),X,470,T(118,124),GOLD,1,SERIF,align='c',sp=T(18,40),glow=0.45)
        text(c,T("WHY SERVERS MIX IT UP","EQUILIBRIUM"),X,520,22,GRAY,0.9,MONO,align='c',sp=8,shadow=0)
        text(c,T("2,151 场男子比赛：两边得分率几乎一样","2,151 men's matches: win rates nearly equal"),X,610,30,WHITE,0.95,SANS,align='c')
        text(c,T("冯·诺依曼 1928 · 纳什 1950 · 诺贝尔奖 1994","von Neumann 1928 · Nash 1950 · Nobel 1994"),X,662,26,GOLD2,1,MONO,align='c',glow=0.3)
    else:
        grad(c,w,0,430,0.7,0); grad(c,w,1040,h,0,0.88); hgrad(c,h,0,260,0.55,0); hgrad(c,h,820,1080,0,0.55)   # 四周压暗，主体居中发亮（EP03 黑底亮主体）
        brand(c)
        rich(c,[(T("发球，该往","Serve: which "),WHITE),(T("哪边","side"),GOLD),(T("发？","?"),WHITE)],540,215,T(66,62),align='c',glow=0.5)
        b=pt('ball'); text(c,T("出手到落地  < 0.5 秒","racket to bounce  < 0.5 s"),b[0]+40,b[1]-30,28,WHITE,0.92,SANS); leader(c,b[0]+8,b[1]-6,b[0]+34,b[1]-22,WHITE,0.6)
        dot(c,*tt,MAG,6); leader(c,tt[0]-4,tt[1]+10,tt[0]-30,tt[1]+48,MAG); text(c,T("中路","T"),tt[0]-40,tt[1]+80,28,MAG,0.95,SANS,align='r'); text(c,"64.7%",tt[0]-40,tt[1]+124,46,MAG,1,SANS,align='r',glow=0.5)
        dot(c,*tw,CYAN,6); leader(c,tw[0]+4,tw[1]+10,tw[0]+30,tw[1]+48,CYAN); text(c,T("外角","Wide"),tw[0]+40,tw[1]+80,28,CYAN,0.95,SANS); text(c,"65.0%",tw[0]+40,tw[1]+124,46,CYAN,1,SANS,glow=0.5)
        text(c,T("纳 什 均 衡","NASH"),540,1200,T(112,128),GOLD,1,SERIF,align='c',sp=T(26,48),glow=0.45)
        text(c,T("WHY SERVERS MIX IT UP","EQUILIBRIUM"),540,1247,22,GRAY,0.9,MONO,align='c',sp=8,shadow=0)
        text(c,T("2,151 场男子比赛：两边得分率几乎一样","2,151 men's matches: win rates nearly equal"),540,1318,32,WHITE,0.95,SANS,align='c')
        text(c,T("冯·诺依曼 1928 · 纳什 1950 · 诺贝尔奖 1994","von Neumann 1928 · Nash 1950 · Nobel 1994"),540,1372,26,GOLD2,1,MONO,align='c',glow=0.3)
    c.restore()
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(out,quality=95); print(out)
if __name__=='__main__':
    make(sys.argv[1],sys.argv[2])
