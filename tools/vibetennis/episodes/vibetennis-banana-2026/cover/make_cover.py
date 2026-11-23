"""vibetennis EP14 不是补钾封面。标题两行，文案少。
底图来自审片静帧（cover/raw/<A|B|C>_<tall|wide|vert>.jpg），由 mk_raw.py 从 16:9 静帧裁出。
  python3 cover/make_cover.py <A|B|C> tall|wide|vert <输出.jpg> [zh|en]
"""
import sys
from pathlib import Path
import numpy as np, skia
from PIL import Image
HERE=Path(__file__).resolve().parent; REPO=Path(__file__).resolve().parents[5]; RAW=HERE/'raw'
LANG=sys.argv[4] if len(sys.argv)>4 else 'zh'
def T(zh,en): return en if LANG=='en' else zh
SANS=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Bold()); SANSR=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Normal())
GOLD=(255,196,64); WHITE=(245,245,240)
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

COPY={
 'A':(lambda: [T("不是补钾","Not potassium")], lambda: [(T("更站得住的理由，","The more defensible reason: "),WHITE),(T("是补糖","carbohydrate"),GOLD)]),
 'B':(lambda: [T("他们为什么","Why players"),T("吃香蕉？","eat bananas")], lambda: [(T("防抽筋，","To stop cramp? "),WHITE),(T("还没有被证明","Not shown."),GOLD)]),
 'C':(lambda: [T("一根香蕉","One banana"),T("大约 27 克碳水","is about 27 g of CHO")], lambda: [(T("大概刚够下限","Roughly the lower end"),GOLD)]),
}
def make(opt,kind,out):
    bg=np.array(Image.open(RAW/f'{opt}_{kind}.jpg').convert('RGBA')); H,W=bg.shape[:2]
    surf=skia.Surface(W,H); c=surf.getCanvas(); c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    s=W/1080 if kind!='wide' else 1.0
    c.save(); c.scale(s,s); w,h=W/s,H/s
    L1S,Q2=COPY[opt]
    if kind=='wide':
        grad(c,w,h*0.45,h,0,0.92); grad(c,w,0,160,0.5,0)
        brand(c,60,92,34,44)
        text(c,''.join(L1S()) if LANG=='zh' else ' '.join(L1S()),80,h-170,T(88,72),WHITE,1,SANS); rich(c,Q2(),80,h-60,T(72,64),align='l',glow=0)
    else:
        grad(c,w,0,200,0.6,0); grad(c,w,h*0.5,h,0,0.95)
        brand(c)
        y0=h-(470 if kind=='vert' else 420)
        lines=L1S()
        for i,ln in enumerate(lines): text(c,ln,70,y0+i*112,T(96,84),WHITE,1,SANS)
        rich(c,Q2(),70,y0+len(lines)*112+20,T(88,80),align="l",glow=0)
    c.restore()
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(out,quality=95); print(out)
if __name__=='__main__':
    make(sys.argv[1],sys.argv[2],sys.argv[3])
