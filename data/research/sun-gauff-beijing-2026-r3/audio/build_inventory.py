import json,hashlib,datetime
from pathlib import Path
root=Path(__file__).parent
rows=[
(0.0,5.24,'The serve is definitely, the second serve, definitely probably the weakest link of her game.','她的发球，尤其二发，显然可能是她比赛中最薄弱的一环。','resolved'),
(27.58,30.32,'But I like her mentality, though.','但我很欣赏她的心态。','uncertain_pronoun'),
(36.34,39.8,'Anytime you pick the serve, that’s your confidence.','待核实，不使用译文。','uncertain_wording'),
(54.54,58.78,'Oh, Coco has the answer, but she kept being posed the problem.','科科虽然找到了答案，但对手一直在给她出难题。','resolved'),
(59.14,60.94,'The questions were there from Sun.','孙心然一直在提出考验。','uncertain_name'),
(61.04,65.5,'Do it over and over. It’s high topspin to the forehand of Sun.','待核实，不使用译文。','uncertain_wording'),
(74.32,77.28,'Hit that backhand like that.','待核实，不使用译文。','uncertain_wording'),
(76.88,81.46,'I think Coco knew she needed it too. You could hear the come on from her.','我想科科也知道自己需要这一分。你能听到她喊了声“加油”。','uncertain_wording'),
(81.64,85.7,'Dip below sixty degrees Fahrenheit, low teens Celsius.','气温降到了华氏六十度以下，摄氏十几度。','resolved'),
(103.88,105.66,'Quality stuff from the youngster.','这位小将打得真漂亮。','resolved'),
(105.98,106.68,'Nice.','漂亮。','uncertain_foreground'),
(131.22,133.7,'She just continues to bash the ball.','她还在不断大力击球。','uncertain_interjection'),
(134.65,136.94,'I mean, just continue to watch.','待核实，不使用译文。','uncertain_wording'),
(136.88,139.86,'And Sun is back on the lettering on the court.','待核实，不使用译文。','uncertain_name'),
(140,143.59,'Two points from losing with Swiatek before she won in three.','待核实，不使用译文。','uncertain_wording'),
(160.24,164.24,'Oh, it’s all right in front of her.','机会就在她眼前。','uncertain_interjection'),
(184.84,190.18,'I think she has understood the one thing, Coco, is that…','待核实，不使用译文。','uncertain_incomplete_source_sentence'),
(194.25,199.8,'And Coco Gauff back out in front for the first time in forty minutes, and she’s got triple set point.','科科·高芙时隔四十分钟再度领先，她拿到了三个盘点。','resolved'),
(202.28,203.86,'And it’s a swing and a miss.','这一拍挥空了。','resolved'),
(204.24,205.72,'And that’s a little deflated look.','她的神情有些低落。','resolved'),
(205.66,211.82,'The shoulders have fallen for Sun Xinran, because Coco Gauff finds a way to earn the opening set.','孙心然垂下了肩膀，科科·高芙还是设法拿下了首盘。','uncertain_name_boundary'),
(211.84,215.04,'It wasn’t easy, but she gets it done in just short of an hour.','并不容易，但她在不到一小时内拿下了首盘。','resolved'),
(214.62,217.72,'Good on you, Billie Jean.','待核实，不使用译文。','uncertain_wording'),
(226.5,229.8,'Well done. Just stay with it.','打得好。继续坚持。','uncertain_wording'),
(243.32,247.0,'Coco, relentless. She loves the middle of the court today.','科科毫不松懈。今天她很喜欢利用场地中路。','resolved'),
(266.56,272.42,'And Coco Gauff continues to refuse to lose before the semifinals in Beijing.','科科·高芙在北京延续了半决赛前的不败纪录。','resolved'),
(276.24,278.75,'Well, on paper it looked like it was going to be a beatdown.','从纸面实力看，这本应是一场悬殊的较量。','resolved'),
(279.04,281.99,'Number four in the world versus five eighty-two.','世界第四对阵世界第五百八十二。','resolved'),
(282.11,285.63,'The opening set was more competitive than anyone could have imagined.','首盘比任何人想象的都更激烈。','resolved'),
(285.63,291.61,'But in the end, it’s Coco Gauff who strikes a commanding pose in the second set, as she runs away with it.','但最后，科科·高芙在第二盘展现了压倒性的优势，一路拉开差距。','resolved'),
(291.61,298.74,'And now she finds her way to the round of sixteen at this WTA one thousand event with a seven-five, six-one win.','她最终以七比五、六比一获胜，晋级这站 WTA 一千赛十六强。','resolved'),
]
utterances=[{'id':i,'start':a,'end':b,'en':en,'zh':zh,'status':status} for i,(a,b,en,zh,status) in enumerate(rows)]
p={'source_url':'https://www.youtube.com/watch?v=Wg6m85wS3Ps','source_sha256':'79951bd5316ac8910ce6fc1200260c62492d1f791ed3690729dadeb7a6296b90','method':'asr_cross_checked','reviewer':'Codex broadcast_audio agent','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewed_from':0,'reviewed_to':298.74,'status':'partial','foreground_english':utterances,'uncertain_spans':[{'start':r['start'],'end':r['end'],'id':r['id'],'reason':r['status']} for r in utterances if r['status']!='resolved'],'evidence':['tiny.en-full.json','base.en-full.json','base.en-refined.json','small.en-refined.json','medium.en-priority.json'],'notes':['Independent tiny.en and base.en reviewed full 425.48s source; small.en full-source raw log is partial and not claimed complete, stopped after 382.85s because interview is unused and English forcing over Chinese created hallucinations.','All bilingual cue timings are absolute source seconds. Conservative inventory times are unions across ASR; final packets will use inspected word boundaries.','Proper-name spelling Gauff is normalized from repeated Golf/Gough ASR variants against source player identity. Other name ambiguities remain explicitly unresolved until third-model evidence.','No human listening claim; method is asr_cross_checked.']}
(root/'commentary-inventory-draft.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
