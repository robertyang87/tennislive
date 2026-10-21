from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import json
R=Path(__file__).resolve().parents[3];out=R/'research/swiatek-season-end-2026/subtitle-audit';out.mkdir(exist_ok=True)
F=lambda n:ImageFont.truetype(str(R/'assets/fonts/SmileySans-Oblique.ttf'),n)
S=lambda n:ImageFont.truetype(str(R/'assets/fonts/TLScore-Bold.ttf'),n)
old=Image.open(out/'published-card-reference.jpg').convert('RGB');clean=Image.open(out/'clean-source-frame.jpg').convert('RGB');new=old.copy();new.paste(clean.crop((650,150,995,370)),(650,150));new=new.convert('RGBA');layer=Image.new('RGBA',new.size);d=ImageDraw.Draw(layer)
WHITE=(244,251,247,255);MUTED=(213,226,219,255);GREEN=(198,246,90,255);INK=(20,30,24,255);NAME=(32,47,54,255);RIGHT=992
measure=ImageDraw.Draw(Image.new('RGBA',(1,1)))
def run(text,f,color,y,x=None,stroke=4,outline=INK):
 b=d.textbbox((0,0),text,font=f,stroke_width=0);x=RIGHT-(b[2]-b[0])-b[0] if x is None else x;d.text((x+1,y-b[1]+1),text,font=f,fill=(0,0,0,255),stroke_width=stroke,stroke_fill=(0,0,0,255));d.text((x,y-b[1]),text,font=f,fill=color,stroke_width=stroke,stroke_fill=outline);return b[3]-b[1]
y=122;h=run('领先之后被逆转',F(58),WHITE,y);y+=h+12
f=F(44);left='2026.09.07';right=' · 美网第四轮';w1=d.textlength(left,font=f);w2=d.textlength(right,font=f);x=RIGHT-w1-w2;h_date=run(left,f,MUTED,y,x=x);h_place=run(right,f,GREEN,y,x=x+w1);h=max(h_date,h_place);y+=h+12
f=S(72);chunks=[('5',WHITE),('-',MUTED),('7',GREEN),(' ',WHITE),('3',WHITE),('-',MUTED),('6',GREEN)];total=sum(d.textlength(t,font=f) for t,c in chunks);x=RIGHT-total;b=f.getbbox('5-7 3-6',anchor='ls');baseline=y-b[1]
for t,c in chunks:d.text((x+1,baseline+1),t,font=f,fill=(0,0,0,255),anchor='ls',stroke_width=4,stroke_fill=(0,0,0,255));d.text((x,baseline),t,font=f,fill=c,anchor='ls',stroke_width=4,stroke_fill=INK);x+=d.textlength(t,font=f)
y+=b[3]-b[1]+12
f=F(44);people_chunks=[('斯瓦泰克',WHITE),(' vs ',MUTED),('郑钦文',GREEN)];tw=sum(d.textlength(t,font=f) for t,c in people_chunks);xx=RIGHT-tw;hh=0
for t,c in people_chunks:
 hh=max(hh,run(t,f,c,y,x=xx,stroke=4,outline=INK));xx+=d.textlength(t,font=f)
bottom=y+hh
# Existing accent rail retained. No panel, fill or name-row background.
d.rounded_rectangle((1017,122,1023,bottom),radius=3,fill=GREEN);new.alpha_composite(layer);new=new.convert('RGB');new.save(out/'card-original-font-v9-full.jpg',quality=95)
canvas=Image.new('RGB',(840,588),'#eef1f4');cd=ImageDraw.Draw(canvas);cd.text((28,16),'现版 · 手机尺寸',font=F(24),fill='#142a3f');cd.text((448,16),'原字体 · 字幕描边效果',font=F(24),fill='#142a3f');canvas.paste(old.resize((390,520),Image.Resampling.LANCZOS),(15,56));canvas.paste(new.resize((390,520),Image.Resampling.LANCZOS),(435,56));canvas.save(out/'card-original-font-v9-comparison.jpg',quality=95)
p=out/'card-readability-analysis.json';r=json.load(open(p));r['previous_background_proposal']='rejected by user: 不要加背景 / 很丑';r['current_proposal']={'image':'card-original-font-v9-comparison.jpg','background':'none; transparent typography with existing right accent rail','date_format':'2026.09.07 · 美网第四轮; unchanged','font_phone_css_estimate':{'topic':58*390/1080,'date_place':44*390/1080,'score':72*390/1080,'people':44*390/1080},'meta_to_score_visible_gap_native_px':12,'people_color':{'winner':'#c6f65a','loser':'#f4fbf7'},'right_shift_native_px':44,'accent_right_margin_native_px':56,'scope':'Static review only; no production spec/video changed'};p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('Type-only static V2 created')
