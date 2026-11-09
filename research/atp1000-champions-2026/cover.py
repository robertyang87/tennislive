from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
R='/home/user/tennislive/assets/fonts/'
BG=(9,14,28); GREEN=(198,246,90); WHITE=(245,247,250)
SRC={'iw':'iw.jpg','mia':'mia.jpg','mc':'mc.jpg','mad':'mad.jpg','rome':'rome.jpg','mtl':'mtl.jpg','cin':'cin_v.png','sh':'sh.jpg','par':'par_v.png'}
NAME={'iw':'印第安维尔斯','mia':'迈阿密','mc':'蒙特卡洛','mad':'马德里','rome':'罗马','mtl':'蒙特利尔','cin':'辛辛那提','sh':'上海','par':'巴黎'}
WHO={'iw':'辛纳','mia':'辛纳','mc':'辛纳','mad':'辛纳','rome':'辛纳','mtl':'谢尔顿','cin':'菲斯','sh':'福基纳','par':'阿尔卡拉斯'}
# 焦点（x,y 比例）与放大：让「脸＋奖杯」落在格子中间
FOC={'iw':(0.55,0.32,1.25),'mia':(0.5,0.3,1.15),'mc':(0.42,0.34,1.1),'mad':(0.5,0.4,1.6),'rome':(0.6,0.32,1.0),
     'mtl':(0.35,0.38,1.05),'cin':(0.62,0.3,1.0),'sh':(0.45,0.36,1.35),'par':(0.56,0.35,1.0)}
STRIP={'iw':(0.62,0.3,1.0),'mia':(0.6,0.3,1.0),'mc':(0.55,0.3,1.0),'mad':(0.5,0.35,1.25),'rome':(0.68,0.3,1.0)}
def cell(k,w,h,foc=None):
    img=ImageOps.exif_transpose(Image.open(SRC[k])).convert('RGB')
    fx,fy,z=(foc or FOC)[k]; W,H=img.size; s=max(w/W,h/H)*z
    im=img.resize((round(W*s),round(H*s)),Image.LANCZOS)
    x=min(max(round(fx*im.width-w/2),0),im.width-w); y=min(max(round(fy*im.height-h/2),0),im.height-h)
    return im.crop((x,y,x+w,y+h))
def f(n,s): return ImageFont.truetype(R+n,s)
def tag(c,d,x,y,k,size=28,who=True):
    t=NAME[k]; ft=f('NotoSansSC-Bold-sub.ttf',size); fw=f('NotoSansSC-Regular-sub.ttf',int(size*0.78))
    d.text((x,y),t,font=ft,fill=WHITE,stroke_width=3,stroke_fill=(0,0,0))
    if who:
        tw=d.textlength(t,font=ft); d.text((x+tw+10,y+size*0.22),WHO[k],font=fw,fill=GREEN,stroke_width=3,stroke_fill=(0,0,0))
def grad(c,box,top=True,a=200):
    x0,y0,x1,y1=box; g=Image.new('L',(1,y1-y0))
    for i in range(y1-y0): g.putpixel((0,i),int(a*((i/(y1-y0)) if not top else (1-i/(y1-y0)))))
    g=g.resize((x1-x0,y1-y0)); c.paste(Image.new('RGB',(x1-x0,y1-y0),BG),(x0,y0),g)

def B():  # 3x3：上两排、标题带、下一排
    c=Image.new('RGB',(1080,1440),BG); d=ImageDraw.Draw(c); order=['iw','mia','mc','mad','rome','mtl','cin','sh','par']
    w,h=360,370; ys=[0,370,1070]
    for i,k in enumerate(order):
        x,y=(i%3)*w,ys[i//3]; c.paste(cell(k,w-4,h-4),(x+2,y+2))
        grad(c,(x+2,y+h-110,x+w-2,y+h-2),top=False,a=210); tag(c,d,x+16,y+h-56,k,26)
    t='9站5冠'; ft=f('SmileySans-Oblique.ttf',165); d.text(((1080-d.textlength(t,font=ft))/2,752),t,font=ft,fill=WHITE)
    s2='2026 ATP1000 冠军全盘点'; fs=f('NotoSansSC-Bold-sub.ttf',44); d.text(((1080-d.textlength(s2,font=fs))/2,968),s2,font=fs,fill=GREEN)
    return c
def C():  # 上：辛纳五连冠五条竖幅；中：标题；下：后四站四个新名字
    c=Image.new('RGB',(1080,1440),BG); d=ImageDraw.Draw(c)
    top=['iw','mia','mc','mad','rome']; w=216; h=620
    for i,k in enumerate(top):
        c.paste(cell(k,w-4,h,STRIP),(i*w+2,0)); grad(c,(i*w+2,h-150,i*w+w-2,h),top=False,a=230)
        ft=f('NotoSansSC-Bold-sub.ttf',26); t=NAME[k]
        d.text((i*w+(w-d.textlength(t,font=ft))/2,h-50),t,font=ft,fill=WHITE,stroke_width=3,stroke_fill=(0,0,0))
    fl=f('NotoSansSC-Bold-sub.ttf',30); lab='前5站 · 辛纳一个人'; d.text((24,22),lab,font=fl,fill=GREEN,stroke_width=4,stroke_fill=(0,0,0))
    t='9站5冠'; ft=f('SmileySans-Oblique.ttf',160); d.text(((1080-d.textlength(t,font=ft))/2,616),t,font=ft,fill=WHITE)
    s='2026 ATP1000 冠军全盘点'; fs=f('NotoSansSC-Bold-sub.ttf',42); d.text(((1080-d.textlength(s,font=fs))/2,812),s,font=fs,fill=GREEN)
    bot=['mtl','cin','sh','par']; w2,h2=540,276; y0=888
    for i,k in enumerate(bot):
        x,y=(i%2)*w2,y0+(i//2)*h2; c.paste(cell(k,w2-4,h2-4),(x+2,y+2)); grad(c,(x+2,y+h2-100,x+w2-2,y+h2-2),top=False,a=210)
        tag(c,d,x+18,y+h2-54,k,28)
    d.text((24,y0+18),'后4站 · 4个人',font=fl,fill=GREEN,stroke_width=4,stroke_fill=(0,0,0))
    return c
def A():  # WTA 那张的版式（上 4、标题、罗马通栏、下 4）
    c=Image.new('RGB',(1080,1440),BG); d=ImageDraw.Draw(c)
    boxes={'iw':(0,0,540,240),'mia':(540,0,540,240),'mc':(0,240,540,240),'mad':(540,240,540,240),
           'rome':(0,720,1080,240),'mtl':(0,960,540,240),'cin':(540,960,540,240),'sh':(0,1200,540,240),'par':(540,1200,540,240)}
    for k,(x,y,w,h) in boxes.items():
        c.paste(cell(k,w-4,h-4),(x+2,y+2)); grad(c,(x+2,y+h-90,x+w-2,y+h-2),top=False,a=200); tag(c,d,x+16,y+h-52,k,28)
    t='9站5冠'; ft=f('SmileySans-Oblique.ttf',150); d.text(((1080-d.textlength(t,font=ft))/2,492),t,font=ft,fill=WHITE)
    s='2026 ATP1000 冠军全盘点'; fs=f('NotoSansSC-Bold-sub.ttf',46); d.text(((1080-d.textlength(s,font=fs))/2,648),s,font=fs,fill=GREEN)
    return c
for n,fn in (('A',A),('B',B),('C',C)): fn().save(f'cover_{n}.jpg',quality=93)
row=Image.new('RGB',(3*1080+80,1440),(40,40,40))
for i,n in enumerate('ABC'): row.paste(Image.open(f'cover_{n}.jpg'),(i*(1080+40),0))
row.resize((row.width//2,row.height//2)).save('compare.jpg',quality=88)
