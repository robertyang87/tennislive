from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,html,sys,shutil
R=Path('/workspace/andreeva-finals-production');REPO=Path('/workspace/tennislive-andreeva');P=R/'production';D=R/'delivery';S=REPO/'specs/reels/andreeva-finals-2026.json';s=json.loads(S.read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();cursor=1.2;ts={}
for seg in s['segments']:
 length=seg.get('seconds',seg.get('end',0)-seg.get('start',0));ts[seg['_id']]=(cursor,cursor+length);cursor+=length
outro=4.554;total=cursor+outro
def clock(t):return f'{int(t)//60:02d}:{int(t)%60:02d}'
groups=[
(['cold-quote'],'本人冷开场','法网夺冠当天发布会整答16.7秒；按9帧量脸固定裁切。','“我还是不敢相信，自己正带着大满贯奖杯参加新闻发布会。”整答保留，不和巴黎正文重复。'),
(['card-intro','card-january','adelaide-final','card-ao','card-spring'],'一月首冠，澳网遇阻','阿德莱德完整冠军点；澳网只用准确原生赛果章；春季简短衔接。','阿德莱德0比3后连赢九局，赛季首冠。1/25澳网第四轮2-6 4-6负斯维托丽娜。春季四站硬地都未进4强。'),
(['card-linz','linz-final'],'林茨：一比六后的逆转','完整冠军点与真实反应，保留现场完整夺冠解说及“整个星期的努力”。','1-6 6-4 6-3战胜波塔波娃，赛季第二冠。'),
(['card-madrid','madrid-final'],'马德里：冠军还差一步','完整终局赛点及科斯秋克真实夺冠反应，不误作安德烈耶娃的情绪。','3-6 5-7收获亚军，转向巴黎。'),
(['card-rg','rg-final'],'巴黎：首次成为大满贯冠军','从同分准备、发球到完整冠军点、跪坐及握手；真实英语解说双语，法语背景原声保留。','罗马8强后，法网半决赛战胜科斯秋克；决赛6-3 6-2战胜赫瓦林斯卡，本季第三冠。'),
(['card-grass','wimbledon-r2'],'温网：先赢一盘仍出局','新核官方88秒源，完整同分准备/发球/终局/真实反应；主解说完整句。','6-4 5-7 4-6负克雷吉茨科娃，止步第二轮。'),
(['card-us','us-qf'],'美网：两个赛点的遗憾','完整长回合终局与真实结果反应；不凭模板添加裁判宣告。','6-2 6-7(7) 2-6被高芙逆转，止步8强；第二盘两个赛点未兑现。'),
(['card-asia','card-beijing','beijing-final'],'亚洲：先拿门票，再争冠军','10/9正式资格在前，10/11北京完整终局在后；单站积分只叠真实视频。','首次取得单打年终资格；北京是今年第五场决赛，5-7 4-6负郑钦文收获亚军。'),
(['card-ending'],'下一站年终','简洁结尾与标准片尾；不预写未来结果。','北京后首次升到世界第3；因赛程调整退出武汉，下一站年终。你期待她走到哪一步？')]
rows=[]
for ids,title,visual,story in groups:
 lo=ts[ids[0]][0];hi=ts[ids[-1]][1]+(outro if ids[-1]=='card-ending'else 0);rows.append(dict(start=lo,end=hi,time=clock(lo)+'–'+clock(hi),chapter=title,visual=visual,narrative=story))
pdf=D/'安德烈耶娃2026年终之路_五分钟提纲.pdf';png=pdf.with_suffix('.png');hist=D/'history';hist.mkdir(exist_ok=True)
old=D/'first-delivery-evidence.json'
if old.exists():
 prev=json.loads(old.read_text())
 for k,file in [('pdf',pdf),('preview',png)]:
  target=hist/('v1-'+file.name)
  if file.exists()and not target.exists():shutil.copy2(file,target)
  if target.exists()and sha(target)==prev.get(k+'_sha256'):prev[k]=str(target)
 old.write_text(json.dumps(prev,ensure_ascii=False,indent=2)+'\n')
body=''.join('<tr>'+''.join('<td>'+html.escape(r[k])+'</td>'for k in ['time','chapter','visual','narrative'])+'</tr>'for r in rows)
page='''<!doctype html><meta charset="utf-8"><style>@page{size:A4 landscape;margin:9mm}*{box-sizing:border-box}body{font-family:"Noto Sans CJK SC",Arial,sans-serif;font-size:10px;line-height:1.4;color:#17324c;margin:0}h1{font-size:22px;margin:0 0 5px}p{margin:0 0 7px}table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{border:1px solid #bacad8;padding:6px 7px;vertical-align:top}th{background:#17324c;color:#fff;text-align:left}th:nth-child(1){width:9%}th:nth-child(2){width:19%}th:nth-child(3){width:33%}th:nth-child(4){width:39%}tr:nth-child(even){background:#f0f5f8}.foot{font-size:9.4px;line-height:1.4;margin-top:7px}</style><h1>安德烈耶娃2026年终之路｜实际排稿约4分33秒</h1><p><b>8站重点：四大满贯＋阿德莱德、林茨两冠＋马德里、北京两站亚军。7个完整终局赛点＋澳网准确事实章，无额外回合。</b><br>主线：19岁首夺大满贯，也会先赢一盘后失利、错失赛点。资格先到，北京决赛随后。普通巡回赛仅简短交代，全季19站另附完整逐场工作簿。</p><table><tr><th>实际时段</th><th>章节</th><th>画面与原声</th><th>叙事事实</th></tr>'''+body+'''</table><p class="foot"><b>时长依据：</b>当前20段；12段旁白实际整句合成、排入71.72秒，7个完整终局＋本人整答按真实源窗排入195.83秒，正文267.55秒；加封面1.20秒、实际片尾4.554秒，共273.304秒。原生预览及成片仍需验收，此页不冒充最终成片QC。</p><p class="foot"><b>事实边界：</b>19站66场实打50胜16负；14轮空、1次对手W/O另列，零RET。3冠5次决赛。10/9是WTA正式公布首次<b>单打</b>年终资格日，她曾参加2025双打年终；不能写成首次参加任何年终。武汉退出是调整赛程，不写成伤病或实打负场。官方Race6306与19站积分总和6372差66仍未证实原因。</p><p class="foot"><b>呈现：</b>1080×1440铺满；比赛固定球场中心，讲话按本次9帧测得人物中心。右上单站所得积分＋赛事完整信息仅放真实视频，不放章节卡。澳网赛果章不插不完整比赛画面，不向观众解释制作缺口。未发布、未正式render。</p>'''
hfile=P/'outline-current.html';hfile.write_text(page);sys.path[:0]=[str(REPO/'tools'),str(REPO/'src')];from render_stat_card import _launch_browser
from playwright.sync_api import sync_playwright
import fitz
with sync_playwright()as pw:
 b=_launch_browser(pw);t=b.new_page();t.goto(hfile.as_uri());t.evaluate('document.fonts.ready');t.pdf(path=str(pdf),print_background=True,prefer_css_page_size=True);b.close()
f=fitz.open(pdf);assert len(f)==1;f[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(png)
ev={'schema':'andreeva.actual-current-outline.v2','created_utc':datetime.now(timezone.utc).isoformat(),'spec':str(S),'spec_sha256':sha(S),'seconds':total,'matchpoints':7,'ao':'native factual chapter only','extras':0,'actual_source_windows':8,'foreground_cues':25,'rows':rows,'pdf':str(pdf),'pdf_sha256':sha(pdf),'png':str(png),'png_sha256':sha(png),'pages':1,'pdf_proof_actually_viewed':False,'formal_render_dispatched':False,'publication_approved':False,'outline_review':s['_outline_review']};(P/'outline-current.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n');print(pdf);print(png);print(total)
repo=REPO/'research/andreeva-finals-2026';shutil.copy2(pdf,repo/pdf.name);shutil.copy2(P/'outline-current.json',repo/'outline-current.json');(repo/'outline.md').write_text('# 安德烈耶娃2026年终之路\n\n当前约4分33秒，20段，7完整终局赛点＋澳网准确事实章。8站重点，普通站简短交代，全季19站逐场工作簿保留。\n\n'+ '\n\n'.join('**'+x['time']+' '+x['chapter']+'**\n\n'+x['visual']+' '+x['narrative']for x in rows)+'\n\n10月9日资格在10月11日北京决赛之前。非正式render/最终成片QC授权。\n')
