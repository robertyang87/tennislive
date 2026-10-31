# 3:4 HD covers (2160x2880). Layout coordinates in 1080x1440 space, canvas scaled x2.
import json, numpy as np, skia
from PIL import Image
D='/workspace/tennis_ep/topspin/cover/'
SANS=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Bold())
SANSR=skia.Typeface.MakeFromName('Noto Sans CJK SC',skia.FontStyle.Normal())
SERIF=skia.Typeface.MakeFromName('Noto Serif CJK SC',skia.FontStyle.Bold())
MONO=skia.Typeface.MakeFromName('Noto Sans Mono CJK SC',skia.FontStyle.Normal())
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
    text(c,"网球时差",x+icon+gap,base,size,col,1,SANS,sp=1,shadow=0.5)
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

# ---------- A 比特新语：竖向全场透视，两颗小球同一拍、不同转速 ----------
def A(c,an):
    grad(c,0,520,0.75,0); grad(c,1150,1440,0,0.85)
    brand(c)
    text(c,"上旋球为什么会",60,232,104,WHITE,1,SERIF)
    text(c,"突然往下坠？",60,356,104,WHITE,1,SERIF)
    text(c,"WHY DOES A TOPSPIN BALL DIVE?",64,410,22,GRAY,0.9,MONO,sp=5,shadow=0)
    L=an['launch']; text(c,"同一拍  108 km/h · 15.2°",L[0]+40,L[1]-14,26,WHITE,0.92,SANS); leader(c,L[0]+6,L[1]-4,L[0]+34,L[1]-20,WHITE,0.6)
    g=an['land_A4000']; dot(c,g[0],g[1],GOLD2,6); leader(c,g[0]+10,g[1]-6,g[0]+150,g[1]-70,GOLD2)
    text(c,"4000 转 · 22.5 m",g[0]+160,g[1]-80,40,GOLD2,1,SANS,glow=0.5); text(c,"压进底线  IN",g[0]+160,g[1]-38,26,GOLD2,0.9,SANS)
    b=an['land_A0']; dot(c,b[0],b[1],CYAN,6); leader(c,b[0]+10,b[1]-4,b[0]+150,b[1]-40,CYAN)
    text(c,"0 转 · 32.1 m",b[0]+160,b[1]-50,40,CYAN,1,SANS,glow=0.5); text(c,"飞出底线 8 m 多  OUT",b[0]+160,b[1]-10,26,CYAN,0.9,SANS)
    rich(c,[("只改转速，落点就近了 ",WHITE),("9.6 米",GOLD)],60,1300,56)
    text(c,"按 Rod Cross 公开弹道模型计算 · 球场全长 23.77 m",62,1356,24,GRAY,0.95,SANSR)
make('c0.5.png','cover_A_bitxinyu.jpg',A)

# ---------- B 小作坊：黑底金球 + 向下的马格努斯力 ----------
def B(c,an):
    brand(c)
    rich(c,[("上旋球为什么会突然",WHITE),("往下坠",GOLD),("？",WHITE)],540,190,54,align='c',glow=0.5)
    b=an['ball']; m=an['magTip']
    text(c,"迎风 ≈148 km/h",b[0]+175,b[1]-168,26,ORANGE,1,SANS,align='l',glow=0.3)
    text(c,"顺风 ≈68 km/h",b[0]+175,b[1]+186,26,CYAN,1,SANS,align='l',glow=0.3)
    text(c,"尾流上偏 ↑",b[0]-480,b[1]-130,28,GOLD2,0.95,SANS,align='l',glow=0.3)
    text(c,"马格努斯力 ↓",m[0]+60,m[1]-90,34,GOLD2,1,SANS,align='l',glow=0.5)
    text(c,"0.41 N",m[0]+60,m[1]-40,40,GOLD2,1,MONO,align='l',glow=0.5)
    text(c,"上 旋 下 坠",540,1185,112,GOLD,1,SERIF,align='c',sp=26,glow=0.45)
    text(c,"WHY TOPSPIN DIVES",540,1232,22,GRAY,0.9,MONO,align='c',sp=8,shadow=0)
    text(c,"3200 转/分时，向下的力≈自重的 73%",540,1306,32,WHITE,0.95,SANS,align='c')
    text(c,"F = ½·C_L·ρ·A·v²   ≈ 1.7 倍重力",540,1362,30,GOLD2,1,MONO,align='c',glow=0.3)
make('c1.5.png','cover_B_xiaozuofang.jpg',B)

# ---------- C 许先森：电影感 3D 大场面 ----------
def C(c,an):
    grad(c,0,560,0.7,0); grad(c,1080,1440,0,0.85)
    brand(c)
    text(c,"上旋球为什么会",60,232,104,WHITE,1,SERIF)
    rich(c,[("突然",WHITE),("往下坠",GOLD),("？",WHITE)],60,356,104,SERIF,glow=0.5)
    text(c,"THE DIVE OF TOPSPIN",64,410,22,GRAY,0.9,MONO,sp=6,shadow=0)
    b=an['ball']; text(c,"上旋 4000 转 · 落在 22.5 m",b[0]-50,b[1]+30,30,GOLD2,1,SANS,align='r',glow=0.5); text(c,"向下的马格努斯力一直都在",b[0]-50,b[1]+70,26,MAG,1,SANS,align='r',glow=0.3)
    a=an['a0']; text(c,"同一拍不转 → 飞出 32.1 m",a[0]-60,a[1]-78,28,CYAN,1,SANS,align='l',glow=0.3)
    rich(c,[("偏离的 ",WHITE),("七成",GOLD),(" 发生在后半程",WHITE)],60,1290,54)
    text(c,"半程只低 0.9 m → 落地时差 3.1 m（按 Rod Cross 模型计算）",62,1350,25,GRAY,0.95,SANSR)
make('c2.5.png','cover_C_xuxiansen.jpg',C)
