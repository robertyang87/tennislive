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
# 冷开场：月亮姐武汉 1/4 决赛赛点与赛后（WTA 官方集锦解说原声）
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
S.append(live("rg20",403.0,407.4,"闪回②：2020 法网颁奖台上，戴口罩的斯瓦泰克捧着冠军奖杯（法网官方 OwKaLdNEjlI）。",
  "这几秒只有掌声：法语场内播报在 388.5 结束，两档英文转写在 403–407.4 都无词（small 399.82 的 Thank you 在段首之前）。","颁奖，不是回合。"))
S.append(q("rgsfi",106.2,109.8,[(106.42,109.44,"But inside, there is a storm, believe me.\n可我心里，其实是一场风暴。")],
  "闪回③：2026 法网半决赛场上采访（SdEjFtD4CTU），主持人说她看起来很平静，她这样回答。两档逐词一致（medium But@106.42…me.@109.12；small 106.26–109.12）。段首 106.2 在上一句 do.（106.0）之后，段尾 109.8 在看台喊 We love you（110.36）之前。","场上采访，不是回合。",kind="ceremony"))
S.append(live("rgsf",1004.0,1012.4,"闪回④：2026 法网半决赛赛后，月亮姐和看台上的家人朋友相拥、挥手（nuivYz2nq08）。",
  "这段只有欢呼：medium 在 992.56–1015.40 无词；small 在 1004.56 起转出一句 the next match. Thank you（与 medium 对不上，画面没人对镜头说话），按看台噪声的幻听处理。","赛点已经打完，赛后庆祝。"))
S.append(card("波兰双子星","从青梅竹马到巅峰相见",10.0,"十二年前，她们第一次隔网。九年前，她们站上同一个领奖台。这一次，只有一个人能走进决赛。"))
S.append(photo("ao2017-podium.jpg",12.0,"十月十七号晚上，武汉一千赛半决赛，斯瓦泰克对月亮姐。一千赛的半决赛，第一次由两个波兰人来打。",
  "WTA 官方图库 photo 2655257（4935×3290，取 width=4000 版本）：说明原文「Left to right: 2017 Australian Open girls' doubles runners-up Maja Chwalinska and Iga Swiatek; and champions Carson Branstine and Bianca Andreescu」。裁左边两人（1800×2400，3:4，未放大）。「一千赛半决赛第一次两个波兰人」出自 WTA 4593212。",AO17,
  "两人的脸在画面上部 15%–30%，底部字幕区是奖盘和短裤，不压脸。"))
S.append(card("一起开始\n打比赛","01",8.0,"月亮姐说，感觉自己认识她一辈子了，因为她们是一起开始打比赛的。"))
S.append(q("pol15",3.3,22.95,[(3.5,8.18,"Maja Chwalińska, mam 14 lat,\n我是玛雅·赫瓦林斯卡，14岁，"),(8.62,10.48,"mieszkam w Dąbrowie Górniczej\n住在达布罗瓦古尔尼恰，"),(10.48,16.5,"i trenuję od 7 roku życia.\n7岁开始练球。"),(16.74,18.66,"Nazywam się Iga Świątek, mam 14 lat,\n我叫伊加·斯瓦泰克，14岁，"),(18.78,20.52,"trenuję w Warszawskim Klubie Tenisowym Mera,\n在华沙梅拉网球俱乐部训练，"),(20.66,22.8,"trenuje mnie Michał Kaznowski i gram od 8 lat.\n教练是卡兹诺夫斯基，打球8年了。")],
  "Polsat Sport 官方频道（-Vsfptr_DC8，2015 年两人 14 岁时的采访）。两档波兰语逐词转写（data/source_asr/-Vsfptr_DC8/small.pl.json、medium.pl.json）一致；画面里先是戴发箍的月亮姐（5–12 秒），再是站在波兰网协背景板前的斯瓦泰克（18–21 秒）。段尾 22.95 在第三位队友自我介绍（23.06）之前。","采访，不是回合。",kind="ceremony"))
S.append(q("pol15",105.0,118.7,[(105.4,106.5,"Jesteśmy zgrane.\n我们很合得来。"),(106.98,109.1,"Ja z Mają już byłam na kilku drużynówkach,\n我和玛雅打过好几次团体赛，"),(109.16,110.34,"dobrze się znamy,\n很了解彼此，"),(110.44,111.44,"zagadujemy się.\n总有聊不完的话。"),(112.82,115.66,"Czasami oczywiście są jakieś sprzeczki,\n当然，有时也会拌嘴，"),(115.72,118.4,"ale potrafimy szybko to rozwiązać.\n但我们很快就能和好。")],
  "Polsat Sport 官方频道（-Vsfptr_DC8，2015 年两人 14 岁时的采访）。两档波兰语逐词转写（data/source_asr/-Vsfptr_DC8/small.pl.json、medium.pl.json）一致；三人坐在球网前，话筒在中间的斯瓦泰克面前（106–116 秒画面），她说「我和玛雅」。段首 105.0 在上一句（104.0）之后，段尾 118.7 在下一句（124.2）之前。","采访，不是回合。",kind="ceremony"))
S.append(q("pol15",528.2,551.6,[(528.52,531.0,"Nie gram tak jakoś siłowo jak większość dziewczyn,\n我不像大多数女孩那样靠力量，"),(531.04,533.16,"więc gram bardziej tak wszechstronnie,\n所以打得更全面，"),(533.24,536.54,"dużo slice'ów, zmianę rotacji, to jest taka moja gra.\n切削、变旋转，这就是我的打法。"),(536.54,541.46,"I myślę, że w większości meczów to jest kluczem,\n我觉得很多比赛里，关键在于"),(541.54,547.84,"że wygrywam na przykład mecze dzięki temu, że lepiej gram właśnie w takich kluczowych momentach:\n我能在关键分上打得更好："),(547.84,551.26,"slice'y, różne takie zmiany rytmu, a nie tylko bum-bum.\n切削和节奏变化，不只是砰砰砰。")],
  "Polsat Sport 官方频道（-Vsfptr_DC8，2015 年两人 14 岁时的采访）。两档波兰语逐词转写（data/source_asr/-Vsfptr_DC8/small.pl.json、medium.pl.json）一致；戴发箍的月亮姐对着镜头（530–548 秒）。段首 528.2 在上一句（522.0）之后，段尾 551.6 在下一句（553.94）之前。","采访，不是回合。",kind="ceremony"))
S.append(n("jfc16",0.3,15.4,"两个人搭档，拿下了欧洲青少年锦标赛，十四岁组和十六岁组的双打冠军。二〇一六年青少年联合会杯决赛，赢下最后一分，她们抱在了一起",
  "匈牙利网协（2016 青少年联合会杯决赛东道主）官方频道「Poland wins Junior Fed Cup 2016」（p9Xzx3vDPJw，25 秒）：最后一分、两人拥抱（7–11 秒）、与美国队握手。两档转写在 0–15.68 都无词（15.68 起 Thank you very much 是握手时的现场声，段尾收在之前）。波兰 2016 年夺冠：ITF 稿《Poland defeats USA to take Junior Fed Cup title》（itftennis.com/news/243760.aspx，维基引用）＋ ZooTennis 2016-10 赛报；欧青赛双打冠军出自 WTA 4593212。",
  "最后一分在 6 秒前后打完，之后是拥抱与握手。",label="jfc16"))
S.append(photo("ao2017-close.jpg",15.0,"那年秋天在斯德哥尔摩，两个十五岁的女孩，第一次在职业赛里交手，斯瓦泰克赢了。几个月后的澳网，两个人搭档，打进青少年女双决赛，拿了亚军。",
  "同一张 WTA 官方图（photo 2655257），裁得更近（两人半身）。斯德哥尔摩 W10 第二轮、两人都 15 岁：WTA 4593212、4593251；2017 澳网青少年女双亚军：WTA 4593212、照片说明。",AO17,
  "两人的脸在画面上部 20%–35%，字幕区压在奖盘和腰部，不压脸。"))
S.append(card("一个登顶\n一个停下","02",5.0,"后来，两个人走上了完全不同的路。"))
S.append(n("wb18",316.0,326.0,"二〇一八年夏天，十七岁的斯瓦泰克，打进温网青少年女单决赛，离冠军只差最后一局。",
  "温网官方「Iga Swiatek 2018 Girls' Singles Champion Final Highlights」（Jw9sJZjk97o）：决赛最后一局的回合。两档转写在 299.5–326.24 都无词（之前 294–299 解说说 A game away from the title）。17 岁：生日 2001-05-31，决赛 2018-07-15。","最后一局的回合，段尾 326.0 在解说开口之前；冠军点在下一段。",label="wb18"))
S.append(q("wb18",326.0,357.0,[(326.24,331.62,"How good is that? How good is that point?\n这一分太漂亮了！"),(339.96,349.8,"Iga Swiatek is the junior girls' singles champion at Wimbledon.\n斯瓦泰克成了温网青少年女单冠军。"),(349.82,355.0,"A wonderful tournament, conceding just one set.\n整届比赛，她只丢了一盘。")],
  "同一条：冠军点之后她捂着脸、和团队拥抱（336–356）。两档一致（medium 326.24–354.80；small 326.36–354.78；名字两档都转错，按画面与官方标题写 Iga Swiatek）。段尾 357.0 在 And now the 2018（357.32）之前。","冠军点已经打完，这是庆祝。",kind="broadcast"))
S.append(q("wb18",368.2,386.3,[(368.6,372.42,"There's a lot to be written in this lady's career, for sure,\n她的职业生涯，还有很多篇章要写，"),(372.42,375.0,"if she can continue to improve, stay focused,\n只要她继续进步、保持专注，"),(375.0,379.5,"and more important than just about anything else is to enjoy the journey,\n更重要的是，享受这段旅程，"),(381.24,382.56,"enjoy the ups, enjoy the downs,\n享受高峰，也享受低谷，"),(383.04,385.8,"because there's going to be plenty of them along the way.\n因为一路上，这样的起落会有很多。")],
  "同一条：颁奖与捧杯（368–386）时的解说。两档逐词一致（medium 368.70–385.80；small 368.60–385.80）。段首 368.2 在 Forever.（两档都有，366.34/367.12）之后，段尾 386.3 在温网片尾板（388 秒起）之前。","颁奖，不是回合。",kind="ceremony"))
S.append(n("rg20",364.5,375.0,"两年后的法网，世界排名第五十四、没有种子的她一盘没丢，拿下冠军。她成了波兰第一个大满贯单打冠军。",
  "法网官方决赛集锦（OwKaLdNEjlI）：最后两分与冠军点（366–375）。两档转写在 349–375 没有可对上的英文（small 355.66 一句 Oh, I'm sorry 只有 small 有、画面是回合中无人说话，按幻听处理）；375.2 起是法语场内播报（Jeu, set et match），段尾收在之前。","冠军点在 374 秒前后打完，段尾 375.0 停在她捂嘴那一刻。",label="rg20"))
S.append(n("rg20",407.6,414.6,"那一年，她十九岁，站上了法网最高的领奖台。",
  "同一条：颁奖台上戴口罩捧杯、举杯（403–414）。法语播报在 388.5 结束；两档在 403–420.9 都无英文（small 399.82 的 Thank you 在段首之前）。段尾 414.6 在法网片尾图形（415 秒起）之前。六座大满贯：WTA 4593251「six-time Grand Slam champion」。","颁奖，不是回合。"))
S.append(n("wb25",16.0,34.8,"后来，她当上世界第一，又拿下了好几座大满贯。二〇二五年温网决赛，六比零、六比零，这是她的第六座。",
  "温网官方「PURE EMOTION! | Iga Swiatek | Championship Winning Moment & Celebration」（Ds27hJRfSG4）：冠军点那一分（16–34）。两档转写在 0.34–41.32 都无词。段首 16.0 是切到广角的发球，段尾 34.8 在她倒地（36 秒）之前。第六座大满贯：WTA 4593251「six-time Grand Slam champion」，温网 2025 是第六座（2020/2022/2023/2024 法网、2022 美网、2025 温网）。","冠军点在 34 秒前后打完。",label="wb25"))
S.append(q("wb25",34.9,56.8,[(41.32,48.3,"Iga conquers the grass and becomes a Wimbledon champion.\n斯瓦泰克征服草地，成为温网冠军。")],
  "同一条：她倒在草地上、和阿尼西莫娃拥抱（36–56）。medium 41.32–48.30 整句；small 44.00–48.24 只转出后半句，前半句按 medium。段尾 56.8 在 small 重复转出的那半句（57.18，medium 无词）之前。","冠军点已经打完，这是庆祝。"))
S.append(card("月亮姐\n停了下来","2021年",8.6,"同一时间，月亮姐却撑不住了。二〇二一年，十九岁的她宣布，因为抑郁暂停职业生涯。"))
S.append(q("rgpc",333.2,391.6,[
  (333.56,335.08,"I was struggling a lot.\n那段时间我过得很艰难。"),
  (337.10,339.00,"You know, I pushed at the beginning.\n一开始我硬撑着，"),
  (339.94,344.54,"I thought that I just need to stay very strong, tough, and just keep practicing.\n以为只要够坚强，坚持训练就行。"),
  (345.64,349.04,"Yeah, but then I just couldn't get out of bed anymore.\n可后来，我连床都起不来了。"),
  (349.90,353.68,"I was just like lifeless, to be honest.\n说实话，我整个人没有一点生气。"),
  (355.28,361.08,"And yeah, I knew that I need to take a break because otherwise I'm just not able to\n我知道必须停下来，不然的话，"),
  (362.12,364.58,"like live, I think.\n我觉得我都没法好好生活。"),
  (365.24,367.26,"Yeah, I needed to take a break.\n我需要停下来。"),
  (368.26,374.18,"And I honestly didn't know if I'm gonna come back or not, to be like honest with you.\n说实话，我不知道还会不会回来。"),
  (374.96,380.64,"Yeah, but after like months I decided to come back.\n但几个月后，我决定回来。"),
  (381.70,387.14,"I needed to kind of figure a few things in my head, I would say.\n我得先把脑子里的一些事想清楚。"),
  (388.42,391.30,"Yeah, and I came back. I'm happy that I did.\n我回来了，我很庆幸自己回来了。")],
  "法网官方频道 2026 法网八强后的赛后发布会（1ihxUf32bQk）：记者问停赛那段日子。两档逐词一致（medium 333.56–391.38；small 328.90–391.30），YouTube 自动字幕同。段首 333.2 在上一句 before the break I would say（333.02）之后，段尾 391.6 在下一个提问（395.22）之前。",
  "发布会，不是回合。",kind="ceremony"))
S.append(photo("maja-2022-comeback.jpg",9.0,"一年后，她回到了赛场。只是离出头的那一天，还要再等四年。",
  "WTA 官方图库 photo 2663731（4700×3105，取 width=4000），WTA 2022-07-01 稿件配图，标题原文「One year after taking an indefinite break from tennis due to depression, Maja Chwalinska's ...」；裁人物居中 1980×2640（3:4，未放大）。",M22,
  "她的脸在画面上部约 15%，字幕区是腿和草地，不压脸。"))
S.append(card("国家队\n队友","2025年联合杯",9.6,"这些年，她们也一直是国家队的队友。二〇二五年联合杯，两个人都在波兰队，一起打进了决赛。"))
S.append(q("uc25",181.3,195.2,[(181.54,184.34,"I think it's the third year in a row we're making semis or better.\n我们连续三年打进四强以上了。"),(184.74,187.9,"So two years ago it was semis, last year it was a final.\n前年是四强，去年是决赛。"),(188.32,190.72,"So you guys answer the question, what's coming tomorrow.\n明天会怎样，你们来回答吧。"),(191.76,194.66,"Team Poland into the finals. Well done, congratulations!\n波兰队打进决赛，恭喜！")],
  "同一条：齐林斯基接受场边采访，赫瓦林斯卡站在他身旁（186 秒画面）。两档一致（medium 181.54–194.66）。段首 181.3 在上一句（181.04）之后，段尾 195.2 在片尾板（196 秒起）之前。",
  "场边采访，不是回合。",kind="ceremony"))
S.append(card("从资格赛\n到决赛","03",5.0,"二〇二六年春天，轮到月亮姐了。"))
S.append(n("rgqf",141.0,159.4,"世界排名第一百一十四的她，从资格赛打起。四分之一决赛对卡林斯卡娅，七比六、六比三，她第一次打进大满贯四强。",
  "法网官方八强集锦（-ygefQ6dXFc）：第二盘最后两分与赛点（150–158）。两档转写在这一窗口里只有对不上的幻听（medium 130.88–149.90 一句 Thank you very much、small 148.00–164.34 一句 And now it's time for the second round，画面是比赛中、没人对镜头说话）；159.56 起是场内播报，段尾收在之前。比分 7-6(3) 6-3：puntodebreak、tennismajors。","赛点在 158 秒前后打完，段尾 159.4 停在她跪地之前。",label="rgqf"))
S.append(n("rgsf",976.0,991.0,"半决赛对施奈德，最后一分落地，她倒在了红土上。从资格赛打起，这是她在巴黎的第九场胜利。",
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
S.append(n("wuhm",194.0,217.2,"这个星期在武汉，月亮姐三盘赢了萨卡里。决胜盘前十一局，两个人都保住了发球局，第十二局她破发拿下比赛。第一次打进一千赛四强，下周一，她还会第一次进入世界前二十。",
  "WTA 官方集锦（0-v-yZvYAk8）决胜盘回合，空当 194.1–225.46（两档都无词）。「首进 1000 赛四强、周一首进前 20」：WTA 4593212。","决胜盘的回合，旁白不讲这一分；段尾在空当之内。",label="wuhm",crosses_cut="208.76 广角切到月亮姐近景：上一分已经打完，换镜头前后都是同一场、她本人。"))
S.append(n("wuhs",203.1,221.0,"斯瓦泰克也是两盘过关，八个发球局一个没丢，三个破发点全部化解。这样一来，十站一千赛，她每一站都打进过半决赛。",
  "WTA 官方集锦（O8f_vcT29uY）第二盘回合，空当 202.72–251.24（两档都无词）。「全部 10 站 WTA1000 都进过半决赛」：WTA 4593251。","第二盘回合，旁白不讲这一分；段尾在空当之内。",label="wuhs"))
S.append(photo("iga-wuhan-qf.jpg",17.0,"赛后她说，两个波兰人都进了半决赛，对波兰网球意义很大。她真为月亮姐高兴，这一年月亮姐进步了很多。十年前在斯德哥尔摩，赢的是斯瓦泰克；这一次，是她们第一次在巡回赛上相遇。",
  "WTA 官方图库 photo 4593270「Iga Swiatek, Wuhan 2026」（文件名 Iga_Swiatek_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5，Day 5＝10 月 16 日八强日，紫色球衣与集锦一致），取 width=4000，裁 1965×2620（3:4，未放大）。斯瓦泰克场上采访原话出自 WTA 4593251（It's great that we have two Polish players in the semifinals … I'm really happy for Maja. She for sure improved her game this year）。","https://photoresources.wtatennis.com/photo-resources/2026/10/16/9a51ec1e-9524-492c-85d6-49580c011f6f/Iga_Swiatek_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5-DSC_3430A.jpg",
  "她的脸在画面上部 15%–35%，字幕区是球衣，不压脸。"))
S.append(n("wuhm",156.0,186.9,"这一场，斯瓦泰克要冲击她第一个武汉决赛。赢了，十站一千赛的决赛，她就全都打进过。月亮姐要冲击的，是生涯第一个一千赛决赛。从二〇一四年第一次在少年比赛里交手，到今天在一千赛半决赛碰面，已经过去了十二年。",
  "WTA 官方集锦（0-v-yZvYAk8）第二盘回合，空当 154.4–187.5（两档都无词）：段首 156.0 是 155 秒特写之后切回广角的发球，段尾 186.9 停在这一分打完、切萨卡里特写（186.92）之前。斯瓦泰克一胜即「首进武汉决赛、10 站 WTA1000 都进过决赛」：WTA 4593251。月亮姐此前没进过 1000 赛半决赛（WTA 4593212 首进 1000 赛四强），所以是第一个 1000 赛决赛。","段尾停在切近景之后，这一分已经打完。"))
S.append(q("wuhm",280.6,299.45,[(281.16,282.66,"What an effort by the Pole.\n波兰姑娘拼尽了全力。"),(283.6,285.36,"A dominant opening set, score-wise;\n首盘比分一边倒，"),(285.36,287.82,"she had to outlast the Greek in the end.\n最后还是得熬过这位希腊对手。"),(292.0,294.0,"And when it seemed the experience of Sakkari\n当萨卡里的经验似乎"),(294.0,295.64,"might prevail in the end,\n就要占上风时，"),(295.92,297.96,"Maja says, “No, no, not this year,\n玛雅说：不，今年不行，"),(298.36,299.2,"not this tournament.”\n这项赛事也不行。")],
  "回到冷开场那场的赛后：月亮姐向看台致意、离场（281–299）。解说两档一致（small 281.16–299.16；medium 275.74–299.20），字幕沿用已发布 chwalinska-sakkari-wuhan-2026-qf 第 10 段的审听稿。段首 280.6 在 semifinal（279.42–279.76）之后。",
  "比赛已经结束，赛后致意。"))
S.append(photo("ao2017-podium.jpg",9.6,"九年前一起举着亚军奖盘的两个人，这一次只能有一个人往前走。你站谁？",
  "回到开头那张 2017 澳网领奖台合影（WTA 官方图库 photo 2655257）收尾。",AO17,
  "两人的脸在画面上部 15%–30%，底部字幕区是奖盘和短裤，不压脸。"))
json.dump(S,open('research/swiatek-chwalinska-story-2026/gen/segments.json','w'),ensure_ascii=False,indent=1)
print(len(S))
