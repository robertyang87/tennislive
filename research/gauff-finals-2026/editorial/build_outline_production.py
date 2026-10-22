from pathlib import Path
import json,hashlib,html,sys,datetime
import fitz
from playwright.sync_api import sync_playwright
R=Path('/workspace/gauff-finals-production');REPO=Path('/workspace/tennislive-gauff');sys.path.insert(0,str(REPO/'tools'));from render_stat_card import _launch_browser
facts=json.loads((R/'facts/canonical.json').read_text());focus_ids={901,902,709,903,904,1017,905};focus=[e for e in facts['events']if e['event_id']in focus_ids];brief=[e for e in facts['events']if e['event_id']not in focus_ids];assert len(focus)==7 and len(brief)==9
spec=json.loads((REPO/'specs/reels/gauff-finals-2026.json').read_text());narr=[{'id':x['_id'],'seconds':x['seconds'],'text':x['narration']}for x in spec['segments']if x.get('narration')]
groups=[('同一站，一年之后',22,'本人辛辛那提夺冠致辞的一年改变短句作冷开场；接年度主线。','去年停车场落泪与今年捧杯的真实对照，不借别场采访。'),('澳网：开局遇挫',28,'澳网1/4决赛完整赛点、确定结果与反应。','澳网8强＋430分，1比6、2比6负斯维托丽娜；联合杯单打3胜1负略提。'),('春季：第一次走到决赛',36,'迈阿密决赛完整赛点与整句解说；其余站只用短句衔接。','迈阿密亚军＋650分；多哈首战失利、迪拜4强、印第安维尔斯赛中退赛略提。'),('罗马到巴黎：接近与失落',56,'罗马决赛、法网第三轮各保留一个完整终局赛点与真实反应。','罗马亚军＋650分；法网第三轮＋130分，先赢一盘被波塔波娃逆转；斯图加特8强、马德里第四轮略提。'),('温网：拼到决胜盘抢十',35,'温网半决赛完整赛点及反应，保留服务高芙主线的完整原声。','温网4强＋780分；输给穆霍娃。柏林首战失利略提，不另加对佩古拉1/4决赛比赛视频。'),('辛辛那提：终于等到首冠',39,'决赛对佩古拉的完整冠军点与庆祝；由真实原声接住一年变化。','冠军＋1000分。首盘失利后连赢十二盘；多伦多4强略提。'),('美网：不留遗憾地拼到底',65,'对安德烈耶娃、莱巴金娜各一个完整终局赛点；同次QF本人不留遗憾的完整短句；接真实赛后整段精彩评论，不额外加球。','美网4强＋780分。QF救两赛点逆转，SF先赢一盘后落败；采访不冒充半决赛失利后发言。'),('北京之后，年终仍在等她',25,'简短旁白交代北京与武汉退赛；WTA资格文章中的高芙本人实拍，结尾一问与片尾。','北京第四轮略提；10月14日官方公布连续第五年入围。未知的未来赛事结果不预写。')]
ranges=[(0,2),(2,4),(4,6),(6,10),(10,12),(12,14),(14,20),(20,22)]
computed=[]
for j,(a,b)in enumerate(ranges):
 secs=sum(x.get('seconds',x.get('end',0)-x.get('start',0))for x in spec['segments'][a:b])+(1.2 if j==0 else 4.554 if j==7 else 0)
 z=list(groups[j]);z[1]=secs;computed.append(tuple(z))
groups=computed;cur=0;rows=[]
def stamp(t):return f'{int(t)//60:02d}:{int(t)%60:02d}'
for title,seconds,visual,story in groups:rows.append({'time':f'{stamp(cur)}–{stamp(cur+seconds)}','start':cur,'end':cur+seconds,'title':title,'visual':visual,'story':story});cur+=seconds
assert 270<=cur<=320
body=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>'for x in [r['time'],r['title'],r['visual'],r['story']])+'</tr>'for r in rows)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>@page{size:A4 landscape;margin:9mm}*{box-sizing:border-box}body{font-family:"Noto Sans CJK SC",Arial,sans-serif;font-size:11px;line-height:1.48;color:#17324c;margin:0}h1{font-size:23px;margin:0 0 6px}.lead{margin:0 0 10px;font-size:11.5px}.tag{font-weight:bold;color:#087e79}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #bdcbd9;padding:7px 8px;vertical-align:top}th{background:#17324c;color:white;text-align:left}th:nth-child(1){width:9%}th:nth-child(2){width:19%}th:nth-child(3){width:35%}th:nth-child(4){width:37%}tr:nth-child(even){background:#f0f5f8}.foot{font-size:10px;margin:8px 0 0}.small{font-size:9.3px;color:#4a6074}</style><body>'''
page+='<h1>高芙2026年终之路｜约5分钟制作提纲</h1><p class="lead"><span class="tag">7站重点 · 8场比赛完整赛点 · 其余9站简短带过</span>　预计约'+str(round(cur)//60)+'分'+str(round(cur)%60).zfill(2)+'秒（实际选窗与整句配音已量，含4.554秒实测片尾；成片待编码复核）。<br>主线：从去年同地落泪，到今年辛辛那提捧杯；她的这一年，有接近、有失利，也有继续相信自己的时刻。</p>'
page+='<table><thead><tr><th>预计时段</th><th>章节</th><th>真实画面与原声</th><th>时间线与赛事最终积分</th></tr></thead><tbody>'+body+'</tbody></table>'
page+='<p class="foot"><b>重点积分：</b>澳网430｜迈阿密650｜罗马650｜法网130｜温网780｜辛辛那提1000｜美网780。重点合计4420分，其余9站1354分，全年合计5774分。每站只计一次；同站出现两场比赛不重复加分。</p>'
page+='<p class="foot"><b>完整回合：</b>8场真实比赛均保留发球准备、发球、整个回合、确定结果及真实反应。额外精彩球或关键点按需要最多1个／场，本片不额外加球。美网救2赛点由官方战报与赛季事实交代，不把第2盘4比3时的长回合冒称赛点。采访独立计，不增加比赛回合。</p>'
page+='<p class="foot"><b>呈现：</b>1080×1440裁切铺满；比赛固定球场中心，采访实测人物中心。真实精彩原声整句保留并配英中字幕；赛事信息卡只叠真实比赛／本人视频，轮次用1/4决赛、1/8决赛，不叠章节静态卡。</p>'
page+='<p class="foot small">全季已核：16站、62场实际单打，47胜15负；11次轮空、1次对手W/O另列，本人印第安维尔斯RET仍计负场。官方10月19日Race第5、5774分；10月14日为官方公开确认资格日，不冒称最早数学锁定时刻。此页为已授权系列的新制作提纲，已取得8场完整终局与真实原声证据；此页并非最终成片QC，也不编造用户逐字批准。</p></body></html>'
hp=R/'editorial/outline.html';hp.write_text(page);pdf=R/'delivery/高芙2026年终之路_五分钟提纲.pdf';png=R/'delivery/高芙2026年终之路_五分钟提纲_样张.png'
with sync_playwright()as pw:
 b=_launch_browser(pw);tab=b.new_page();tab.goto(hp.as_uri());tab.evaluate('document.fonts.ready');tab.pdf(path=str(pdf),print_background=True,prefer_css_page_size=True);b.close()
doc=fitz.open(pdf);assert len(doc)==1;doc[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(png)
out={'schema':'gauff-finals-editorial-outline/v1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'player':'Coco Gauff','season':2026,'angle':'从去年同地落泪，到今年辛辛那提捧杯；年终之路由真实高光和低谷串起。','planned_seconds':cur,'target_seconds':[270,320],'scope':'fourGrandSlams+onlysinglestitleCincinnati+Miami/RomeRU;9otherplayedstationsbrief','focus_events':focus,'brief_events':brief,'shown_match_count':8,'required_matchpoint_count':8,'optional_extra_count':0,'own_quote_candidates':['Cincy actual144.42–148.80 fullwhatdifference/thankHim; parkinglot sentence accuratelyparaphrased bynarration','USQF actual48.25–52.52 fullleavecourtwithoutregrets sentence'],'narration_plan':narr,'rows':rows,'outline_approval_state':'series_production_authorized_initial_outline_actually_shown_by_root_production_revision_requires_no_fabricated_user_quote','initial_outline_actually_shown_by_root':True,'spec_sha256_at_generation':hashlib.sha256((REPO/'specs/reels/gauff-finals-2026.json').read_bytes()).hexdigest(),'formal_render_authorized':False,'final_film_qc':False,'pdf':str(pdf),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'proof':str(png),'proof_sha256':hashlib.sha256(png.read_bytes()).hexdigest(),'facts_sha256':hashlib.sha256((R/'facts/canonical.json').read_bytes()).hexdigest()}
(R/'editorial/outline.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(pdf);print('planned',cur,'pages',len(doc));print(out['pdf_sha256'])
