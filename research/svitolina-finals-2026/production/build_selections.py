from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re
P=Path(__file__).parent;ROOT=P.parent;A=ROOT/'audio';idx={s['key']:s for s in json.load(open(ROOT/'media/source-index.json'))}
def cap(a,b,en,zh):
 assert len(re.findall('[\u4e00-\u9fff]',zh))<=16,(zh,len(zh));return {'start':a,'end':b,'en':en,'zh':zh}
D={
'cold-rome':('rome-final',526.76,537.68,[cap(526.79,528.45,'I told my coach that would be nice','我跟教练说 这样挺好'),cap(528.45,532.25,'before I finish my career to have a round number.','生涯结束前 能凑个整数'),cap(532.25,534.95,'So he told me that hopefully','他就说 希望'),cap(534.95,536.38,"we're gonna get this this year.",'今年就能做到'),cap(536.38,537.42,"So I'm glad.",'所以我很高兴')]),
'auckland-final':('auckland-final',258.68,275.12,[cap(263.84,267.74,'Elina Svitolina is the champion in Auckland.','斯维托丽娜赢下奥克兰冠军'),cap(269.36,271.90,'Her 19th career title,','她职业生涯的第19冠'),cap(271.90,274.84,'and she had to work hard for it in this final.','这场决赛她赢得很艰难')]),
'ao-sf':('ao-sf',450.52,472.40,[cap(462.28,466.72,'So impressive from the world No. 1.','世界第一 表现太出色了'),cap(466.72,472.10,'Sabalenka moves through to the final once again in Melbourne.','萨巴伦卡再次闯进墨尔本决赛')]),
'dubai-final':('dubai-final',239.20,251.76,[cap(241.14,245.72,'It is a dream debut Dubai title','梦幻般的迪拜首冠'),cap(245.72,247.48,'for Jessica Pegula,','属于杰西卡·佩古拉'),cap(247.48,251.60,'and she seals it in style with an ace.','她用一记ACE漂亮收官')]),
'rome-final':('rome-final',219.92,255.52,[cap(235.84,240.56,'Elina Svitolina is a Roman champion once again.','斯维托丽娜再次在罗马捧杯'),cap(240.56,243.62,'The third act of a glorious trilogy','荣耀三部曲的第三幕'),cap(243.62,247.38,'set under the ancient skies of the Eternal City.','永恒之城的古老天空之下'),cap(247.38,252.42,'A story of defiance, determination and perseverance,','这是抗争 坚定与坚持的故事'),cap(252.42,255.22,'ultimately ending in glory.','最终以荣耀作结')]),
'rg-qf':('rg-qf',228.00,245.52,[]),
'wimbledon-r1':('wimbledon-r1',363.32,383.28,[cap(367.38,368.02,'There it is.','拿下来了'),cap(368.02,374.18,'Snigur takes the biggest win of her career,','斯尼古尔拿下生涯最大胜利'),cap(374.18,378.04,'defeating fellow Ukrainian Elina Svitolina','击败同胞斯维托丽娜'),cap(378.04,381.20,'in straight sets on No. 2 Court,','在2号球场直落两盘'),cap(381.20,383.06,'and in some style.','而且赢得漂亮')]),
 'toronto-sf':('toronto-sf',249.32,271.80,[cap(258.74,261.66,'A first final of the season,','本赛季第一次闯进决赛'),cap(261.66,266.02,'a first Canadian final for Iga Swiatek.','斯瓦泰克首进加拿大站决赛'),cap(267.86,269.24,'Tough for Svitolina.','斯维托丽娜很遗憾'),cap(269.62,271.50,'She battled so hard.','她拼得那么顽强')]),
'us-r3':('us-r3',168.80,185.60,[cap(173.32,174.48,"She's done it.",'她做到了'),cap(174.48,177.80,'Anna Kalinskaya is into the last 16 in New York','卡林斯卡娅闯进美网第四轮'),cap(177.80,182.02,'for the first time in her career.','这是她职业生涯的第一次'),cap(182.10,185.50,'What a crazy, crazy roller coaster!','真是一场疯狂的过山车')])}
labels={
'auckland-final':('冠军·250分', '2026.01.11', '奥克兰决赛', '斯维托丽娜 vs 王欣瑜', '6-3 7-6(6)', [270.9, 274.4]),
'ao-sf':('止步4强·780分', '2026.01.29', '澳网半决赛', '斯维托丽娜 vs 萨巴伦卡', '2-6 3-6', [468.6, 472.24]),
'dubai-final':('亚军·650分', '2026.02.21', '迪拜决赛', '斯维托丽娜 vs 佩古拉', '2-6 4-6', [239.68, 243.08]),
'rome-final':('冠军·1000分', '2026.05.16', '罗马决赛', '斯维托丽娜 vs 高芙', '6-4 6-7 6-2', [232.2, 235.4]),
'rg-qf':('止步8强·430分', '2026.06.02', '法网1/4决赛', '斯维托丽娜 vs 科斯秋克', '3-6 6-2 2-6', [237.0, 240.4]),
'wimbledon-r1':('第1轮·10分', '2026.06.30', '温网第一轮', '斯维托丽娜 vs 斯尼古尔', '5-7 2-6', [377.8, 383.0]),
'toronto-sf':('止步4强·390分', '2026.08.12', '多伦多半决赛', '斯维托丽娜 vs 斯瓦泰克', '3-6 6-1 3-6', [264.3, 269.2]),
'us-r3':('第3轮·130分', '2026.09.04', '美网第三轮', '斯维托丽娜 vs 卡林斯卡娅', '3-6 6-2 3-6', [181.8, 185.5]),
}
extra={'cold-rome':[A/'window-context/rome-svi-speech-small.en-en.json',A/'window-context/rome-svi-speech-medium.en-en.json',A/'window-context/cold-rome-turbo-en.json',A/'window-context/cold-tail-small.en-en.json',A/'window-context/cold-tail-medium.en-en.json'],'dubai-final':[A/'window-context/dubai-terminal-small.en-en.json',A/'window-context/dubai-terminal-medium.en-en.json'],'rome-final':[A/'window-context/rome-terminal-small.en-en.json',A/'window-context/rome-terminal-medium.en-en.json'],'wimbledon-r1':[A/'window-context/wimbledon-terminal-turbo-en.json',A/'window-context/wimbledon-call-large-large-v3-en.json'],'rg-qf':[A/'window-context/rg-fr-small-fr.json',A/'window-context/rg-fr-turbo-fr.json',A/'window-context/rg-pa-large-large-v3-fr.json']}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows={};packets=P/'foreground-packets';packets.mkdir(exist_ok=True)
for key,(source,a,b,cues) in D.items():
 src=idx[source];ev=[]
 if key not in ['cold-rome','rome-final','dubai-final']:
  ev.extend([A/f'tail-context/{source}-small.en.json',A/f'tail-context/{source}-medium.en.json'])
 ev.extend(extra.get(key,[]));assert all(f.is_file() for f in ev),(key,ev)
 reviewed_from=min(json.load(open(f))['range'][0] for f in ev);reviewed_to=max(json.load(open(f))['range'][1] for f in ev);assert reviewed_from<=a and reviewed_to>=b
 notes=['Actual local paired ASR; not human listening. Canonical player spelling and obvious ASR name/pronoun mistranscriptions normalized only using official same-match identities; raw retained.','Outgoing native .25s dissolve padding uses audio_tail:silence outside selected body only. No words inside selected body removed.']
 if key=='wimbledon-r1':notes.append('Medium skips noisy368–374 call; small/turbo and independent multilingual large-v3 consistently support biggest win/career meaning. Snigur and Elina canonical spelling; male his from large-v3 is obvious ASR gender error for the visibly identified woman, normalized to her. All raw variants retained. No human ear confirmation claimed.')
 if key=='cold-rome':notes.append('The broad medium speech pass conflates the final so I am glad with the later very happy after applause; focused same-byte534.8–541.8 small.en and medium.en both agree so I am glad ending537.40/537.42. Small hallucinates cheering as Whoa after537.4; medium yields no additional foreground speech. Start at526.76 lies at independently estimated I onset526.74–526.80, after preceding20th clause.')
 no_en=''
 if key=='rg-qf':
  no_en='No intelligible foreground English. Original court ambience includes distant French chair/PA; English-only model outputs are French-to-English hallucinations, not English captions. Three French-capable model attempts fail to give a reliable full French transcription. Original sound is retained, and no French transcript/listening pass is claimed. Parent authorized this honest English-only foreground scope on2026-10-22.'
  notes.append('Non-English background PA transcription remains unverified; this packet is complete only for the required foreground-English inventory, not a French speech audit. No fabricated French subtitles and no muted source.')
 packet={'schema':'tennislive.foreground-audio-packet.v1','source_url':src['canonical_url'],'source_sha256':src['sha256'],'method':'asr_cross_checked','reviewer':'Codex local source-bound paired ASR with source frames; no human listening','reviewed_at':datetime.now(timezone.utc).isoformat(),'reviewed_from':reviewed_from,'reviewed_to':reviewed_to,'status':'complete','uncertain_spans':[],'foreground_english':cues,'no_foreground_english_reason':no_en,'review_notes':notes,'asr_evidence':[{'path':str(f),'sha256':sha(f),'model':json.load(open(f))['model']} for f in ev]}
 if key=='rg-qf':packet['non_english_background_status']='French PA full text unresolved; explicitly not approved as transcribed speech.'
 pp=packets/(key+'.json');pp.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
 row={'key':key,'source_name':source,'source_file':src['path'],'source_url':src['canonical_url'],'source_sha256':src['sha256'],'start':a,'end':b,'frame':'person' if key=='cold-rome' else 'court','cx':.5,'captions':cues,'audio_review_packet':str(pp),'audio_review_packet_sha256':sha(pp),'asr_evidence':packet['asr_evidence'],'audio_tail':'silence','notes':notes,'no_foreground_english_reason':no_en,'ready_for_native_preview':True,'final_film_qc':False}
 if key in labels:
  topic,date,place,people,score,window=labels[key];row['label']={'topic':topic,'date':date,'place':place,'people':people,'score':score};row['label_safe_window_candidate']=window;row['label_safe_window_status']='actual native composition review still required; candidate not automatic visual pass'
 rows[key]=row
out={'schema':'svitolina-selected-source-windows.v1','generated_utc':datetime.now(timezone.utc).isoformat(),'selections':rows,'sources':list(idx.values()),'complete_terminal_match_points':8,'extra_rallies':0,'cold_quote_repeated_in_body':False,'video_body_seconds':sum(r['end']-r['start'] for r in rows.values()),'scope':'Source/audio selection only; actual native captions/card and final encoded-film QC pending.'}
(P/'selections.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('Saved',len(rows),'video windows',out['video_body_seconds'],'seconds',sum(len(r['captions']) for r in rows.values()),'cues')
