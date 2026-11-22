"""vibetennis EP13 网中间矮封面（16:9 封面另外内嵌成视频前 3 帧＋attached_pic）：标题两行，文案少（所有者 2026-11-08「封面文案太多了」）。
底图是 3D 场景无字模式（r3d/still_cover.js，notext=1，CAM 覆盖机位）：
  A：结尾段中央带特写——白带子把网正中往下拽（tall 2160×2880 / wide 1920×1080 / vert 1080×1920）
  B：标题段——金色悬链线被白带子拽成浅 V（tall）
  C：余量段——反手位扇形俯视（tall）
  抽出来的图放 cover/raw/<A|B|C>_<tall|wide|vert>.jpg
    python3 cover/make_cover.py <A|B|C> tall|wide|vert <输出.jpg> [zh|en]
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

COPY={
 'A':(lambda: [T("球网中间","Why is the net"),T("为什么矮一截？","lower in the middle?")], lambda: [(T("不是塌的，","Not sagging. "),WHITE),(T("是被拉的","Pulled down."),GOLD)]),
 'B':(lambda: [T("球网是","Is the net"),T("悬链线吗？","a catenary?")], lambda: [(T("答案：","Answer: "),WHITE),(T("不是","no"),GOLD)]),
 'C':(lambda: [T("职业球员","Why pros"),T("为什么爱打斜线？","go crosscourt")], lambda: [(T("网中间矮 ","Net is "),WHITE),(T("15.6 厘米","6 in lower"),GOLD)]),
}
def make(opt,kind,out):
    bg=np.array(Image.open(RAW/f'{opt}_{kind}.jpg').convert('RGBA')); H,W=bg.shape[:2]
    surf=skia.Surface(W,H); c=surf.getCanvas(); c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    s=W/1080 if kind!='wide' else 1.0
    c.save(); c.scale(s,s); w,h=W/s,H/s
    L1S,Q2=COPY[opt]
    if kind=='wide':   # 画面主体在上半，标题压到下方（底部渐黑）
        grad(c,w,h*0.45,h,0,0.92); grad(c,w,0,160,0.5,0)
        brand(c,60,92,34,44)
        text(c,''.join(L1S()) if LANG=='zh' else ' '.join(L1S()),80,h-170,T(88,72),WHITE,1,SANS); rich(c,Q2(),80,h-60,T(88,72),align='l',glow=0)
    else:              # 竖版：三行压在下方
        grad(c,w,0,200,0.6,0); grad(c,w,h*0.5,h,0,0.95)
        brand(c)
        y0=h-(470 if kind=='vert' else 420)
        for i,ln in enumerate(L1S()): text(c,ln,70,y0+i*112,T(96,84),WHITE,1,SANS)
        rich(c,Q2(),70,y0+2*112+20,T(96,84),align="l",glow=0)
    c.restore()
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(out,quality=95); print(out)
if __name__=='__main__':
    make(sys.argv[1],sys.argv[2],sys.argv[3])
