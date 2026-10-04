from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
p=Path(__file__).parent
rows=[
('opening_out',7.0,8.3,'Out it goes.','球出界了。'),
('opening_name',9.48,13.84,'That is Alexander Zverev, who wastes very little time.','亚历山大·兹维列夫很快就抓住了机会。'),
('exquisite',29.3,32.24,'Oh, yes! Exquisite!','好球！太精妙了！'),
('gets_him',39.5,40.3,'Gets him!','他得手了！'),
('djokovic_exclamation',41.22,42.48,'Oh, Djokovic!','哦，德约科维奇！'),
('zverev_exclamation',71.16,74.8,'Oh! Alexander Zverev!','哦！亚历山大·兹维列夫！'),
('missed_bp',98.3,101.98,"Well, Djokovic didn't take advantage there.",'德约科维奇没能抓住这个机会。'),
('hustle',102.9,105.08,'Great hustle from Zverev.','兹维列夫奋力救球。'),
('firstset_verdict',108.2,112.82,'The set does go the way of our top seed, Alexander Zverev.','头号种子亚历山大·兹维列夫拿下这一盘。'),
('no_way',127.18,130.4,'Oh, no way!','哦，难以置信！'),
('got_it',131.02,131.98,"He's got it!",'他打成了！'),
('remarkable',133.28,135.62,'That is remarkable!','这太不可思议了！'),
('beautiful',147.4,149.1,'Oh, beautiful!','哦，太漂亮了！'),
('placements',150.2,151.8,'Perfect placements.','落点太精准了。'),
('puts_away',167.78,169.02,'Puts it away!','他把这一球打死了！'),
('big_time',169.38,171.58,'Comes up with a big-time play.','关键时刻打出了精彩一击。'),
('brilliant',187.4,189.04,'Brilliant!','太精彩了！'),
('place_loves',192.24,193.82,"It's a place he loves.",'他爱这片场地。'),
('stretching',212.54,214.62,'Oh, he was stretching there, Zverev.','哦，兹维列夫奋力伸展开来救球。'),
('extra_pace',225.76,228.56,'Injecting the extra pace up the line.','沿直线打出了更快的球速。'),
('breathing',269.0,271.86,"I don't think anybody breathing.",'我觉得大家都屏住了呼吸。'),
('done_again',280.46,282.74,"He's done it again!",'他又做到了！'),
('novak_name',283.9,285.66,'Novak Djokovic.','诺瓦克·德约科维奇。'),
('place_reflection',288.1,290.38,"There's something about this place.",'这片场地有些特别之处。'),
('man_reflection',293.34,295.62,'And there is something about this man.','而这个人也有些特别之处。'),
('unbeaten',296.26,299.96,'The unbeaten record here in Beijing continues.','他在北京的不败纪录仍在延续。'),
('breathe_in',303.96,305.32,'Breathe it in.','尽情感受这一刻。')
]
cues=[dict(id=i,start=a,end=b,en=en,zh=zh,text=en+'\n'+zh,status='asr_cross_checked_candidate') for i,a,b,en,zh in rows]
notes={
'opening_out':'Resolved using third independently downloaded large-v3-turbo tight7.06–8.18 Out it goes and three offset small.en tight outputs. Medium.en sound-alike variants kept in raw evidence.',
'gets_him':'Third turbo isolated38–40.8 says Gets him; targeted medium.en says Gets him; small.en full Get him sound-alike supports same. General Chinese preserves meaning without inventing shot type.',
'placements':'Third turbo context and tight both placements(p0.825), small.en context and tight consistently placements; medium.en/base singular documented as minor recognition difference.',
'stretching':'Third turbo context and tight independently match Oh he was stretching there Zverev; medium.en/base phonetic ending variants are compatible with verified surname. No invented backhand/drop/angle term.',
'zverev_exclamation':'All passes have exclamation plus phonetic Alexander Zverev; multilingual spelling/small.en Sverif/medium.en Alex Alvis-Verif normalized from independently verified match identity. Interjection covers71.16–72.58; name73.6–74.8, split for final captions if needed.',
'breathing':'Four full passes and both targeted English passes agree content I do not think anybody breathing; no invented is has been added. Start chosen near actual word cluster270 after low-confidence long silence alignment. Earlier266.8–268.2 phrase still unresolved and must be handled separately.',
'novak_name':'medium.en full and targeted agree Novak Djokovic with0.99 proper-name probability; small.en No Bank Djokovic and multilingual phonetic forms resolved from verified match identity.',
'puts_away':'Both full English passes agree puts; targeted medium singular put variant documented, not a different utterance.',
'unbeaten':'No invented victory count; only the record actually mentioned in broadcast is translated.'}
for c in cues:
 if c['id'] in notes:c['review_note']=notes[c['id']]
uncertain=[dict(start=266.44,end=268.56,text='How/Out/And it goes',reason='Independent small.en/medium.en context=How, turbo context=How(p0.054), turbo tight/offset=And(p0.279); unresolved. This exact local span must not retain original speech without listening. Next sentence starts after this span, approx269.0–271.86; preserve it independently.')]
evidence=[dict(path=str(f.relative_to(p.parents[3])),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),model=json.loads(f.read_text()).get('model')) for f in sorted((p/'raw').glob('*.json')) if json.loads(f.read_text()).get('schema')=='tennislive.raw-asr-evidence.v1']
packet=dict(schema='tennislive.original-audio-cue-proposal.v1',source_url='https://www.youtube.com/watch?v=cjaHThpISKk',source_path='/workspace/djokovic-cja-research/source/cjaHThpISKk.mp4',source_sha256='2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2',created_at=datetime.now(timezone.utc).isoformat(),method='asr_cross_checked',actual_listening_performed=False,reviewer='OpenAI original_audio: actual source Whisper base/small auto-language, small.en/medium.en noVAD full/targeted plus large-v3-turbo third-model crosscheck; no audio perception available',status='candidate_requires_final_window_binding',timestamp_convention='source-absolute seconds; segment quote at/end must subtract source start',cues=cues,uncertain_spans=uncertain,raw_evidence=evidence,coverage_notes=['YouTube source-caption retrieval failed with429; no captions.txt used.','Small/base auto-language probabilities0.9913/0.9423 confirmed English.','False Thank you in248–256 is absent in both targeted English passes; do not print it.','313.05–319.18 is digitally silent according to probe; inconsistent You/Thank you hallucinations excluded, final video ends309.1.','All selected windows must separately enumerate every foreground utterance; this candidate list does not certify arbitrary TTS windows or final spec.'])
(p/'candidate-cues.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
lines=['# 真实原声候选字幕（源绝对秒）','', '方法：实际音轨4种Whisper全源、两种英语模型短窗及large-v3-turbo第三模型交叉核验；未实际耳听，不声称人工审听。最终窗口仍须绑定。','']
for c in cues:lines +=[f"- {c['id']} {c['start']:.2f}–{c['end']:.2f}: {c['en']}",f"  {c['zh']}"]
lines +=['','## 暂不能签完整的语句','']
for c in uncertain:lines+=[f"- {c['start']:.2f}–{c['end']:.2f} {c['text']}：{c['reason']}"]
(p/'candidate-cues.md').write_text('\n'.join(lines)+'\n')
