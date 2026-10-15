import json
V={"pitch":"+10Hz","_why":"网球有故事沿用云健 +18% 语速、+10Hz 音高（与 let-not-net-2026 同一档）。语速走 --rate +18%，音高逐段写在这里。"}
def n(src,a,b,text,ok="B-roll，配旁白讲道理，不讲这一分。"):
    return {"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":text,"voice":dict(V),"point_end_ok":ok}
def q(src,a,b,cues,why,ok):
    return {"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":"","quote":[{"at":round(x,2),"end":round(y,2),"text":t} for x,y,t in cues],"_quote_kind":"broadcast","_why":why,"point_end_ok":ok}
def card(title,kicker,sec,text):
    return {"title_card":title,"kicker":kicker,"seconds":sec,"narration":text,"voice":dict(V)}
S=[]
S.append(q("ao",17.0,29.6,[(1.5,3.7,"Foot fault!\n脚误！"),(6.3,8.74,"Pretty handy if you haven't released the ball yet.\n他球都还没抛出去呢。"),(8.74,12.46,"That AI has got to kind of calm down a bit.\n这个 AI 得冷静一下了。")],
  "冷开场：2025 澳网汤普森对科普费尔，电子司线在发球方抛球之前连喊脚误（画面先是汤普森、再切到准备发球的球员，旁白不点名是谁）。两档整片转写只转到解说（23.3–29.46，逐词一致：pretty handy… / that AI… calm down a bit）；电子司线的喊声在两档整片转写里都没有，另用 2 秒小窗、带提示词的 medium.en 补探（research/fault-not-out-2026/asr_probe.py）在 18.62、19.00、19.44、20.30 秒各探到一次 Foot fault，与解说随后说的 foot fault remix 对得上，字幕不写次数，只写一条 Foot fault 覆盖 18.5–20.7。",
  "冷开场是发球前的准备与喊声，不是回合；段尾 29.6 在下一句解说（30.78）之前。"))
S.append(n("wb",22.2,30.4,"这是二〇二五年澳网，电子司线连喊脚误，可发球的人连球都还没抛。"))
S.append(n("wb",43.2,51.6,"发球出了问题，不管是机器还是司线，喊的都是 fault，不是 out。这是为什么？"))
S.append(card("Fault不是出界\n是没做到","01",5.6,"因为 fault 说的不是球落在哪，而是这一发没做到。"))
S.append(n("wb",81.0,92.4,"fault 来自古法语，本义是缺失、做不到。英语的 fail 是失败，网球里取消比赛资格叫 default，都出自同一个拉丁词根。"))
S.append(n("wb",92.6,104.0,"发球的目标，是斜对面那一个发球区。球落在发球线后面、底线前面，还在场地里，喊 out 说不通。"))
S.append(n("wb",104.2,111.8,"所以回合里的球出界，喊 out；发球没落进发球区，喊 fault。"))
S.append(card("机器也分\nOut和Fault","温网",11.4,"二〇二五年温网，比赛场上不再有司线员，电子司线接手。系统里预录的人声，照样分成三句：out，fault，foot fault。"))
S.append(card("球没出界\n也能是Fault","02",11.0,"规则里的 fault，比发球出界宽得多。脚误、挥拍没碰到球、球先砸到网柱，甚至砸到自己的搭档，都算。"))
S.append(n("ky",2.6,8.0,"二〇一八年温网，克耶高斯发球，司线盯着他的脚。","克耶高斯发球的近景，这一发打出去之后的判罚在下一段。"))
S.append(q("ky",8.0,16.8,[(0.0,3.5,"Oh, he's been called. There it is.\n被判了，就是这一下。"),(5.4,7.12,"Yeah, that's what he has to do.\n他只能这么做。"),(7.22,8.7,"He can't call it before you hit it.\n你击球之前，他不能喊。")],
  "温网官方。两档转写一致（small 8.08–11.36、13.80–16.48；medium 8.84–11.46、11.46–16.66）。2 秒小窗补探在 8.48 秒探到 fault 一词，可能是司线的喊声，两档整片转写都没有，未能确认，字幕不加。",
  "司线判脚误之后的交涉与回放，不是新的一分；段尾 16.8 在下一句解说（19.40）之前。"))
S.append(n("wb",168.0,176.6,"女子巡回赛的规则书里写着：脚误要是在击球之前就喊，这一发判 let，再发一次。"))
S.append(n("md",0.0,8.3,"二〇二一年年终总决赛抢七，梅德韦杰夫二发被判脚误。主裁看了回放。","判罚前后的远景和主裁近景；窗口在两档转写都无人声的 0–8.48 之间。"))
S.append(q("md",46.85,61.8,[(0.17,1.29,"Does the foot touch the line?\n脚碰到线了吗？"),(2.15,2.99,"Oh, that's tight.\n哦，太接近了。"),(4.11,4.79,"You show it again.\n再放一遍。"),(5.05,6.05,"That's really tight.\n真的太接近了。"),(6.67,9.53,"That's a tough judgment call, isn't it?\n这一下很难判，对吧？"),(10.07,14.77,"Has he put enough pressure onto the front part of the foot to touch the line?\n他前脚掌压下去，碰到线了吗？")],
  "Tennis TV 官方。两档逐词一致（medium 47.02–61.62；small 47.06–61.60），medium 把 onto 记成 on to，按 small 写。段首 46.85 在上一句 as we'll see（46.78）之后。",
  "脚误回放的慢镜头，不是新的一分。"))
S.append(q("md",74.8,81.14,[(0.08,2.14,"Well, make your own mind up about that one.\n是不是脚误，你自己判断吧。"),(2.32,6.26,"Mohamed Lahyani is sticking with the call.\n主裁拉哈亚尼维持原判。")],
  "两档逐词一致；ASR 把主裁名拼成 Lajani，按本人姓名 Lahyani 写。段尾 81.14 在下一句 We can see（81.18）之前。",
  "主裁宣布维持原判，不是回合。"))
S.append(q("md",129.2,139.22,[(0.14,2.72,"I'm like, maybe I touched the line,\n我心想，也许我是碰到线了，"),(2.72,4.42,"but I was so close.\n可差得太少了。"),(4.42,7.18,"So I want to say, if you want to call it on the second serve,\n所以我想说：要在二发上判，"),(7.18,10.0,"make an electronic system for this.\n就上电子系统吧。")],
  "梅德韦杰夫赛后场上采访原话，两档逐词一致（medium 多记一个 if you 口误，按 small 写）。段尾 139.22 在 this（139.20）之后、下一句 I don't think（139.20 起，small 139.44）之前。",
  "赛后采访，不是回合。"))
S.append(n("wb",224.6,230.4,"其实就在那一年，澳网已经把脚误也交给了电子系统。"))
S.append(n("bu",0.0,4.5,"今年中网，布勃利克也被判了脚误。","布勃利克发球的远景，判罚喊声在下一段；窗口在两档转写都无人声的 0–4.56 之间。"))
S.append(q("bu",4.5,7.6,[(0.1,1.42,"It's all going on.\n热闹起来了。"),(1.68,2.96,"If you didn't hear, foot fault.\n没听清的话：脚误。")],
  "Tennis TV 官方。两档逐词一致（small 记成 foot fault，medium 连写 footfault）。",
  "判罚之后的交涉，不是回合。"))
S.append(n("bu",21.6,27.6,"这回他踩的是中点的延长线，规则里，这也算脚误。","布勃利克交涉之后回到发球位，不是回合；窗口在两档转写都无人声的 21.44–27.76 之间。"))
S.append(q("bu",37.3,52.5,[(0.14,5.98,"So you say it's actually the centre line?\n你是说，其实是中线？"),(8.84,11.56,"I played tennis 30 years.\n我打了 30 年网球，"),(11.56,14.48,"The first time I hear this foot fault in my life.\n这辈子头一回听说这种脚误。")],
  "两档转写一致（small 37.44–43.22、46.18–51.66；medium 40.26–43.28、46.14–51.78）。两档都把最后一句记成 this is also football，按画面里布勃利克向主裁交涉、话题正是这次脚误，写作 this foot fault。段尾 52.5 在 Yeah, it is（52.62）之前。",
  "场边交涉，不是回合。"))
S.append(card("两次Fault\n丢掉一分","03",7.0,"一发失误，还有二发；连着两次 fault，就是双误，直接丢一分。"))
S.append(q("rb",0.0,5.7,[(1.86,5.54,"I can't believe what we're seeing.\n真不敢相信眼前这一幕。")],
  "澳网官方。两档一致（small 1.86–5.46，medium 2.14–5.54）。段尾 5.7 避开 6.72–7.52 那句两档都听不清的话。",
  "双误之后的反应，不是回合。"))
S.append(q("rb",8.4,14.6,[(0.1,2.72,"Double fault from Rublev,\n鲁布列夫双误，"),(3.14,6.1,"another turnaround, 5-4 deep in the third.\n第三盘 5比4，局面又变了。")],
  "两档逐词一致（small 8.68–14.42，medium 8.50–14.50）。",
  "双误之后的反应，不是回合。"))
S.append(n("rb",15.0,26.0,"二〇一八年澳网，第三盘五比四，鲁布列夫双误，球拍遭了殃。连着两次没做到，这一分就白白送了出去。","鲁布列夫回到座位、擦汗，不是回合；窗口在两档转写都无人声的 14.50–30.00 之间。"))
S.append(card("一次脚误\n送出赛点","2009年美网",12.0,"最出名的一次 fault，在二〇〇九年美网半决赛。小威廉姆斯五比六、十五比三十，二发被判脚误，变成双误，对手拿到赛点。"))
S.append(card("罚掉一分\n比赛结束","小威廉姆斯",9.0,"她对着司线怒吼，被判违反体育道德，罚一分。这一分正好是赛点，比赛就这样结束了。"))
S.append(card("31次双误\n她还是赢了","1999年澳网",8.4,"也有人双误三十一次，照样赢球：一九九九年澳网，库尔尼科娃三盘击败佐伯美穗。"))
S.append(n("wb",230.6,240.6,"别的项目也用 fault。羽毛球的规则里，出界、触网、发球违例，统统叫 fault，out 只是其中一种。"))
S.append(n("wb",240.8,250.0,"壁球更狠，只有一次发球，失误就丢分。网球的职业表演赛 UTS，也只给一次发球。"))
S.append(n("wb",276.0,286.4,"所以 out 说的是球落在哪，fault 说的是这一发没做到。要是网球也只给一次发球，你觉得比赛会更好看吗？","B-roll，窗口在两档转写都无人声的 274.0–292.0 之间。"))
json.dump(S,open('/tmp/claude-0/fault/gen/segments.json','w'),ensure_ascii=False,indent=1)
print(len(S))
