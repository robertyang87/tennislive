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
f=F(44);left='2026.09.07';right=' · 美网第四轮';w1=d.textlength(left,font=f);w2=d.textlength(right,font=f);x=RIGHT-w1-w2
# Mixed digits/CJK share ONE baseline, not independently aligned glyph tops.
row_box=f.getbbox(left+right,anchor='ls');row_baseline=y-row_box[1]
for text,color,xx in [(left,MUTED,x),(right,GREEN,x+w1)]:
 d.text((xx+1,row_baseline+1),text,font=f,fill=(0,0,0,255),anchor='ls',stroke_width=4,stroke_fill=(0,0,0,255))
 d.text((xx,row_baseline),text,font=f,fill=color,anchor='ls',stroke_width=4,stroke_fill=INK)
y+=row_box[3]-row_box[1]+12
f=S(72);chunks=[('5',WHITE),('-',MUTED),('7',GREEN),(' ',WHITE),('3',WHITE),('-',MUTED),('6',GREEN)];total=sum(d.textlength(t,font=f) for t,c in chunks);x=RIGHT-total;b=f.getbbox('5-7 3-6',anchor='ls');baseline=y-b[1]
for t,c in chunks:d.text((x+1,baseline+1),t,font=f,fill=(0,0,0,255),anchor='ls',stroke_width=4,stroke_fill=(0,0,0,255));d.text((x,baseline),t,font=f,fill=c,anchor='ls',stroke_width=4,stroke_fill=INK);x+=d.textlength(t,font=f)
y+=b[3]-b[1]+12
f=F(44);people_chunks=[('斯瓦泰克',WHITE),(' vs ',MUTED),('郑钦文',GREEN)];tw=sum(d.textlength(t,font=f) for t,c in people_chunks);xx=RIGHT-tw
# Center the shorter Latin vs on the visible vertical center of both names.
name_bounds=[f.getbbox(t) for t,c in people_chunks if t.strip()!='vs']
name_height=max(b[3]-b[1] for b in name_bounds)
for t,c in people_chunks:
 bounds=f.getbbox(t);glyph_height=bounds[3]-bounds[1]
 yy=y+(name_height-glyph_height)/2 if t.strip()=='vs' else y
 run(t,f,c,yy,x=xx,stroke=4,outline=INK);xx+=d.textlength(t,font=f)
bottom=y+name_height
# Existing accent rail retained. No panel, fill or name-row background.
d.rounded_rectangle((1017,122,1023,bottom),radius=3,fill=GREEN)
# Shrink the entire card uniformly about its top-right anchor; preserve typography.
SCALE=0.90
layer=layer.resize((round(layer.width*SCALE),round(layer.height*SCALE)),Image.Resampling.LANCZOS)
new.alpha_composite(layer,(round(1023*(1-SCALE)),round(122*(1-SCALE))))
new=new.convert('RGB');new.save(out/'card-original-font-v11-full.jpg',quality=95)
previous=Image.open(out/'card-original-font-v10-full.jpg').convert('RGB')
canvas=Image.new('RGB',(840,588),'#eef1f4');cd=ImageDraw.Draw(canvas)
cd.text((28,16),'上一版',font=F(24),fill='#142a3f');cd.text((448,16),'日期对齐 · vs 居中',font=F(24),fill='#142a3f')
canvas.paste(previous.resize((390,520),Image.Resampling.LANCZOS),(15,56));canvas.paste(new.resize((390,520),Image.Resampling.LANCZOS),(435,56));canvas.save(out/'card-original-font-v11-comparison.jpg',quality=95)
p=out/'card-readability-analysis.json';r=json.loads(p.read_text());current=r['current_proposal']
current.update({'image':'card-original-font-v11-comparison.jpg','scale_from_v9':SCALE,'font_changes':False,'scale_scope':'entire card including all four text rows, spacing, outline/shadow and accent rail; top-right anchored','sizes_native_px':{k:round(v*SCALE,1) for k,v in {'topic':58,'date_place':44,'score':72,'people':44}.items()},'outline_px':4*SCALE,'shadow_px':SCALE,'visible_glyph_gaps_native_px':12*SCALE,'right_shift_px':44,'text_right_native_px':round(1023+(992-1023)*SCALE),'rail_right_native_px':1023})
current['vs_alignment']='Visible glyph center aligned vertically with player names; original spacing and font retained'
current['date_event_alignment']='Shared alphabetic baseline; full-row glyph bounds determine following score position'
current['date_event_baseline_fix_native_px']=6*SCALE
r['superseded_proposals']['v9_size']='User: 对比度够了，但感觉字号有点大 / 整体都要缩小; V10 scales complete card to 90%'
p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print('Created V11 static preview: shared date/event baseline and vertically centered vs; V10 scale retained')
