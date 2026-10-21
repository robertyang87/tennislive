from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json
R=Path('/workspace/tennislive');out=R/'research/swiatek-season-end-2026/subtitle-audit';tmp=Path('/tmp/swiatek-subtitle-style');tmp.mkdir(exist_ok=True)
Image.new('RGBA',(1080,300),(0,0,0,0)).save(tmp/'transparent.png')
# Same CJK face, bold, dark outline (4px) and 1px shadow as the actual reel subtitles.
header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 300
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CARD,Noto Sans CJK SC,60,&H00F7FBF4,&H000000FF,&H00181E14,&H00000000,1,0,0,0,100,100,0,0,1,4,1,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
rows=[r'{\pos(20,20)\fs84}领先之后被逆转',r'{\pos(20,20)\fs60\fscx85\c&H00DBE2D5&}2026.09.07 · {\c&H005AF6C6&}美网第四轮',r'{\pos(20,20)\fnTL Score\fs92\c&H00F7FBF4&}5-{\c&H005AF6C6&}7 {\c&H00F7FBF4&}3-{\c&H005AF6C6&}6',r'{\pos(20,20)\fs60\c&H00F7FBF4&}斯瓦泰克 vs {\c&H005AF6C6&}郑钦文']
images=[]
for i,text in enumerate(rows):
 ass=tmp/f'row-{i}.ass';ass.write_text(header+f'Dialogue: 0,0:00:00.00,0:00:01.00,CARD,,0,0,0,,{text}\n');p=tmp/f'row-{i}.png'
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(tmp/'transparent.png'),'-vf',f'ass={ass}:fontsdir={R}/assets/fonts:alpha=1','-frames:v','1','-pix_fmt','rgba',str(p)],check=True)
 im=Image.open(p).convert('RGBA');box=im.getbbox();assert box;images.append(im.crop(box))
old=Image.open('/tmp/swiatek-final/card-16-at-seven-seconds.jpg').convert('RGB');clean=Image.open('/tmp/swiatek-clean-uso.jpg').convert('RGB');new=old.copy();new.paste(clean.crop((650,150,995,380)),(650,150));new=new.convert('RGBA');top=122;y=top;gaps=[6,4,6,0];positions=[]
for i,im in enumerate(images):
 x=992-im.width;new.alpha_composite(im,(x,y));positions.append({'row':i,'box':[x,y,x+im.width,y+im.height]});y+=im.height+gaps[i]
rail=Image.new('RGBA',new.size);ImageDraw.Draw(rail).rounded_rectangle((1017,top,1023,y),radius=3,fill=(198,246,90,255));new.alpha_composite(rail);new=new.convert('RGB');new.save(out/'card-subtitle-effect-v8-full.jpg',quality=95)
prev=Image.open(out/'card-type-only-v6-full.jpg').convert('RGB');canvas=Image.new('RGB',(840,588),'#eef1f4');d=ImageDraw.Draw(canvas);f=ImageFont.truetype(str(R/'assets/fonts/SmileySans-Oblique.ttf'),24);d.text((28,16),'上一张静态样张',font=f,fill='#142a3f');d.text((448,16),'字幕效果 · 输白赢黄绿',font=f,fill='#142a3f');canvas.paste(prev.resize((390,520),Image.Resampling.LANCZOS),(15,56));canvas.paste(new.resize((390,520),Image.Resampling.LANCZOS),(435,56));canvas.save(out/'card-subtitle-effect-v8-comparison.jpg',quality=95)
p=out/'card-readability-analysis.json';r=json.load(open(p));r['current_proposal']={'image':'card-subtitle-effect-v8-comparison.jpg','background':'none','font':'Noto Sans CJK SC, bold; score remains TL Score','outline':4,'shadow':1,'effect_source':'actual published subtitles.ass TL style','text_colors':'unchanged; winner name brand green, loser name original title white','date':'2026.09.07 · 美网第四轮','sizes':{'topic':84,'meta':60,'score':92,'people':60},'meta_scale_x':85,'alignment':'right; text edge992, rail edge1023','rows':positions,'scope':'Single-frame static preview only. No video rendered or published.'};p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('Subtitle-style static preview created',positions)
