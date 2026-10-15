import json
V={"pitch":"+10Hz","_why":"网球有故事沿用云健 +18% 语速、+10Hz 音高（与 fault-not-out-2026 同一档）。"}
A='assets/reel/medvedev-real'
LABELS={
 "us19":{"topic":"被嘘进了决赛","date":"2019.09.08","place":"美网 决赛","score":"5-7 3-6 7-5 6-4 4-6","people":"梅德韦杰夫 vs 纳达尔"},
 "md21":{"topic":"不想在红土上打","date":"2021.05.05","place":"ATP1000 马德里 第二轮","score":"4-6 6-4 6-2","people":"梅德韦杰夫 vs 福基纳"},
 "ci21":{"topic":"撞上场边摄像机","date":"2021.08.21","place":"ATP1000 辛辛那提 半决赛","score":"6-2 3-6 3-6","people":"梅德韦杰夫 vs 卢布列夫"},
 "us21":{"topic":"拦下年度全满贯","date":"2021.09.12","place":"美网 决赛","score":"6-4 6-4 6-4","people":"梅德韦杰夫 vs 德约科维奇"},
 "ao22":{"topic":"对着主裁怒吼","date":"2022.01.28","place":"澳网 半决赛","score":"7-6(5) 4-6 6-4 6-1","people":"梅德韦杰夫 vs 西西帕斯"},
 "us23":{"topic":"颁奖台上的玩笑","date":"2023.09.10","place":"美网 决赛","score":"3-6 6-7(5) 3-6","people":"梅德韦杰夫 vs 德约科维奇"},
 "ao25":{"topic":"球拍砸向摄像机","date":"2025.01.14","place":"澳网 第一轮","score":"6-2 4-6 3-6 6-1 6-2","people":"梅德韦杰夫 vs 萨姆雷吉"},
 "mc26":{"topic":"生涯第一次双蛋","date":"2026.04.08","place":"ATP1000 蒙特卡洛 第二轮","score":"0-6 0-6","people":"梅德韦杰夫 vs 贝雷蒂尼"},
 "ws26":{"topic":"我该去打匹克球","date":"2026.08.25","place":"温斯顿-塞勒姆 第二轮","score":"5-7 3-6","people":"梅德韦杰夫 vs 达姆"},
}
def lab(k):
    return {"image":f"{A}/label-{k}.png","kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":4.2,"motion":"editorial","label":dict(LABELS[k])}
def n(src,a,b,text,why,ok="不是回合的收尾：画面是场边、近景或颁奖，段尾不在一分打到一半。",label=None):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":text,"voice":dict(V),"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    return s
def q(src,a,b,cues,why,ok,label=None,kind="broadcast"):
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":"","quote":[{"at":round(x-a,2),"end":round(y-a,2),"text":t} for x,y,t in cues],"_quote_kind":kind,"_why":why,"point_end_ok":ok}
    if label: s["inset"]=lab(label)
    return s
def card(title,kicker,sec,text):
    return {"title_card":title,"kicker":kicker,"seconds":sec,"narration":text,"voice":dict(V)}
S=[]
# 冷开场：2022 澳网半决赛换边时冲主裁吼（Wide World of Sports 原声）
c=q("ao22r",0.0,10.9,[(0.0,2.76,"His father can talk every point? Are you stupid?\n他父亲每一分都能说话？你傻吗？"),(3.18,10.38,"His father can talk every point, his father can talk every point!\n他父亲每一分都能说话，每一分！")],
  "冷开场：全片最出圈的一幕放到最前面当由头，正文讲到 2022 澳网时接着放后半段（第 23 段，11.2 秒起）。两档逐词基本一致（small 记成 can't talk，按 medium 的 can talk 写）。段尾 10.9 在下一句 Will you answer（11.46）之前。stupid 按账号所有者交接文档不算脏话，不消音。",
  "换边时的争执，不是回合。")
c["_ending_payoff_required"]=False
c["_ending_payoff_why"]="网球有故事：冷开场是全片由头，正文按时间讲九年的名场面，讲到 2022 澳网半决赛时接着放这段争执的后半段，交代来龙去脉和罚款。"
S.append(c)
S.append(n("ao22",311.3,325.8,"对着主裁大吼的这个人，就是梅德韦杰夫。撒硬币，踢摄像机，砸球拍，他的罚单能列一长串。可也是他，在颁奖台上让全场笑出了声。他是反派，还是只是太真实？","澳网官方加长集锦（uWxN2lH2Fa0），同一场半决赛第一盘的破发点回合，空当 296.89–336.47（两档转写都无词）。","这一分在 324 秒前后打完，段尾 325.8 停在西西帕斯握拳，换边之前。"))
S.append(card("被嘘的\n那几年","01",4.2,"故事要从二〇一七年的温网说起。"))
S.append(card("朝主裁椅\n扔了硬币","2017年温网 第二轮",9.6,"那年他二十一岁，五盘输给了贝梅尔曼斯。握手之后，他掏出几枚硬币，朝主裁的椅子扔了过去。"))
S.append(card("一时上头\n做了件坏事","罚款14500美元",8.0,"这场他一共被罚了一万四千五百美元。事后他说：一时上头，我做了件坏事。"))
S.append(n("us19",141.29,155.69,"两年后的美网，第一周他对着看台竖中指，被嘘了好几场。决赛他从零比二追到二比二，最后还是输给了纳达尔。被嘘了两个星期的人，在颁奖台上拿起了话筒。","美网官方颁奖仪式（9CQYJlU5_Ew），致辞之间的空当 141.29–155.69（两档转写都无词）。",label="us19"))
S.append(q("us19",128.6,141.2,[(128.9,131.6,"I want to talk about you guys.\n我想说说你们。"),(131.6,136.0,"I know, earlier in the tournament I said something kind of in a bad way.\n我知道，之前我说话不太好听。"),(136.0,138.6,"Now I'm saying it in a good way:\n现在我换个好听的说法：") ,(138.6,141.14,"because of your energy, guys, I was here in the final.\n是你们的能量把我送进了决赛。")],
  "梅德韦杰夫颁奖致辞原声，两档逐词一致（small 129.38–141.14、medium 129.26–141.14）。段首 128.6 在上一句 didn't go my way and I（128.5 前后）之后。","颁奖致辞，不是回合。",kind="ceremony"))
S.append(q("us19",192.7,208.9,[(192.84,196.0,"Yeah, as I said, it's electric.\n我说过，这里的气氛太热烈了。"),(196.0,200.5,"You were booing me for a reason, I never said that it was not,\n你们嘘我是有原因的，我从没否认，"),(200.5,203.6,"but you guys see that I can also change,\n但你们也看到了，我也能改变，"),(203.6,205.8,"because I'm a human being, I can make mistakes.\n我是人，我也会犯错。"),(206.1,208.68,"And again, thank you very much from the bottom of my heart.\n再次衷心感谢你们。")],
  "两档逐词一致（small 190.76–208.88；medium 192.84–208.68）。段尾 208.9 在 Thank you（209.42）之前。","颁奖致辞，不是回合。",kind="ceremony"))
S.append(card("冠军\n也一样真","02",5.2,"后来他拿了大师赛，拿了大满贯，脾气一点没改。"))
S.append(n("md21",91.95,105.0,"二〇二一年马德里，他在红土上已经连输六场。比赛打到一半，他边走边嘟囔，说根本不想在这种场地上打球。","Tennis TV 官方马德里第二轮集锦，回合间空当 91.95–115.15。","第二盘回合，旁白不讲这一分；段尾 105.0 在空当之内。",label="md21"))
S.append(q("md21",12.5,19.98,[(12.64,14.36,"Yeah, he's not looking happy, Medvedev.\n梅德韦杰夫看起来很不高兴。"),(14.66,16.92,"I don't want to play here on this surface.\n我不想在这种场地上打球。"),(17.68,19.98,"Well, pretty clear what he's thinking.\n他心里怎么想，很清楚了。")],
  "梅德韦杰夫本人的牢骚夹在解说之间。medium 逐词：surface；small 记成 circuit，按 medium 与画面写 surface。段尾 19.98 在 ASR 末尾的 Thank you 幻听（19.98 起，两档都只有这一词且画面无人说话）之前。","第一盘局间，不是回合。"))
S.append(n("md21",106.0,115.1,"结果他翻盘赢下了这场，止住了红土上的六连败，这也是他第一次在马德里赢球。","第三盘回合，空当之内。","第三盘回合与庆祝，段尾 115.1 在解说开口（115.15）之前。"))
S.append(q("md21",148.0,156.3,[(148.4,150.8,"See what he's writing on the camera here.\n看他在镜头上写了什么。"),(150.8,153.34,"It might be something about clay.\n好像跟红土有关。"),(154.36,156.18,"He loves the clay, of course he does.\n他爱红土，当然爱。")],
  "赛点后他在镜头上写下 Love clay :)。两档一致（small 144.30–156.10 记成 Klee；medium 147.16–156.18 写 clay）。段首 148.0 在 and ace（147.16–147.9）之后。","比赛已经结束，签名镜头。"))
S.append(n("ci21",0.15,9.69,"同一年八月，辛辛那提半决赛，对手是卢布列夫。他追一个球，整个人撞上了场边的摄像机。","Tennis TV 官方「Medvedev Collides With Court Camera in Cincinnati」，撞上摄像机在 7.5 秒前后，空当 0.15–9.69。","这一分在撞上摄像机时结束，段尾 9.69 在解说开口之前。",label="ci21"))
S.append(q("ci21",12.9,16.2,[(13.06,16.06,"You okay, sir?\n你没事吧，先生？")],
  "两档一致（small 13.06–16.06；medium 段首记在 9.84，词只有 You ok sir）。","撞上摄像机之后，不是回合。"))
S.append(n("ci21",16.27,29.6,"他先问了问摄像师，转头就让主裁把摄像机挪走：我的手差点撞断了。接着他又踢了一脚镜头。领先一盘的比赛，最后他输给了卢布列夫。","空当 16.27–32.25，踢镜头在 27 秒前后。","交涉与踢镜头，不是回合。"))
S.append(n("us21",124.5,135.8,"二〇二一年美网决赛，德约科维奇离年度全满贯只差一场。全场都在等他创造历史，梅德韦杰夫没给他机会，三盘全是六比四。","美网官方决赛集锦（MEFpXBwnyQA），第三盘回合，空当 114.87–143.47。","第三盘的回合，段尾 135.8 在冠军点那一分（136 秒发球）开始之前。",label="us21"))
S.append(q("us21",136.0,149.1,[(145.36,148.98,"Six-four, six-four, six-four.\n6比4、6比4、6比4。")],
  "冠军点那一分＋倒地。两档：small 143.62–148.96、medium 145.36–148.98，按 medium 写比分。136–145 只有现场声。","冠军点在 142 秒打完，之后是倒地庆祝。"))
S.append(n("us21",149.13,159.4,"他慢慢倒在地上，吐着舌头，像一条死鱼。这是他从足球游戏里学来的庆祝，说是给一起打游戏的朋友看的。","倒地庆祝之后，妻子在看台、网前握手；空当 149.13–161.97。"))
S.append(n("ao22",299.8,311.2,"二〇二二年澳网半决赛，对手是西西帕斯。他认定对方父亲在看台上一直指导，主裁却不管。于是有了开头那一幕，他还没吼完。","澳网官方加长集锦（uWxN2lH2Fa0），回合画面，空当 296.89–336.47。","回合间画面，旁白不讲这一分；段尾在空当之内。",label="ao22"))
S.append(q("ao22r",11.2,29.1,[(11.46,15.48,"Will you answer my question? Can you answer my question, please?\n你能回答我的问题吗？"),(15.98,17.44,"Can his father talk every point?\n他父亲能每一分都说话吗？"),(19.58,22.02,"Oh my God, you are so bad, man.\n天哪，你太差劲了。"),(23.62,25.92,"How can you be so bad in the semi-final?\n半决赛你怎么能这么差？"),(25.92,29.06,"Look at me, I'm talking to you.\n看着我，我在跟你说话。")],
  "澳网转播方 Nine 的 Wide World of Sports 官方频道（xH4R5HNq-6s）：冷开场那段争执的后半段。两档逐词基本一致。段首 11.2 在冷开场最后一句（10.38）之后。","换边时的争执，不是回合。"))
S.append(q("ao22r",90.1,93.9,[(90.28,93.76,"If you don't, you are a, how can I call it, small cat.\n不然你就是个，怎么说呢，小猫。")],
  "两档一致（small 88.04–93.72；medium 90.28–93.76）。段首 90.1 在上一句（87.10–89.90）之后。","换边时的争执，不是回合。"))
S.append(n("ao22",474.9,483.7,"他因此被罚了一万两千美元，赛后说自己完全后悔。四盘过后，他还是进了决赛。","比赛结束、握手，空当 474.87–489.73。"))
S.append(card("低谷里的\n梅总","03",5.6,"这几年，冠军越来越难拿，他的情绪也越来越藏不住。"))
S.append(n("us23",136.53,146.61,"二〇二三年美网决赛，他又输给了德约科维奇。颁奖台上，他先开了个玩笑。","美网官方颁奖仪式（6q9HMdjYpVg），致辞之间空当 136.53–146.61。",label="us23"))
S.append(q("us23",153.1,185.7,[(153.28,157.64,"First of all, I want to ask Novak, what are you still doing here? Come on.\n先问问诺瓦克：你怎么还在这儿？"),(159.56,164.98,"No jokes apart. What is it, our third final?\n不开玩笑，这是第三次决赛了吧？"),(165.5,167.66,"Maybe not the last. Hope so.\n也许不是最后一次，希望吧。"),(167.84,170.9,"Because you're probably going to be in many more.\n你大概还会进很多次。"),(171.36,175.6,"I don't know when are you planning to slow down a little bit,\n不知道你打算什么时候慢下来，"),(175.6,178.3,"but congrats to you and your team.\n恭喜你和你的团队。"),(178.44,181.6,"I mean, 24. I feel like I have not a bad career,\n24个啊。我觉得我生涯还不错，"),(181.6,184.86,"and I have 20 titles. You have 24 Grand Slams. Wow.\n我有20个冠军，你有24个大满贯。")],
  "梅德韦杰夫颁奖致辞原声，两档逐词一致（small 153.56–182.84；medium 153.28–184.86）。段尾 185.7 在下一句 And so yeah（185.90）之前。","颁奖致辞，不是回合。",kind="ceremony"))
S.append(n("us23",191.6,198.17,"接着，他讲起了一件巧事：那天又是他的结婚纪念日。","致辞中间的掌声空当 189.29–198.17。"))
S.append(q("us23",198.3,225.4,[(198.4,202.9,"On the second note, I was here two years ago when I won,\n还有一件事，两年前我在这里夺冠，"),(202.9,210.0,"and I was like, what a great anniversary gift for my wife.\n我想，这份纪念日礼物真不错。"),(210.0,215.5,"And yeah, it's funny, because dates usually change,\n有意思的是，日期一般会变，"),(215.5,220.5,"but today, Sunday, again is the anniversary,\n可今天这个星期天，又是纪念日，"),(220.5,222.64,"so I thought, come on, do it one more time.\n我就想，来吧，再来一次。"),(222.64,225.26,"But, yeah, it didn't happen.\n可惜，没成。")],
  "梅德韦杰夫颁奖致辞原声，两档一致（medium 198.40–225.26）。德约随后致辞也说 Happy anniversary to your wife（644.12），互相印证。段尾 225.4 在下一句（231.66）之前。","颁奖致辞，不是回合。",kind="ceremony"))
S.append(n("ao25",296.0,306.8,"二〇二五年澳网首轮，对手是世界第四百一十八位的萨姆雷吉。这场他打得很挣扎，第三盘丢掉，大比分一比二落后。","澳网官方加长集锦（MWNZOZr_uMU），第三盘结束后的近景与观众，空当 293.25–306.87；记分条 2-6 6-4 6-3（萨姆雷吉 2、6、6 / 梅德韦杰夫 6、4、3）。",label="ao25"))
S.append(q("ao25",306.9,325.9,[(307.02,312.6,"Well, through the soft, forgiving lens of nostalgia,\n隔着怀旧那层柔光滤镜，"),(312.6,317.26,"and you'll excuse the pun of lens,\n原谅我拿镜头打比方，"),(318.0,321.72,"you'll forgive him, because he's going to be paying for that camera,\n你会原谅他，反正摄像机他得赔，"),(321.72,325.78,"and he'll be happy to put his hand in his pocket if he wins this match.\n只要赢下这场，他掏钱也乐意。")],
  "球拍砸向网上摄像机（308–323 秒近景），解说原声两档一致（small 310.38–325.36；medium 307.02–325.78）。两档转写里都没有梅德韦杰夫本人的话，未见脏话，不消音。","第三盘与第四盘之间砸拍，不是回合；段尾在下一分（326 秒）之前。"))
S.append(n("ao25",325.93,335.6,"这场他最后五盘赢了下来。可这一届澳网，砸摄像机加上第二轮的事，他一共被罚了七万六千美元。","第四盘回合，空当 325.93–338.55。","第四盘回合，旁白不讲这一分；段尾 338.5 在解说开口之前。"))
S.append(n("mc26",93.97,107.0,"今年蒙特卡洛第二轮，他零比六、零比六输给贝雷蒂尼，只打了四十九分钟。这是他职业生涯第一次吃到双蛋。","Tennis TV 官方（yNxzL-8i9NU），第二盘回合，空当 93.97–107.07。","第二盘回合，旁白不讲这一分；段尾在解说开口（107.22）之前。",label="mc26"))
S.append(q("mc26",107.1,111.5,[(107.22,111.42,"This is becoming a real headache now for Medvedev, and goodness me.\n梅德韦杰夫真的头疼了，天哪。")],
  "摔拍（109.25–111.4），两档一致（small 107.22–111.42；medium 107.84–111.42）。两档转写里没有梅德韦杰夫本人的话，未见脏话，不消音。","摔拍，不是回合。"))
S.append(n("mc26",152.0,162.5,"他把球拍砸了好几下，最后扔进了场边的垃圾桶。整场比赛，他一局都没拿到。","赛点后两人走向网前握手，空当 151.15–164.61；段尾在 Tennis TV 片尾台标（约 164 秒）之前。官方集锦没有扔垃圾桶的画面，旁白按报道讲。","比赛已经结束，握手。"))
S.append(n("ws26",123.17,136.0,"八月的温斯顿-塞勒姆，他是头号种子，却直落两盘输给了外卡达姆，这是达姆第一次赢下世界前十。五场输了四场，他开始认真考虑转行。","Tennis TV 官方当日集锦（l7F7uLC-GGM），梅德韦杰夫与达姆的回合，空当 123.17–143.15。","回合中间的一段，旁白不讲这一分；段尾在空当之内。",label="ws26"))
c=q("wsc",0.0,17.6,[(0.6,3.6,"Maybe I should start a career in pickleball,\n也许我该改行打匹克球，"),(3.6,5.8,"not too late,\n现在还不晚，"),(5.8,8.6,"with Jack Sock, in doubles.\n和索克搭档打双打。"),(11.0,14.9,"Every sport on this planet is better, man.\n这星球上哪项运动都更好。"),(14.9,17.6,"Even curling right now.\n现在连冰壶都更好。")],
  "Tennis TV 官方竖版短片（9aqUxco0bqo，Tennis TV 台标、片内烧录黄字）：前半是场边椅子上的自言自语，后半是赛后发布会。前半两档转写对得上（medium：start a career in pickleball, not too late, with jacksaw…）；后半两档都没转出来，按片内烧录字幕逐字写。","场边与发布会，不是回合。")
S.append(c)
S.append(n("us19",210.01,219.2,"扔硬币的是他，在颁奖台上让全场鼓掌的也是他。你更喜欢哪一个梅总？","2019 美网颁奖，致辞结束后他笑着举手致意，空当 210.01–219.25。"))
json.dump(S,open('research/medvedev-not-villain-2026/gen/segments.json','w'),ensure_ascii=False,indent=1)
json.dump(LABELS,open('research/medvedev-not-villain-2026/gen/labels.json','w'),ensure_ascii=False,indent=1)
print(len(S))
