import sys,json
from PIL import Image, ImageDraw, ImageFont, ImageOps
R='/home/user/tennislive/assets/fonts/'
D='/tmp/claude-0/atp/cover/'
# key: (城市名, focus_x, focus_y) — 焦点是原图宽高的比例
F=json.loads(sys.argv[1]) if len(sys.argv)>1 else {}
tiles=[('iw','印第安维尔斯'),('mia','迈阿密'),('mc','蒙特卡洛'),('mad','马德里'),('rome','罗马'),('mtl','蒙特利尔'),('cin','辛辛那提'),('sh','上海'),('par','巴黎')]
def crop(img,w,h,fx,fy):
    W,H=img.size; s=max(w/W,h/H)*F.get('zoom',{}).get('',1)
    im=img.resize((round(W*s),round(H*s)),Image.LANCZOS)
    x=min(max(round(fx*im.width-w/2),0),im.width-w); y=min(max(round(fy*im.height-h/2),0),im.height-h)
    return im.crop((x,y,x+w,y+h))
canvas=Image.new('RGB',(1080,1440),(10,12,20))
lab=ImageFont.truetype(R+'NotoSansSC-Bold-sub.ttf',30)
boxes={'iw':(0,0,540,240),'mia':(542,0,538,240),'mc':(0,242,540,238),'mad':(542,242,538,238),
       'rome':(0,720,1080,238),'mtl':(0,960,540,238),'cin':(542,960,538,238),'sh':(0,1200,540,240),'par':(542,1200,538,240)}
for k,name in tiles:
    x,y,w,h=boxes[k]; fx,fy,z=F.get(k,[0.5,0.35,1.0])
    img=ImageOps.exif_transpose(Image.open(D+k+'.jpg')).convert('RGB')
    W,H=img.size; s=max(w/W,h/H)*z
    im=img.resize((round(W*s),round(H*s)),Image.LANCZOS)
    cx=min(max(round(fx*im.width-w/2),0),im.width-w); cy=min(max(round(fy*im.height-h/2),0),im.height-h)
    canvas.paste(im.crop((cx,cy,cx+w,cy+h)),(x,y))
    d=ImageDraw.Draw(canvas,'RGBA'); tw=d.textlength(name,font=lab)
    ly=y+h-62 if k not in () else y+14
    d.rounded_rectangle((x+14,ly,x+14+tw+22,ly+46),radius=8,fill=(10,14,26,190))
    d.text((x+25,ly+4),name,font=lab,fill='white')
d=ImageDraw.Draw(canvas)
big=ImageFont.truetype(R+'SmileySans-Oblique.ttf',150); sub=ImageFont.truetype(lab.path,46)
t='9站5冠'; tw=d.textlength(t,font=big); d.text(((1080-tw)/2,492),t,font=big,fill='white')
s='2026 ATP1000 冠军全盘点'; sw=d.textlength(s,font=sub); d.text(((1080-sw)/2,648),s,font=sub,fill=(198,246,90))
canvas.save(D+'cover.jpg',quality=93); print('ok')
