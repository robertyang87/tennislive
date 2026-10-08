from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,re
repo=Path('/workspace/tennislive-repo')
path=repo/'specs/reels/djokovic-medvedev-beijing-2026-sf.json'
spec=json.loads(path.read_text());slug=spec['slug']
manifestpath=repo/'data/audio_reviews'/f'{slug}.json'
manifest=json.loads(manifestpath.read_text())
wraps={
'Oh well, that could have been pretty nasty.':'噢，刚才那一下\n可能会相当危险。',
'But what a response from Novak Djokovic.':'但诺瓦克·德约科维奇\n回应得太精彩了。',
'Yeah! Yeah! Yeah! Yeah! Yeah! Yeah!':'呀！呀！呀！\n呀！呀！呀！',
'The shot beforehand from Djokovic.':'说的是德约科维奇\n前一拍的击球。',
'Djokovic collapses to the ground in a heap.':'德约科维奇一下\n倒在了地上。',
"That's a brilliant combination from Djokovic.":'德约科维奇这一组\n击球组合太精彩了。',
}
splits={
'After the most extraordinary level in this match, it has ended on a Medvedev default.':[
 (360.60,362.56,'After the most extraordinary level','打出极其非凡的水准后，'),
 (362.56,363.54,'in this match,','这场比赛'),
 (363.72,366.06,'it has ended on a Medvedev default.','却以梅德韦杰夫\n被判失格结束。')],
'Oh well, that could have been pretty nasty.':[
 (89.40,91.42,'Oh well, that could have been','噢，刚才那一下可能会'),
 (91.42,92.70,'pretty nasty.','相当危险。')],
'But what a response from Novak Djokovic.':[
 (92.74,93.86,'But what a response','但这记回应太精彩了'),
 (93.86,94.90,'from Novak Djokovic.','来自诺瓦克·德约科维奇。')],
'A ridiculously physical opening set of tennis.':[
 (161.98,164.04,'A ridiculously physical','体能消耗惊人的'),
 (164.04,165.50,'opening set of tennis.','首盘比赛。')],
'But this time he does find a way through.':[
 (267.18,268.58,'But this time','但这一次'),
 (268.58,270.78,'he does find a way through.','他终于找到了突破口。')],
'Oh, he just went straight back at him.':[
 (309.36,310.84,'Oh, he just went straight','噢，他直接回击'),
 (310.84,311.50,'back at him.','朝对手打了回去。')],
'Djokovic collapses to the ground in a heap.':[
 (311.62,313.52,'Djokovic collapses to the ground','德约科维奇倒向地面'),
 (313.52,314.14,'in a heap.','整个人一下瘫倒了。')],
'Just a flurry of errors from Medvedev.':[
 (345.54,347.00,'Just a flurry of errors','突然连续出现失误'),
 (347.00,348.62,'from Medvedev.','来自梅德韦杰夫。')],
"That's a brilliant combination from Djokovic.":[
 (352.24,354.36,"That's a brilliant combination",'这一组击球组合太精彩了'),
 (354.36,355.26,'from Djokovic.','来自德约科维奇。')],
'And Djokovic continues to play the big point so well today.':[
 (194.80,196.84,'And Djokovic continues to play','而德约科维奇依旧'),
 (196.84,198.80,'the big point so well today.','今天的关键分\n打得那么出色。')],
"Well, no real protest from Daniil Medvedev, but it's hard to argue with the decision from Mohamed Lahyani and the the ATP supervisor there.":[
 (369.90,371.38,'Well, no real protest','并没有真正的抗议'),
 (371.38,373.36,'from Daniil Medvedev,','来自梅德韦杰夫，'),
 (373.42,375.40,"but it's hard to argue with",'但很难反驳'),
 (375.40,377.58,'the decision from Mohamed Lahyani','拉希亚尼作出的判罚'),
 (377.58,379.90,'and the the ATP supervisor there.','以及现场ATP监督的判罚。')],
}
sys.path.insert(0,str(repo/'tools'))
from foreground_audio_gate import plan_hash,require,_text
from build_match_reel import _quote_lines_fit_the_frame,quote_overflow_rows,load_spec
count=0
for entry in manifest['segments']:
 i=entry['index'];seg=spec['segments'][i];packetpath=repo/entry['transcript_path'];packet=json.loads(packetpath.read_text())
 original=packet.get('original_sentence_utterances',packet['foreground_english'])
 packet['original_sentence_utterances']=original
 utterances=[]
 for row in original:
  if row['en'] in splits:
   parts=splits[row['en']]
   if _text(' '.join(p[2] for p in parts))!=_text(row['en']):raise ValueError('split dropped original English')
   utterances.extend({'start':a,'end':b,'en':en,'zh':zh} for a,b,en,zh in parts)
  else:
   new=dict(row);new['zh']=wraps.get(row['en'],row['zh']);utterances.append(new)
 packet['foreground_english']=utterances
 packet['caption_layout_method']='Native subtitles: English preserved exactly and split only at actual word timestamps into consecutive semantic clauses; explicit Chinese line breaks preserve complete meaning with each line <=16 Chinese widths. Original sentence transcript retained in original_sentence_utterances. No source selection changes.'
 packet['reviewed_at']=datetime.now(timezone.utc).isoformat()
 packetpath.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
 entry['transcript_sha256']=hashlib.sha256(packetpath.read_bytes()).hexdigest()
 start=seg['start'];speed=seg.get('speed') or 1
 seg['quote']=[{'at':round((u['start']-start)/speed,3),'end':round((u['end']-start)/speed,3),'text':u['en']+'\n'+u['zh']} for u in utterances]
 count+=len(utterances)
_quote_lines_fit_the_frame(spec)
manifest['plan_sha256']=plan_hash(spec);manifest['reviewed_at']=datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n');manifestpath.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
sources={'main':Path('/workspace/tennislive-media/LgRD3TLoxr0.mp4')}
require(spec,root=repo,sources=sources);require(load_spec(path),root=repo,sources=sources)
report={'native_quote_overflow_rows':quote_overflow_rows(spec),'cues':count,'raw_gate':'pass','normalized_gate':'pass','plan_sha256':manifest['plan_sha256'],'source_sha256':packet['source_sha256']}
(repo/'data/research'/slug/'audio/layout-repair-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
