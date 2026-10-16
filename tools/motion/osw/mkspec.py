import json,sys
sys.path.insert(0,'/workspace/tennislive/tools'); sys.path.insert(0,'/workspace/tennislive')
from pathlib import Path
SLUG="ostapenko-swiatek-h2h-2026"
REL=f"https://github.com/robertyang87/tennislive/releases/download/reel-src-{SLUG}/"
yt=lambda i:"https://www.youtube.com/watch?v="+i
sources={"bhm19":yt("M8Yz16YMWNI"),"uso23f":yt("XjP-EPi24Bo"),
 "doh25f":yt("2NzTfbETqPc"),"stu25":yt("BRiLTQbYYXQ"),"wuhsh":yt("uI4UCjY34b4"),"wuhli":yt("N6FzVa8YsdQ"),
 "iw21":yt("wOsrLbiWZJ4"),"dxb22":yt("vNSSJMmRIBM")}
V={"pitch":"+10Hz","_why":"网球有故事沿用云见 +18% 语速、+10Hz 音高。"}
def L(key,topic,date,place,score,people="奥斯塔彭科 胜 斯瓦泰克"):
    return {"label":{"topic":topic,"date":date,"place":place,"people":people,"score":score},"image":f"assets/reel/osw/osw-{key}.png",
            "kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":3.2,"motion":"editorial"}
S=[]
V_='交手全表 6 场全是奥斯塔彭科胜（2019 伯明翰、2021 印第安维尔斯、2022 迪拜、2023 美网、2025 多哈、2025 斯图加特），2025-04-19 之后至 2026-10-16 两人未再交手： https://www.tennislive.net/wta/match/jelena-ostapenko-VS-iga-swiatek/nature-valley-classic-birmingham-2019/ ；https://www.foretennis.com/matches/wta/ostapenko-swiatek/104122 ；WTA 2025-02-14 稿 5-0 https://www.wtatennis.com/news/4216096/ostapenko-makes-it-a-perfect-5-0-against-swiatek-to-reach-doha-final'
def seg(src,a,b,narr="",inset=None,why=""):
    if isinstance(inset,str): why,inset=inset,None
    s={"source":src,"start":a,"end":b,"cx":0.5,"track":False,"narration":narr}
    if narr: s["voice"]=V
    if inset: s["inset"]=inset
    if why: s["_why"]=why
    if src.startswith("a_"): s["_band_skip_why"]="全屏动效图表卡：账号所有者 2026-10-16 定，右上角字卡只贴在比赛画面上，图表卡不贴。"
    if False: s["_band_skip_why"]="同一场 2023 美网，信息条已在本场第一段（uso23s）贴过。"
    if src=="doh25" and len(S)>10: pass
    S.append(s)
def Q(src,a,b,en,zh,at=0.2,end=None,why="",cold=False):
    seg(src,a,b,"",why); S[-1]["quote"]=[{"at":at,"end":end or round(b-a-0.2,2),"text":en+"\n"+zh}]; S[-1]["_quote_kind"]="broadcast"
    if cold: S[-1]["_ending_payoff_required"]=False; S[-1]["_band_skip_why"]="冷开场，这一场在正片首次出现时贴了右上角信息条。"
def C(): S[-1]["_ending_payoff_required"]=False; S[-1]["_band_skip_why"]="冷开场，这一场在正片首次出现时贴了右上角信息条。"
# 开场
seg("doh25f",3457.6,3461.0,"做过世界第一的斯瓦泰克，","2025 多哈半决赛（WTA 官方全场 1080p）斯瓦泰克近景，解说空当。");C()
seg("doh25f",3464.0,3468.6,"偏偏有一个人，她一次都没赢过。",L("h2h","交手纪录","2025.04.19","六次交手","6-0","奥斯塔彭科 vs 斯瓦泰克"),"多哈赛点回合，右上角叠 6-0 交手角标。");S[-1]["_ending_payoff_required"]=False
Q("doh25f",3473.9,3481.6,"And a reaction to match, Jelena Ostapenko!","赛点拿下，看奥斯塔彭科的反应！",at=2.5,end=7.4,why="赛点后奥斯塔彭科转身庆祝、全场起立。",cold=True)
# 2019
seg("bhm19",21.2,27.2,"伯明翰草地，十八岁的资格赛选手斯瓦泰克，遇上法网冠军。",
    L("bhm19","第一次交手","2019.06.18","伯明翰首轮 · 非官方画面","6-0 6-2"),"粉丝号搬运的 WTA 转播原片：Nature Valley 草地全景、局间斯瓦泰克与教练交流。非官方画面，角标已注明。")
seg("bhm19",27.2,33.2,"首盘六比零，全场接发球三十八分拿下二十四分。",L("ret52","接发球得分率","2025.04.19","六场合计 matchstat","52%","奥斯塔彭科"),"局间斯瓦泰克与教练场边交流（解说此前说奥斯塔彭科首盘五比零领先）。")
# 2021 / 2022：WTA 官方集锦 720p，账号所有者 2026-10-17 点名放大铺满 + 轻锐化
seg("iw21",242.3,248.1,"二零二一年印第安维尔斯，二号种子斯瓦泰克，",L("iw21","第二次交手","2021.10.12","印第安维尔斯 1/8决赛","6-4 6-3"),"2021 印第安维尔斯 WTA 官方集锦：首盘慢镜回放多角度，解说空当。");S[-1]["point_end_ok"]="242–252s 是上一分的多角度慢镜回放（contact_04 看过），画面没有常驻记分条，248.8s 的翻牌是回放换机位被误认。"
Q("iw21",259.6,267.5,"Ostapenko breaks. What a first set from Jelena Ostapenko.","奥斯塔彭科破发！首盘打得太漂亮了。",why="首盘破发制胜分与奥斯塔彭科庆祝。");S[-1]["point_end_ok"]="破发那一分在 263s 前打完（contact_04：264.5s 奥斯塔彭科庆祝、266–270s 看台），267.9s 的翻牌是盘末比分字板。"
seg("iw21",458.6,462.6,"四比六、三比六，两盘出局。","赛点前奥斯塔彭科发球局。")
seg("dxb22",220.2,226.0,"二零二二年迪拜，斯瓦泰克先拿一盘，",L("dxb22","第三次交手","2022.02.16","迪拜","4-6 6-1 7-6(4)"),"2022 迪拜 WTA 官方集锦回合，解说空当。")
seg("dxb22",337.5,342.5,"决胜盘，奥斯塔彭科先破发。","决胜盘破发后（解说 329–336s：finds the first break in the deciding set）。")
seg("dxb22",466.0,471.5,"抢七七比四，斯瓦泰克被逆转。","决胜盘抢七回合。")
seg("dxb22",494.9,500.6,"这是她三十七连胜前，最后一场失利。","赛后看台与场边近景。")
# 2023（美网官方全场 1080p）
seg("uso23f",4919.6,4925.4,"二零二三年美网，斯瓦泰克是卫冕冠军，也是世界第一。",
    L("uso23","世界第一之夜","2023.09.03","美网 1/8决赛","3-6 6-3 6-1"),"决胜盘斯瓦泰克近景与回合。")
seg("uso23f",4926.0,4931.0,"斯瓦泰克先赢一盘，奥斯塔彭科随即提速。","决胜盘回合。")
seg("uso23f",4979.2,4985.0,"奥斯塔彭科说：打得又快又狠，斯瓦泰克就有麻烦。","决胜盘回合，奥斯塔彭科底线准备。")
seg("uso23f",5004.0,5009.6,"决胜盘六比一。","赛点回合。")
Q("uso23f",5009.6,5018.0,"Game, set, Jelena Ostapenko stuns number one.","奥斯塔彭科爆冷击败世界第一！",why="赛点后奥斯塔彭科转身庆祝、全场。")
seg("uso23f",5019.4,5026.0,"七十五周的世界第一到此为止。她说：突然间，我失去了控制。",L("uso75","世界第一止步","2023.09.04","美网 1/8决赛后","75周","斯瓦泰克 连续世界第一"),"网前握手，斯瓦泰克在画面中，右上角叠 75 周角标。")
# 2025 多哈（WTA 官方全场 1080p）
seg("doh25f",3430.6,3436.6,"二零二五年多哈，三届卫冕冠军斯瓦泰克。",
    L("doh25","终结三连冠","2025.02.14","多哈 半决赛","6-3 6-1"),"斯瓦泰克发球近景，场边时钟 1:09。")
Q("doh25f",3436.7,3441.6,"I'm just trying to think the last time Swiatek lost a match winning just four games.","她上次只拿四局就输球，是何时？",why="斯瓦泰克发球局。")
Q("doh25f",3487.5,3496.55,"She has the winning formula against Swiatek,","她有赢斯瓦泰克的公式，",at=0.1,end=4.4,why="网前握手后奥斯塔彭科挥手致意。");S[-1]["quote"].append({"at":4.5,"end":8.85,"text":"as the three-time champion is brushed aside.\n三届冠军被扫地出局。"})
# 2025 斯图加特
seg("stu25",246.0,250.2,"同年斯图加特，斯瓦泰克扳回一盘，",
    L("stu25","第六次交手","2025.04.19","斯图加特 1/4决赛","6-3 3-6 6-2"),"决胜盘末段回合。")
seg("stu25",250.4,254.6,"决胜盘六比二，还是她。","决胜盘赛点前回合。")
Q("stu25",260.95,269.6,"It is a sensational six in a row","惊人的六连胜，",end=4.6,why="赛点与奥斯塔彭科握拳。");S[-1]["quote"].append({"at":4.7,"end":8.5,"text":"for Jelena Ostapenko against Iga Swiatek.\n奥斯塔彭科对斯瓦泰克！"})
# 收尾
seg("wuhli",1070.3,1075.4,"武汉这一周，两人只可能在决赛碰面。",
    {"label":{"topic":"武汉公开赛","date":"2026.10.15","place":"武汉 1/8决赛","people":"斯瓦泰克 胜 克鲁格","score":"6-1 6-4"},"image":"assets/reel/osw/osw-wuhli.png","kind":"story_text","corner":"tr","width":0.6,"pad":0.085,"show_for":3.2,"motion":"editorial"},
    "武汉 1/8 决赛斯瓦泰克对克鲁格赛点回合（WTA 官方 16 强合集 N6FzVa8YsdQ）。");S[-1]["point_end_ok"]="下一段 1075.5s 起无缝接同一源，赛点在下一段打完、翻牌和斯瓦泰克庆祝都在下一段里（缩略图墙 contact_17/18 看过）。"
Q("wuhli",1075.5,1082.4,"And the final point goes Iga Swiatek's way.","最后一分，属于斯瓦泰克。",why="斯瓦泰克赢下赛点后近景。")
seg("wuhsh",271.5,274.7,"克星续写，还是破局？",L("wuhsh","武汉公开赛","2026.10.16","武汉 1/4决赛","7-6(8) 6-1","奥斯塔彭科 胜 施奈德"),"武汉 1/4 决赛奥斯塔彭科胜施奈德后近景（WTA 官方集锦），片尾。")
EV={"h2h":"交手 6-0","ret52":"接发球得分率 52%","uso75":"连续 75 周告终"}
for x in S:
    lab=(x.get("inset") or {}).get("label")
    k=(x.get("inset") or {}).get("image","").split("osw-")[-1][:-4]
    if lab and k in EV: lab.pop("score",None); lab["event"]=EV[k]
POST={("uso23f",5019.4):"赛点在 5010s 打完，这段是网前握手（contact_05 看过）",("uso23f",5009.6):"赛点在 5010s 打完，这段是赛后庆祝与全场",("doh25f",3487.5):"赛后挥手致意",("doh25f",3552.5):"赛后场内采访",("doh25f",3557.9):"赛后场内采访",("doh25f",3473.9):"赛点刚打完的庆祝",("wuhli",1075.5):"赛点与赛后",("wuhsh",271.5):"赛后近景",("uso23f",5004.0):"赛点回合，下一段 5009.6s 无缝接续，翻牌与庆祝都在下一段"}
for x in S:
    k=(x["source"],x["start"])
    if k in POST and "point_end_ok" not in x: x["point_end_ok"]=POST[k]+"；后面的记分条翻牌是赛后字板，不是在打的分。"
spec={"slug":SLUG,"date":"2026-10-16","_column":"网球有故事","title":"奥斯塔彭科对斯瓦泰克六战全胜","cx":0.5,"track":False,"tts_backend":"edge","_tts_backend_why":"不用情绪风格；网球有故事近期成片用 edge 云见 +18% +10Hz，沿用同一把嗓子。",
 "_voice_why":"渲染传 --voice zh-CN-YunjianNeural --rate +18% --pitch +10Hz。",
 "cover":{"eyebrow":"网球有故事","layout":"solo","subject":"奥斯塔彭科","hook":"六次交手\n斯瓦泰克一场没赢","narration":"六次交手，斯瓦泰克一场没赢。",
  "topic":"奥斯塔彭科 vs 斯瓦泰克 · 交手史",
  "portrait":{"image":"assets/reel/osw-h2h-cover.jpg","focus":0.4,"focus_y":0.35,"zoom":1.0,
   "source_url":"https://photoresources.wtatennis.com/wta/photo/2025/02/14/4f4acebe-943d-4d6b-ab64-a4b19e7f81a0/Ostapenko-SF-Karim-Jaafar-AFP.jpg",
   "_portrait_why":"WTA 官网 2025-02-14 多哈半决赛奥斯塔彭科胜斯瓦泰克赛后稿配图（AFP Karim Jaafar），2816×1872，奥斯塔彭科握拳。"}},
 "push":{"auto":False,"_why":"账号所有者尚未批准：只开 PR 审阅，不合并、不推送。","summary":"克星六战全胜","lead":"六次交手，斯瓦泰克一场没赢过奥斯塔彭科。"},
 "editorial":{"mode":"match_review","question":"为什么斯瓦泰克打不过奥斯塔彭科？","thesis":"假设武汉决赛两人相遇：回顾六次交手，奥斯塔彭科6-0领先，盘数12-3、局数83-47，三次决胜盘全胜。",
  "beats":["开场：6-0 克星关系。","主体：2019 伯明翰、2021 印第安维尔斯、2022 迪拜、2023 美网、2025 多哈、2025 斯图加特逐场关键画面。","收尾：武汉只可能决赛相遇，第七次悬念。"],
  "human_context":{"angle":"一边倒的克星关系：抢时间的打法。","facts":["交手 6-0","接发球得分率 52%（matchstat）"],"sources":[
   "https://www.wtatennis.com/news/4216096/ostapenko-makes-it-a-perfect-5-0-against-swiatek-to-reach-doha-final",
   "https://apnews.com/article/us-open-iga-swiatek-jelena-ostapenko-86e2adf9b9d2e68afa5e4ceeb30335d5",
   "https://ausopen.com/articles/news/indian-wells-ostapenko-ousts-swiatek-fritz-beats-berrettini",
   "https://www.wtatennis.com/news/4252173/ostapenko-defeats-sabalenka-for-first-time-to-claim-stuttgart-title",
   "https://www.wtatennis.com/tournaments/1075/wuhan-open-wuhan-chn/2026/draws"]}},
 "_facts":{
  "h2h":"WTA 2025-02-14 稿：奥斯塔彭科 5-0；2025-04-19 斯图加特 1/4 决赛 6-3 3-6 6-2 后 6-0。六场比分见各段角标；盘数 12-3、局数 83-47、决胜盘 3-0 由六场比分逐盘相加。",
  "bhm19":"WTA 签表 2019 伯明翰首轮 奥斯塔彭科 6-0 6-2 斯瓦泰克；Ubitennis 2019-06-18：斯瓦泰克为资格赛选手；斯瓦泰克 2001-05-31 生，时年 18 岁；奥斯塔彭科 2017 法网冠军。接发球 24/38：网球记者 Chris Oddo 当天 X 帖 https://x.com/TheFanChild/status/1141070177888399360 。",
  "iw21":"WTA 比分页 LS015：奥斯塔彭科(24) 6-4 6-3 斯瓦泰克(2)。引语：AO 2021-10-13 稿 Ostapenko: I ... took the time away from her so she couldn't do much against me.",
  "dxb22":"WTA 比分页 LS009：4-6 6-1 7-6(4)。WTA 2025-02-14 稿：Swiatek's last loss before ... 37-match winning streak。轮次各来源不一（WTA 写 Round of 16/third round，赛事单写 R2），片中不提轮次。",
  "uso23":"AP 2023-09-04：卫冕冠军、世界第一斯瓦泰克 3-6 6-3 6-1 负于 20 号种子奥斯塔彭科，世界第一将让给萨巴伦卡；引语 Swiatek: I felt no control suddenly. Ostapenko: She likes to have some time. When I play fast, aggressive and powerful, she's a little bit in trouble.（AP/Reuters/CNN 一致）。75 周：2022-04-04 至 2023-09-10 连续世界第一。",
  "doh25":"WTA 2025-02-14 稿：6-3 6-1，终结三届卫冕冠军斯瓦泰克在多哈 15 连胜；赛事播报单用时 1:10。",
  "stu25":"WTA 2025-04-21 稿：奥斯塔彭科决赛 6-4 6-1 胜萨巴伦卡夺冠，获保时捷。",
  "ret52":"matchstat 交手页：奥斯塔彭科六场接发球得分率 52%。未使用来源不明的 41%。",
  "wuhan":"WTA 签表：1/4 决赛 奥斯塔彭科 7-6(8) 6-1 施奈德；斯瓦泰克 6-4 6-1 李安。半决赛：斯瓦泰克对赫瓦林斯卡，奥斯塔彭科对卡尔塔尔。两人分处上下半区。片中不写积分数字。",
  "dropped":"「奥斯塔彭科斯图加特决赛负萨巴伦卡」为错：她赢了冠军；「多哈决赛负阿尼西莫娃」属实但片中未用。"},
 "_claims":{"一场没赢过":V_,"一次都没赢":V_,"偏偏有一个人，她一次都没赢过。":V_,"六次交手，斯瓦泰克一场没赢。":V_},
 "conform":{"iw21":"WTA 官方集锦最高 1280×720，账号所有者 2026-10-17 要求放大铺满 1080×1440","dxb22":"同上，WTA 官方集锦最高 1280×720"},
 "conform_sharpen":{"iw21":"720p 放大后轻度锐化（账号所有者点名）","dxb22":"同上"},
 "source_quality_exceptions":{yt(i):{"min_height":720,"approved_by":"user","reason":"账号所有者 2026-10-17 审 PR #1278：不要动画卡，点名用这条 720p WTA 官方集锦剪关键分、放大铺满并轻锐化。"} for i in ["wOsrLbiWZJ4","vNSSJMmRIBM"]},
 "sources":sources,
 "source_fallbacks":{k:f"https://github.com/robertyang87/tennislive/releases/download/source-{v.split('=')[1]}/{v.split('=')[1]}.mp4" for k,v in sources.items() if "youtube" in v},
"primary":"stu25",
 "mixed_fps":{"uso23f":"美网官方全场录像原片帧率与主源不同"},
 "_production_status":"render_local_review","segments":S}
json.dump(spec,open(f'/workspace/tennislive/specs/reels/{SLUG}.json','w'),ensure_ascii=False,indent=2)
from tools.render_story_info_band import render_label
Path('/workspace/tennislive/assets/reel/osw').mkdir(parents=True,exist_ok=True)
for s in S:
    if 'inset' in s: render_label(s['inset']['label'],Path('/workspace/tennislive/'+s['inset']['image']))
tot=sum(s['end']-s['start'] for s in S);an=sum(s['end']-s['start'] for s in S if s['source']=='bhm19')
print(len(S),round(tot,1),round(an,1),round(1-an/tot,3))
for s in S:
    n=len(s['narration']);d=s['end']-s['start']
    if n/ max(d,.1)>4.6: print("tight",n,round(d,1),s['narration'])
