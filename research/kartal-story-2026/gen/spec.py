import json,sys
sys.path.insert(0,'research/kartal-story-2026/gen')
from labels import LABELS
V={"pitch":"+10Hz","_why":"网球有故事沿用云健 +18% 语速、+10Hz 音高（与 swiatek-chwalinska-story-2026 同一档）。"}
A='assets/reel/kartal-story'
def lab(k):
    return {"image":f"{A}/label-{k}.png","kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":7.0,"motion":"editorial","label":dict(LABELS[k])}
def n(src,a,b,text,why,ok="不是回合的收尾：画面是局间、近景、庆祝或采访，段尾不在一分打到一半。",label=None,crosses_cut=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":text,"voice":dict(V),"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    if crosses_cut: s["crosses_cut"]=crosses_cut
    return s
# 段与段之间有 0.18 秒溶解：原声字幕离段边至少 0.22 秒，否则会和相邻旁白段的窗口重叠。
EDGE=0.22
def q(src,a,b,cues,why,ok,label=None,kind="broadcast",crosses_cut=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":"","quote":[{"at":round(max(x-a,EDGE),2),"end":round(min(y-a,(b-a)-EDGE),2),"text":t} for x,y,t in cues],"_quote_kind":kind,"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    if crosses_cut: s["crosses_cut"]=crosses_cut
    return s
def card(title,kicker,sec,text):
    return {"title_card":title,"kicker":kicker,"seconds":sec,"narration":text,"voice":dict(V)}
def photo(img,sec,text,why,src,safety):
    return {"image":f"{A}/{img}","image_kind":"photo","seconds":sec,"narration":text,"voice":dict(V),"_why":why,"_photo_source":src,"_photo_caption_safety":safety}
QF_PHOTO="https://photoresources.wtatennis.com/wta/photo/2026/10/17/7878daa7-c5c9-466e-b455-084d83d626dc/Sonay_Kartal_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5-DSC_4105.jpg"
OPP="对手是另一场半决赛的胜者"
S=[]
# 冷开场：今天半决赛的第二个赛点、她举拍、包厢起立（WTA 官方集锦解说原声）
c=q("sf",252.7,275.6,[(264.1,266.95,"Kartal waltzes into the Wuhan final.\n卡尔塔尔闯进了武汉决赛！"),(267.32,270.9,"Her big moment in a 1000 arrives.\n她的一千赛高光时刻来了，"),(272.9,274.4,"An outstanding victory.\n一场了不起的胜利。")],
  "冷开场：WTA 官方集锦（abL2j0xldOc）第二盘抢七。252.60 切入时记分条是 7 6 6 / 6 6 5（第二个赛点，奥斯塔彭科发球；6-4 那个赛点她用反手制胜分救掉，解说 250.92 Saved in magnificent fashion），奥斯塔彭科这一拍打出边线，262.72 切到卡尔塔尔举拍，265.48 切到包厢起立。解说两档一致（medium 264.10–274.04；small 263.56–273.94，名字两档都转错，按官方标题写 Kartal）。段尾 275.6 在下一句 resilience（276.84）之前。",
  "赛点在 262 秒前后打完，之后是庆祝与包厢。",crosses_cut="254.08、256.28 是同一个赛点的发球与回合换机位，262.72、265.48 切到她举拍和包厢：都是同一个赛点前后的镜头。")
c["_ending_payoff_required"]=False
c["_ending_payoff_why"]="网球有故事：冷开场是本期由头（她怎么打进的决赛），正文倒回她的来路，回到武汉这一周时用同一场的第一盘抢七交代过程，最后用她赛后的场上采访收住，不重放赛点。"
S.append(c)
S.append(card("排名第170\n打进决赛","2026 武汉",7.2,"排名第一百七十。这个数字说的不是她的水平，是她停下来的那半年。"))
S.append(n("sf",213.95,223.3,"武汉一千赛半决赛，卡尔塔尔连赢两个抢七，淘汰了奥斯塔彭科。七个月前，她因为背伤退赛。",
  "同一条 WTA 官方集锦第二盘回合：镜头 213.84 切入、224.12 切走；两档转写在 213.70–223.44 无词。",
  "回合进行中，旁白不讲这一分；段尾停在切镜头之前。"))
# 01 从小的对手
S.append(card("和拉杜卡努\n一起长大","01",7.5,"她在布莱顿长大。从小到大，她最常碰到的对手，叫拉杜卡努。"))
S.append(n("u10",14.0,28.5,"二〇一一年，英国十岁以下组。两个小女孩，打出了一个停不下来的回合。后来，一个拿了美网冠军，一个还在一场一场地打。",
  "英国网协 LTA 官方频道「Young Emma Raducanu vs. Sonay Kartal | 2011 U10's Epic Rally」（INkEB95UIa8）：同一个广角机位一镜到底（0–41 秒无切点，41 秒起是 LTA 片尾）。两档转写在 0–24 无词，24.30 和 31.84 两档各报一个 you，画面里没人对着镜头说话，按现场噪声处理。拉杜卡努 2021 美网冠军为公知事实（仓库已有多条）。",
  "LTA 剪的是一个长回合，段尾 28.5 停在回合进行中、广角无切点——这一段讲的是两个小孩的来路，不是比分。"))
S.append(q("lta22",51.7,57.1,[(52.02,53.54,"Emma and I, we grew up playing each other,\n我和艾玛从小就是对手，"),(54.12,56.26,"kind of from mini tennis.\n从迷你网球就开始了。")],
  "英国网协 LTA 官方频道 2022 年专访「Getting to know Sonay Kartal」（vqIpczMjb5I）：她对着镜头讲队友。medium 52.02–56.26 一句完整，small 这一段无词（漏转），按 medium 与 LTA 官网同期稿（lta.org.uk/news/2022/april/introducing-sonay：Emma and I, we've grown up playing each other）写。镜头 51.56 切入、76.76 切走，段首 51.7 在 I mean（51.66）之后，段尾 57.1 远早于下一句（76.54）。",
  "采访，不是回合。",kind="ceremony"))
S.append(q("lta22",92.9,106.9,[(93.16,95.84,"I've got an older brother, he's five years older than me,\n我有个哥哥，比我大五岁，"),(96.48,98.48,"and he used to play just for fun.\n他打球只是为了好玩。"),(99.6,101.5,"And my parents used to take me up to the club,\n爸妈带我去俱乐部，"),(101.76,104.44,"and I used to just sit on the grass and watch him play.\n我就坐在草地上看他打。"),(105.28,106.64,"That's how it all began.\n一切就是这么开始的。")],
  "同一条 LTA 专访：她讲怎么开始打网球。两档逐词一致（medium 93.16–106.64；small 93.30–106.60）。镜头 81.52 切入、112.12 切走，段首 92.9 在上一句（88.82 结束）之后，段尾 106.9 在主持人下一问（106.96）之前。",
  "采访，不是回合。",kind="ceremony"))
S.append(q("lta22",171.6,181.1,[(172.14,173.84,"I also just want to still love tennis.\n我也想一直热爱网球，"),(174.34,178.48,"I don't want that feeling of enjoying coming on the court to ever disappear\n不想让上场的快乐消失，"),(179.32,180.92,"and almost have to feel like a chore.\n不想让它变成一份苦差。")],
  "同一条 LTA 2022 专访：主持人问目标，她说进前一百、打满大满贯之后补的这一句。两档逐词一致（medium 172.14–180.92；small 172.16–180.82，small 多一个 like、kind of，按 medium 写）。镜头 165.16 切入、181.32 切走，段首 171.6 在 slams（170.40）之后，段尾 181.1 让溶解（0.18 秒）停在切点之前。LTA 官网同期稿同句：I also still want to love tennis – I don't want that feeling of enjoying coming on the court to ever disappear。",
  "采访，不是回合。",kind="ceremony"))
# 02 一场一场打上来
S.append(card("一场一场\n打上来","02",9.8,"她个子不高，靠的是脚步和耐心，把一个又一个球救回去。她的排名，也是这么一场一场打上来的。"))
S.append(n("wb24",69.0,81.0,"二〇二四年温网，排名两百九十五的她，从资格赛打进第三轮。二十七年来，英国女子资格赛球员里，她是第一个做到的。",
  "温网官方频道「Sonay Kartal vs Coco Gauff | Highlights | Wimbledon 2024」（mXnEXUPITgg）第三轮回合，戴白帽的是卡尔塔尔。镜头 68.20 切入、83.52 切走，两档转写在这一段只有 63.58–89.88 一句 Thank you very much（两档都在广角回合上报，画面里没人说话，按幻听处理）。排名 295：维基 Sonay Kartal（In June 2024, ranked No. 295, she qualified）；英国女子资格赛选手 1997 年 Karen Cross 之后第一人：LTA 2024-07 稿＋tennismajors（见 _claims）。",
  "旁白不讲这一分的比分；段尾停在切镜头之前。",label="wb24"))
S.append(n("iw",190.5,200.4,"后来，她拿到生涯第一个冠军，最高升到世界第四十四。今年三月，背已经开始疼了，她还是逆转了凯斯。",
  "WTA 官方集锦「Madison Keys vs. Sonay Kartal | 2026 Indian Wells Round 3」（z8Sffkz5m8s）：镜头 189.96 切入、203.60 切走；两档转写在 190.42–200.48 无词。生涯第一冠 2024 莫纳斯提尔、最高世界第 44（2025-07-14）：维基＋NBC；比分 2-6 6-2 6-3、比赛中背已经不适（At times in this match I was in discomfort with my back）：WTA 4465394 Match Reaction＋AOL/BBC。",
  "旁白不讲这一分；段尾停在切镜头之前。",label="iw"))
# 03 停下来的半年
S.append(n("iw",55.9,64.6,"赢下凯斯那晚，她说比赛里背时不时在疼，可正是这样的比赛，打出了她身上的斗士。",
  "同一条印第安维尔斯集锦：镜头 55.84 切入、68.60 切走，段尾 64.6 在同一个镜头里；两档转写在 52.72–74.12 无词。原话 At times in this match I was in discomfort with my back, so it's a match like today which shows the fighter in me：BBC（AOL 转载）＋LTA 2026-03 稿。",
  "旁白不讲这一分；段尾停在切镜头之前。"))
S.append(card("停下来\n的半年","03",13.0,"两天后的第四轮，她撑不住了，四比六、三比四落后时退赛。背部应力性骨折。四个大满贯，她错过了三个，包括家门口的温网。"))
S.append(q("doc",113.7,143.5,[(113.82,115.52,"Tennis is all I've known, right?\n网球是我唯一熟悉的事，"),(116.04,117.64,"The past 18 years I've done it every day,\n过去18年我每天都在打，"),(118.12,122.28,"and just not being able to do that,\n突然什么都做不了，"),(122.54,126.88,"and just feeling so like I couldn't do the basic of things.\n连最基本的事都做不到。"),(127.38,132.22,"I couldn't brush my teeth without almost standing back up and just being in agony.\n刷牙都得马上直起腰，疼得要命。"),(132.6,134.44,"So it was definitely a tough injury,\n这真的是一次难熬的伤，"),(135.72,139.28,"but it's definitely made me a stronger person,\n但它让我变得更强大，"),(139.74,140.3,"a better person,\n变成更好的人，"),(140.4,143.02,"and hopefully it'll make me a better tennis player.\n希望也让我成为更好的球员。")],
  "英国网协 LTA 官方频道复出专访「The Comeback is ON | Sonay Kartal's Road Back From Injury」（8u0X2vm7svU，4K）：她坐着讲伤病。两档逐词一致（medium 113.82–143.02；small 114.02–143.00，small 把 all I've known 记成 what I've known、多一个 kind of，按 medium 写）。镜头 40.36 切入、174.72 切走，段首 113.7 在 So you've got those things and（112.20–113.58）之后，段尾 143.5 在主持人下一问（143.66）之前。",
  "采访，不是回合。",kind="ceremony"))
S.append(q("doc",395.6,406.0,[(396.24,399.24,"I've been kind of good to go really from kind of US Open time.\n其实美网时我就能复出了，"),(400.5,402.08,"Decided not to play that,\n但我决定不打，"),(402.96,405.6,"to almost just put my body under a bit more stress.\n让身体再多扛一些强度。")],
  "同一条 LTA 专访：主持人问复出时机。两档逐词一致（medium 396.32–415.90；small 396.24–415.88）。镜头 375.80 切入、421.88 切走，段首 395.6 在 choices to make（395.32）之后，段尾 406.0 在 stress（405.28–405.60）之后、下一个词 to（405.60 起，407.54 才接 try）之前，只留前半句。WTA 4593140 同一件事她在武汉的原话：ready to get back kind of end of August time … I didn't rush myself。",
  "采访，不是回合。",kind="ceremony"))
# 04 武汉的五场球
S.append(card("武汉的\n五场球","04",7.8,"她本可以早点回来。可她说，受伤后最好的建议，是别着急。"))
S.append(n("r2",131.5,143.5,"九月，她在比利·简·金杯总决赛复出。到了武汉，她先赢卡利尼娜和本西奇，又只用六十三分钟，送走了保利尼。",
  "WTA 本西奇那场集锦（1TKV_Ywr8J8）：镜头 131.36 切入、156.12 切走；两档转写在 131.36–153.94 无词。复出在比利·简·金杯总决赛：WTA 4593140＋AOL；保利尼 63 分钟：WTA 视频标题 Kartal routs Paolini in 63 minutes。",
  "旁白不讲这一分；段尾停在同一个镜头之内。"))
S.append(q("r2",279.2,295.3,[(279.4,281.5,"And takes it with a thunderous forehand,\n一记重炮正手拿下，"),(283.04,285.6,"and Sonay Kartal continues her comeback\n卡尔塔尔继续她的复出之路，"),(285.76,289.08,"from that stress fracture that saw her miss six months of this season.\n这个赛季她因应力性骨折缺席半年。"),(290.7,294.46,"Third round in Beijing is now matched with a third round appearance in Wuhan.\n继北京之后，武汉又进第三轮。")],
  "WTA 官方集锦「Sonay Kartal vs. Belinda Bencic | 2026 Wuhan Round 2」（1TKV_Ywr8J8）：赛点一拍正手、她握拳、致意。两档逐词一致（medium 279.40–294.46），名字两档都转错，按官方标题写 Sonay Kartal。段首 279.2 在赛点那一拍之前（第一个赛点解说 267.82），段尾 295.3 在 295.56 切镜头之前（溶解 0.18 秒不跨切点）。比分 6-0 7-5：LTA 2026-10 稿。",
  "赛点在 280 秒打完，之后是庆祝。",crosses_cut="280.88、282.64、285.16、291.00 是赛点那一拍之后的庆祝与致意镜头，都是她本人。"))
S.append(q("qf",266.5,284.5,[(266.76,271.48,"She's the first Briton ever to make the last four in Wuhan.\n首位打进武汉半决赛的英国人。"),(272.62,273.24,"What a story.\n多好的故事。"),(275.8,277.84,"Out for six months this season,\n这个赛季停了六个月，"),(278.44,283.62,"but now getting to the latter stages of the biggest of events.\n现在却打到了大赛的最后阶段。")],
  "WTA 官方集锦「Elina Svitolina vs. Sonay Kartal | 2026 Wuhan Quarterfinal」（T22a9v9UZuk）：赛后庆祝、握手、致意。两档逐词一致（medium 261.58–283.62；small 264.26–283.71），Briton 按 medium。段首 266.5 在 semi-final（265.02）之后、262.08 那个镜头之内，段尾 284.5 在 It's Kartal in three（285.60）之前。",
  "比赛已经结束，庆祝与致意。",label="qf",crosses_cut="277.72 切的是赛后庆祝、握手与看台，都是同一场比赛结束之后。"))
S.append(n("sf",99.7,114.6,"半决赛，对手两次发球胜盘，两次都被她破回。两盘都是先落后，再追回来。第一盘抢七，十一比九；第二盘，又是抢七。六个盘点，她一个没给。",
  "WTA 官方集锦（abL2j0xldOc）第一盘抢七：记分条 6 5 / 6 5（99.6–122 逐格读过：第一盘 6 平之后的抢七，5 平），镜头 99.52 切入、122.64 切走；两档转写在 102.76–119.06 无词，100.08–102.76 一句 managed to put her under pressure 和 119.06 so good 是解说低声，旁白压在上面。两次发球胜盘被破、救下 6 个盘点、抢七 11-9：The Independent（Yahoo）与 AOL（Express）赛报，WTA 4593140 比分 7-6(9) 7-6(5)。",
  "抢七回合进行中，旁白不讲这一分的比分；段尾 114.6 在抢七回合之间。",label="sf"))
S.append(q("sf",362.0,374.4,[(362.04,365.82,"I was dreaming of playing this match when I was fully fit before the injury,\n受伤之前，我就梦想打这样的比赛，"),(366.14,370.02,"so to be able to come back here in my third event\n复出第三站就能来到这里，"),(370.36,374.12,"and to achieve this regardless is a huge milestone for me.\n做到这一步，对我是一座里程碑。")],
  "同一条：赛后场上采访，主持人问排名 170 打进决赛。两档逐词一致（medium 362.04–374.12；small 363.48–374.10），开头 I was I was 的重复按书面去掉。段首 362.0 在主持人问句（360.20）与 Yeah you know（361.68–361.88）之后，段尾 374.4 在 so yeah（374.60）之前。",
  "场上采访，不是回合。",kind="ceremony"))
S.append(photo("wuhan-qf-smile.jpg",19.0,f"十月十八号的决赛，{OPP}。打完这一站，她会回到世界前五十左右，成为新的英国一姐。七个月前，她疼得连刷牙都难。伤好了，她没有急。如果是你，你等得住吗？这场决赛，你押她吗？",
  "WTA 官方图库「Sonay_Kartal_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5-DSC_4105」（photo 4593547，4700×3000，Day 5＝10 月 16 日 1/4决赛那天，白色背心与 Svitolina 那场集锦一致），裁 2250×3000（3:4，未放大）。排名升到第 50、成为英国一号：The Independent（Yahoo）赛报。",QF_PHOTO,
  "她的脸在画面上部 8%–30%，字幕区是球衣，不压脸。"))
json.dump(S,open('research/kartal-story-2026/gen/segments.json','w'),ensure_ascii=False,indent=1)
print(len(S))
