import json,hashlib
from pathlib import Path
out=Path('/workspace/scratch/fokina-final-captions'); base=Path('/workspace/tennislive-efficiency/data/source_asr/402fnpRkS3c')
cues=[]
def add(start,end,en,zh,evidence,status='cross_asr_text_supported',note=None):
 c={'id':f'c{len(cues)+1:03d}','start':start,'end':end,'en':en,'zh':zh,'status':status,'evidence':evidence,'timing_method':'existing ASR word timestamps; no acoustic boundary verification'}
 if note:c['note']=note
 cues.append(c)
add(13.30,15.06,'Brilliant start,','开局精彩！',['small:0','medium:0'])
add(16.72,20.94,'and an early break for the 20-year-old,','这位二十岁的小将率先破发，',['small:0','medium:0'])
add(20.94,24.50,'appreciated by the two-time former champion.','两届赛会冠军也为他鼓掌。',['small:0-1','medium:0'],'cross_asr_text_supported','“two-time former champion”是原解说称呼；字幕不自行补出看台人物姓名。')
add(26.30,28.38,'There is again the drop shot,','又是一记放短，',['small:2','medium:1'])
add(28.52,30.48,'but this is exquisite.','处理得真是精妙。',['small:2','medium:1'])
add(99.68,101.54,"It's sensational!",'太精彩了！',['small:5','medium:5'],'cross_asr_text_supported','small只识别Sensational；It\'s来自medium，概率0.458，可仅保留Sensational避免添入低确定性起词。')
add(104.84,107.12,'And a second break is secured.','再度完成破发。',['small:6','medium:5'])
add(121.68,124.70,'And a flawless set of tennis','这一盘打得无可挑剔，',['small:7','medium:7'],'cross_asr_text_supported','与后续for Rafael Jodar组成同一句；中间有裁判报分重叠，见a003。')
add(126.72,128.66,'for Rafael Jodar.','拉斐尔·霍达尔的表现太出色了。',['small:7','medium:9'],'cross_asr_text_supported','人名按已核实的真实对阵规范拼写；不把for改成独立宣布胜者。')
add(142.50,144.04,'Outrageous!','简直不可思议！',['small:8','medium:10'])
add(149.04,150.32,'Yes!','好球！',['small:9','medium:11'])
add(151.96,153.46,"Don't forget about me,",'“别忘了，我还在！”',['small:10','medium:12'])
add(154.66,156.16,'says Davidovich Fokina.','福基纳用表现作出了回应。',['small:11','medium:13'],'cross_asr_text_supported','上一cue是解说代入球员的修辞，并非声称球员真的说出这句话。')
add(162.28,166.20,'A disappointing end to the game.','这一局的收尾令人失望。',['small:12','medium:14'])
add(173.90,175.96,'Oh, that is remarkable!','噢，太不可思议了！',['small:12','medium:15'])
add(181.26,185.58,'What a chase from Davidovich Fokina','福基纳这次追球太惊人了，',['small:13','medium:16'])
add(189.70,191.46,'to get his first break of the match.','拿下了本场第一次破发。',['small:13','medium:16'],'cross_asr_text_supported','两档把to拉长185.5..190.04；字幕采用189.70以避免4秒以上单个介词显示。该起点不是已做声学核验的真实词头。')
add(222.44,223.76,'Oh!','噢！',['small:14','medium:19'])
add(227.70,228.42,'Jaw-dropping!','令人瞠目结舌！',['small:14','medium:19'])
add(229.08,230.94,'How good that is!','这一球打得太棒了！',['small:14','medium:20'],'cross_asr_context_selection','small为cute，medium为good；语境与相同含义优先medium，仍非人工听辨。')
add(253.54,256.16,'What an effort,','多么顽强的拼搏，',['small:15','medium:21'])
add(256.56,260.68,'once again from Davidovich Fokina.','福基纳再一次做到了。',['small:15','medium:21'])
add(260.68,264.64,'Down a set and a break in the final in Shanghai.','上海决赛中，他一度落后一盘和一个破发。',['small:16','medium:22'],'cross_asr_context_selection','small为Down the set；medium为Down a set，采用medium。中文过去情境结合其刚扳回次盘的画面，不虚构眼下仍落后。')
add(284.96,286.24,"He's punished him.",'这一球给了对手有力回击。',['small:17','medium:23'])
add(295.44,297.56,'This time he converts.','这一次，他兑现了破发点。',['small:18','medium:25'],'cross_asr_context_selection','破发点由本场原画面第三盘0-0/AD福基纳确认；原词converts。')
add(358.42,359.68,'A second break.','第二次破发。',['small:21','medium:28'],'cross_asr_text_supported','A/The冠词不一致；共同可确认second break。可改为Second break.避免强断冠词。')
add(404.50,405.40,'That was my thought.','我刚才也是这么想的。',['small:25','medium:30'],'cross_asr_text_supported','前一问句见a008，尚不能当已解决。')
add(405.40,405.80,'Yeah.','是的。',['small:25','medium:30'])
add(440.64,443.88,'Alejandro Davidovich Fokina','亚历杭德罗·达维多维奇·福基纳，',['small:26','medium:36'],'cross_asr_text_supported','人名规范化；与下一cue为一个完整夺冠宣布句，不能在445.5切掉后半句。')
add(443.88,450.48,'claims a maiden Masters 1000 title in Shanghai.','在上海夺得生涯首座大师赛冠军！',['small:26','medium:36'])
add(454.50,458.36,'A week where he has proved his resilience.','这一周，他证明了自己的坚韧。',['small:27','medium:37'],'cross_asr_text_supported','small起点453.8但A延伸到455.12；medium词起点454.50。采用medium词起点。')
add(460.68,465.76,'He has worked his way through so many difficult situations,','他闯过了一个又一个艰难关口，',['small:28','medium:38'])
add(466.22,469.98,"but it's a third title of the season.",'最终拿下了本赛季第三个冠军。',['small:28','medium:38'])
# Only audibly plausible, unresolved draft text lives separately; never silently publish it.
a=[]
def amb(id,start,end,issue,small,medium,recommendation,draft_en=None,draft_zh=None):
 x={'id':id,'start':start,'end':end,'issue':issue,'small_text':small,'medium_text':medium,'recommendation':recommendation,'publication_ready':False}
 if draft_en:x['draft_en']=draft_en
 if draft_zh:x['draft_zh']=draft_zh
 a.append(x)
amb('a001',49.68,53.04,'明显两档冲突：medium机械复制26秒的整句话且多个零长词；small语句也有语法/人名问题。','82% are first served at the Dvitovich-Vakina.','There is again the drop shot, but this is exquisite.','补核原声/独立可靠识别，不得把percentage统计当已证实事实写入字幕。')
amb('a002',66.74,69.48,'仅medium短句且词概率0.454..0.648；small未识别。',None,"1st. / Let's walk up.",'不把可能裁判/背景声猜成解说；音频补核。')
amb('a003',120.66,128.66,'裁判报分与主解说重叠，ASR混串；中间six games to one可能真实，the new one for Leeds不可信。','And the flawless Cheddar Tennis, the Rafael Hodar.','Game and a flawless set of tennis / Six games to one, the new one for Leeds. / For Rafael Hoddar.','已保留跨档主解说共同支持句；裁判报分需听辨后补独立cue。不能单凭比分板反推出原声逐字。')
amb('a004',193.98,198.22,'medium独有完整一句；nuclear形容词可能识别错误，small漏整句。',None,'The nuclear athleticism that is so often associated with this guy.','需补核首个形容词；后半高置信度可成草稿，未声学确认前不假称逐字可靠。','The [unclear] athleticism that is so often associated with this guy.','这位球员一贯展现的惊人运动能力。')
amb('a005',213.24,214.96,'medium独有：great词概率0.194；small无。',None,'Oh, great point.','可保留双语草案，但明确待补听，不能据画面自行认定原词。','Oh, great point.','噢，精彩的一分。')
amb('a006',311.62,314.38,'共同前后句明确，中间at play/up very冲突；可能网球习语at bay，但未经听辨不得替换。',"Couldn't keep him at play long enough.","Couldn't keep him up very long enough.",'原声补核at bay还是其他词；不可用习语合理性替代证据。',"Couldn't keep him [unclear] long enough.",'没能让他……坚持得足够久。')
amb('a007',359.46,376.46,'small Nivel’s clean与重复no；medium未识别，可能裁判、背景噪音或幻觉。',"Nivel's clean. / Game, no, no, no, no, no. / Game, no, no, no, no, no, no.",None,'需补核，暂不生成伪解说。')
amb('a008',402.50,404.50,'两档均record，但画面脚部事件可能是racket；问句Did/Then及at/with冲突。','Then he hit himself with the record,','Did he hit himself at the record','只记录可见脚部/鞋事件；不得先写受伤/砸脚。补听是否Did he hit himself with the racket?，下一回应已双档稳定保留。','Did he hit himself [unclear]?','他是不是碰到自己了？')
amb('a009',320.68,350.66,'medium从1数到24且后面9词零长；small为15-1/11-30，严重冲突，均不像稳定解说。','15-1 / 11-30','1, 2, 3, ... 24','保留原音，不烧录数字幻觉；若确有裁判报分需独立补听。')
amb('a010',413.00,431.82,'medium一串3,2,1和反复1,2,1，初词概率0.01..0.015，small无任何对应。',None,'3, 2, 1 / 1, 2, 1 / 1, 2, 1 / 1, 2, 1 / 1, 2, 1','明显数字幻觉候选，不烧录；仍不能声称该区间绝无真实讲话。')
amb('a011',56.94,58.34,'small独有Yeah且p0.15；medium无。','Yeah.',None,'待声学核实，不假设为解说。')
for start,end,seg in [(113.04,113.10,6),(290.68,291.10,24),(383.50,383.98,29)]:
 amb('a'+str(len(a)+1).zfill(3),start,end,'medium独有低概率Oh感叹，无small对应。',None,f'medium:{seg} Oh','作为低可信背景感叹记录；补核后可双语保留Oh!/噢！。')
(out/'cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2)+'\n')
(out/'ambiguities.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
report={
 'source':{'video_id':'402fnpRkS3c','sha256':'805bfda10e11ffccc9f1ecc03db4af4661c5ead00d4858d4625c70618737c975','duration_seconds':480.211882,'reviewed_interval':[0,470.18]},
 'asr_versions':[{'path':str(base/(n+'.en.json')),'sha256':hashlib.sha256((base/(n+'.en.json')).read_bytes()).hexdigest(),'model':n+'.en','segments':len(json.loads((base/(n+'.en.json')).read_text())['segments'])} for n in ['small','medium']],
 'method':'逐段比较两档ASR文本与已有ASR词时码；结合另两名智能体实际源画面ledger纠正对阵人名和情境。未获得直接音频感知输入，未人工听辨。双档同属Whisper，不能视为独立人类听审或完全独立模型证据。',
 'cue_count':len(cues),'ambiguity_count':len(a),'en_max_chars':max(len(c['en']) for c in cues),
 'full_speech_coverage_certified':False,'all_cues_acoustically_verified':False,'human_listening_claimed':False,
 'publication_ready':False,'reason':'至少14个有限歧义范围尚未补核；目前cues是有证据支持的双语草稿，不能称完整逐句原声字幕。原ASR真实解说段仅29/39，不能为达到60-100条而编词或机械分字。',
 'end_announcement':{'complete_sentence_start':440.64,'complete_sentence_end':450.48,'preferred_edit_window':[440.60,450.56],'english':'Alejandro Davidovich Fokina claims a maiden Masters 1000 title in Shanghai.','warning':'439.24..445.5截断claims后的宾语，不能当完整句冷开。'},
 'span_accounting':'两档每段均已纳入支持cues或歧义；中间无ASR文字不等于已证实无讲话。保留原8分钟比赛有效段，待根补核清单，避免丢真实解说。',
 'span_timing_limits':'词时码存在长停顿词/零长度词/重叠，尤以185.5..190.04的to及253..264、453.8首词。没有执行声学重对齐；单cue时码可用作剪辑草稿，尚非全部真实词边界证明。',
 'camera_signature':{'observed_in_reviewed_video_ledgers':False,'image_reading':'APERTURA ESPAÑOLA / CAMBIO DE TERCIO','note':'用户另发图片不能当成本条视频内存在的证据；不写入原声字幕。西语apertura española可为西班牙开局/国际象棋西班牙开局，cambio de tercio为转换话题/转个方向，不能据同国对手直接断言作者唯一意图。'},
 'production_files_changed':False,'dispatch_or_publication_performed':False,
}
(out/'method-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
assert all(0<=c['start']<c['end']<=470.18 for c in cues)
assert all(cues[i]['end']<=cues[i+1]['start'] for i in range(len(cues)-1))
print(json.dumps({'cues':len(cues),'ambiguities':len(a),'max_en_chars':report['en_max_chars'],'ready':False},ensure_ascii=False))
