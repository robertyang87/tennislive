from pathlib import Path
import json,sys,hashlib
REPO=Path('/workspace/tennislive');ROOT=Path('/workspace/pegula-finals-production');SLUG='pegula-finals-2026';ASSETS=Path('assets/reel')/SLUG
sys.path[:0]=[str(REPO/'tools'),str(REPO/'src')]
from render_story_info_band import render_label
plan={r['id']:r for r in json.loads((ROOT/'narration-plan.json').read_text())}
source_index={r['key']:r for r in json.loads((ROOT/'source-index.json').read_text())}
extra=ROOT/'production/middle-source-index.json'
if extra.exists():
 for r in json.loads(extra.read_text()):source_index[r['key']]=r
selection_path=ROOT/'production/selections.json'
selected=json.loads(selection_path.read_text()) if selection_path.exists() else {}
old=json.loads((REPO/'specs/reels'/f'{SLUG}.json').read_text()) if (REPO/'specs/reels'/f'{SLUG}.json').exists() else {}
oldsegs={s.get('_id'):s for s in old.get('segments',[])}
voice={'pitch':'+0Hz','_why':'自然云健+6%/+0Hz；完整语义整段合成，无人工加速。'}
labels={
'ao':('止步澳网4强','2026.01.29','澳网半决赛','佩古拉 vs 莱巴金娜','3-6 6-7(7)'),
'dubai-final':('本季第一冠','2026.02.21','迪拜决赛','佩古拉 vs 斯维托丽娜','6-2 6-4'),
'iw-qf':('止步8强','2026.03.12','印第安维尔斯四分之一决赛','佩古拉 vs 莱巴金娜','1-6 6-7(4)'),
'miami-qf':('先赢一盘仍落败','2026.03.25','迈阿密四分之一决赛','佩古拉 vs 莱巴金娜','6-2 3-6 4-6'),
'charleston-final':('本季第二冠','2026.04.05','查尔斯顿决赛','佩古拉 vs 斯塔罗杜布采娃','6-2 6-2'),
'berlin-sf':('决胜盘6比0过关','2026.06.20','柏林半决赛','佩古拉 vs 萨巴伦卡','6-4 6-7(4) 6-0'),
'berlin-final':('柏林亚军','2026.06.21','柏林决赛','佩古拉 vs 诺斯科娃','4-6 6-4 3-6'),
'dc-final':('本季第四次决赛','2026.08.03','华盛顿决赛','佩古拉 vs 伊埃拉','6-4 4-6 0-6'),
'cincy-sf':('本季第五次进决赛','2026.08.22','辛辛那提半决赛','佩古拉 vs 斯瓦泰克','7-5 4-6 6-4'),
'cincy-final':('辛辛那提亚军','2026.08.23','辛辛那提决赛','佩古拉 vs 高芙','2-6 4-6'),
'us-qf':('逆转晋级4强','2026.09.08','美网四分之一决赛','佩古拉 vs 纳瓦罗','3-6 6-4 6-3'),
'us-sf':('止步美网4强','2026.09.10','美网半决赛','佩古拉 vs 萨巴伦卡','5-7 2-6'),
'wuhan-mp3':('三个赛点未兑现','2026.10.14','武汉第二轮','佩古拉 vs 奥斯塔彭科','6-2 6-7(7) 3-6'),
}
# All labels belong to actual video segments. No static/title/transition label fallback.
segments=[];pending=[]
def card(key):
 p=plan[key];row={'_id':'card-'+key,'_timeline_date':p['date'],'title_card':p['title'],'seconds':p['seconds'],'narration':p['text'],'voice':voice,'kicker':p['kicker'],'_voice_intent':p['intent'],'_voice_emphasis':p['main_emphasis']}
 if key=='qualification':
  row.pop('title_card');row.update(image=str(ASSETS/'qualification-evidence.png'),image_kind='evidence')
 segments.append(row)
def video(key,optional=False):
 if key not in selected:
  if not optional:pending.append(key)
  return
 r=selected[key];seg={k:r[k] for k in ['start','end','cx','frame','cx_face','_frame_why','visual_image','audio_tail','point_end_ok'] if k in r}
 seg.update(_id=key,source=r['source_name'],narration='',voice=voice,fit='crop',track=False,cx=r.get('cx',.5),_quote_kind=r.get('quote_kind','broadcast'),_why=r.get('visual_review',r.get('notes','Actual same-match official source; complete selected temporal window.')))
 if seg.get('frame')=='court':seg['_frame_why']=r.get('_frame_why') or '实际比赛及同场赛后比赛反应；按用户要求固定球场中心cx=.5，不跟踪、不改为人物取景。'
 caps=r.get('captions',[])
 if caps:seg['quote']=[{'at':round(c['start']-r['start'],3),'end':round(c['end']-r['start'],3),'text':c['en']+'\n'+c['zh']} for c in caps]
 else:seg['_quote_skip_why']=r.get('no_foreground_english_reason','')
 if r.get('audio_tail_why'):seg['_audio_tail_why']=r['audio_tail_why']
 if key in labels:
  topic,date,place,people,score=labels[key];label=dict(topic=topic,date=date,place=place,people=people,score=score)
  img=ASSETS/f'context-{key}.png';render_label(label,REPO/img)
  safe=r.get('label_safe_window');after=round(safe[0]-r['start'],3) if safe else .8;hold=round(min(15,safe[1]-safe[0]),3) if safe else min(3.0,r['end']-r['start']-.8)
  seg['inset']={'image':str(img),'kind':'story_text','corner':'tr','width':.60,'pad':.043,'show_after':after,'show_for':hold,'motion':'editorial','label':label}
  seg['_label_window_why']=r.get('label_window_why','Actual-video-only label; selected live interval must be checked in native caption previews before final render.')
 if key=='cold-quote':seg['_band_skip_why']='真实本人冷开场，人物特写会被右上大信息字卡遮住；同场完整比赛信息在正文辛辛那提决赛真实视频上展示，紧接旁白明确2024、2026两次亚军，不将其理解为本季两座同站亚军。'
 prev=oldsegs.get(key,{})
 if prev.get('start')==seg['start'] and prev.get('end')==seg['end']:
  for k in ['frame','cx','cx_face','_frame_why']:
   if k in prev:seg[k]=prev[k]
 segments.append(seg)
sequence=[('v','cold-quote'),('c','intro'),('c','january'),('v','ao'),('c','dubai'),('v','dubai-final'),('v','dubai-speech'),('c','sunshine'),('o','miami-qf'),('c','charleston'),('v','charleston-final'),('c','clay'),('c','berlin'),('v','berlin-sf'),('c','summer'),('v','dc-final'),('c','cincy'),('v','cincy-sf'),('v','cincy-final'),('c','us-open'),('v','us-qf'),('v','us-qf-reaction'),('v','us-qf-interview'),('c','us-semi'),('v','us-sf'),('c','asia'),('v','wuhan-mp3'),('v','wuhan-final'),('c','qualification'),('c','ending')]
for typ,key in sequence:
 if typ=='c':card(key)
 else:video(key,optional=typ=='o')
used={s['source'] for s in segments if 'source' in s};sources={};fallback={};quality={};mixed={}
for key in sorted(used):
 r=source_index[key];sources[key]=r['canonical_url'];fallback[key]=r['archive_url'];quality[key]={'why':f"实际官方源字节已下载并ffprobe；SHA256 {r['sha256']}。全片取景和原声须逐段验收。",'width':r['width'],'height':r['height'],'fps':r['fps']}
 if r['fps']!='25/1':mixed[key]=f"原生{r['fps']}fps按实际时长转为主片25fps，不改变声音或比赛速度。"
spec={'slug':SLUG,'date':'2026-10-22','_column':'网球有故事','title':'佩古拉：起伏中的年终之路','cover':{'eyebrow':'网球有故事','layout':'solo','story_kind':'person','subject':'佩古拉','hook':'本季两冠五次决赛\n连续第五年进年终','topic':'佩古拉：起伏中的年终之路','portrait':{'image':str(ASSETS/'cover-charleston.jpg'),'fit':'cover','focus':.43,'focus_y':.44,'zoom':1.0,'source_url':'https://www.wtatennis.com/news/4482273','_credit':'Matthew Stockman/Getty Images, WTA official Charleston2026 title photograph','_portrait_why':'实际5181×3454同年查尔斯顿捧杯实拍，正脸双眼可见，实际原图已核脸/奖杯/赛事背景。'},'scrim':'clear'},'segments':segments,'sources':sources,'source_fallbacks':fallback,'cx':.5,'track':False,'tts_backend':'edge','_tts_backend_why':'沿用系列已定自然云健+6%/+0Hz，完整句合成，冻结实际字节并自动五项验收。','preserve_source_audio':True,'push':{'auto':True,'summary':'佩古拉年终之路','lead':'迪拜、查尔斯顿两冠，五次赛季决赛；也有法网首轮失利与亚洲赛季的波折。10月14日正式确认连续第五年入围之后，时间线继续至宁波退赛。'},'editorial':{'mode':'match_review','question':'佩古拉怎样从两冠、三次亚军和首轮失利，积累出连续第五张年终门票？','thesis':'按全年16站真实单打成绩串联高光、低谷和反弹，美网后继续至亚洲赛季与官方资格确认，不预写未来结果。','chapters':['一月出发','第一座冠军','春天的硬仗','低谷之后','北美起伏','美网之后','年终门票'],'beats':['赛季两冠与三次亚军','法网先赢一盘仍首轮出局','柏林再进决赛','辛辛那提连续三场三盘胜利','美网再进大满贯4强','退赛、武汉失利与连续第五年资格'],'human_context':{'angle':'连续苦战夺冠，也有首轮出局与决赛失利；她一次次重返争冠行列，积累出连续第五年的年终资格。','_facts_file':'research/pegula-finals-2026/season-results.json','sources':['https://api.wtatennis.com/tennis/players/316956/matches?year=2026&type=S&page=0&pageSize=200&sort=desc','https://www.wtatennis.com/news/4591678','https://x.com/WTA/status/2110339830022385710','https://www.wtatennis.com/news/4592575'],'facts':['实打16站64场，50胜14负、12次轮空，1场对手RET胜，无W/O。','2冠、3次亚军，5次决赛；16站积分5835，与10/19官方Race相符。','澳网和美网打进4强；法网首轮出局、温网止步8强。','10/14WTA正式确认连续第五年入围；不将武汉失利写成获胜，不称已计算最早数学锁定日。','新加坡、北京、宁波赛前退赛；不编具体未公布伤情，不预写东京/年终结果。']}},'_no_probe_why':quality,'mixed_fps':mixed,'_story_label_style':'最新主线透明右上：标题89、比分固定98、日期和姓名73，width.60/pad.043，最长15秒且不跨源片段；只放实际视频，禁止转场/章节卡。','_outline_review':{'received':True,'response':'继续，信息字卡不要在转场卡片上','request':'requests/stories/pegula-finals-2026.json'},'_render_blockers':pending,'_cold_open_why':'本人2026辛辛那提亚军自嘲直接带入情绪。紧接旁白明确她2024也在这里获得亚军，从今年两冠三次亚军倒回一月；正文不重复这段发言。','_social_search':{'x':'已取得WTA资格原帖2110339830022385710；本人和赛事账号公开检索边界保存在late-season-audit。','instagram':'新加坡退赛IGStory原件已过期，用WTA官方逐字报道；宁波未知原因不虚构。'}}
assert not any('title_card_story_label' in s for s in segments)
assert all('start' in s for s in segments if s.get('inset',{}).get('kind')=='story_text')
(REPO/'specs/reels'/f'{SLUG}.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n');print('segments',len(segments),'missing',pending,'video seconds',sum(s['end']-s['start'] for s in segments if 'start' in s),'narration seconds',sum(s.get('seconds',0) for s in segments))
