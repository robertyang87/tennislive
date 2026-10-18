import json,sys
sys.path.insert(0,'research/fokina-story-2026/gen')
from labels import LABELS
V={"pitch":"+10Hz","_why":"网球有故事沿用云健 +18% 语速、+10Hz 音高（与 kartal-story-2026 同一档）。"}
A='assets/reel/fokina-story'
def lab(k):
    return {"image":f"{A}/label-{k}.png","kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":7.0,"motion":"editorial","label":dict(LABELS[k])}
OK_CUT="不是回合的收尾：画面是局间、近景、庆祝或采访，段尾不在一分打到一半。"
def n(src,a,b,text,why,ok=OK_CUT,label=None,crosses_cut=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":text,"voice":dict(V),"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    if crosses_cut: s["crosses_cut"]=crosses_cut
    return s
# 段与段之间有 0.18 秒溶解：原声字幕离段边至少 0.22 秒，否则会和相邻旁白段的窗口重叠。
EDGE=0.22
def q(src,a,b,cues,why,ok=OK_CUT,label=None,kind="broadcast",crosses_cut=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":"","quote":[{"at":round(max(x-a,EDGE),2),"end":round(min(y-a,(b-a)-EDGE),2),"text":t} for x,y,t in cues],"_quote_kind":kind,"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    if crosses_cut: s["crosses_cut"]=crosses_cut
    return s
def card(title,kicker,sec,text):
    return {"title_card":title,"kicker":kicker,"seconds":sec,"narration":text,"voice":dict(V)}
def photo(img,sec,text,why,src,safety):
    return {"image":f"{A}/{img}","image_kind":"photo","seconds":sec,"narration":text,"voice":dict(V),"_why":why,"_photo_source":src,"_photo_caption_safety":safety}
TWO="两档转写（small.en / medium.en）逐词一致"
S=[]
# 冷开场：上海半决赛赛点、他笑着走到网前（Tennis TV 官方集锦解说原声）
c=q("sf",286.6,303.8,[(288.88,292.52,"For the second time in his career,\n职业生涯第二次，"),(293.52,299.66,"Alejandro Davidovich Fokina is into the final of a Masters 1000.\n福基纳打进了大师赛决赛。")],
  f"冷开场：Tennis TV 官方集锦（TXmXxVJ3o_M）决胜盘 5-3 赛点、他笑着回头、两人网前拥抱。{TWO}（288.88–299.66，名字两档都转错，按官方标题写 Davidovich Fokina）。段尾 303.8 在 Tennis TV 片尾板（304.4 起）之前。",
  "赛点在 289 秒前后打完，之后是庆祝与握手。",crosses_cut="290、292.5、295、297.5、300 切到他笑、他低头、兹维列夫、网前拥抱：都是同一个赛点之后。")
c["_ending_payoff_required"]=False
c["_ending_payoff_why"]="网球有故事：冷开场是本期由头（他怎么站上上海决赛），正文倒回他五次决赛的来路，回到上海这一周时用同一场 ATP 官方集锦重放赛点之后的解说收住。"
S.append(c)
S.append(card("前5次决赛\n全是亚军","2022—2025",8.6,"他职业生涯的前五次决赛，全是亚军。五个冠军点，一个都没握住。"))
# 01 温网少年
S.append(card("温网\n少年","01",8.8,"二〇一七年，十八岁的他拿下温网青少年冠军，一盘没丢。那一年，他青少年组二十胜一负。"))
S.append(q("jw",43.5,55.4,[(43.84,49.8,"I started with my father in the beach, in the sand courts in my city,\n我是跟着爸爸在海边开始的，"),(49.8,55.02,"and it was my father who pushed me to play tennis.\n是爸爸推着我去打网球。")],
  f"温网官方频道 2017 年青少年冠军新闻发布会（W98zNwzcSvk）：他坐在发布台前讲怎么开始打球。{TWO}（43.84–55.02；small 把 pushed 写成 push、多一个 to，按 medium 与语义写）。段首 43.5 在上一句（42.8 结束）之后，段尾 55.4 在下一句（56.1）之前。",
  "发布会，不是回合。",kind="ceremony",crosses_cut="同一个机位，只有推拉变焦。"))
# 02 五次亚军
S.append(card("五次\n亚军","02",6.4,"二〇二二年四月，蒙特卡洛。第二轮，他碰上了世界第一。"))
S.append(n("mcd",201.0,206.8,"他破了德约科维奇九个发球局，三盘赢下世界第一。",
  "Tennis TV 官方集锦（QEq571d-4_Q）决胜盘最后一局：185–207 同一个广角机位，赛点在 205 秒前后打完。两档转写在 185–207.8 只有 196.3 一声 Oh、203.1 一声 Wow（现场惊呼，压在旁白下）。破发九次：ATP 西语简介＋ATP 上海赛前要点 PDF。",
  "段尾 206.8 在赛点打完之后、解说开口（207.8）之前。",label="mcd"))
S.append(q("mcd",207.4,223.4,[(207.82,218.34,"There it is, it is a day Alejandro Davidovich Fokina will remember for a very, very long time.\n这一天，福基纳会记很久很久。"),(218.42,222.98,"Only his second top 10 win, this time it's over the world number one.\n生涯第二场赢前十，赢的是世界第一。")],
  f"同一条：他和德约网前拥抱、坐在场边抱头笑。{TWO}（207.82–222.98）。段尾 223.4 在下一句 You have to give him（222.98 起）只露半个词，字幕收到 222.98。",
  "比赛已经结束，庆祝与握手。",crosses_cut="209、211、213、221、223 切到他、德约、网前拥抱、场边：都是赛点之后。"))
S.append(n("mcc",19.5,27.6,"一周后，他打进生涯第一个决赛，对手是卫冕冠军西西帕斯。",
  "Tennis TV 官方「Tsitsipas match point & celebration」（IUIM1yIVFjA）：第二盘抢七的赛点回合，14–29 同一个广角机位。两档转写在 0–27.9 无词。",
  "段尾 27.6 在这一分落地、解说开口（27.94）之前。",label="mcf"))
S.append(q("mcc",27.6,39.2,[(27.94,29.18,"It's just wide.\n出界了。"),(29.18,37.4,"And it is mission accomplished in Monte Carlo for Stefanos Tsitsipas.\n西西帕斯在蒙特卡洛完成了卫冕。")],
  f"同一条：他一拍出界，西西帕斯倒地，他仰头站在网前。{TWO}（27.94–37.40）。",
  "比赛已经结束。",crosses_cut="30.5、32、33.5、35 切到网前、倒地的西西帕斯、他：都是赛点之后。"))
S.append(q("mcc",133.2,142.6,[(134.36,136.36,"Alejandro, first but not last,\n亚历杭德罗，第一次，"),(136.36,137.72,"I'm pretty sure about it.\n但肯定不是最后一次。"),(138.72,142.16,"And I would like to tell you congratulations.\n我想跟你说声恭喜。")],
  f"同一条：颁奖仪式上西西帕斯拿着话筒对他讲话，138 切到他捧着亚军盘笑。{TWO}（134.36–142.16）。",
  "颁奖致辞，不是回合。",kind="ceremony",crosses_cut="138 切到他，是同一段致辞。"))
S.append(card("2025\n离冠军最近","2025",9.8,"二〇二五年，他又打进四次决赛。二月的德尔雷海滩，决胜盘五比二，对手发球，他握到两个冠军点。"))
S.append(q("dr",354.0,383.3,[(364.14,365.54,"Yeah!\n漂亮！"),(370.86,375.6,"Oh, has he made it?\n他拿下了吗？")],
  f"Tennis TV 官方集锦（r2K-9DFDzmM）决胜盘 5-2、凯茨马诺维奇发球 15-40：第一个冠军点（340.5 起记分条 40-15）打到 372（372.5 切到对手近景），段首 354.0 在这一分回合中段，第二个冠军点 375.5–384。{TWO}（364.14 一声 Yeah，370.86–375.60 一句）。段尾 383.3 在下一句（383.5）之前，第二个冠军点的回合在 384 秒前后打完——段尾停在这一分最后一拍之前。",
  "第二个冠军点打到最后一拍时切走，下一段直接接对手夺冠：这一段讲的是他握着两个冠军点，回合结果由下一段交代。",label="dr",crosses_cut="372.5、374 切到对手擦汗，是第一个冠军点打完之后。"))
S.append(q("dr",459.9,467.7,[(460.28,464.1,"After match point heartache in one of his previous finals,\n他在之前一次决赛里痛失赛点，"),(464.52,467.28,"this time he saves a couple of match points.\n这一次，他救下了两个赛点。")],
  f"同一条：凯茨马诺维奇夺冠后的包厢和颁奖。{TWO}（460.28–469.02；small 把 match 转成 Matt's，按 medium 与语义写）。段首 459.9 在上一句 Delray Beach（455.70）之后，段尾 467.7 在 Champion, everyone（468.18）之前。",
  "比赛已经结束，庆祝与颁奖。",crosses_cut="456、460、464、468 都是比赛结束之后的庆祝与颁奖。"))
S.append(q("ac",472.4,479.0,[(473.12,478.36,"It's heartbreak again for Alejandro Davidovich Fokina.\n福基纳又一次心碎了。")],
  f"Tennis TV 官方集锦（Vx3B-kCQDTs）：三月阿卡普尔科决赛，马哈奇戴墨西哥帽捧杯。{TWO}（473.12–478.36）。段首 472.4 在 small 那一句 behind it（471.54）之后。",
  "颁奖，不是回合。",label="ac"))
S.append(n("wa",289.7,296.0,"七月的华盛顿，决胜盘五比三，他发球胜赛，三十比零领先。",
  "Tennis TV 官方集锦（56wc7QQEwEw）：290 秒起记分条 7 1 5 / 5 6 3、他发球（这一局已到 30-40 破发点）。两档转写在 289–296.1 无词。决胜盘 5-3 发球胜赛、30-0 领先被破：ATP 华盛顿决赛报道＋Eastern Mirror（AFP）。",
  "回合进行中，旁白交代这一局怎么开始的；段尾停在解说开口之前。",label="wa"))
S.append(q("wa",296.0,302.4,[(296.18,299.52,"Oh, nervy game from 30-love up,\n三十比零领先，却打得发紧，"),(299.52,300.8,"mis-hit forehands.\n正手连连打飞。")],
  f"同一条：他被破发的那一分与之后。{TWO}（296.18–300.80）。",
  "这一局打完，切到下一局之前。"))
S.append(q("wa",306.6,322.0,[(307.76,309.08,"Oh my gosh!\n天哪！"),(311.06,314.02,"Unbelievably fortunate from De Minaur,\n德米纳尔运气太好了，"),(314.02,315.78,"acknowledges it, but what a time.\n他也承认，偏偏是这个时候。"),(316.92,318.74,"Please, players are ready.\n请，球员已准备。"),(319.1,321.62,"Two hours and 39 minutes on the clock.\n比赛已经打了两小时三十九分钟。") ],
  f"同一条：5-4 德米纳尔发球，318 秒打出 CHAMPIONSHIP POINT 字样。{TWO}（307.76–321.62；Please, players are ready 是主裁播报，small 转成 These players，按 medium 写）。",
  "冠军点那一局打到中途切走，下一段旁白交代三个冠军点。"))
S.append(n("wa",334.8,348.8,"那一局打了十分钟，对手连救三个冠军点。最后一个，德米纳尔放了一个高球，擦着边线落地，离出界只差十六毫米。",
  "同一条：德米纳尔发球局的后几分，328.5–348.98 两档转写无词。三个冠军点、16 毫米：ATP 华盛顿决赛报道（ATP 自己的测量）＋Tennis.com；那一局 10 分钟：Eastern Mirror（AFP）。",
  "回合之间，段尾在解说开口（348.98）之前。"))
S.append(q("wa",348.9,356.2,[(348.98,354.68,"And that is superb from the Australian, just superb.\n这位澳大利亚人打得太漂亮了。")],
  f"同一条：德米纳尔保发之后。{TWO}（348.98–354.68）。",
  "这一局打完。"))
S.append(q("wa",455.2,462.4,[(455.58,458.84,"It's the other way for Alejandro Davidovich Fokina.\n福基纳那边，是另一番滋味。"),(459.02,462.52,"How will he recover from another setback?\n又一次挫折，他要怎么走出来？")],
  "同一条：德米纳尔抢七夺冠之后，他坐在场边把头埋进毛巾。medium 455.58–462.52；small 把第二句转成 oh he recovered from another setback，按 medium 与语序写成问句。段尾 462.4 在主持人开口（462.52）之前，字幕收到 462.18。",
  "比赛已经结束。",crosses_cut="458、461 切到他和德米纳尔，都是赛后。"))
S.append(q("bs",446.6,459.3,[(446.94,453.66,"Well, it's the biggest title of Joao Fonseca's very young career so far.\n这是丰塞卡年轻生涯里最大的冠军，"),(453.66,459.0,"As he wins the 500 level event here in Basel.\n他拿下了巴塞尔的五百赛。")],
  f"Tennis TV 官方集锦（MLCcQ08dVaU）：十月巴塞尔决赛赛点、丰塞卡庆祝与网前握手。{TWO}（446.94–459.00；small 头一个词转成 That's，按 medium）。",
  "赛点在 446 秒前后打完，之后是庆祝。",label="bs",crosses_cut="447.5、450、452.5、455 切到丰塞卡、包厢、看台：都是赛点之后。"))
S.append(n("bs",459.4,469.6,"第五个决赛，又是亚军。那年秋天，他升到生涯最高的世界第十四，却一个冠军都还没有。",
  "同一条：网前握手、颁奖台上他站在一旁。两档转写在 459.0–485 无词（485.4 Thank you 在片尾）。生涯最高第 14：ATP 西语简介＋ATP 上海赛前要点 PDF。",
  "颁奖，不是回合。"))
# 03 最乱的夏天
S.append(card("最乱的\n夏天","03",14.4,"二〇二六年五月，法网。打完首轮，教练和他一起吃了晚饭。几个小时后，教练发来一条短信：不干了。他说，教练飞去了迈阿密，还拉黑了他和妻子的电话。"))
S.append(n("ml",405.0,410.6,"一个月后，马略卡，家门口，第六个决赛。",
  "Tennis TV 官方集锦（7JY8UtZrvFg）第二盘 5-3 他的发球局：396–410 同一个广角机位，赛点是 407.5 那一发。两档转写在 388.2–410.84 无词。",
  "段尾 410.6 在赛点那一发落地之后、解说开口之前。",label="ml"))
S.append(q("ml",410.6,445.0,[(410.84,416.88,"Mission finally accomplished for Alejandro Davidovich Fokina.\n福基纳终于做到了。"),(418.22,422.72,"He's a champion on the ATP tour for the very first time.\n他第一次拿到巡回赛冠军，"),(423.76,426.9,"And he does it on Spanish soil in Mallorca.\n就在西班牙的马略卡。"),(429.78,430.74,"What a moment.\n多美的时刻。"),(431.56,433.92,"It's been a long time coming.\n这一天等了很久，"),(434.24,435.54,"you have to say that.\n不得不说。"),(435.54,439.46,"And the disappointments of finals past\n过去那些决赛的失落，"),(439.46,444.38,"washed away in a wave of emotion.\n在这一刻全被冲走了。")],
  "同一条：赛点之后他平静地走到网前握手（420–428），转身怒吼（432.5），看台上的西班牙国旗、包厢（435–447）。medium 410.84–444.38 逐词；small 漏了第一句、其余逐词一致，第一句按 medium 与 ATP 报道写。",
  "比赛已经结束，庆祝与握手。",crosses_cut="412.5、415、417.5、420、432.5、435 切到他、看台、网前握手、怒吼、国旗：都是赛点之后。"))
S.append(n("wb",150.0,161.4,"一周后的温网第四轮，他和阿利亚西姆打满五盘。第四盘，对手五比四发球胜赛，他扭伤脚踝，叫了医疗暂停。",
  "温网官方集锦（vOrKPuPncdg）：150–172 记分条第四盘 4-3、5-4（162 起对手 5-4）。两档转写在 149.1–165.5 无词。扭伤脚踝、医疗暂停在对手 5-4 发球胜赛时：The Star（Reuters）＋Tennis Majors。",
  "回合之间与近景，段尾在解说开口（165.5）之前。",label="wb"))
S.append(q("wb",199.4,216.4,[(201.8,205.8,"Finally he takes it. And there is the release of the emotion.\n终于拿下了，情绪一下子释放出来。"),(210.9,214.1,"Two prize fighters at the end of 12 rounds.\n像两个打满十二回合的拳手。")],
  f"同一条：第五盘 5-1 阿利亚西姆的赛点、庆祝和网前握手。{TWO}（201.8–214.1）。段尾 216.4 在 217.5 转场之前。",
  "赛点在 201 秒前后打完。",crosses_cut="202.5、205、207.5、210、212.5、215 切到看台、阿利亚西姆、他、网前：都是赛点之后。"))
S.append(card("停下来的\n两个多月","2026.07—09",10.8,"输球之后，两人在网前吵了起来。紧接着，是背伤。北美的硬地赛季，他全部缺席，美网也退了赛。"))
# 04 上海这一周
S.append(n("cdf",410.0,420.8,"九月，他在成都复出。成都决赛，他一个破发点都没给胡尔卡奇。抢七三比六落后，最后七个小分，他拿了六个。",
  "Tennis TV 官方集锦（9u2kSI8md88）第二盘抢七：400–427 同一个广角机位。两档转写在 397.5–421.0 无词。复出首战 6-4 6-4 胜胡安·塞伦多洛（ATP 成都第二轮报道），全场没面对破发点、抢七 3-6 落后：ATP 成都决赛报道＋Tennis Majors。",
  "抢七回合之间，段尾在解说开口（421.0）之前。",label="cdf"))
S.append(q("cdf",441.0,456.0,[(441.32,443.2,"But the smile says it all.\n笑容说明了一切。"),(444.34,447.88,"After losing his first five tour level finals,\n头五次决赛全输之后，"),(448.38,450.32,"he's now won two in a row.\n他现在连赢了两个。"),(451.26,453.96,"And this one came having not played a match\n而这一个冠军之前，"),(453.96,455.58,"for two and a half months.\n他两个半月没打比赛。")],
  f"同一条：他转身振臂、蹲下捂脸。{TWO}（441.32–455.58，按 small 断句）。段首 441.0 在 did you not（440.08）之后，段尾 456.0 在 What a week（455.80）只露半个词，字幕收到 455.58。",
  "比赛已经结束。",crosses_cut="442.5、445 切到他振臂、捂脸：都是赛点之后。"))
S.append(card("上海\n这一周","04",6.4,"然后，是上海。第三轮对蒂亚福，他救下了一个赛点。"))
S.append(n("sh3",100.0,105.9,"决胜盘，又是抢七。",
  "ATP 官方集锦（x2hTyMZ_k8k）决胜盘抢七：95–110 同一个广角机位。两档转写在 92.3–106.16 无词。救下 1 个赛点：ATP 上海赛前要点 PDF＋ATP 半决赛报道。",
  "抢七回合之间，段尾在解说开口之前。",label="sh3"))
S.append(q("sh3",105.9,116.4,[(106.16,112.12,"Oh, he's done it!\n他做到了！"),(113.48,115.84,"What a victory that is!\n多么漂亮的胜利！")],
  f"同一条：抢七最后一分、他对着镜头怒吼、网前握手。{TWO}（106.16–128.72）。段尾 116.4 在 For Alejandro（119.30）之前。",
  "比赛已经结束。",crosses_cut="112.5、115 切到他怒吼：都是赛点之后。"))
S.append(n("sh4",94.0,102.8,"第四轮对胡尔卡奇，先丢一盘，又一次打进决胜盘抢七。",
  "ATP 官方集锦（OSnzyodnKdE）决胜盘抢七：90–104 同一个广角机位。两档转写在 84.1–103.1 无词。",
  "抢七回合之间，段尾在解说开口（103.1）之前。",label="sh4"))
S.append(q("sh4",102.9,107.6,[(103.1,106.9,"Oh, what an incredible finish!\n多么精彩的收尾！")],
  f"同一条：抢七最后一分、他蹲下、回放、他振臂。{TWO}。段尾 107.6 在 108 切到回放之前。",
  "比赛已经结束。",crosses_cut="106 切到他蹲下，是赛点之后。"))
S.append(n("sfa",136.2,142.3,"半决赛对兹维列夫，他也先丢一盘。",
  "ATP 官方集锦（NKFVL_lELNE）决胜盘 5-3 他的发球局：139–142 记分条 7 4 3 / 5 6 5、40-15。两档转写在 135.9–142.5 无词。",
  "赛点回合进行中，段尾在解说开口（142.5）之前。",label="sf"))
S.append(q("sfa",142.4,164.8,[(142.5,152.7,"For the second time in his career, Alejandro Davidovich Fokina is into the final of a Masters 1000.\n生涯第二次，打进大师赛决赛。"),(157.2,164.2,"And for the second time in his career, he gets the better of Alexander Zverev.\n也是生涯第二次赢下兹维列夫。")],
  f"同一条：赛点之后他笑、网前握手、指天、包厢和看台的西班牙国旗。{TWO}。段尾 164.8 在下一句（168.3）之前。",
  "比赛已经结束。",crosses_cut="145、148、151、154、157、160 都是赛点之后的庆祝与握手。"))
S.append(q("sfi",65.5,71.8,[(65.72,68.3,"At the end, it's not easy when you're out.\n离开赛场的日子不好过，"),(68.62,71.52,"So you have a lot of time to think.\n你会有很多时间去想。")],
  "ATP 官方场上采访（KHT6c3b6ecw）：主持人问停赛两个月有没有改变他。medium 65.72–71.52 逐词；small 在句尾补 no?（口头禅），按 medium 写。段尾 71.8 在下一句（72.38）之前。",
  "采访，不是回合。",kind="ceremony"))
S.append(q("sfi",82.2,94.9,[(82.46,86.64,"For me, I think before I was not enjoying, I was very frustrated,\n以前我并不享受，总是很沮丧，"),(87.38,91.6,"and this kind of time gave me a lot of thinking,\n这段时间让我想了很多，"),(91.86,94.54,"to see what I want to do with my future.\n想清楚了未来要做什么。")],
  "同一条采访。medium 82.46–94.54 逐词，small 一致（small 多一个 not，按 medium 写）。段首 82.2 在 very,（81.84）之后。",
  "采访，不是回合。",kind="ceremony"))
S.append(photo("sh-sf-handshake.jpg",19.4,"十月十八号的决赛，对手是二十岁的霍达尔。两人从没交过手，两个西班牙人会师上海。四年前，西西帕斯对他说，第一次，但不会是最后一次。这是他第八个决赛。输过五次的人，你觉得这一次，他握得住吗？",
  "ATP Media 官方图库 2026 上海半决赛（photo 4593539「Alexander-ZVEREV-vs-Alejandro-DAVIDOVICH-FOKINA-0182」）：他笑着走到网前和兹维列夫握手。收尾回到上海这一场。决赛对手与首次交手：ATP 上海赛前要点 PDF＋ATP 霍达尔半决赛报道；第八个决赛＝此前 2 胜 5 负。",
  "https://www.atptour.com/en/news/zverev-davidovich-fokina-shanghai-2026-saturday",
  "照片里没有字，台头和字幕落在画面上下两条带里，不压脸。"))
json.dump(S,open('research/fokina-story-2026/gen/segments.json','w'),ensure_ascii=False,indent=1)
print(len(S),"segments")
