from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import json
import argparse
import re
parser=argparse.ArgumentParser()
parser.add_argument("--score",default="5-7 3-6")
parser.add_argument("--layout-test",action="store_true")
args=parser.parse_args()
variant=("v14-tiebreak-five-set" if len(args.score.split())==5 else "v14-tiebreak") if args.layout_test else "v14"
R=Path(__file__).resolve().parents[3];out=R/'research/swiatek-season-end-2026/subtitle-audit';out.mkdir(exist_ok=True)
F=lambda n:ImageFont.truetype(str(R/'assets/fonts/SmileySans-Oblique.ttf'),n)
S=lambda n:ImageFont.truetype(str(R/'assets/fonts/TLScore-Bold.ttf'),n)
L=lambda n:ImageFont.truetype(str(R/'assets/fonts/TLScore-Light.ttf'),n)
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
SCORE_GAP=10
y+=row_box[3]-row_box[1]+SCORE_GAP
score_text=args.score
max_score_width=max(d.textlength('领先之后被逆转',font=F(58)),w1+w2,d.textlength('斯瓦泰克 vs 郑钦文',font=F(44)))
def score_layout(text,size):
 main=S(size);light=L(size);small=L(round(size*0.48));runs=[];cursor=0
 def add(t,font,color,dy=0,stroke=4):
  nonlocal cursor
  runs.append((t,font,color,cursor,dy,stroke));cursor+=d.textlength(t,font=font)
 main_top=main.getbbox('6',anchor='ls')[1]
 small_top=small.getbbox('5',anchor='ls')[1]
 raise_baseline=main_top-3-small_top
 for i,pair in enumerate(text.split()):
  match=re.fullmatch(r'(\d+)-(\d+)(?:\((\d+)\))?',pair)
  if not match:raise ValueError(f'Invalid score: {pair}')
  a,b,tie=match.groups()
  if tie is not None and {a,b}!={'6','7'}:raise ValueError('Tiebreak annotation requires a 7-6 or 6-7 set')
  if i:cursor+=max(18,size*0.3)  # Keep complete set scores visibly separated.
  add(a,main if int(a)>int(b) else light,GREEN if int(a)>int(b) else WHITE)
  if tie is not None and a=='6':
   cursor+=1;add(tie,small,WHITE,raise_baseline,2);cursor+=2
  add('-',light,MUTED);add(b,main if int(b)>int(a) else light,GREEN if int(b)>int(a) else WHITE)
  if tie is not None and b=='6':
   cursor+=1;add(tie,small,WHITE,raise_baseline,2);cursor+=2
 return runs,cursor
score_size=69
runs,total=score_layout(score_text,score_size)
while total>max_score_width:
 score_size-=1;runs,total=score_layout(score_text,score_size)
score_slot=S(72).getbbox('5-7 3-6',anchor='ls');score_slot_height=score_slot[3]-score_slot[1]
top=min(font.getbbox(t,anchor='ls')[1]+dy for t,font,c,dx,dy,stroke in runs)
bottom_score=max(font.getbbox(t,anchor='ls')[3]+dy for t,font,c,dx,dy,stroke in runs)
baseline=y+(score_slot_height-(bottom_score-top))/2-top
for t,font,color,dx,dy,stroke in runs:
 xx=RIGHT-total+dx
 d.text((xx+1,baseline+dy+1),t,font=font,fill=(0,0,0,255),anchor='ls',stroke_width=stroke,stroke_fill=(0,0,0,255))
 d.text((xx,baseline+dy),t,font=font,fill=color,anchor='ls',stroke_width=stroke,stroke_fill=INK)
y+=score_slot_height+SCORE_GAP
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
new=new.convert('RGB');
if not args.layout_test:new.save(out/f'card-original-font-{variant}-full.jpg',quality=95)
previous=Image.open(out/'card-original-font-v13-full.jpg').convert('RGB')
canvas=Image.new('RGB',(840,588),'#eef1f4');cd=ImageDraw.Draw(canvas)
cd.text((28,16),'上一版',font=F(24),fill='#142a3f');cd.text((448,16),('五盘含抢七 · 排版示意' if len(args.score.split())==5 else '抢七上标 · 非本场赛果') if args.layout_test else '比分略放大 · 上下收紧',font=F(24),fill='#142a3f')
canvas.paste(previous.resize((390,520),Image.Resampling.LANCZOS),(15,56));canvas.paste(new.resize((390,520),Image.Resampling.LANCZOS),(435,56));canvas.save(out/f'card-original-font-{variant}-comparison.jpg',quality=95)
if args.layout_test:
 detail=Image.new('RGB',(920,320),'#eef1f4');dd=ImageDraw.Draw(detail)
 dd.text((20,12),'实际两盘比分 · 输盘细体',font=F(24),fill='#142a3f')
 dd.text((480,12),'上标与字重示意 · 非本场赛果',font=F(24),fill='#142a3f')
 for xx,frame in [(10,Image.open(out/'card-original-font-v14-full.jpg')),(470,new)]:
  crop=frame.crop((580,105,1040,350));detail.paste(crop,(xx,60))
 detail.save(out/f'card-original-font-{variant}-detail.jpg',quality=95)
 print(json.dumps({'layout_test_only':True,'score':score_text,'font_size_before_group_scale':score_size,'width_before_group_scale':total,'max_width_before_group_scale':max_score_width},ensure_ascii=False));raise SystemExit(0)
p=out/'card-readability-analysis.json';r=json.loads(p.read_text());current=r['current_proposal']
current.update({'image':'card-original-font-v14-comparison.jpg','scale_from_v9':SCALE,'font_changes':False,'scale_scope':'entire card including all four text rows, spacing, outline/shadow and accent rail; top-right anchored','sizes_native_px':{k:round(v*SCALE,1) for k,v in {'topic':58,'date_place':44,'score':score_size,'people':44}.items()},'outline_px':4*SCALE,'shadow_px':SCALE,'visible_glyph_gaps_native_px':{'title_to_date':12*SCALE,'score_row_padding_top_bottom':SCORE_GAP*SCALE},'right_shift_px':44,'text_right_native_px':round(1023+(992-1023)*SCALE),'rail_right_native_px':1023})
current['score_weights']='Per set: larger game count TL Score Bold + brand yellow-green; smaller game count TL Score Light + white; separators and superscript use Light. Same font family retained.'
current['tiebreak']='Bare small digit at upper right of losing game count6, 48% of main score font; includes superscript width in five-set fit; static only'
current['score_fit']='Maximum font size69 before 90% group scale; shrink only score until entire one-line score fits the widest text row. Static prototype only.'
current['score_adjustment']={'previous_font_px_before_group_scale':66,'font_px_before_group_scale':score_size,'scale_from_previous':score_size/66,'placement':'right aligned; score row spacing above/below reduced from12 to10; title/date positions and vs alignment retained'}
current['vs_alignment']='Visible glyph center aligned vertically with player names; original spacing and font retained'
current['date_event_alignment']='Shared alphabetic baseline; full-row glyph bounds determine following score position'
current['date_event_baseline_fix_native_px']=6*SCALE
r['superseded_proposals']['v9_size']='User: 对比度够了，但感觉字号有点大 / 整体都要缩小; V10 scales complete card to 90%'
p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print('Created V14 static preview: score enlarged66 to69; score gaps12 to10; per-set weights and superscripts retained')
