from pathlib import Path
import json, hashlib
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'data-canonical.json').read_text())
W, H = 1080, 1440
CJK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
CJK_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
NUM = '/workspace/shelton-finals-production/native/assets/fonts/Inter-SemiBold.ttf'

def font(size, bold=False, number=False):
    return ImageFont.truetype(NUM if number else CJK_B if bold else CJK, size,
                              index=0 if number else 2)

im = Image.new('RGB', (W,H), '#071322')
pix = im.load()
for y in range(H):
    for x in range(W):
        glow = max(0, 1 - ((x-900)/1050)**2 - ((y-80)/700)**2)
        pix[x,y] = (7+int(3*glow),19+int(10*glow),34+int(17*glow))
d=ImageDraw.Draw(im)
WHITE='#f4f8fc'; MUTED='#9eafc4'; MINT='#7debc1'; GREY='#66788e'

def text(x,y,s,f,fill=WHITE,anchor=None):
    d.text((x,y),s,font=f,fill=fill,anchor=anchor,stroke_width=0)

# Keep the first 139px clear for both lines of the native series header.
text(60,139,'年终资格积分榜',font(74,True))
text(64,235,DATA['date_label_zh'],font(31),MUTED)
text(1016,246,'8席全部确定',font(30,True),MINT,anchor='ra')
text(99,292,'排名',font(26),MUTED,anchor='ma')
text(172,292,'球员',font(26),MUTED)
text(782,292,'赛季积分',font(26),MUTED,anchor='ra')
text(920,292,'资格',font(26),MUTED,anchor='ma')

row_h=55; step=61; y0=334
for row in DATA['rows']:
    y=y0+(row['rank']-1)*step
    active=row['highlight']; focus=row['focus']; withdrawn=row['status']=='withdrawn'
    fill='#153d50' if focus else '#102d3d' if active else '#0c1b2d'
    d.rounded_rectangle((60,y,1020,y+row_h),radius=11,fill=fill,
                         outline=MINT if focus else '#16313e' if active else '#14283d',
                         width=3 if focus else 1)
    if active:d.rounded_rectangle((60,y+9,65,y+row_h-9),radius=2,fill=MINT)
    ink=GREY if withdrawn else WHITE
    text(99,y+row_h/2,str(row['rank']),font(32,number=True),MINT if active else ink,anchor='mm')
    f=font(36,True if active else False)
    assert d.textlength(row['player_zh'],font=f)<420,row['player_zh']
    text(172,y+row_h/2,row['player_zh'],f,ink,anchor='lm')
    text(782,y+row_h/2,f"{row['points']:,}",font(38,number=True),MINT if active else ink,anchor='rm')
    if active:
        d.rounded_rectangle((835,y+11,1000,y+row_h-11),radius=18,
                             fill=MINT if focus else '#1b4452')
        text(918,y+row_h/2,DATA.get('focus_qualification_label_zh','已晋级') if focus else '已晋级',font(22,True),
             '#092820' if focus else MINT,anchor='mm')
    elif withdrawn:
        text(918,y+row_h/2,'已退赛',font(22),GREY,anchor='mm')

# Reserve 1260–1370px for native narration captions. Sinner's withdrawn
# status remains explicitly visible in his own row.
d.line((64,1380,1016,1380),fill='#2c425b',width=1)
footer='高亮=已晋级  ·  积分：Live-Tennis  ·  资格：ATP / Nitto'
assert d.textlength(footer,font=font(23))<952
text(64,1394,footer,font(23),MUTED)
im.save(ROOT/'race-points-qualified.png')
proof={'canvas':[W,H],'data_sha256':hashlib.sha256((ROOT/'data-canonical.json').read_bytes()).hexdigest(),
       'image_sha256':hashlib.sha256((ROOT/'race-points-qualified.png').read_bytes()).hexdigest(),
       'highlighted':[r['player_zh'] for r in DATA['rows'] if r['highlight']],
       'focus':DATA['focus_name_zh'],'race_points':next(r['points'] for r in DATA['rows'] if r['focus']),'race_rank':next(r['rank'] for r in DATA['rows'] if r['focus']),'status':'rendered_not_yet_visual_approval',
       'ranking_source':DATA['sources']['live_race'],'qualification_source':DATA['sources']['official_qualification']}
(ROOT/'render-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(proof,ensure_ascii=False))
