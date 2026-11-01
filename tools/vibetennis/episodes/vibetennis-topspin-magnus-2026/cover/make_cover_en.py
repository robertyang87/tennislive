"""vibetennis 第 3 集英文版封面：中文版选定的 B（小作坊风）画面层原样（raw_hd/c1.5.png 与锚点 c1.5.json，
来自会话里的原生高清渲染），文字换英文，左上 logo＋「Tennis Jetlag」（所有者 2026-10-31）。

一次出三张：poster_en.jpg（3:4，2160×2880，推送海报）、cover_en_9x16.jpg（1080×1920，短视频平台竖版）、
thumb_en_16x9.jpg（1920×1080，YouTube 封面＋成片内嵌 attached_pic＋片头 3 帧）。拉丁字体：Inter / Noto Serif / Roboto Mono。
依赖路径 D / OUT 指向会话工作目录（和中文版 make_cover.py 一样依赖会话产物）。
"""
# 3:4 HD covers (2160x2880). Layout coordinates in 1080x1440 space, canvas scaled x2.
import json, numpy as np, skia
from PIL import Image
D='/workspace/tennis_ep/topspin/cover/'; OUT='/workspace/tennis_ep/topspin_en/cover/'
SANS=skia.Typeface.MakeFromName('Inter',skia.FontStyle.Bold())
SANSR=skia.Typeface.MakeFromName('Inter',skia.FontStyle.Normal())
SERIF=skia.Typeface.MakeFromName('Noto Serif',skia.FontStyle.Bold())
MONO=skia.Typeface.MakeFromName('Roboto Mono',skia.FontStyle.Normal())
GOLD=(255,196,64); GOLD2=(255,214,110); CYAN=(110,220,255); MAG=(255,90,210); ORANGE=(255,140,40); WHITE=(245,245,240); GRAY=(160,165,175)
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
    """parts: list of (str,color)"""
    tot=sum(width(s,tf,size) for s,_ in parts); xx=x-(tot if align=='r' else tot/2 if align=='c' else 0)
    for s,col in parts: xx+=text(c,s,xx,y,size,col,1,tf,glow=glow if col!=WHITE else 0)
    return tot
ICON=None
def brand(c,x=60,base=92,size=34,icon=44,gap=12,col=GOLD):
    global ICON
    if ICON is None:
        im=Image.open('/workspace/tennis_ep/v2/brand/icon_official.png').convert('RGBA'); im=im.crop(im.split()[3].getbbox()).resize((icon*2,icon*2),Image.LANCZOS)
        a=np.array(im).astype(np.float32); a[...,:3]*=a[...,3:4]/255.0
        ICON=skia.Image.fromarray(np.ascontiguousarray(a.round().astype(np.uint8)),colorType=skia.kRGBA_8888_ColorType,alphaType=skia.kPremul_AlphaType)
    cy=base-size*0.36; c.drawImageRect(ICON,skia.Rect.MakeXYWH(x,cy-icon/2,icon,icon),skia.SamplingOptions(skia.FilterMode.kLinear),skia.Paint(AntiAlias=True))
    text(c,"Tennis Jetlag",x+icon+gap,base,size,col,1,SANS,sp=0.5,shadow=0.5)
def grad(c,y0,y1,a0,a1):
    p=skia.Paint(Shader=skia.GradientShader.MakeLinear([(0,y0),(0,y1)],[skia.Color4f(0,0,0,a0),skia.Color4f(0,0,0,a1)]))
    c.drawRect(skia.Rect.MakeLTRB(0,y0,1080,y1),p)
def dot(c,x,y,col,r=7): c.drawCircle(x,y,r*2.4,P(col,0.35,blur=10)); c.drawCircle(x,y,r,P(col,1))
def leader(c,x0,y0,x1,y1,col,a=0.85): c.drawLine(x0,y0,x1,y1,P(col,a,stroke=2.2))
def make(raw,out,draw):
    bg=np.array(Image.open(D+'raw_hd/'+raw).convert('RGBA'))
    surf=skia.Surface(2160,2880); c=surf.getCanvas()
    c.drawImage(skia.Image.fromarray(bg,colorType=skia.kRGBA_8888_ColorType),0,0)
    c.save(); c.scale(2,2); draw(c, json.load(open(D+'raw_hd/'+raw.replace('.png','.json')))); c.restore()
    img=surf.makeImageSnapshot(); Image.fromarray(img.toarray()[...,:3][...,::-1] if False else img.convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]).save(D+out,quality=95)
    print(out)


RAW=np.array(Image.open(D+'raw_hd/c1.5.png').convert('RGBA')); AN=json.load(open(D+'raw_hd/c1.5.json'))
RAWI=skia.Image.fromarray(RAW,colorType=skia.kRGBA_8888_ColorType)
def save(surf,name):
    img=surf.makeImageSnapshot().convert(colorType=skia.kRGBA_8888_ColorType).toarray()[...,:3]
    Image.fromarray(img).save(OUT+name,quality=95,subsampling=0); print(name,img.shape)
def labels(c,an,k=1.0):
    b=an['ball']; m=an['magTip']
    text(c,"Into the air ≈148 km/h",b[0]+175,b[1]-168,26*k,ORANGE,1,SANS,align='l',glow=0.3)
    text(c,"With the air ≈68 km/h",b[0]+175,b[1]+186,26*k,CYAN,1,SANS,align='l',glow=0.3)
    text(c,"Wake tilts up ↑",b[0]-480,b[1]-130,28*k,GOLD2,0.95,SANS,align='l',glow=0.3)
    text(c,"Magnus force ↓",m[0]+60,m[1]-90,34*k,GOLD2,1,SANS,align='l',glow=0.5)
    text(c,"0.41 N",m[0]+60,m[1]-40,40*k,GOLD2,1,MONO,align='l',glow=0.5)
def poster_layout(c,an,dy=0):
    rich(c,[("Why does topspin suddenly ",WHITE),("dive",GOLD),("?",WHITE)],540,190+dy,54,align='c',glow=0.5)
    an2={k:[v[0],v[1]+dy,v[2]] for k,v in an.items()}; labels(c,an2)
    text(c,"TOPSPIN DIVE",540,1185+dy,104,GOLD,1,SERIF,align='c',sp=10,glow=0.45)
    text(c,"THE MAGNUS EFFECT",540,1232+dy,22,GRAY,0.9,MONO,align='c',sp=8,shadow=0)
    text(c,"At 3200 rpm, the downward force ≈ 73% of the ball’s weight",540,1306+dy,30,WHITE,0.95,SANS,align='c')
    text(c,"F = ½·C_L·ρ·A·v²   ≈ 1.7 × gravity",540,1362+dy,30,GOLD2,1,MONO,align='c',glow=0.3)
# ---- 3:4 poster 2160x2880 (push cover)
surf=skia.Surface(2160,2880); c=surf.getCanvas(); c.drawImage(RAWI,0,0)
c.save(); c.scale(2,2); brand(c); poster_layout(c,AN); c.restore(); save(surf,'poster_en.jpg')
# ---- 9:16 1080x1920 (short-video platforms): same art, re-laid out with headroom
surf=skia.Surface(1080,1920); c=surf.getCanvas(); c.clear(skia.Color4f(0,0,0,1))
DY=250; c.drawImageRect(RAWI,skia.Rect.MakeXYWH(0,DY,1080,1440),skia.SamplingOptions(skia.FilterMode.kLinear))
for y0,y1,a0,a1 in [(DY,DY+120,1,0),(DY+1320,DY+1440,0,1)]:
    p=skia.Paint(Shader=skia.GradientShader.MakeLinear([(0,y0),(0,y1)],[skia.Color4f(0,0,0,a0),skia.Color4f(0,0,0,a1)])); c.drawRect(skia.Rect.MakeLTRB(0,y0,1080,y1),p)
brand(c,x=60,base=150)
text(c,"Why does topspin",540,330,84,WHITE,1,SERIF,align='c')
rich(c,[("suddenly ",WHITE),("dive",GOLD),("?",WHITE)],540,430,84,SERIF,align='c',glow=0.5)
an2={k:[v[0],v[1]+DY+40,v[2]] for k,v in AN.items()}; labels(c,an2)
text(c,"TOPSPIN DIVE",540,1520,104,GOLD,1,SERIF,align='c',sp=10,glow=0.45)
text(c,"THE MAGNUS EFFECT",540,1567,22,GRAY,0.9,MONO,align='c',sp=8,shadow=0)
text(c,"At 3200 rpm, the downward force",540,1650,34,WHITE,0.95,SANS,align='c')
text(c,"≈ 73% of the ball’s weight",540,1698,34,WHITE,0.95,SANS,align='c')
text(c,"F = ½·C_L·ρ·A·v²   ≈ 1.7 × gravity",540,1770,32,GOLD2,1,MONO,align='c',glow=0.3)
save(surf,'cover_en_9x16.jpg')
# ---- 16:9 1920x1080 (YouTube thumbnail + embedded attached_pic + lead-in frames)
surf=skia.Surface(1920,1080); c=surf.getCanvas(); c.clear(skia.Color4f(0,0,0,1))
Y0,Y1=470,2230; sc=1080/(Y1-Y0); OX=1920-2160*sc+120     # art on the right, ball at ~x=1305
c.save(); c.translate(OX,-Y0*sc); c.scale(sc,sc); c.drawImage(RAWI,0,0,skia.SamplingOptions(skia.FilterMode.kLinear)); c.restore()
p=skia.Paint(Shader=skia.GradientShader.MakeLinear([(OX-40,0),(OX+520,0)],[skia.Color4f(0,0,0,1),skia.Color4f(0,0,0,0)])); c.drawRect(skia.Rect.MakeLTRB(0,0,OX+520,1080),p)
TX=lambda x:OX+x*2*sc; TY=lambda y:(y*2-Y0)*sc
an2={k:[TX(v[0]),TY(v[1]),v[2]] for k,v in AN.items()}; b=an2['ball']; m=an2['magTip']; k=1.25
text(c,"≈148 km/h",b[0]+190,b[1]-150,34,ORANGE,1,SANS,align='l',glow=0.3)
text(c,"≈68 km/h",b[0]+190,b[1]+190,34,CYAN,1,SANS,align='l',glow=0.3)
text(c,"Magnus force ↓  0.41 N",m[0]+50,m[1]-60,38,GOLD2,1,SANS,align='l',glow=0.5)
brand(c,x=80,base=110,size=38,icon=48)
text(c,"Why does topspin",84,300,86,WHITE,1,SERIF)
rich(c,[("suddenly ",WHITE),("dive",GOLD),("?",WHITE)],84,404,86,SERIF,glow=0.5)
text(c,"THE MAGNUS EFFECT · 1852",90,470,22,GRAY,0.9,MONO,sp=6,shadow=0)
text(c,"TOPSPIN DIVE",84,820,96,GOLD,1,SERIF,sp=6,glow=0.45)
text(c,"At 3200 rpm, the downward force ≈ 73% of its weight",88,900,30,WHITE,0.95,SANS)
text(c,"F = ½·C_L·ρ·A·v²   ≈ 1.7 × gravity",88,960,30,GOLD2,1,MONO,glow=0.3)
save(surf,'thumb_en_16x9.jpg')
