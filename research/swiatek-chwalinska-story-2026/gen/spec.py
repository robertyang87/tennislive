import json,sys
sys.path.insert(0,'research/swiatek-chwalinska-story-2026/gen')
from labels import LABELS
V={"pitch":"+10Hz","_why":"网球有故事沿用云健 +18% 语速、+10Hz 音高（与 medvedev-not-villain-2026 同一档）。"}
A='assets/reel/swiatek-chwalinska'
def lab(k):
    return {"image":f"{A}/label-{k}.png","kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":7.0,"motion":"editorial","label":dict(LABELS[k])}
def n(src,a,b,text,why,ok="不是回合的收尾：画面是局间、近景、庆祝或采访，段尾不在一分打到一半。",label=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":text,"voice":dict(V),"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
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
S.append(q("wuhs",290.6,300.0,[(290.88,294.7,"As Iga Swiatek rolls through in straight sets,\n斯瓦泰克直落两盘过关，"),(294.7,296.9,"six-four, six-one,\n6比4、6比1，"),(296.9,299.34,"and will face fellow Pole Maja Chwalinska in the semifinals.\n半决赛将对阵同胞赫瓦林斯卡。")],
  "同一天晚上斯瓦泰克的八强战，WTA 官方集锦（O8f_vcT29uY）赛后握手、致意。解说两档一致（small 290.88–299.14；medium 291.32–299.34），字幕沿用已发布 swiatek-li-wuhan-2026-qf 第 8 段的审听稿。段首 290.6 在上一句（290.10 结束）之后。",
  "比赛已经结束，握手和致意。"))
S.append(photo("ao2017-podium.jpg",14.0,"十月十七号晚上，武汉一千赛半决赛，两个波兰人要隔网相遇。这在一千赛的历史上还是第一次。可九年前，她们站在网的同一边。",
  "WTA 官方图库 photo 2655257（4935×3290，取 width=4000 版本）：说明原文「Left to right: 2017 Australian Open girls' doubles runners-up Maja Chwalinska and Iga Swiatek; and champions Carson Branstine and Bianca Andreescu」。裁左边两人（1800×2400，3:4，未放大）。「一千赛半决赛第一次两个波兰人」出自 WTA 4593212。",AO17,
  "两人的脸在画面上部 15%–30%，底部字幕区是奖盘和短裤，不压脸。"))
S.append(card("一起开始\n打比赛","01",8.0,"月亮姐说，感觉自己认识她一辈子了，因为她们是一起开始打比赛的。"))
S.append({"_placeholder":"pol15"})
S.append(n("jfc16",0.3,15.4,"二〇一六年，青少年联合会杯决赛，波兰对美国。赢下最后一分，两个人在红土上抱在了一起，波兰拿到了冠军。那一年，她们还拿下了欧洲青少年锦标赛十六岁组的双打冠军。",
  "匈牙利网协（2016 青少年联合会杯决赛东道主）官方频道「Poland wins Junior Fed Cup 2016」（p9Xzx3vDPJw，25 秒）：最后一分、两人拥抱（7–11 秒）、与美国队握手。两档转写在 0–15.68 都无词（15.68 起 Thank you very much 是握手时的现场声，段尾收在之前）。波兰 2016 年夺冠：ITF 稿《Poland defeats USA to take Junior Fed Cup title》（itftennis.com/news/243760.aspx，维基引用）＋ ZooTennis 2016-10 赛报；欧青赛双打冠军出自 WTA 4593212。",
  "最后一分在 6 秒前后打完，之后是拥抱与握手。",label="jfc16"))
S.append(photo("ao2017-close.jpg",15.0,"那年秋天，她们在斯德哥尔摩的职业赛里第一次碰面，都是十五岁，斯瓦泰克赢了。几个月后的澳网，两个人搭档打进青少年女双决赛，拿了亚军。",
  "同一张 WTA 官方图（photo 2655257），裁得更近（两人半身）。斯德哥尔摩 W10 第二轮、两人都 15 岁：WTA 4593212、4593251；2017 澳网青少年女双亚军：WTA 4593212、照片说明。",AO17,
  "两人的脸在画面上部 20%–35%，字幕区压在奖盘和腰部，不压脸。"))
S.append(card("一个登顶\n一个停下","02",5.0,"后来，两个人走上了完全不同的路。"))
S.append({"_placeholder":"rg20"})
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
  (368.26,374.18,"And I honestly didn't know if I'm gonna come back or not, to be like honest with you.\n说实话，我不知道自己还会不会回来。"),
  (374.96,380.64,"Yeah, but after like months I decided to come back.\n但几个月后，我决定回来。"),
  (381.70,387.14,"I needed to kind of figure a few things in my head, I would say.\n我得先把脑子里的一些事想清楚。"),
  (388.42,391.30,"Yeah, and I came back. I'm happy that I did.\n我回来了，我很庆幸自己回来了。")],
  "法网官方频道 2026 法网八强后的赛后发布会（1ihxUf32bQk）：记者问停赛那段日子。两档逐词一致（medium 333.56–391.38；small 328.90–391.30），YouTube 自动字幕同。段首 333.2 在上一句 before the break I would say（333.02）之后，段尾 391.6 在下一个提问（395.22）之前。",
  "发布会，不是回合。",kind="ceremony"))
S.append(photo("maja-2022-comeback.jpg",9.0,"一年后，她回到了赛场。只是离出头的那一天，还要再等四年。",
  "WTA 官方图库 photo 2663731（4700×3105，取 width=4000），WTA 2022-07-01 稿件配图，标题原文「One year after taking an indefinite break from tennis due to depression, Maja Chwalinska's ...」；裁人物居中 1980×2640（3:4，未放大）。",M22,
  "她的脸在画面上部约 15%，字幕区是腿和草地，不压脸。"))
S.append(card("从资格赛\n到决赛","03",5.0,"今年春天，轮到月亮姐了。"))
S.append({"_placeholder":"rgsf"})
S.append(q("rgsfi",4.4,25.6,[(4.68,7.8,"You are in Roland Garros' final. How does it sound?\n你打进法网决赛了，感觉怎么样？"),(12.62,14.98,"I mean, like a dream, honestly.\n说真的，像做梦一样。"),(15.52,16.9,"I don't know what's going on.\n我都不知道发生了什么。"),(19.92,20.9,"I'm just...\n我只是……"),(21.54,23.1,"Yeah, I don't know what to say.\n我不知道该说什么。"),(23.2,24.98,"I'm sorry. I'm just very happy.\n抱歉，我就是太开心了。")],
  "法网官方频道半决赛场上采访（SdEjFtD4CTU）。两档逐词一致（medium 4.68–24.58；small 4.88–24.54）。段首 4.4 在主持人前半句 The character continues（3.60–4.2，两档转写不一致，不收）之后，段尾 25.6 在 You understand（26.12）之前。",
  "场上采访，不是回合。",kind="ceremony"))
S.append({"_placeholder":"rgf"})
S.append(q("rgfs",176.6,185.6,[(177.18,180.3,"I will definitely not forget these three weeks.\n这三个星期，我一定不会忘记。"),(181.84,185.3,"Paris will stay forever in my heart. Merci.\n巴黎会永远留在我心里。谢谢。")],
  "Tennis Channel（法网美国转播方）官方频道「Maja Chwalinska Finalist Speech」（LXRhlHKGKZc）：亚军致辞的最后一句。两档一致（medium 177.18–184.92；small 176.94–184.14）。段首 176.6 在 Thank you so much（171.68–176.56）之后。",
  "颁奖致辞，不是回合。",kind="ceremony"))
S.append(n("uc25",132.2,147.7,"这些年，她们也一直是国家队的队友。二〇二五年联合杯，斯瓦泰克和月亮姐都在波兰队，一起打进了决赛。",
  "联合杯官方频道「Team Poland 2025 Run To the Finals」（15fLzmh_o7A）：斯瓦泰克的单打回合，空当 131.92–147.94（两档都无词）。波兰队阵容（斯瓦泰克、赫瓦林斯卡等）与决赛负美国：维基 2025 United Cup（引 ATP、BBC 2025-01-05）；同一条集锦 104 秒起赫瓦林斯卡/齐林斯基的混双赢球。","单打回合，旁白不讲这一分；段尾在下一句（147.94）之前。"))
S.append(q("uc25",181.3,195.2,[(181.54,184.34,"I think it's the third year in a row we're making semis or better.\n我们已经连续第三年打进四强以上了。"),(184.74,187.9,"So two years ago it was semis, last year it was a final.\n前年是四强，去年是决赛。"),(188.32,190.72,"So you guys answer the question, what's coming tomorrow.\n明天会怎样，你们来回答吧。"),(191.76,194.66,"Team Poland into the finals. Well done, congratulations!\n波兰队打进决赛，恭喜！")],
  "同一条：齐林斯基接受场边采访，赫瓦林斯卡站在他身旁（186 秒画面）。两档一致（medium 181.54–194.66）。段首 181.3 在上一句（181.04）之后，段尾 195.2 在片尾板（196 秒起）之前。",
  "场边采访，不是回合。",kind="ceremony"))
S.append(n("wuhm",194.2,212.0,"这个星期在武汉，月亮姐三盘赢了萨卡里，第一次打进一千赛的四强。下周一，她会第一次进入世界前二十。",
  "WTA 官方集锦（0-v-yZvYAk8）决胜盘回合，空当 194.1–225.46（两档都无词）。「首进 1000 赛四强、周一首进前 20」：WTA 4593212。","决胜盘的回合，旁白不讲这一分；段尾在空当之内。",label="wuhm"))
S.append(n("wuhs",203.1,222.0,"斯瓦泰克也是两盘过关。她成了现役唯一一个，在十站一千赛里都打进过半决赛的球员。",
  "WTA 官方集锦（O8f_vcT29uY）第二盘回合，空当 202.72–251.24（两档都无词）。「2009 年以来第四人、现役唯一」：WTA 4593251。","第二盘回合，旁白不讲这一分；段尾在空当之内。",label="wuhs"))
S.append(n("wuhs",222.6,250.6,"赛后她说，两个波兰人都进了半决赛，对波兰网球意义很大。她真为月亮姐高兴，这一年月亮姐进步了很多。十年前在斯德哥尔摩，赢的是斯瓦泰克；这一次，是她们第一次在巡回赛上相遇。",
  "同一条，空当之内。斯瓦泰克场上采访原话出自 WTA 4593251（I'm really happy for Maja. She for sure improved her game this year）。","第二盘回合，段尾在空当之内。"))
S.append({"_placeholder":"ending"})
json.dump(S,open('research/swiatek-chwalinska-story-2026/gen/segments.json','w'),ensure_ascii=False,indent=1)
print(len(S))
