"""vibetennis 球拍篇（三部曲②）封面（不进视频）：沿用 EP07 所有者选定的 B 版式（杂志信息图）——
粗黑体两行问句（「球拍」金色）＋四格时间轴＋一个关键数字（带范围和出处），主体退到一侧。
底图是 3D 场景无字模式（r3d/still_cover.js，notext=1）在 89.5 s：大拍面段，木拍拍面外圈多出来的那一圈被填亮——
正好是封面那个数字「拍面大了 40% 以上」。
    tall：W=2160 H=2880 CAM="0.3,0.9,12.5,-0.3,1.1,0"
    wide：W=1920 H=1080 CAM="-1.6,0.6,10.5,-3.2,-0.3,0"
    vert：W=1080 H=1920 CAM="0.3,0.6,13.5,-0.3,0.9,0"（9:16，短视频平台竖版封面）
  抽出来的图放 cover/raw/B_<tall|wide|vert>.jpg
    python3 cover/make_cover.py B tall|wide|vert <输出.jpg> [zh|en]
数字口径：「40% 以上」两源（Harvard Crimson 1981、Inside Tennis），木拍约 70 平方英寸三源（Head 专利 US 3,999,756、名人堂、
Taraborrelli 2019）；时间轴年份：拉科斯特钢拍专利 1963 授权、霍华德·黑德大拍面专利 1976 授权、1980 前后复合材料成主流——
都见 papers/vibetennis-racket-2026/sources.md。
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

Q2=lambda: [(T("是","Did the "),WHITE),(T("球拍","racket"),GOLD),(T("，",""),WHITE)]
TL4=lambda: [(T("约 1870","1870s"),T("木拍","Wood")),("1963",T("钢拍专利","Steel patent")),("1976",T("大拍面专利","Oversize patent")),(T("1980 前后","c. 1980"),T("碳纤维","Carbon fibre"))]
def timeline(c,x0,x1,y,size=26):
    n=4; xs=[x0+(x1-x0)*i/(n-1) for i in range(n)]
    c.drawLine(x0,y,x1,y,P(GOLD,0.55,stroke=2.5))
    for x,(yr,lab) in zip(xs,TL4()):
        dot(c,x,y,GOLD,6); text(c,yr,x,y-22,size*0.95,GOLD2,1,MONO,align='c',shadow=0.4)
        text(c,lab,x,y+16+size,size,WHITE,0.95,SANS,align='c')
BIG=lambda: T("拍面 +40% 以上","Head +40%")
CAP=lambda: T("霍华德·黑德的大拍面（普林斯），比传统木拍大了 40% 以上","Howard Head's oversize (Prince): 40%+ larger than traditional frames")   # 两源原话都是「比传统拍大 40% 以上」，不绑 1976 专利年份，也不和 70 平方英寸硬算
NOTE=lambda: T("Harvard Crimson 1981 · Inside Tennis · 美国专利 US 3,999,756","Harvard Crimson 1981 · Inside Tennis · US Patent 3,999,756")
L2=lambda: T("改写了网球吗？","change tennis?")
def make(opt,kind,out):
    bg=np.array(Image.open(RAW/f'{opt}_{kind}.jpg').convert('RGBA')); H,W=bg.shape[:2]
    surf=skia.Surface(W,H); c=surf.getCanvas(); c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    s=W/1080 if kind!='wide' else 1.0
    c.save(); c.scale(s,s); w,h=W/s,H/s
    if kind=='wide':
        hgrad(c,h,0,1250,0.9,0.1); grad(c,w,0,160,0.5,0)
        brand(c,60,92,34,44)
        rich(c,Q2(),80,300,T(118,96),align='l',glow=0); text(c,L2(),80,430,T(118,96),WHITE,1,SANS)
        timeline(c,130,1030,580,26)
        text(c,BIG(),80,820,T(92,92),GOLD,1,SANS,glow=0.25); text(c,CAP(),84,870,28,WHITE,0.95,SANS); text(c,NOTE(),84,912,20,GRAY,0.95,MONO,shadow=0)
    else:
        yb=h-210   # 底部数字块：tall h=1440 → 1230，vert h=1920 → 1710
        grad(c,w,0,h*0.5,0.92,0.15); grad(c,w,h*0.62,h,0.1,0.92)
        brand(c)
        rich(c,Q2(),70,300,T(120,92),align='l',glow=0); text(c,L2(),70,440,T(120,92),WHITE,1,SANS)
        timeline(c,130,950,560,28)
        text(c,BIG(),70,yb,T(104,104),GOLD,1,SANS,glow=0.25); text(c,CAP(),74,yb+60,T(28,25),WHITE,0.95,SANS); text(c,NOTE(),74,yb+106,T(20,19),GRAY,0.95,MONO,shadow=0)
    c.restore()
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(out,quality=95); print(out)
if __name__=='__main__':
    make(sys.argv[1],sys.argv[2],sys.argv[3])
