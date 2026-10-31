"""vibetennis 第一集英文版封面：画面层与中文 v9 完全相同（hero.py 的球场＋本脚本的两个张角扇形），
只把文字换成英文，品牌名写英文「Tennis Jetlag」（所有者 2026-10-31）。

先跑同目录 hero.py。字体用拉丁字体：Noto Serif（可变字重，取 Black）与 Inter（可变字重），路径见 SERIF/SANS；
可用 $VT_EN_SERIF / $VT_EN_SANS 覆盖。输出 poster_en.jpg（2160×2880）到 $VT_COVER_WORK。
"""
import os
from pathlib import Path
REPO = Path(__file__).resolve().parents[5]
FONTS = os.environ.get("VT_FONTS", "/tmp/vt/fonts")
os.chdir(os.environ.get("VT_COVER_WORK", "."))
import numpy as np, cv2, json, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=2160,2880
g=json.load(open('geo7.json')); B1,B2,C,E=[np.array(g[k]) for k in ('B1','B2','C','E')]
hero=cv2.cvtColor(cv2.imread('hero7.png'),cv2.COLOR_BGR2RGB).astype(np.float32)/255
lay=np.zeros((H,W,3),np.float32)
GOLD=(1.0,0.74,0.25); CYAN=(0.35,0.85,1.0)
def wedge(A,P,Q,col,fill,edge,rad,lw):
    poly=np.array([A,P,Q],np.int32)
    f=np.zeros_like(lay); cv2.fillPoly(f,[poly],tuple(c*fill for c in col),cv2.LINE_AA)
    # fade fill with distance from apex
    yy,xx=np.mgrid[0:H,0:W]; d=np.hypot(xx-A[0],yy-A[1]); L=max(np.linalg.norm(P-A),np.linalg.norm(Q-A))
    f*=np.clip(1-d/L,0.15,1)[...,None]
    lay[:]+=f
    for T in (P,Q): cv2.line(lay,tuple(A.astype(int)),tuple(T.astype(int)),tuple(c*edge for c in col),lw,cv2.LINE_AA)
    a1=math.degrees(math.atan2(P[1]-A[1],P[0]-A[0])); a2=math.degrees(math.atan2(Q[1]-A[1],Q[0]-A[0]))
    lo,hi=sorted([a1,a2])
    if hi-lo>180: lo,hi=hi,lo+360
    cv2.ellipse(lay,tuple(A.astype(int)),(rad,rad),0,lo,hi,tuple(c*1.2 for c in col),lw+2,cv2.LINE_AA)
wedge(E,B1,B2,GOLD,0.22,0.9,260,3)
wedge(C,B1,B2,CYAN,0.20,0.8,330,3)
# eye icon (line art) at E, looking left
ex,ey=E.astype(int); s=78
pts=[]
for t in np.linspace(0,math.pi,40): pts.append((ex+s*math.cos(t)*1.0, ey-s*0.55*math.sin(t)))
for t in np.linspace(math.pi,2*math.pi,40): pts.append((ex+s*math.cos(t)*1.0, ey-s*0.55*math.sin(t)))
cv2.polylines(lay,[np.array(pts,np.int32)],True,(1.0,0.9,0.7),4,cv2.LINE_AA)
cv2.circle(lay,(ex-10,ey),int(s*0.32),(1.0,0.8,0.35),4,cv2.LINE_AA)
cv2.circle(lay,(ex-14,ey),int(s*0.12),(1.0,0.85,0.5),-1,cv2.LINE_AA)
# broadcast camera icon at C (looking up-court)
cx,cy=C.astype(int)
cv2.rectangle(lay,(cx-46,cy-4),(cx+46,cy+66),(0.5,0.9,1.0),4,cv2.LINE_AA)
cv2.rectangle(lay,(cx-26,cy-34),(cx+26,cy-4),(0.5,0.9,1.0),4,cv2.LINE_AA)
cv2.line(lay,(cx,cy+66),(cx,cy+130),(0.5,0.9,1.0),4,cv2.LINE_AA)
cv2.line(lay,(cx-40,cy+150),(cx,cy+130),(0.5,0.9,1.0),4,cv2.LINE_AA); cv2.line(lay,(cx+40,cy+150),(cx,cy+130),(0.5,0.9,1.0),4,cv2.LINE_AA)
glow=cv2.GaussianBlur(lay,(0,0),10)*1.1+cv2.GaussianBlur(lay,(0,0),36)*0.6
out=hero+lay+glow
# vignette + slight haze
yy,xx=np.mgrid[0:H,0:W]; r=np.hypot((xx-W/2)/W,(yy-H*0.55)/H)
out*=np.clip(1.15-r*1.1,0.35,1)[...,None]
out=np.clip(out,0,1)
rng=np.random.default_rng(5); out=out+rng.normal(0,0.008,out.shape)
img=Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8))
d=ImageDraw.Draw(img)
SERIF=os.environ.get("VT_EN_SERIF","/usr/share/fonts/truetype/sand-box/google/Noto Serif/NotoSerif-VariableFont_wdth,wght.ttf")
SANS=os.environ.get("VT_EN_SANS","/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf")
def font(path,size,style):
    f=ImageFont.truetype(path,size)
    try: f.set_variation_by_name(style)
    except Exception: pass
    return f
Y=(255,200,40); WH=(245,245,240); GR=(150,155,165)
icon=Image.open(str(REPO/'assets/logo/brand/account/icon-transparent-1024.png')).convert('RGBA').resize((64,64),Image.LANCZOS)
# --- logo: icon | Tennis Jetlag, ink-centred on CY (same spot as the Chinese v9) ---
CY=210; GAP=22; BRAND='Tennis Jetlag'
fT=font(SANS,58,'Black')
m=Image.new('L',(1200,200),0); ImageDraw.Draw(m).text((50,50),BRAND,font=fT,fill=255)
tb=m.getbbox(); tw,th=tb[2]-tb[0],tb[3]-tb[1]
capb=Image.new('L',(1200,200),0); ImageDraw.Draw(capb).text((50,50),'TJ',font=fT,fill=255); cb=capb.getbbox()
ib=icon.split()[3].point(lambda v:255 if v>40 else 0).getbbox(); icon_c=icon.crop(ib); iw,ih=icon_c.size
x=140
img.paste(icon_c,(x,CY-ih//2),icon_c); x+=iw+GAP
# centre on cap height (ignore the descender of "g") so it lines up with the icon like the CJK mark
d.text((x-(tb[0]-50),CY-(cb[3]-cb[1])//2-(cb[1]-50)),BRAND,font=fT,fill=Y)
# title: a complete question, two serif lines
ftt=font(SERIF,176,'Black')
d.text((134,300),'Why does tennis',font=ftt,fill=WH)
d.text((134,510),'look faster live?',font=ftt,fill=WH)
ft=font(SANS,40,'SemiBold')
d.text((150,800),'S A M E   S E R V E   ·   T W O   V I E W P O I N T S',font=ft,fill=GR)
# diagram labels
fl=font(SANS,96,'Black'); fs=font(SANS,46,'Bold')
d.text((E[0]-30,E[1]+80),'138°/s',font=fl,fill=Y); d.text((E[0]-26,E[1]+190),'Courtside',font=fs,fill=(235,225,200))
d.text((C[0]+110,C[1]-10),'19°/s',font=fl,fill=(110,205,255)); d.text((C[0]+114,C[1]+100),'TV camera',font=fs,fill=(185,215,235))
# bottom copy
f1=font(SERIF,120,'Black')
d.text((140,2440),'Same serve, courtside:',font=f1,fill=WH)
d.text((140,2600),'7× faster',font=f1,fill=Y)
d.text((146,2790),'Courtside it sweeps ~138° a second across your view; on TV, only ~19°',font=font(SANS,44,'SemiBold'),fill=GR)
img.save('poster_en.jpg',quality=94,subsampling=0)
img.resize((360,480),Image.LANCZOS).save('thumb_en.jpg')
