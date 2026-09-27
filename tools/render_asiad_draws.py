#!/usr/bin/env python3
"""Faithful redraw of the supplied 25 September 2026 draw images; no forecasts."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/asiad-2026-draws'
FONT=OUT/'NotoSansCJKsc-Regular.otf'
DISPLAY=OUT/'SmileySans-Oblique.ttf'
# Each record preserves printed source position, name, delegation, and seed.
def p(pos,original,display,country,seed=None):
    return dict(source_position=pos,original_name=original,display_name=display,country=country,seed=seed)
w=[
p(1,'Eala Alexandra','伊埃拉','PHI',1),p(2,'Bye','轮空',''),p(3,'Cheapchandej Patcharin','Cheapchandej','THA'),p(4,'Qureshi Mahin Aftab','Qureshi','PAK'),
p(5,'Yuldasheva Sevil','Yuldasheva','UZB'),p(6,'Farzami Mandegar','Farzami','IRI'),p(7,'Chogsomjav Martaa','Chogsomjav Martaa','MGL'),p(8,'Garland J.','葛蓝乔安娜','TPE',8),
p(9,'Wang Xiyu','王曦雨','CHN',4),p(10,'Junarto Anjali Kirana','Junarto','INA'),p(11,'Zhiyenbayeva Sonja','Zhiyenbayeva','KAZ'),p(12,'Karunaratne A.','Karunaratne','HKG'),
p(13,'Tursunova Anastasiya','Tursunova','TJK'),p(14,'Ku Yeonwoo','Ku Yeonwoo','KOR'),p(15,'Bista Swastika','Bista','NEP'),p(16,'Uchijima Moyuka','内岛萌夏','JPN',6),
p(17,'Sawangkaew M.','萨王凯','THA',5),p(18,'Chogsomjav Maralgoo','Chogsomjav Maralgoo','MGL'),p(19,'Shek Cheuk Ying','Shek C. Y.','HKG'),p(20,'Shubina Darya','Shubina','UZB'),
p(21,'Reinnamah M.','Reinnamah','INA'),p(22,'Yang Ya-Yi','Yang Ya-Yi','TPE'),p(23,'Suhail Ushna','Suhail','PAK'),p(24,'Putintseva Yuliya','普汀塞娃','KAZ',3),
p(25,'Sakatsume H.','坂诘姬野','JPN',7),p(26,'Madis Tennielle','Madis','PHI'),p(27,'Back Dayeon','Back Dayeon','KOR'),p(28,'Gurung Shivali','Gurung','NEP'),
p(29,'Safi Meshkatolzahra','Safi','IRI'),p(30,'Asimova Shakhzoda','Asimova','TJK'),p(31,'Bye','轮空',''),p(32,'Zhang Shuai','张帅','CHN',2)]
m=[
p(1,'Wong C.','黄泽林','HKG',1),p(3,'Al-Mashni Zaid','Al-Mashni','JOR'),p(4,'Murtaza Muzammil','Murtaza','PAK'),p(6,'Alwazer Fares','Alwazer','YEM'),p(8,'Watanuki Y.','绵贯阳介','JPN',13),
p(9,'Samrej Kasidit','Samrej','THA',12),p(11,'Khadka Pradip','Khadka','NEP'),p(14,'Rahmani Kasra','Rahmani','IRI'),p(16,'Skatov Timofei','Skatov','KAZ',5),
p(17,'Kwon Soonwoo','权纯雨','KOR',4),p(19,'Purevdorj Undrakh','Purevdorj','MGL'),p(22,'Meng Fanming','孟凡茗','CHN'),p(24,'Sultanov K.','Sultanov','UZB',14),
p(25,'Suresh Ekambaram D.','Suresh','IND',11),p(27,'Trismuwantara M.','Trismuwantara','INA'),p(30,'Rakhmatov Anvar','Rakhmatov','TJK'),p(32,'Tseng Chun-Hsin','曾俊欣','TPE',6),
p(33,'Nagal Sumit','纳加尔','IND',7),p(35,'Hong Seongchan','Hong S.','KOR'),p(38,'Amonov Somon','Amonov','TJK'),p(40,'Fomin Sergey','Fomin','UZB',9),
p(41,'Fitriadi M.','Fitriadi','INA',16),p(43,'Shoaib Muhammad','Shoaib','PAK'),p(46,'Yazdani Ali','Yazdani','IRI'),p(48,'Wu Yibing','吴易昺','CHN',3),
p(49,'Matsuoka Hayato','松冈隼','JPN',8),p(51,'Thompson Kairan Creer','Thompson','HKG'),p(54,'Alkotop Mohammad','Alkotop','JOR'),p(56,'Hsu Yu-Hsiou','许育修','TPE',10),
p(57,'Jones Maximus','Jones','THA',15),p(59,'Urnukh Zolbadar','Urnukh','MGL'),p(62,'Bastola Abhishek','Bastola','NEP'),p(64,'Shevchenko A.','舍甫琴科','KAZ',2)]
# The sole played R1 match retains both entrants, separately shown in a preliminary box.
men32=[m[0],dict(source_position=[3,4],original_name='Al-Mashni Zaid / Murtaza Muzammil winner',display_name='首轮胜者①',country='',seed=None)]+m[3:]
assert len(w)==len(men32)==32 and len(m)==33
BG='#0c1922'; TEXT='#f3f7fa'; MUTED='#9fb2bf'; LINE='#647e8f'; ACC='#c6f65a'; PANEL='#152a37'
def font(n,display=False):return ImageFont.truetype(str(DISPLAY if display else FONT),n)
def text(d,xy,s,n=28,c=TEXT,anchor=None,display=False):d.text(xy,s,font=font(n,display),fill=c,anchor=anchor)
def base(sex,part):
    im=Image.new('RGB',(1080,1440),BG);d=ImageDraw.Draw(im)
    d.rectangle((0,0,360,10),fill=ACC);d.rectangle((360,0,720,10),fill='#69b2db');d.rectangle((720,0,1080,10),fill='#f4ba63')
    text(d,(56,40),'网球时差 · 网球有故事',38,display=True)
    text(d,(56,109),'2026 爱知·名古屋亚运会',30,MUTED)
    text(d,(56,161),f'{sex}签表',57,display=True)
    text(d,(1024,180),part,30,ACC,anchor='ra')
    d.line((56,238,1024,238),fill=LINE,width=2)
    return im,d

def row(d,item,x,y,width=300,size=28):
    label=item['display_name']; seed=item['seed']; iscn=item['country']=='CHN'
    if seed:label+=f' [{seed}]'
    # All entrant names render >=28px; supplementary country codes use 18px.
    while d.textlength(label,font=font(size))>width and size>28:size-=1
    assert d.textlength(label,font=font(size))<=width,(label,width)
    if iscn:d.rounded_rectangle((x-8,y-23,x+width+3,y+24),radius=7,fill='#274133')
    text(d,(x,y),label,size,ACC if iscn else TEXT,anchor='lm')
    return x+width

def tree(d,ys,start,step,levels):
    x=start
    for _ in range(levels):
        nxt=x+step
        for a,b in zip(ys[::2],ys[1::2]):
            d.line((x,a,nxt,a,nxt,b,x,b),fill=LINE,width=2)
        ys=[(a+b)/2 for a,b in zip(ys[::2],ys[1::2])];x=nxt
    return x,ys[0]

def footer(d,sex):
    if sex=='男单':
        d.rounded_rectangle((56,1005,1024,1080),radius=10,fill=PANEL)
        text(d,(76,1008),'① 唯一需先赛的首轮：Al-Mashni（JOR）',27)
        text(d,(76,1046),'对 Murtaza（PAK）→ 胜者对黄泽林',27)
        text(d,(56,1084),'原表64槽、33人；合并31个轮空，仅为排版。',27,MUTED)
    else:
        text(d,(56,1020),'30位球员 · 32个签位 · 2个轮空',30,ACC)
        text(d,(56,1065),'[数字]为种子；空白连线不代表已晋级。',27,MUTED)
    text(d,(56,1124),'来源：9月25日原始签表｜本图为赛前落位',25,MUTED)
    text(d,(56,1162),'潜在对阵均须双方此前晋级，以实际赛果为准。',25,MUTED)

def full(sex,arr,slug):
    im,d=base(sex,'完整签表 · 可暂停查看')
    text(d,(56,258),'上半区',27,ACC);text(d,(1024,258),'下半区',27,ACC,anchor='ra')
    ys=[310+i*44 for i in range(16)]
    for i,it in enumerate(arr[:16]):row(d,it,42,ys[i],300)
    for i,it in enumerate(arr[16:]):row(d,it,750,ys[i],295)
    xl,yl=tree(d,ys,352,39,4);xr,yr=tree(d,ys,730,-39,4)
    d.line((xl,yl,xr,yr),fill=ACC,width=4)
    text(d,(540,yl-45),'决赛',28,ACC,anchor='mm')
    footer(d,sex);im.save(OUT/f'{slug}-full.png')

def half(sex,arr,slug,start):
    part='上半区' if start==0 else '下半区'
    im,d=base(sex,part+' · 分区放大')
    for x,s in [(56,'首战位置'),(480,'16强'),(660,'八强'),(835,'半决赛')]:text(d,(x,263),s,27,MUTED)
    ys=[310+i*44 for i in range(16)]
    for i,it in enumerate(arr[start:start+16]):row(d,it,56,ys[i],350,32)
    tree(d,ys,425,143,4)
    footer(d,sex)
    im.save(OUT/f'{slug}-{"upper" if start==0 else "lower"}.png')

def route(sex,player,slug,stages):
    im,d=base(sex,player+' · 晋级路线')
    text(d,(56,267),'首战已落位；后续仅为签表推演',32,ACC)
    n=len(stages); h=130 if n==5 else 164; gap=20
    for i,(rnd,opponent,note) in enumerate(stages):
        y=323+i*(h+gap)
        d.rounded_rectangle((56,y,1024,y+h),radius=15,fill=PANEL,outline=LINE,width=2)
        text(d,(82,y+8),rnd,28,ACC)
        text(d,(82,y+45),opponent,43,display=True)
        text(d,(82,y+96),note,24,MUTED)
        if i<n-1:
            for dash_y in range(y+h+2,y+h+gap-2,7):
                d.line((540,dash_y,540,min(dash_y+3,y+h+gap-2)),fill=ACC,width=3)
    text(d,(56,1078),'虚线为潜在路线，不代表已晋级。',29,ACC)
    text(d,(56,1124),'来源：9月25日原始签表｜本图为赛前落位',25,MUTED)
    text(d,(56,1162),'潜在对阵均须双方此前晋级，以实际赛果为准。',25,MUTED)
    im.save(OUT/(slug+'.png'))

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    data=dict(source_date='2026-09-25',women=dict(entrants=w,draw_slots=32,byes=2),men=dict(entrants=m,draw_slots=64,byes=31,display_slots=men32,preliminary_match=[3,4]))
    (OUT/'draw-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    for sex,arr,slug in [('女单',w,'women'),('男单',men32,'men')]:
        full(sex,arr,slug)
        for start in [0,16]:half(sex,arr,slug,start)
    print('Rendered bracket images at 1080×1440; source positions preserved in draw-data.json')

    route('男单','吴易昺','men-wu-route',[
        ('首战 · 第二轮','Yazdani Ali','吴易昺首轮轮空；本场对手已由签表确定'),
        ('16强 · 潜在','Fitriadi [16]','按种子路线；对手须先战胜Shoaib'),
        ('八强 · 潜在','纳加尔 [7]','该分区还有Fomin等球员'),
        ('半决赛 · 潜在','舍甫琴科 [2]','松冈隼等同在这一侧'),
        ('决赛 · 潜在','黄泽林 / 权纯雨等','须先赢下各自半区，才有机会相遇')])
    route('男单','黄泽林','men-wong-route',[
        ('首战 · 第二轮','Al-Mashni / Murtaza胜者','两人需先进行唯一一场非轮空首轮'),
        ('16强 · 潜在','绵贯阳介 [13]','绵贯须先过Alwazer这一关'),
        ('八强 · 潜在','Skatov [5]','该分区还有Samrej等球员'),
        ('半决赛 · 潜在','权纯雨 / 曾俊欣等','孟凡茗也在这四分之一区'),
        ('决赛 · 潜在','吴易昺 / 舍甫琴科等','吴黄重逢最早只能发生在决赛')])
    route('女单','王曦雨','women-wang-route',[
        ('首轮 · 已落位','Junarto Anjali Kirana','9月25日抽签落位'),
        ('16强 · 潜在','Zhiyenbayeva / Karunaratne','两人首轮交手，胜者进入这一位置'),
        ('八强 · 潜在','内岛萌夏 [6]','按种子路线推演'),
        ('半决赛 · 潜在','伊埃拉 [1]','葛蓝乔安娜等球员也在另一四分之一区'),
        ('决赛 · 潜在','张帅 / 普汀塞娃等','中国金花分处两半区，可在决赛相遇')])
    route('女单','张帅','women-zhang-route',[
        ('首战 · 16强','Safi / Asimova胜者','张帅首轮轮空'),
        ('八强 · 潜在','坂诘姬野 [7]','按种子路线推演'),
        ('半决赛 · 潜在','普汀塞娃 [3] / 萨王凯 [5]','两人同在另一个四分之一区'),
        ('决赛 · 潜在','伊埃拉 / 王曦雨等','须先赢下各自半区，才有机会相遇')])
    for slug,label in [('women-wang-archive','资料画面｜2026 辛辛那提'),('women-zhang-archive','资料画面｜2026 比利·简·金杯'),('women-eala-archive','资料画面｜2026 华盛顿')]:
        im=Image.new('RGBA',(750,74),(0,0,0,0));d=ImageDraw.Draw(im)
        d.rounded_rectangle((0,0,749,73),radius=10,fill=(12,25,34,220))
        text(d,(22,37),label,34,anchor='lm')
        im.save(OUT/(slug+'.png'))

    for source in sorted(OUT.glob('*.png')):
        im=Image.open(source)
        if im.size==(1080,1440):
            im.crop((0,0,1080,1200)).save(source.with_name(source.stem+'-video.png'))
    print('Rendered 10 video cards at 1080×1200; original full-height images retained')
