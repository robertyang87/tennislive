from pathlib import Path
import json, html, sys
from playwright.sync_api import sync_playwright
import fitz

ROOT=Path('/workspace/pegula-finals-production')
REPO=Path('/workspace/tennislive')
sys.path.insert(0,str(REPO/'tools'))
from render_stat_card import _launch_browser
spec=json.loads((REPO/'specs/reels/pegula-finals-2026.json').read_text())
assert len(spec['segments'])==41 and not spec['_render_blockers']
groups=[
 ('冷开场与一月',0,5,'本人自嘲两座辛辛那提亚军奖杯；澳网首盘盘点＋完整赛点','明确两次亚军分属2024/2026；布里斯班与澳网4强'),
 ('迪拜首冠',5,9,'首盘盘点＋冠军赛点；本人颁奖发言','先逆转阿尼西莫娃，再击败斯维托丽娜'),
 ('阳光双赛',9,12,'迈阿密首盘盘点＋完整赛点','印第安维尔斯与迈阿密均止步8强，三次负于莱巴金娜'),
 ('查尔斯顿',12,15,'长回合精彩球＋冠军赛点','四场三盘进入决赛，本季第二冠'),
 ('红土低谷与柏林',15,19,'柏林第二盘抢七盘点＋完整赛点','法网首轮出局；柏林决胜盘6比0，最终亚军'),
 ('温网与华盛顿',19,22,'伊埃拉第二盘破发盘点＋完整赛点','温网8强；华盛顿先赢一盘仍失利'),
 ('辛辛那提',22,27,'半决赛救破发点＋赛点；决赛精彩球＋赛点','连续三场三盘进入赛季第五次决赛，再负高芙'),
 ('美网逆转',27,32,'救破发点＋真实完整赛点；反应、本人采访','逆转纳瓦罗，谈消极念头与自我调整'),
 ('美网半决赛',32,36,'救破发点＋真实完整赛点；赛后完整解说','负于萨巴伦卡；本季大满贯最好成绩4强'),
 ('亚洲赛季',36,39,'武汉第三个赛点被救＋全场最后赛点','退出新加坡、北京；武汉三个赛点未兑现遭逆转'),
 ('年终门票与展望',39,41,'WTA官方资格海报，结尾不叠信息卡','10月14日正式官宣连续第五年入围；此后退出宁波'),
]
offsets=[];cur=1.2
for s in spec['segments']:
 offsets.append(cur);cur+=s.get('seconds',s.get('end',0)-s.get('start',0))
offsets.append(cur)
def stamp(t):return f'{int(t)//60:02d}:{int(t)%60:02d}'
rows=[]
for title,a,b,visual,narr in groups:
 rows.append([f'{stamp(offsets[a])}–{stamp(offsets[b])}',title,visual,narr])
body=''.join('<tr>'+''.join('<td>'+html.escape(t)+'</td>' for t in r)+'</tr>' for r in rows)
page='''<!doctype html><meta charset="utf-8"><style>@page{size:A4 landscape;margin:9mm}*{box-sizing:border-box}body{font-family:"Noto Sans CJK SC",Arial,sans-serif;font-size:10.5px;line-height:1.4;color:#16324f;margin:0}h1{font-size:22px;margin:0 0 6px}p{margin:0 0 9px}table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{border:1px solid #bdcbd9;padding:6px 7px;vertical-align:top}th{background:#16324f;color:white;text-align:left}th:nth-child(1){width:10%}th:nth-child(2){width:15%}th:nth-child(3){width:37%}th:nth-child(4){width:38%}tr:nth-child(even){background:#f0f5fa}.foot{font-size:9.5px;margin-top:8px}</style>'''
page+=f'<h1>佩古拉2026年终之路｜完整回合版执行提纲</h1><p>按最新要求更新：展示的11场比赛各含一个完整终局赛点，再加一个完整精彩球或关键转折点，合计22个回合。<br>主体约{stamp(cur)}，另含原生片尾；预计总片长约10分45秒。时长以正式渲染为准，原有整句旁白保留。</p>'
page+='<table><thead><tr><th>预计时段</th><th>章节</th><th>真实画面与原声</th><th>旁白坐标与结果</th></tr></thead><tbody>'+body+'</tbody></table>'
page+='<p class="foot">完整性：从发球准备、发球、整个回合到确定结果与实际反应；精彩球/神仙球/关键转折点合计只选一个额外回合。美网两场补真实赛点，原救破发点各保留为唯一额外回合。采访、赛后反应不增加比赛回合。</p>'
page+='<p class="foot">画面：1080×1440铺满；比赛固定球场中心，采访按实测人物中心固定裁切。最新透明右上信息卡仅叠真实视频，不上转场卡；轮次用1/4决赛、1/8决赛；最长15秒且不跨片段。原声完整语义配英中字幕，自然整句旁白，无烧录背景音乐。</p>'
page+='<p class="foot">事实边界：全季资料16站、64场计战绩，50胜14负，12次轮空，2冠、3次亚军。10月14日采用官方公开确认日期，不宣称最早数学锁定日。不预写东京或年终赛果；固定竖裁可能限制远端横向跑动的可见范围，内部审片逐段记录。</p>'
dest=ROOT/'editorial/execution-outline-v2.html';dest.write_text(page)
pdf=ROOT/'delivery/佩古拉2026年终之路_完整回合版提纲.pdf'
with sync_playwright() as pw:
 browser=_launch_browser(pw);tab=browser.new_page();tab.goto(dest.as_uri());tab.evaluate('document.fonts.ready');tab.pdf(path=str(pdf),print_background=True,prefer_css_page_size=True);browser.close()
doc=fitz.open(pdf);assert len(doc)==1,len(doc);doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(ROOT/'editorial/execution-outline-v2-proof.png')
(ROOT/'editorial/execution-outline-v2.json').write_text(json.dumps({'rows':rows,'body_seconds':cur,'point_policy':'11 matches, each exactly 1 complete terminal match point + 1 complete extra rally','final_film_qc':False},ensure_ascii=False,indent=2)+'\n')
print(pdf)
