#!/usr/bin/env python3
"""Use the same native explainer template as wawrinka-wildcard (August 27).

No alternate card compositor or CSS: all cards use explainer._slide_html, exactly as wawrinka-wildcard.
Requires repository assets, Playwright Chromium and the normal tennislive TTS deps.
"""
from pathlib import Path
import argparse, json, subprocess, sys, html, re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca()
from tennislive.video import explainer as E
E._ASS_FONT='Noto Sans SC'
ASSETS=ROOT/'assets/explainer/zheng-wildcards'

def diagram(c, i):
    # Bespoke evidence and explanatory graphics in the unchanged native SVG slot.
    lime='#c6f65a'; white='#f2faf5'; muted='#a9c8b8'; blue='#75ceef'
    def txt(x,y,t,size=28,color=white,anchor='start'):
        return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="700" fill="{color}" text-anchor="{anchor}">{html.escape(str(t))}</text>'
    def box(x,y,w,h,fill='#163e30',stroke='none',rx=20):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    def photo(path,x,y,w,h):
        return f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><image href="{E._data_uri(ROOT/path)}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/></svg>'
    def arrow(x,y,w=110):
        return f'<path d="M{x} {y}h{w}m-15 -12 15 12-15 12" fill="none" stroke="{lime}" stroke-width="5"/>'
    def ticket(x,y,w,h,label,num,status):
        return box(x,y,w,h,'#e9f3d9')+f'<path d="M{x+20} {y+h-65}h{w-40}" stroke="#537753" stroke-dasharray="5 6"/>'+txt(x+24,y+48,label,29,'#173c2a')+txt(x+w/2,y+h/2+24,num,80,'#173c2a','middle')+txt(x+w/2,y+h-25,status,23,'#173c2a','middle')
    v=''
    if i==1:
        for x,venue,name,n in [(25,'beijing-diamond-court.jpg','中网 · 96签',8),(465,'wuhan-optics-valley-centre-court.jpg','武网 · 56签',4)]:
            v+=photo('assets/venues/'+venue,x,20,410,235)+box(x,255,410,130)+txt(x+24,302,name)+txt(x+24,354,f'正赛外卡 {n} 张',38,lime)
        v+=box(25,430,850,110,'#244936')+txt(65,475,'赛事的发卡数',28)+arrow(330,483,140)+txt(530,478,'个人接卡上限',28,lime)+txt(530,520,'还要另算一本账',23,muted)
    elif i==2:
        v+=txt(30,55,'年度单打外卡总数',30)+txt(870,68,'≤ 6',68,lime,'end')
        for j in range(6):
            x=30+j*144;v+=box(x,110,120,195,'#c6f65a' if j<3 else '#294b3d')+txt(x+60,185,'WC',34,'#173c2a' if j<3 else muted,'middle')+txt(x+60,254,j+1,38,'#173c2a' if j<3 else muted,'middle')
        v+=f'<path d="M30 328v20h408v-20" stroke="{lime}" stroke-width="4" fill="none"/>'+txt(234,395,'其中正赛 ≤ 3',39,lime,'middle')+txt(35,468,'正赛与资格赛合计计算',30)+txt(35,521,'WTA 1000 / 500 / 250 · 大满贯不计入',25,muted)
    elif i==3:
        for j,(name,state,venue) in enumerate([('巴特洪堡','已持卡出场','badhomburg-centre-court.jpg'),('华盛顿','已持卡出场','washington-fitzgerald-tennis-center.jpg'),('中网','获卡 · 待出场','beijing-diamond-court.jpg')]):
            x=20+j*293;v+=photo('assets/venues/'+venue,x,15,273,145)+ticket(x,177,273,310,name,str(j+1),state)
        v+=txt(450,551,'首场前退出，可不计入使用次数',29,muted,'middle')
    elif i==4:
        v+=f'<circle cx="146" cy="220" r="87" fill="#d9ba69"/><path d="M90 136 55 30h65l28 99 28-99h65l-39 109" fill="#c45f65"/>'+txt(146,246,'金',62,'#493918','middle')+txt(146,357,'奥运冠军',33,lime,'middle')+txt(146,403,'不自动豁免',25,muted,'middle')
        for y,n,t in [(45,'10','当年进过世界前十'),(218,'GS','大满贯单打冠军'),(391,'WTA','总决赛单打冠军')]:
            v+=box(300,y,575,145)+txt(370,y+83,n,45,lime,'middle')+txt(440,y+82,t,29)
    elif i==5:
        for x,name,date,desc in [(20,'中网报名截止','此前已形成名单','美网涨分不能倒改'),(475,'武网报名截止','美网之后','新一期正式排名可用')]:
            v+=box(x,90,405,390,'#edf4df')+box(x,90,405,85,'#76964a')+txt(x+202,145,name,32,'#fff','middle')+txt(x+202,275,date,32,'#153b2a','middle')+txt(x+202,407,desc,27,'#36583d','middle')
        v+=txt(450,40,'同一份美网成绩 · 两道截止线',32,lime,'middle')+arrow(393,330,110)+txt(450,554,'入围看截止排名，不看今天的即时排名',30,muted,'middle')
    elif i==6:
        v+=box(25,30,385,460,'#eef4df')+box(25,30,385,80,'#76964a')+txt(217,85,'SEPTEMBER 2026',27,'#fff','middle')+txt(217,290,'14',160,'#173d2b','middle')+txt(217,360,'纽约 17:00',37,'#173d2b','middle')+txt(217,440,'北京时间 9/15 05:00',24,'#466447','middle')
        v+=arrow(430,250,85)+txt(700,175,'4 周',75,lime,'middle')+txt(700,300,'10月12日',45,white,'middle')+txt(700,360,'武网正赛开始',30,muted,'middle')+txt(450,550,'按通则推算 · 如无 WTA 专项调整',27,muted,'middle')
    elif i==7:
        v+=photo('assets/venues/wuhan-optics-valley-centre-court.jpg',20,15,860,280)
        for x,n,t in [(20,'01','达到直入条件'),(320,'02','自动列入名单'),(620,'03','适用参赛义务')]:
            v+=box(x,325,260,150)+txt(x+24,377,n,34,lime)+txt(x+24,436,t,27)
        v+=txt(450,552,'“强制”不等于排名不够也保送',34,lime,'middle')
    elif i==8:
        colors=[lime]*43+[blue]*8+['#eab8bc']*4+['#e7c36d']
        v+=txt(30,45,'56 个正赛席位',37)+txt(870,45,'以2025官方构成为例',23,muted,'end')
        for j,col in enumerate(colors):v+=box(32+(j%8)*73,95+(j//8)*56,61,43,col,rx=7)
        for y,col,t in [(145,lime,'43 直接入围'),(235,blue,'8 资格赛'),(325,'#eab8bc','4 外卡'),(415,'#e7c36d','1 特别豁免')]:v+=box(648,y-25,20,20,col,rx=4)+txt(683,y,t,27)
        v+=txt(450,554,'总签位 ≠ 普通排名的直入线',33,lime,'middle')
    elif i==9:
        uri=E._data_uri(ASSETS/'wuhan-2025-entry.jpg')
        v+=txt(30,58,'2025 · 首批接受名单',35)+txt(870,58,'截止排名 9月8日',25,muted,'end')
        v+=f'<svg x="20" y="100" width="565" height="450" viewBox="20 2300 560 390"><image href="{uri}" width="600" height="2837"/></svg>'
        v+=txt(735,262,'41',132,lime,'middle')+txt(735,326,'达尼洛维奇',29,white,'middle')+txt(735,390,'普通排名末位',24,muted,'middle')+txt(735,478,'今年仍须看新名单',22,muted,'middle')
    elif i==11:
        v+=ticket(20,180,225,240,'个人剩余额度','1','正赛外卡')
        v+=arrow(263,290,80)
        for y,head,tail,col in [(75,'武网凭排名入围','不占外卡 → 中网可用',lime),(325,'两站都需要外卡','才会遇到额度取舍',blue)]:
            v+=box(380,y,495,175)+txt(415,y+65,head,32,col)+txt(415,y+123,tail,29)
        v+=txt(450,560,'“原计划留武汉”尚无团队直接证实',28,muted,'middle')
    return '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">'+v+'</svg>'

def evidence(filename):
    # Show the supplied account header and complete post text; omit app chrome below.
    uri=E._data_uri(ASSETS/filename)
    return f'<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg"><defs><clipPath id="post"><rect width="900" height="600" rx="14"/></clipPath></defs><image href="{uri}" width="900" height="1436" preserveAspectRatio="xMinYMin meet" clip-path="url(#post)"/></svg>'

def segments(data):
    out=[]
    for i,c in enumerate(data['cards'][:-1]):
        title=['中网外卡来了，武网怎么办？','赛事发卡，球员还要算额度','全年六次，正赛最多三次','已用两次，中网将是第三次','奥运冠军，也要对照豁免条款','同一份成绩，两道截止线','美网成绩，赶得上武网报名','武网如今也是强制参赛','五十六签，不等于前五十六','去年直入线，卡在第四十一','今年的正赛名单，尚未公布','兼顾两站，关键看武网入围','八强不是门槛，胜利增加选择'][i]
        label=c['tag'].split('/')[-1].strip()
        if i==0:
            out.append(E.ExplainerSegment(kind='cover',label='网球有故事',title='中网外卡来了，武网怎么办？',narration=c['narration'],image='assets/reel/zheng-us-open-2026-r4.jpg',credit='AP / Seth Wenig · 美网第四轮'))
            out.append(E.ExplainerSegment(kind='announcement',label='官宣',title='中网确认，她将出战正赛',narration='中网官宣，郑钦文确认参加今年正赛。她在报名截止时的排名不足以直接入围，这次拿到的是正赛外卡。北京的门打开了，可她今年常规正赛外卡只剩最后一次，武汉怎么办？',diagram=evidence('china-open-announcement.jpg'),credit='用户提供 · 中网ChinaOpen微博截图',points=('截止时排名不足以直接入围','本次凭正赛外卡出战中网')))
            out.append(E.ExplainerSegment(kind='poster',label='北京之约',title='北京确定了，武汉怎么进？',narration='北京这一站已经明确。接下来的问题是：她还剩多少次接正赛外卡的额度，武汉又能不能靠排名进去？先把规则里的两本账分开。',image='assets/explainer/zheng-wildcards/china-open-poster.jpg',credit='用户提供 · 2026中网郑钦文参赛海报'))
        elif i in (10,12):
            img='assets/venues/wuhan-optics-valley-centre-court.jpg' if i==10 else 'assets/reel/zheng-us-open-2026-r4.jpg'
            pts=('截至9月8日：官方球员名单暂不可用','能否直入，等待截止排名与接受名单') if i==10 else ('八强不是中网外卡的规则门槛','胜利提升排名，也增加参赛选择')
            out.append(E.ExplainerSegment(kind='photo',label=label,title=title,narration=c['narration'],image=img,credit=c['source'] if i==10 else 'AP / Seth Wenig · 美网第四轮',points=pts))
        else:
            out.append(E.ExplainerSegment(kind='rule',label=label,title=title,narration=c['narration'],diagram=diagram(c,i),credit=c['source'],points=()))
    return out

def runner(cmd,**kw):
    if cmd[0]=='ffmpeg':
        cmd=list(cmd)
        if '-preset' in cmd:cmd[cmd.index('-preset')+1]='ultrafast'
        cmd[1:1]=['-threads','2','-filter_complex_threads','1']
        if '-filter_complex' in cmd:
            j=cmd.index('-filter_complex')+1
            cmd[j]=re.sub(r"subtitles='([^']+)'",lambda m:m.group(0)+":fontsdir='"+str(ROOT/'assets/fonts')+"'",cmd[j])
        cmd[-1:-1]=['-threads','2']
    return subprocess.run(cmd,**kw)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--cards-only',action='store_true');ap.add_argument('--assemble-only',action='store_true');a=ap.parse_args()
    out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'specs/explainers/zheng-china-wuhan-wildcards.json').read_text())
    beats=segments(data)
    # A shared page supports single-process Chromium without changing the template.
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    slides=[]
    if a.assemble_only:
        slides=[out/f'slide_{i:02d}.jpg' for i in range(len(beats))]
    else:
        with sync_playwright() as pw:
            browser=launch_chromium(pw)
            page=browser.new_page(viewport={'width':E.W,'height':E.H},device_scale_factor=2)
            for i,beat in enumerate(beats):
                html_path=out/f'slide_{i:02d}.html'
                html_path.write_text(E._slide_html(i,beat,topic='郑钦文的中国赛季',column='网球有故事'))
                page.goto(html_path.as_uri())
                page.wait_for_function("document.fonts.status === 'loaded' && Array.from(document.images).every(i=>i.complete)")
                path=out/f'slide_{i:02d}.jpg'
                page.screenshot(path=str(path),type='jpeg',quality=86)
                slides.append(path)
                print('Native card',i+1,flush=True)
            browser.close()
    from PIL import Image
    sheet=Image.new('RGB',(1080,360*((len(slides)+3)//4)),'#061c14')
    for i,p in enumerate(slides):sheet.paste(Image.open(p).resize((270,360)),((i%4)*270,(i//4)*360))
    sheet.save(out/'contact-sheet.jpg')
    (out/'narration.json').write_text(json.dumps([{'title':s.title,'narration':s.narration} for s in beats],ensure_ascii=False,indent=2))
    if a.cards_only:return
    audios=E.synthesize_narration(beats,out,rate='+22%')
    outro=ROOT/'assets/brand/outro_master.mp4'
    if not outro.is_file():raise FileNotFoundError('Native brand outro is required')
    E.assemble_explainer_video(slides,audios,out/'zheng-wildcards-template.mp4',captions=[s.narration for s in beats],outro=outro,runner=runner)
    print(out/'zheng-wildcards-template.mp4',flush=True)
if __name__=='__main__':main()
