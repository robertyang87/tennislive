"""Build this episode from its own source-bound selections; never mark gaps ready."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,argparse
ROOT=Path('/workspace/andreeva-finals-production');REPO=Path('/workspace/tennislive-andreeva');SLUG='andreeva-finals-2026';ASSETS=Path('assets/reel')/SLUG
VOICE={'pitch':'+0Hz','_why':'云健+6%/+0Hz完整语义整句合成，实际字节冻结与时长检查；不人为拆字加速。'}
LABELS={
 'adelaide-final':dict(topic='冠军·500分',date='2026.01.17',place='阿德莱德决赛',people='安德烈耶娃 vs 姆博科',score='6-3 6-1'),
 'ao-r4':dict(topic='澳网第四轮出局',date='2026.01.25',place='澳网第四轮',people='安德烈耶娃 vs 斯维托丽娜',score='2-6 4-6'),
 'linz-final':dict(topic='冠军·500分',date='2026.04.12',place='林茨决赛',people='安德烈耶娃 vs 波塔波娃',score='1-6 6-4 6-3'),
 'madrid-final':dict(topic='亚军·650分',date='2026.05.02',place='马德里决赛',people='安德烈耶娃 vs 科斯秋克',score='3-6 5-7'),
 'rg-final':dict(topic='冠军·2000分',date='2026.06.06',place='法网决赛',people='安德烈耶娃 vs 赫瓦林斯卡',score='6-3 6-2'),
 'wimbledon-r2':dict(topic='第二轮·70分',date='2026.07.01',place='温网第二轮',people='安德烈耶娃 vs 克雷吉茨科娃',score='6-4 5-7 4-6'),
 'us-qf':dict(topic='8强·430分',date='2026.09.09',place='美网1/4决赛',people='安德烈耶娃 vs 高芙',score='6-2 6-7(7) 2-6'),
 'beijing-final':dict(topic='亚军·650分',date='2026.10.11',place='北京决赛',people='安德烈耶娃 vs 郑钦文',score='5-7 4-6')}
SEQUENCE=[('v','cold-quote'),('c','intro'),('c','january'),('v','adelaide-final'),('c','ao'),('c','spring'),('c','linz'),('v','linz-final'),('c','madrid'),('v','madrid-final'),('c','rg'),('v','rg-final'),('c','grass'),('v','wimbledon-r2'),('c','us'),('v','us-qf'),('c','asia'),('c','beijing'),('v','beijing-final'),('c','ending')]
DATES={'intro':'2026-01-01','january':'2026-01-17','ao':'2026-01-25','spring':'2026-03-23','linz':'2026-04-12','madrid':'2026-05-02','rg':'2026-06-06','grass':'2026-07-01','us':'2026-09-09','asia':'2026-10-09','beijing':'2026-10-11','ending':'2026-10-15'}
def load(p):return json.loads(Path(p).read_text())
def build():
 plan={r['id']:r for r in load(ROOT/'production/narration-plan.json')};idx={r['key']:r for r in load(ROOT/'source-index.json')};selpath=ROOT/'production/selections.json';sel=load(selpath)if selpath.exists()else{};sel=sel.get('selections',sel);segments=[];blockers=[]
 for typ,key in SEQUENCE:
  if typ=='c':
   p=plan[key];segments.append(dict(_id='card-'+key,_timeline_date=DATES[key],title_card=p['title'],seconds=p['seconds'],narration=p['text'],voice=VOICE,kicker=p['kicker'],_voice_intent=p['intent'],_voice_emphasis=p['main_emphasis']));continue
  if key not in sel:blockers.append(key+': await verified actual source/whole foreground selection');continue
  r=sel[key];source=idx.get(r['source_name']);assert source and source['sha256']==r['source_sha256'],key
  if r.get('uncertain')or r.get('status')not in ('ready_for_native_integration','complete_asr_cross_checked_not_human_listening'):blockers.append(key+': selection not fully resolved')
  lo,hi=r['start'],r['end'];assert 0<=lo<hi<=source['duration'];packet=Path(r['audio_review_packet']);assert packet.is_file()
  seg={k:r[k]for k in ('audio_tail','point_end_ok','subtitle_bottom_windows','fill_y')if k in r};seg.update(_id=key,source=r['source_name'],start=lo,end=hi,frame=r.get('frame','court'),cx=r.get('cx',.5),track=False,fit='crop',narration='',voice=VOICE,_quote_kind=r.get('quote_kind','broadcast'),_why=r.get('notes','Actual same-event source; native previews pending.'),_frame_why=r.get('_frame_why','比赛固定球场中心cx=.5铺满1080×1440，包含同场真实反应；不自动跟随。'))
  if seg['frame']=='person':seg['cx_face']=r['cx_face']
  if r.get('captions'):seg['quote']=[dict(at=round(c['start']-lo,3),end=round(c['end']-lo,3),text=c['en']+'\n'+c['zh'])for c in r['captions']]
  else:seg['_quote_skip_why']=r['no_foreground_english_reason']
  if key in LABELS:
   safe=r['label_safe_window'];assert lo<=safe[0]<safe[1]<=hi and round(safe[1]-safe[0],3)>=2.8
   seg['inset']=dict(image=str(ASSETS/f'context-{key}.png'),kind='story_text',corner='tr',width=.60,pad=.043,show_after=round(safe[0]-lo,3),show_for=round(min(15,safe[1]-safe[0]),3),motion='editorial',label=LABELS[key]);seg['_label_window_why']=r['label_window_why'];seg['_match_id']=key;seg['_point_role']='match_point'
  else:seg['_band_skip_why']='真实同场本人短句；人物采访不上遮脸的信息卡。同场比赛完整赛事信息已在正文真实比赛视频展示。'
  segments.append(seg)
 used=sorted({s['source']for s in segments if 'source'in s});quality={k:dict(why='官方实际源已下载实测并校SHA256 '+idx[k]['sha256']+'；非最终成片QC。',width=idx[k]['width'],height=idx[k]['height'],fps=idx[k]['fps'])for k in used}
 scope='最新系列授权每集更紧凑约5分钟；四大满贯、全部三冠(法网重合)、马德里和北京两站大分，共8站重点；其余11站一句带过。7场画面出场比赛完整终局赛点；澳网第四轮以准确原生事实章交代，不拼接非同步准备，不借用720豁免。额外完整分最多1且本集暂不加。全季工作簿仍保留19站66实打，另列BYE/W/O，不止于美网。'
 spec=dict(slug=SLUG,primary='adelaide-final',date='2026-10-22',_column='网球有故事',title='安德烈耶娃：从巴黎冠军到单打年终',cover=dict(eyebrow='网球有故事',layout='solo',story_kind='person',subject='安德烈耶娃',hook='19岁首夺大满贯\n首次入围单打年终',topic='安德烈耶娃：从巴黎冠军到单打年终',portrait=dict(image=str(ASSETS/'cover-rg-2026-jb1-2805.jpg'),fit='cover',focus=.14,focus_y=.5,zoom=1.,source_url='https://www.rolandgarros.com/en-us/photo-gallery/2026-edition-gallery-photos-champions-finalists-roland-garros-2026',_credit='Jean-Baptiste Autissier / FFT',_portrait_why='2026法网官方Champions图库JB1_2805实际3000×2000原图，横向裁切取Mirra与本人奖杯；原图已实际查看，fresh JPEG全HEADblob/原图URL去重通过；原生封面仍需实核。'),scrim='clear'),segments=segments,sources={k:idx[k]['canonical_url']for k in used},source_fallbacks={k:idx[k]['archive_url']for k in used},cx=.5,track=False,tts_backend='edge',_tts_backend_why='完整句自然云健+6%/+0Hz，实际TTS冻结，不用外部模型API。',preserve_source_audio=True,push=dict(auto=True,summary='安德烈耶娃年终之路',lead='阿德莱德、林茨、法网三冠，也有温网失利和美网两个未兑现的赛点。10月9日首次取得单打年终资格，随后北京第五次打进赛季决赛。'),editorial=dict(mode='match_review',question='第一座大满贯之后，安德烈耶娃怎样走到首次单打年终？',thesis='按时间线串起3冠、2亚军和大满贯低谷；10/9资格先于10/11北京决赛，继续至武汉赛程调整退赛及最新已证实状态。',chapters=['一月首冠','春季阻力','林茨反弹','巴黎高光','草地与纽约','亚洲与年终'],beats=['阿德莱德零比三后连赢九局','林茨先失一盘逆转','马德里亚军到巴黎半决赛击败同一对手','19岁首夺大满贯','温网先赢一盘仍止步第二轮','美网两个赛点未兑现','10/9首次单打资格、10/11北京亚军、随后世界第三'],human_context=dict(angle='首夺大满贯不意味着每一站都顺利；她的全年有三次捧杯，也有先赢一盘后出局和未兑现赛点。',_facts_file='research/andreeva-finals-2026/canonical.json',sources=['https://www.wtatennis.com/news/4515090','https://www.wtatennis.com/news/4574376','https://www.wtatennis.com/news/4586608','https://www.wtatennis.com/news/4590575'],facts=['19站66场实打50胜16负，14BYE及1对手W/O另列；零RET。','3冠5次决赛；首座大满贯在2026法网。','10/9官方首次单打年终资格；2025曾参加双打年终，不写首次参加任何年终。','官方Race6306与19站积分简单总和6372差66未解决，不编原因。','10/11北京亚军后10/12世界第3；退出武汉的官方理由调整赛程，不借用郑钦文伤情。'])),_no_probe_why=quality,mixed_fps={k:f'实测原生{idx[k]["fps"]}按实际时长转换主片25fps，不改变速度。'for k in used if idx[k]['fps']!='25/1'},_story_label_style='真实视频右上透明TR89/98/73；width.60/pad.043；>=2.8s且<=15s；禁止静态章节卡放信息inset。',_outline_review=dict(received=False,outline_shown=True,outline_shown_by='root',outline_shown_date='2026-10-22',series_scope_authorized=True,preproduction_may_continue=True,specific_outline_approval_quote=None,formal_render_authorized=False,request='requests/stories/'+SLUG+'.json',latest_scope=scope),_cold_open_why='2026法网夺冠同场本人真实短句；接旁白带回一月，正文不重复同一句。',_render_blockers=blockers,_duration_target_seconds=[270,320],_matchpoint_coverage={'actual_full_match_points':7,'ao_r4':'native factual chapter only; independently checked official1080 sources lack same-point prep; no match video shown','extras':0})
 assert not any('title_card_story_label'in s or (s.get('inset')and'start'not in s)for s in segments)
 return spec
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--write-repo',action='store_true');a=ap.parse_args();spec=build();out=REPO/'specs/reels'/f'{SLUG}.json'if a.write_repo else ROOT/'production/spec-candidate.json'
 if a.write_repo and spec['_render_blockers']:raise SystemExit(json.dumps(spec['_render_blockers']))
 if a.write_repo:
  sys.path[:0]=[str(REPO/'tools'),str(REPO/'src')];from render_story_info_band import render_label
  for k,v in LABELS.items():render_label(v,REPO/ASSETS/f'context-{k}.png')
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n');print(out,'segments',len(spec['segments']),'blockers',len(spec['_render_blockers']))
