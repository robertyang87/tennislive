from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
p=Path(__file__).parent
im=Image.open(p/'cover/sun-usopen-trophy.jpg').convert('RGB');w,h=im.size;cw=int(h*.75);im=im.crop(((w-cw)//2,0,(w+cw)//2,h)).resize((1080,1440),Image.Resampling.LANCZOS).convert('RGBA')
a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
for y in range(700,1440):d.line((0,y,1080,y),fill=(5,10,22,int(220*(y-700)/740)))
im=Image.alpha_composite(im,a);d=ImageDraw.Draw(im);font=str(p/'cover/NotoSansCJKsc-Bold.otf')
def text(x,y,t,size,color):d.text((x,y),t,font=ImageFont.truetype(font,size),fill=color,stroke_width=1)
d.rectangle((0,0,1080,10),fill='#D2F050');logo=Image.open(p/'original4.jpg').crop((70,62,124,116)).resize((56,56)).convert('RGBA');mask=Image.new('L',(56,56));ImageDraw.Draw(mask).ellipse((2,2,54,54),fill=255);im.paste(logo,(60,54),mask);d=ImageDraw.Draw(im);text(132,48,'网球时差 · 网球有故事',34,'white')
text(64,1080,'孙心然',108,'white');text(70,1240,'从青少年赛场到中网',53,'#D2F050');text(72,1360,'摄影：Getty Images / WTA',22,'#D8DDE3')
im.convert('RGB').save(p/'孙心然成长历程_封面.jpg',quality=96)
