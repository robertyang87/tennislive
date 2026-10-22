from pathlib import Path
import json, sys, hashlib

REPO = Path('/workspace/tennislive')
ROOT = Path('/workspace/sabalenka-finals-production')
SLUG = 'sabalenka-finals-2026'
ASSETS = Path('assets/reel') / SLUG
SPEC = REPO / 'specs/reels' / f'{SLUG}.json'
sys.path[:0] = [str(REPO/'tools'), str(REPO/'src')]
from render_story_info_band import render_label

plan = {x[0]: x for x in json.loads((ROOT/'narration-plan.json').read_text())}
records = {}
for name in ['source-manifest.json', 'extra-source-manifest.json']:
    for row in json.loads((ROOT/'research/media'/name).read_text())['sources']:
        if row.get('local_file'): records[row['name']] = row
selected_path = ROOT/'research/production/selections.json'
selected = json.loads(selected_path.read_text()) if selected_path.exists() else {}
previous = json.loads(SPEC.read_text()) if SPEC.exists() else {}
old_segments = {s.get('_id'): s for s in previous.get('segments', [])}
voice = {'pitch': '+0Hz', '_why':'沿用系列自然云健+6%/+0Hz，完整句合成；不靠提速挤入时窗。'}
segments, pending = [], []

labels = {
 'brisbane': ('冠军开启赛季','2026.01.11','布里斯班决赛','萨巴伦卡 vs 科斯秋克','6-4 6-3'),
 'ao': ('澳网亚军','2026.01.31','澳网决赛','萨巴伦卡 vs 莱巴金娜','4-6 6-4 4-6'),
 'iw-final': ('首次在这里夺冠','2026.03.15','印第安维尔斯决赛','萨巴伦卡 vs 莱巴金娜','3-6 6-3 7-6(6)'),
 'miami-point': ('完成阳光双冠','2026.03.28','迈阿密决赛','萨巴伦卡 vs 高芙','6-2 4-6 6-3'),
 'madrid': ('六个赛点未兑现','2026.04.28','马德里四分之一决赛','萨巴伦卡 vs 巴普蒂斯特','6-2 2-6 6-7(6)'),
 'rg': ('止步法网8强','2026.06.03','法网四分之一决赛','萨巴伦卡 vs 施耐德','6-3 5-7 0-6'),
 'wimbledon': ('止步第四轮','2026.07.05','温网第四轮','萨巴伦卡 vs 大坂直美','2-6 6-7(2)'),
 'us': ('本季第二次大满贯亚军','2026.09.12','美网决赛','萨巴伦卡 vs 莱巴金娜','4-6 7-5 2-6'),
 'beijing': ('五次机会全未兑现','2026.10.04','北京第三轮','萨巴伦卡 vs 巴尔通科娃','4-6 3-6'),
 'wuhan': ('救回九个赛点仍落败','2026.10.14','武汉第二轮','萨巴伦卡 vs 安·李','6-3 4-6 6-7(5)'),
}

card_labels = {'iw':'iw-final', 'miami':'miami-point', 'rg':'rg', 'us':'us', 'beijing':'beijing', 'wuhan':'wuhan'}

def card(key):
    _, date, title, text, seconds, kicker = plan[key]
    row = {'_id':'card-'+key, '_timeline_date':date, 'title_card':title,
           'seconds':seconds, 'narration':text, 'voice':voice, 'kicker':kicker}
    if key in card_labels:
        topic, label_date, place, people, score = labels[card_labels[key]]
        row['title_card_story_label'] = dict(topic=topic, date=label_date, place=place, people=people, score=score)
        row['_label_window_why'] = '实际原生预览发现该场比赛右上字卡遮挡远端球员；完整信息移至前置章节卡，沿用相同透明模板和原生位置，关键回合不挂该卡。'
    if key == 'qualification':
        row.pop('title_card')
        row.update(image=str(ASSETS/'qualification-evidence.png'), image_kind='evidence')
    segments.append(row)

def video(key):
    if key not in selected:
        pending.append(key); return
    row = selected[key]
    seg = {k: row[k] for k in ['start','end','frame','cx','cx_face','_frame_why','visual_image'] if k in row}
    seg.update({'_id':key,'source':row['source_name'],'narration':'','voice':voice,
                'fit':'crop','cx':row.get('cx',.5),'track':False,
                '_quote_kind':row.get('quote_kind','broadcast'),
                '_audio_review_state':'actual_asr_cross_checked_not_human_listening',
                '_why':row.get('visual_review',row.get('notes','Actual same-match official source; exact evidence in research production selections.'))})
    if key=='cold-miami':seg['_ending_payoff_required']=True
    captions = row.get('captions',row.get('utterances',[]))
    if captions:
        seg['quote']=[{'at':round(c['start']-row['start'],3),'end':round(c['end']-row['start'],3),
                       'text':c['en']+'\n'+c['zh']} for c in captions]
    else:
        seg['_quote_skip_why']=row.get('no_foreground_english_reason','Actual checked source window contains no identifiable foreground English; see source-bound packet.')
    old=old_segments.get(key,{})
    if old.get('start')==seg['start'] and old.get('end')==seg['end']:
        for k in ['cx','cx_face','frame','_frame_why']:
            if k in old: seg[k]=old[k]
    if key in labels and key not in card_labels.values():
        topic, date, place, people, score = labels[key]
        label = dict(topic=topic,date=date,place=place,people=people,score=score)
        p=ASSETS/f'context-{key}.png';render_label(label,REPO/p)
        safe = row.get('label_safe_window')
        if safe:
            after=round(safe[0]-row['start'],3);duration=round(min(15,safe[1]-safe[0]),3)
        else: after=.8;duration=3.0
        seg['inset']={'image':str(p),'kind':'story_text','corner':'tr','width':.60,'pad':.043,
                      'show_for':duration,'show_after':after,'motion':'editorial','label':label}
        seg['_label_window_why']='在独立核定的赛后握手/反应/走向裁判窗口展示；实际PNG局部原生叠图另有证据，不遮脸。' if key=='madrid' else '在独立核定的连续球场全景上展示；不跨近景人脸。最终原生样帧和成片另行验收。'
    segments.append(seg)

sequence = [
 ('v','cold-miami'),('v','us-quote'),
 ('c','brisbane'),('v','brisbane'),('c','ao'),('v','ao'),
 ('c','iw'),('v','iw-save'),('v','iw-final'),('v','iw-photo'),
 ('c','miami'),('v','miami-point'),('v','miami-reaction-reprise'),('v','miami-after'),
 ('c','madrid'),('v','madrid'),('c','rg'),('v','rg'),('v','rg-quote'),
 ('c','berlin'),('c','wimbledon'),('v','wimbledon'),('c','hardcourt'),
 ('c','us'),('v','us'),('c','qualification'),('c','beijing'),('v','beijing'),
 ('c','wuhan'),('v','wuhan'),('c','ending'),
]
for kind,key in sequence:
    (card if kind=='c' else video)(key)

used={s['source'] for s in segments if 'source' in s}
sources, fallbacks, quality, mixed = {}, {}, {}, {}
for key in sorted(used):
    r=records[key]
    canonical = r.get('official_identity_evidence')
    url=canonical if isinstance(canonical,str) and canonical.startswith('https://www.youtube.com/watch?') else r['source_url']
    sources[key]=url
    archive=r.get('archive_url') or (f"https://github.com/robertyang87/tennislive/releases/download/source-{r['id']}/{r['id']}.mp4" if r.get('id') else None)
    if not archive and 'github.com/' in r['source_url']: archive=r['source_url']
    if archive and archive != url: fallbacks[key]=archive
    stream=next((s for s in r.get('streams',[]) if s.get('codec_type')=='video'),{})
    w,h,fps=stream.get('width',r.get('width')),stream.get('height',r.get('height')),stream.get('r_frame_rate',r.get('fps'))
    assert min(w,h)>=1080,(key,w,h)
    quality[key]={'why':f"实际官方源字节已下载并ffprobe，SHA256 {r['sha256']}；实际选窗、原声与裁切另行验收。",'width':w,'height':h,'fps':fps}
    if fps!='25/1':mixed[key]=f'实际源{fps}fps等时长转为25fps；不变速。'

spec={
 'slug':SLUG,'date':'2026-10-22','_column':'网球有故事',
 'title':'萨巴伦卡：双冠之后的年终之路',
 'cover':{'eyebrow':'网球有故事','layout':'solo','story_kind':'person','subject':'萨巴伦卡',
          'hook':'春天连捧两座奖杯\n带着遗憾走向年终','topic':'萨巴伦卡：双冠之后的年终之路',
          'portrait':{'image':str(ASSETS/'cover-miami.jpg'),'fit':'cover','focus':.56,'focus_y':.4,'zoom':1.0,
                      'source_url':'https://www.wtatennis.com/news/4478904','_credit':'Chris Arjoon/Icon Sportswire via Getty Images, WTA official article',
                      '_portrait_why':'实际6000x4000迈阿密冠军实拍，双眼睁开、脸与奖杯无遮挡；图库标题误标Indian Wells，已按Miami Open杯身与官方文章核对身份。'},'scrim':'clear'},
 'segments':segments,'sources':sources,'source_fallbacks':fallbacks,'cx':.5,'track':False,
 'tts_backend':'edge','_tts_backend_why':'沿用穆霍娃、莱巴金娜已定自然云健+6%/+0Hz；每段完整语义合成。',
 'push':{'auto':True,'summary':'萨巴伦卡年终之路','lead':'从布里斯班冠军、阳光双冠，到两次大满贯亚军；9月29日确认年终资格之后，北京和武汉的起伏仍在继续。'},
 'editorial':{'mode':'match_review','question':'萨巴伦卡如何从阳光双冠，走过两次大满贯决赛的遗憾，再走向年终？',
              'thesis':'按2026赛季时间线讲清14站高光和低谷，美网后继续至北京、武汉；官宣入围不等同状态已恢复。',
              'chapters':['冠军开启赛季','阳光双冠','领先之后','北美再出发','美网之后'],
              'beats':['三冠与两次大满贯亚军的反差','印第安维尔斯救冠军点、迈阿密完成阳光双冠','马德里六赛点未兑现、法网领先后连丢十局','草地及北美热身赛受挫后再进美网决赛','正式入围后北京、武汉仍有起伏'],
              'human_context':{'angle':'春天连续捧杯的人，也会在夏秋反复受挫；她带着这些起伏，再走向年终。',
                               '_facts_file':'research/sabalenka-finals-2026/season-results.json',
                               'sources':['https://api.wtatennis.com/tennis/players/320760/matches?year=2026&type=S&page=0&pageSize=200&sort=desc','https://www.wtatennis.com/news/4583238','https://x.com/WTA/status/2104949796649705950','https://www.wtatennis.com/news/4513629','https://www.wtatennis.com/news/4592337'],
                               'facts':['本赛季14站，实打47胜11负，3冠2次亚军；WTA简介47/10与逐场完赛差异已独立核对，片中不使用冲突简介值。','澳网与美网两次亚军均负莱巴金娜，印第安维尔斯与迈阿密为当年阳光双冠。','法网没有拿到赛点，马德里六个赛点未兑现，武汉挽救九个赛点后仍负。','北京时间9月29日WTA正式官宣连续第六年入围，最早数学锁定日未独立证实。','截至制作日最新完赛为武汉；不预写未来赛果、不宣称赛季结束。']}},
 '_no_probe_why':quality,'mixed_fps':mixed,'preserve_source_audio':True,
 '_story_label_style':'使用主线5ff75d4模板：透明右上，标题89、比分固定98、日期/人名73，width0.60/pad0.043，最长15秒且不跨片段。',
 '_outline_review':{'received':True,'response':'好的','request':'requests/stories/sabalenka-finals-2026.json'},
 '_render_blockers':pending,'_framing':'所有视频3:4裁切铺满；比赛固定球场中心，采访整段固定实测人物中心。',
 '_cold_open_why':'前13秒用三月冠军庆祝和九月亚军发言做对照，再从一月按时间线展开。开场迈阿密4.72秒庆祝在正文完整冠军分后接回，兑现原生ending-payoff要求并前后呼应；美网发言不重复。本人发言取真实美网同次颁奖。'
}
SPEC.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
print('segments',len(segments),'pending',pending,'video_seconds',sum(s['end']-s['start'] for s in segments if 'start' in s),'narration_seconds',sum(s.get('seconds',0) for s in segments))
