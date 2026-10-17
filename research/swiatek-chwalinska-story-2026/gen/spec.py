import json,sys
sys.path.insert(0,'research/swiatek-chwalinska-story-2026/gen')
from labels import LABELS
V={"pitch":"+10Hz","_why":"网球有故事沿用云健 +18% 语速、+10Hz 音高（与 medvedev-not-villain-2026 同一档）。"}
A='assets/reel/swiatek-chwalinska'
def lab(k):
    return {"image":f"{A}/label-{k}.png","kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":7.0,"motion":"editorial","label":dict(LABELS[k])}
def n(src,a,b,text,why,ok="不是回合的收尾：画面是局间、近景、庆祝或采访，段尾不在一分打到一半。",label=None,crosses_cut=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":text,"voice":dict(V),"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    if crosses_cut: s["crosses_cut"]=crosses_cut
    return s
# 段与段之间有 0.18 秒溶解：原声字幕离段边至少 0.22 秒，否则会和相邻旁白段的窗口重叠。
EDGE=0.22
def q(src,a,b,cues,why,ok,label=None,kind="broadcast"):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":"","quote":[{"at":round(max(x-a,EDGE),2),"end":round(min(y-a,(b-a)-EDGE),2),"text":t} for x,y,t in cues],"_quote_kind":kind,"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    return s
def live(src,a,b,why,skip,ok,label=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":"","_quote_skip_why":skip,"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    return s
def card(title,kicker,sec,text):
    return {"title_card":title,"kicker":kicker,"seconds":sec,"narration":text,"voice":dict(V)}
def photo(img,sec,text,why,src,safety):
    return {"image":f"{A}/{img}","image_kind":"photo","seconds":sec,"narration":text,"voice":dict(V),"_why":why,"_photo_source":src,"_photo_caption_safety":safety}
AO17="https://photoresources.wtatennis.com/photo-resources/2022/06/24/4cb6065c-9ea4-437c-ba73-4dc22ffb9f63/Chwalinska-Swiatek-Andreescu-Branstine-AO-2017.jpg"
M22="https://photoresources.wtatennis.com/photo-resources/2022/07/01/c79d925c-9c03-4dea-baf0-b43793e86ef1/Chwalinska-R2-Jimmie.jpg"
S=[]
# 冷开场：赫瓦林斯卡武汉 1/4 决赛赛点与赛后（WTA 官方集锦解说原声）
c=q("wuhm",261.0,280.3,[(268.0,269.8,"In a season of dreams,\n在这个梦幻般的赛季，"),(270.36,274.9,"Maja Chwalinska comes through, emerging battle-hardened\n赫瓦林斯卡历经苦战，"),(275.3,276.54,"to defeat Maria Sakkari\n击败萨卡里，"),(276.54,279.5,"to reach her third career WTA semifinal.\n生涯第三次跻身巡回赛四强。")],
  "冷开场：WTA 官方集锦（0-v-yZvYAk8）赛点那一分（261 起记分条挂 MATCH POINT，萨卡里发球）、她蹲在场上（268）、握手。解说两档一致（small 268.08–279.42；medium 268.00–283.74 一整句），字幕沿用已发布 chwalinska-sakkari-wuhan-2026-qf 第 10 段的审听稿。段尾 280.3 在下一句 What an effort（281.16）之前。",
  "赛点这一分在 266 秒前后打完，之后是庆祝与握手。")
c["_ending_payoff_required"]=False
c["_ending_payoff_why"]="网球有故事：冷开场是本期由头（明天的半决赛对手是怎么来的），正文讲两人十年的来路，回到武汉这一周时用同一场的第三盘回合交代过程，不重放赛点。"
S.append(c)
S.append(q("wuhs",290.6,299.3,[(290.88,294.7,"As Iga Swiatek rolls through in straight sets,\n斯瓦泰克直落两盘过关，"),(294.7,296.9,"six-four, six-one,\n6比4、6比1，"),(296.9,299.34,"and will face fellow Pole Maja Chwalinska in the semifinals.\n半决赛将对阵同胞赫瓦林斯卡。")],
  "同一天晚上斯瓦泰克的八强战，WTA 官方集锦（O8f_vcT29uY）赛后握手、致意。解说两档一致（small 290.88–299.14；medium 291.32–299.34），字幕沿用已发布 swiatek-li-wuhan-2026-qf 第 8 段的审听稿。段首 290.6 在上一句（290.10 结束）之后；段尾 299.3 在 WTA 片尾卡（299.5 起）之前。",
  "比赛已经结束，握手和致意。"))
# 宣传片式闪回：四个快切（只留现场声与原声），再上片名字卡
S.append(q("pol15",31.6,34.3,[(31.88,33.92,"Jesteśmy mistrzami Europy!\n我们是欧洲冠军！")],
  "闪回①：Polsat Sport 2015 年采访（-Vsfptr_DC8），14 岁的两人和队友捧着奖杯喊出来。两档波兰语转写：small 31.88–33.92 mistrzami、medium 31.90–33.82（记成 miejscami），按语义与 small 写。段尾 34.3 在教练开口（34.56）之前。","采访，不是回合。",kind="ceremony"))
S.append(card("波兰双子星","从青梅竹马到巅峰相见",10.0,"十二年前，她们第一次隔网。九年前，她们站上同一个领奖台。这一次，只有一个人能走进决赛。"))
S.append(photo("ao2017-podium.jpg",12.0,"十月十七号晚上，武汉一千赛半决赛，斯瓦泰克对赫瓦林斯卡。一千赛的半决赛，第一次由两个波兰人来打。",
  "WTA 官方图库 photo 2655257（4935×3290，取 width=4000 版本）：说明原文「Left to right: 2017 Australian Open girls' doubles runners-up Maja Chwalinska and Iga Swiatek; and champions Carson Branstine and Bianca Andreescu」。裁左边两人（1800×2400，3:4，未放大）。「一千赛半决赛第一次两个波兰人」出自 WTA 4593212。",AO17,
  "两人的脸在画面上部 15%–30%，底部字幕区是奖盘和短裤，不压脸。"))
S.append(card("一起开始\n打比赛","01",8.0,"赫瓦林斯卡说，感觉自己认识她一辈子了，因为她们是一起开始打比赛的。"))
S.append(q("pol15",3.3,22.95,[(3.5,8.18,"Maja Chwalińska, mam 14 lat,\n我是玛雅·赫瓦林斯卡，14岁，"),(8.62,10.48,"mieszkam w Dąbrowie Górniczej\n住在达布罗瓦古尔尼恰，"),(10.48,16.5,"i trenuję od 7 roku życia.\n7岁开始练球。"),(16.74,18.66,"Nazywam się Iga Świątek, mam 14 lat,\n我叫伊加·斯瓦泰克，14岁，"),(18.78,20.52,"trenuję w Warszawskim Klubie Tenisowym Mera,\n在华沙梅拉网球俱乐部训练，"),(20.66,22.8,"trenuje mnie Michał Kaznowski i gram od 8 lat.\n教练是卡兹诺夫斯基，打球8年了。")],
  "Polsat Sport 官方频道（-Vsfptr_DC8，2015 年两人 14 岁时的采访）。两档波兰语逐词转写（data/source_asr/-Vsfptr_DC8/small.pl.json、medium.pl.json）一致；画面里先是戴发箍的赫瓦林斯卡（5–12 秒），再是站在波兰网协背景板前的斯瓦泰克（18–21 秒）。段尾 22.95 在第三位队友自我介绍（23.06）之前。","采访，不是回合。",kind="ceremony"))
S.append(q("pol15",105.0,118.7,[(105.4,106.5,"Jesteśmy zgrane.\n我们很合得来。"),(106.98,109.1,"Ja z Mają już byłam na kilku drużynówkach,\n我和玛雅打过好几次团体赛，"),(109.16,110.34,"dobrze się znamy,\n很了解彼此，"),(110.44,111.44,"zagadujemy się.\n总有聊不完的话。"),(112.82,115.66,"Czasami oczywiście są jakieś sprzeczki,\n当然，有时也会拌嘴，"),(115.72,118.4,"ale potrafimy szybko to rozwiązać.\n但我们很快就能和好。")],
  "Polsat Sport 官方频道（-Vsfptr_DC8，2015 年两人 14 岁时的采访）。两档波兰语逐词转写（data/source_asr/-Vsfptr_DC8/small.pl.json、medium.pl.json）一致；三人坐在球网前，话筒在中间的斯瓦泰克面前（106–116 秒画面），她说「我和玛雅」。段首 105.0 在上一句（104.0）之后，段尾 118.7 在下一句（124.2）之前。","采访，不是回合。",kind="ceremony"))
S.append(q("pol15",528.2,551.6,[(528.52,531.0,"Nie gram tak jakoś siłowo jak większość dziewczyn,\n我不像大多数女孩那样靠力量，"),(531.04,533.16,"więc gram bardziej tak wszechstronnie,\n所以打得更全面，"),(533.24,536.54,"dużo slice'ów, zmianę rotacji, to jest taka moja gra.\n切削、变旋转，这就是我的打法。"),(536.54,541.46,"I myślę, że w większości meczów to jest kluczem,\n我觉得很多比赛里，关键在于"),(541.54,547.84,"że wygrywam na przykład mecze dzięki temu, że lepiej gram właśnie w takich kluczowych momentach:\n我能在关键分上打得更好："),(547.84,551.26,"slice'y, różne takie zmiany rytmu, a nie tylko bum-bum.\n切削和节奏变化，不只是砰砰砰。")],
  "Polsat Sport 官方频道（-Vsfptr_DC8，2015 年两人 14 岁时的采访）。两档波兰语逐词转写（data/source_asr/-Vsfptr_DC8/small.pl.json、medium.pl.json）一致；戴发箍的赫瓦林斯卡对着镜头（530–548 秒）。段首 528.2 在上一句（522.0）之后，段尾 551.6 在下一句（553.94）之前。","采访，不是回合。",kind="ceremony"))
S.append(n("jfc16",0.3,15.4,"两个人搭档，拿下了欧洲青少年锦标赛，十四岁组和十六岁组的双打冠军。二〇一六年青少年联合会杯决赛，赢下最后一分，她们抱在了一起",
  "匈牙利网协（2016 青少年联合会杯决赛东道主）官方频道「Poland wins Junior Fed Cup 2016」（p9Xzx3vDPJw，25 秒）：最后一分、两人拥抱（7–11 秒）、与美国队握手。两档转写在 0–15.68 都无词（15.68 起 Thank you very much 是握手时的现场声，段尾收在之前）。波兰 2016 年夺冠：ITF 稿《Poland defeats USA to take Junior Fed Cup title》（itftennis.com/news/243760.aspx，维基引用）＋ ZooTennis 2016-10 赛报；欧青赛双打冠军出自 WTA 4593212。",
  "最后一分在 6 秒前后打完，之后是拥抱与握手。",label="jfc16"))
S.append(photo("ao2017-close.jpg",15.0,"那年秋天在斯德哥尔摩，两个十五岁的女孩，第一次在职业赛里交手，斯瓦泰克赢了。几个月后的澳网，两个人搭档，打进青少年女双决赛，拿了亚军。",
  "同一张 WTA 官方图（photo 2655257），裁得更近（两人半身）。斯德哥尔摩 W10 第二轮、两人都 15 岁：WTA 4593212、4593251；2017 澳网青少年女双亚军：WTA 4593212、照片说明。",AO17,
  "两人的脸在画面上部 20%–35%，字幕区压在奖盘和腰部，不压脸。"))
S.append(card("一个登顶\n一个停下","02",5.0,"后来，两个人走上了完全不同的路。"))
S.append(n("rg20",364.5,375.0,"二〇二〇年，十九岁的斯瓦泰克拿下法网，波兰第一个大满贯单打冠军。后来，她当上了世界第一。",
  "法网官方决赛集锦（OwKaLdNEjlI）：最后两分与冠军点（366–375）。两档转写在 349–375 没有可对上的英文（small 355.66 一句 Oh, I'm sorry 只有 small 有、画面是回合中无人说话，按幻听处理）；375.2 起是法语场内播报（Jeu, set et match），段尾收在之前。","冠军点在 374 秒前后打完，段尾 375.0 停在她捂嘴那一刻。",label="rg20"))
S.append(card("赫瓦林斯卡\n停了下来","2021年",9.6,"同一时间，赫瓦林斯卡却撑不住了。二〇二一年，十九岁的她因为抑郁，暂停了职业生涯。"))
S.append(q("rgpc",364.9,374.7,[(365.24,367.26,"Yeah, I needed to take a break.\n我需要停下来。"),(368.26,374.18,"And I honestly didn't know if I'm gonna come back or not, to be like honest with you.\n说实话，我不知道还会不会回来。")],
  "法网官方频道 2026 法网八强后的赛后发布会（1ihxUf32bQk）：记者问停赛那段日子，只留她说「不知道还会不会回来」这一句。两档逐词一致（medium 365.24–374.18；small 同），YouTube 自动字幕同。段首 364.9 在上一句 live, I think.（364.58）之后，段尾 374.7 在下一句 Yeah, but after like months（374.96）之前。",
  "发布会，不是回合。",kind="ceremony"))
S.append(card("国家队\n队友","2025年联合杯",12.0,"一年后，她回到了赛场。这些年，两个人也一直是国家队的队友。二〇二五年联合杯，她们都在波兰队，一起打进了决赛。"))
S.append(q("uc25",181.3,195.2,[(181.54,184.34,"I think it's the third year in a row we're making semis or better.\n我们连续三年打进四强以上了。"),(184.74,187.9,"So two years ago it was semis, last year it was a final.\n前年是四强，去年是决赛。"),(188.32,190.72,"So you guys answer the question, what's coming tomorrow.\n明天会怎样，你们来回答吧。"),(191.76,194.66,"Team Poland into the finals. Well done, congratulations!\n波兰队打进决赛，恭喜！")],
  "同一条：齐林斯基接受场边采访，赫瓦林斯卡站在他身旁（186 秒画面）。两档一致（medium 181.54–194.66）。段首 181.3 在上一句（181.04）之后，段尾 195.2 在片尾板（196 秒起）之前。",
  "场边采访，不是回合。",kind="ceremony"))
S.append(card("各自的\n高光","03",8.0,"二〇二六年，两个人都等来了自己的高光。先是六月的巴黎，轮到赫瓦林斯卡。"))
S.append(n("rgsf",976.0,991.0,"世界第一百一十四的她，半决赛赢下施奈德。她成了法网历史上第一个，从资格赛打进决赛的球员。",
  "法网官方半决赛集锦（nuivYz2nq08）：赛点那一分（980–988 广角）。两档转写在 971.64–989.02 都无词；之前 948–971 是看台齐喊加油（两档转写对不上，段首避开）。资格赛、世界第 114：WTA 4511564 标题《Who is Maja Chwalinska? Get to know the World No. 114 in the Roland Garros final》＋维基。","赛点在 988 秒前后打完，段尾 991.0 停在她倒在红土上那一刻。",label="rgsf"))
S.append(live("rgsf",993.0,1003.6,"同一条：她躺在红土上、起身与施奈德拥抱、向看台挥手（990–1012）。",
  "这段只有掌声与欢呼：medium 989.02–992.56 一句 Thank you very much, and have a nice day 与 small 987.74–1004.56 的 We will see you in the next match 对不上，画面里没人对着镜头说话，按看台噪声的幻听处理，段首 993.0 避开 medium 那一句；medium 在 992.56–1015.40 无词，段尾 1003.6 在 small 那句幻听（1004.56）之前，后面的庆祝放在开头的闪回里。",
  "赛点已经打完，这是倒地与庆祝。"))
S.append(q("rgsfi",4.4,25.6,[(4.68,7.8,"You are in Roland Garros' final. How does it sound?\n你打进法网决赛了，感觉怎么样？"),(12.62,14.98,"I mean, like a dream, honestly.\n说真的，像做梦一样。"),(15.52,16.9,"I don't know what's going on.\n我都不知道发生了什么。"),(19.92,20.9,"I'm just...\n我只是……"),(21.54,23.1,"Yeah, I don't know what to say.\n我不知道该说什么。"),(23.2,24.98,"I'm sorry. I'm just very happy.\n抱歉，我就是太开心了。")],
  "法网官方频道半决赛场上采访（SdEjFtD4CTU）。两档逐词一致（medium 4.68–24.58；small 4.88–24.54）。段首 4.4 在主持人前半句 The character continues（3.60–4.2，两档转写不一致，不收）之后，段尾 25.6 在 You understand（26.12）之前。",
  "场上采访，不是回合。",kind="ceremony"))
S.append(n("rgf",715.0,726.2,"决赛她输给了安德烈耶娃。可这一趟巴黎，让她的排名从第一百一十四升到了第二十一。",
  "法网官方决赛集锦（WVWjACQ11-Y）：冠军点之后网前握手、安德烈耶娃庆祝。706.8–715.2 是法语场内播报（两档转写对不上，只取其后），726.36 起是播报安德烈耶娃名字，段尾收在之前。排名 114→21：维基 Maja Chwalińska（career-high No. 21 on 8 June 2026）＋仓库 chwalinska-gibson 已核。","比赛已经结束，握手与庆祝。"))
S.append(q("rgfs",176.6,185.2,[(177.18,180.3,"I will definitely not forget these three weeks.\n这三个星期，我一定不会忘记。"),(181.84,185.3,"Paris will stay forever in my heart. Merci.\n巴黎会永远留在我心里。谢谢。")],
  "Tennis Channel（法网美国转播方）官方频道「Maja Chwalinska Finalist Speech」（LXRhlHKGKZc）：亚军致辞的最后一句。两档一致（medium 177.18–184.92；small 176.94–184.14）。段首 176.6 在 Thank you so much（171.68–176.56）之后；视频流 185.39 秒结束，段尾 185.2 给溶解留 0.18 秒。",
  "颁奖致辞，不是回合。",kind="ceremony"))
S.append(n("tor",245.3,258.6,"两个月后的多伦多，轮到斯瓦泰克。决赛她六比二、六比三赢下莱巴金娜，八个发球局一个没丢，拿到了这个赛季的第一个冠军。",
  "WTA 官方集锦（bDttZof7qXI，Iga Swiatek vs. Elena Rybakina-Match Highlights）：第二盘最后一局，245 起记分条挂 CHAMPIONSHIP POINT，256 她双臂高举。两档转写在 234.40–258.88 都无词；段首 245.3 是 245.24 切到冠军点那一分的镜头。比分、保发 8/8：WTA 官方接口 LS001 ＋ flashscore OACDWR4j（仓库 swiatek-rybakina-toronto-final 已核）；本赛季第一冠：National Bank Open 官网逐分实录「to clinch her first title of the season」＋ WTA 官方集锦解说。",
  "冠军点在 255 秒前后打完，段尾 258.6 停在她举臂庆祝、解说开口之前。",label="tor",crosses_cut="247.16、248.44 切近景与回广角，254.76 切庆祝近景：都是同一个冠军点前后的镜头，换镜头前后都是她本人。"))
S.append(q("tor",258.7,264.2,[(259.1,263.38,"Sensational, Swiatek takes the title in Toronto.\n精彩！斯瓦泰克拿下多伦多冠军。")],
  "同一条：她举臂、转身走向球网（256–264）。两档一致（medium 259.10–263.38；small 258.88–263.28，名字两档都转错，按画面与官方标题写 Swiatek）。段首 258.7 在冠军点打完之后，段尾 264.2 在 264.44 切镜头之前（溶解 0.18 秒不跨切点），也在下一句 dialed in（268.94）之前。","冠军点已经打完，这是庆祝。"))
S.append(q("tor",292.5,298.4,[(293.06,297.74,"6-2, 6-3, it's Iga Swiatek, the champion in Canada.\n6比2、6比3，冠军是斯瓦泰克！")],
  "同一条：终场图形 FINAL 6 6 / 2 3（288–296）。两档一致（medium 293.06–297.74；small 291.82–297.66）。段首 292.5 在上一句 everyone watching（292.34）之后，段尾 298.4 在莱巴金娜开口致辞（298.90）之前。","比赛已经结束，终场图形。"))
S.append(n("wuhm",243.3,258.6,"这个星期在武汉，赫瓦林斯卡三盘赢下萨卡里。决胜盘第十二局，她破了萨卡里的发球，第一次打进一千赛四强，下周一还会第一次进入世界前二十。",
  "WTA 官方集锦（0-v-yZvYAk8）决胜盘第十二局：记分条 6 3 6 / 0 6 5（244–258 逐格读过，15-30），萨卡里发球；这一局之后就是冷开场里的赛点（261 起）。镜头 243.20 切入、258.88 切走，段首 243.3、段尾 258.6 都在同一个镜头里。两档转写在 242.32–268.00 都无词（之前是第二盘结束时的解说）。⚠️ 上一版这段旁白垫在 194–217 秒，那里记分条是第二盘 3-5 萨卡里盘点，不是决胜盘——账号所有者要求武汉画面简短时逐格读记分条才发现，换成真正的决胜盘。「首进 1000 赛四强、周一首进前 20」：WTA 4593212。","段尾停在这一局 15-30 之后、切镜头之前；赛点在冷开场里已经放过。",label="wuhm"))
S.append(n("wuhs",203.1,211.0,"斯瓦泰克也是两盘过关。十站一千赛，她每一站都打进过半决赛。",
  "WTA 官方集锦（O8f_vcT29uY）第二盘回合，空当 202.72–251.24（两档都无词）。「全部 10 站 WTA1000 都进过半决赛」：WTA 4593251。","第二盘回合，旁白不讲这一分；段尾在空当之内。",label="wuhs"))
S.append(photo("iga-wuhan-qf.jpg",18.5,"赛后她说，两个波兰人都进了半决赛，对波兰网球意义很大。她真为赫瓦林斯卡高兴，这一年赫瓦林斯卡进步了很多。十年前在斯德哥尔摩，赢的是斯瓦泰克；这一次，是她们第一次在巡回赛上相遇。",
  "WTA 官方图库 photo 4593270「Iga Swiatek, Wuhan 2026」（文件名 Iga_Swiatek_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5，Day 5＝10 月 16 日八强日，紫色球衣与集锦一致），取 width=4000，裁 1965×2620（3:4，未放大）。斯瓦泰克场上采访原话出自 WTA 4593251（It's great that we have two Polish players in the semifinals … I'm really happy for Maja. She for sure improved her game this year）。","https://photoresources.wtatennis.com/photo-resources/2026/10/16/9a51ec1e-9524-492c-85d6-49580c011f6f/Iga_Swiatek_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5-DSC_3430A.jpg",
  "她的脸在画面上部 15%–35%，字幕区是球衣，不压脸。"))
S.append(q("wuhm",291.8,299.45,[(292.0,294.0,"And when it seemed the experience of Sakkari\n当萨卡里的经验似乎"),(294.0,295.64,"might prevail in the end,\n就要占上风时，"),(295.92,297.96,"Maja says, “No, no, not this year,\n玛雅说：不，今年不行，"),(298.36,299.2,"not this tournament.”\n这项赛事也不行。")],
  "回到冷开场那场的赛后：赫瓦林斯卡向看台致意、离场（281–299）。解说两档一致（small 281.16–299.16；medium 275.74–299.20），字幕沿用已发布 chwalinska-sakkari-wuhan-2026-qf 第 10 段的审听稿。段首 291.8 在上一句 in the end（287.82）之后，只留最后一句。",
  "比赛已经结束，赛后致意。"))
S.append(photo("ao2017-podium.jpg",17.0,"这一场，斯瓦泰克要冲击她第一个武汉决赛，赫瓦林斯卡要冲击的，是生涯第一个一千赛决赛。九年前一起举着亚军奖盘的两个人，这一次只能有一个人往前走。你站谁？",
  "回到开头那张 2017 澳网领奖台合影（WTA 官方图库 photo 2655257）收尾。斯瓦泰克一胜即首进武汉决赛：WTA 4593251；赫瓦林斯卡此前没进过 1000 赛半决赛（WTA 4593212 首进 1000 赛四强），所以是生涯第一个 1000 赛决赛。账号所有者 2026-10-17「武汉的比赛画面可以简短一点」，这段展望从武汉第二盘回合挪到合影上。",AO17,
  "两人的脸在画面上部 15%–30%，底部字幕区是奖盘和短裤，不压脸。"))
json.dump(S,open('research/swiatek-chwalinska-story-2026/gen/segments.json','w'),ensure_ascii=False,indent=1)
print(len(S))
