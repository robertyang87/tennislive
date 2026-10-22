"""Build the authorized eight-focus-event outline; read shared spec without editing it."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, html, sys
from playwright.sync_api import sync_playwright
import fitz

ROOT = Path('/workspace/pegula-finals-production')
REPO = Path('/workspace/tennislive')
OUT = ROOT / 'revision-v3-scope'
sys.path.insert(0, str(REPO / 'tools'))
from render_stat_card import _launch_browser

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(t):
    seconds = int(t + .000001)
    return f'{seconds // 60:02d}:{seconds % 60:02d}'

spec_path = REPO / 'specs/reels/pegula-finals-2026.json'
spec_bytes = spec_path.read_bytes()
spec = json.loads(spec_bytes)
assert len(spec['segments']) == 31 and not spec.get('_render_blockers')
audit_path = OUT / 'editorial-scope-fact-audit.json'
audit = json.loads(audit_path.read_text())
points = {row['event']: row['points'] for row in audit['scope_partition']['focus_events']}
assert points == {'澳网':780, '迪拜':1000, '查尔斯顿':500, '法网':10, '柏林':325, '温网':430, '辛辛那提':650, '美网':780}
assert sum(points.values()) == 4475
cover_seconds = 1.2
native_outro_seconds = 10.0
clock = cover_seconds
offsets = []
for seg in spec['segments']:
    offsets.append(clock)
    clock += seg.get('seconds', seg.get('end', 0) - seg.get('start', 0))
offsets.append(clock)
total = clock + native_outro_seconds
assert total > 0, total
approx_seconds = round(total)
approx_duration = f'{approx_seconds // 60}分{approx_seconds % 60:02d}秒'

groups = [
    ('冷开场与澳网', 0, 4, '辛辛那提本人亚军感言开场；澳网半决赛完整赛点与反应。', '澳网4强＋780分。连胜凯斯、阿尼西莫娃后负莱巴金娜；布里斯班4强一句带过。'),
    ('迪拜首冠 · 阳光双赛', 4, 8, '迪拜决赛完整冠军点；同场本人颁奖发言。', '迪拜冠军＋1000分。逆转阿尼西莫娃，决赛胜斯维托丽娜；印第安维尔斯、迈阿密均8强，简短交代。'),
    ('查尔斯顿第二冠', 8, 11, '一个完整精彩长回合＋完整冠军点；保留真实反应和整句原声。', '查尔斯顿冠军＋500分。连续四场三盘打进决赛，6比2、6比2胜斯塔罗杜布采娃。'),
    ('红土起伏 · 法网低谷', 11, 13, '法网首轮完整赛点、结果及真实反应。', '法网首轮＋10分。6比1先赢一盘后被比勒尔逆转；马德里第三轮、罗马8强简短交代。'),
    ('柏林草地反弹', 13, 15, '柏林半决赛完整赛点；清楚区分半决赛获胜与决赛失利。', '柏林亚军＋325分。半决赛决胜盘6比0胜萨巴伦卡；决赛负诺斯科娃。'),
    ('温网再遇高芙', 15, 17, '温网1/4决赛完整终局赛点与反应。', '温网8强＋430分。先赢一盘，最终6比4、3比6、3比6被高芙逆转。'),
    ('辛辛那提再进决赛', 17, 20, '半决赛胜斯瓦泰克、决赛负高芙，各留一个完整终局赛点。', '辛辛那提亚军＋650分。连赢三场三盘，赛季第五次决赛；华盛顿亚军、多伦多第四轮简短交代。'),
    ('美网：逆转与自我调整', 20, 28, '对纳瓦罗：救破发点＋完整赛点、反应及本人采访；对萨巴伦卡：救破发点＋完整赛点。', '美网4强＋780分。逆转费尔南德斯、纳瓦罗后负萨巴伦卡；采访明确来自赢下纳瓦罗之后。'),
    ('亚洲赛季 · 年终门票', 28, 31, '简短旁白交代亚洲赛季；WTA官方资格海报，最后接完整片尾。', '退出新加坡、北京；武汉首战三个赛点未兑现遭逆转。10月14日官方公布连续第五年入围；此后宁波退出。'),
]
rows = []
for title, a, b, visual, narrative in groups:
    begin = 0.0 if a == 0 else offsets[a]
    end = total if b == 31 else offsets[b]
    rows.append({'start':round(begin,3),'end':round(end,3),'time':f'{stamp(begin)}–{stamp(end)}','title':title,'segment_range_exclusive':[a,b],'visual':visual,'narrative':narrative})
body = ''.join('<tr>' + ''.join('<td>'+html.escape(value)+'</td>' for value in [r['time'],r['title'],r['visual'],r['narrative']])+'</tr>' for r in rows)
page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>
@page{size:A4 landscape;margin:9mm}*{box-sizing:border-box}body{font-family:"Noto Sans CJK SC",Arial,sans-serif;font-size:10.6px;line-height:1.45;color:#17324c;margin:0}h1{font-size:22px;margin:0 0 5px;letter-spacing:.2px}p{margin:0 0 8px}.lead{font-size:11px}.pill{font-weight:bold;color:#087e79}table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{border:1px solid #bacad8;padding:6px 7px;vertical-align:top}th{background:#17324c;color:white;text-align:left}th:nth-child(1){width:9%}th:nth-child(2){width:17%}th:nth-child(3){width:35%}th:nth-child(4){width:39%}tr:nth-child(even){background:#f0f5f8}.foot{font-size:9.6px;line-height:1.45;margin-top:7px}.small{font-size:9px;color:#4a6074}</style><body>'''
page += '<h1>佩古拉2026年终之路｜八站重点版提纲</h1>'
page += f'<p class="lead"><span class="pill">8站重点 · 10场比赛的完整赛点 · 3个额外回合</span>　当前31段，预计全片约{approx_duration}（含封面与10秒片尾）。<br>其余8站用简短旁白带过；全年时间线保留到年终资格确认及随后状态，不止于美网。</p>'
page += '<table><thead><tr><th>预计时段</th><th>章节</th><th>真实画面与原声</th><th>赛季事实与赛事最终积分</th></tr></thead><tbody>'+body+'</tbody></table>'
page += '<p class="foot"><b>重点站积分：</b>澳网780｜迪拜1000｜查尔斯顿500｜法网10｜柏林325｜温网430｜辛辛那提650｜美网780。合计4475分；其余8站1360分，全季合计5835分。每站只计一次，半决赛、决赛不重复加分。</p>'
page += '<p class="foot"><b>素材取舍：</b>仅查尔斯顿长回合、美网对纳瓦罗救破发点、美网对萨巴伦卡救破发点保留为3个额外回合。10个赛点均按发球、完整回合、确定结果与真实反应组织；不增加迈阿密、华盛顿、武汉比赛片段。美网半决赛的30秒对手决赛展望整段删除，服务佩古拉主线。</p>'
page += '<p class="foot"><b>呈现要求：</b>1080×1440铺满；比赛固定球场中心，采访按人物中心取景。赛事信息卡只叠实际比赛或本人画面，不上章节静态卡；轮次用1/4决赛、1/8决赛。真实原声保完整语义、配英中字幕；固定竖裁的边侧动作和部分反应近景可能出框，须如实记录。</p>'
page += '<p class="foot small">事实边界：16站、64场实际比赛，50胜14负，2冠3次亚军。10月14日为官方公开确认年终资格日期，不冒称最早数学锁定时刻。各段时间按当前素材窗与旁白时槽估算；最终片长及回合、字幕、取景完整性以实片检查为准。本页为更新提纲，不代表最终成片QC。</p></body></html>'
html_path = OUT / 'outline-v3.html'
html_path.write_text(page)
pdf = ROOT / 'delivery/佩古拉2026年终之路_八站重点版提纲.pdf'
proof = ROOT / 'delivery/佩古拉2026年终之路_八站重点版提纲_样张.png'
with sync_playwright() as pw:
    browser = _launch_browser(pw)
    tab = browser.new_page()
    tab.goto(html_path.as_uri())
    tab.evaluate('document.fonts.ready')
    tab.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
    browser.close()
doc = fitz.open(pdf)
assert len(doc) == 1, len(doc)
doc[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(proof)
assert spec_path.read_bytes() == spec_bytes, 'Shared spec changed during build; artifact remains bound to input SHA.'
metadata = {'schema':'pegula-outline-v3/v1','built_utc':datetime.now(timezone.utc).isoformat(),'source_spec':str(spec_path),'source_spec_sha256':hashlib.sha256(spec_bytes).hexdigest(),'source_scope_audit':str(audit_path),'source_scope_audit_sha256':sha(audit_path),'segment_count':31,'featured_events':8,'complete_matchpoint_inventory':10,'extra_rallies_inventory':3,'brief_events':8,'featured_event_points':points,'featured_points_sum':4475,'brief_points_sum':1360,'gross_points_sum':5835,'cover_seconds':cover_seconds,'body_end_seconds_including_cover':round(clock,3),'native_outro_seconds':native_outro_seconds,'estimated_film_seconds':round(total,3),'pdf_pages':len(doc),'rows':rows,'pdf':str(pdf),'pdf_sha256':sha(pdf),'proof':str(proof),'proof_sha256':sha(proof),'final_film_qc':False,'shared_spec_modified':False}
(OUT/'outline-v3.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(metadata,ensure_ascii=False,indent=2))
