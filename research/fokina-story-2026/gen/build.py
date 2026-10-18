import json
segs=json.load(open('research/fokina-story-2026/gen/segments.json'))
YT={"wa":"56wc7QQEwEw","sf":"TXmXxVJ3o_M","sfa":"NKFVL_lELNE","sfi":"KHT6c3b6ecw","jw":"W98zNwzcSvk","mcd":"QEq571d-4_Q","mcc":"IUIM1yIVFjA",
    "dr":"r2K-9DFDzmM","ac":"Vx3B-kCQDTs","bs":"MLCcQ08dVaU","ml":"7JY8UtZrvFg","wb":"vOrKPuPncdg","cdr":"Y_cP9vjbIGk","cdf":"9u2kSI8md88",
    "sh3":"x2hTyMZ_k8k","sh4":"OSnzyodnKdE"}
TT="Tennis TV（ATP 官方）"
INFO={"wa":("25/1",TT),"sf":("50/1",TT),"sfa":("25/1","ATP Tour"),"sfi":("50/1","ATP Tour"),"jw":("25/1","Wimbledon"),"mcd":("30000/1001",TT),
      "mcc":("60000/1001",TT),"dr":("25/1",TT),"ac":("25/1",TT),"bs":("50/1",TT),"ml":("50/1",TT),"wb":("25/1","Wimbledon"),"cdr":("50/1",TT),
      "cdf":("50/1",TT),"sh3":("50/1","ATP Tour"),"sh4":("50/1","ATP Tour")}
used={s.get("source") for s in segs if s.get("source")}
YT={k:v for k,v in YT.items() if k in used}
sources={k:f"https://www.youtube.com/watch?v={v}" for k,v in YT.items()}
MIXED={k:("50 fps 源片落到 25 fps 输出，每两帧取一帧，不补帧、不顿挫" if INFO[k][0]=="50/1" else
          "29.97 fps 源片落到 25 fps 输出，按时间重采样，广角回合里看不出顿挫" if INFO[k][0]=="30000/1001" else
          "59.94 fps 源片落到 25 fps 输出，按时间重采样，颁奖与慢动作镜头看不出顿挫") for k in YT if INFO[k][0]!="25/1"}
spec={
 "slug":"fokina-story-2026","date":"2026-10-18","_column":"网球有故事","title":"五次亚军之后，他站上了大师赛决赛",
 "cx":0.5,"track":False,"tts_backend":"edge",
 "_tts_backend_why":"与 kartal-story-2026 同一把嗓子（edge 云健），不加情绪风格。",
 "_voice_why":"渲染传 --voice zh-CN-YunjianNeural --rate +18%。正文各段 pitch +10Hz；不写 style、lead_pause。",
 "cover":{
  "eyebrow":"网球有故事","layout":"solo","subject":"福基纳",
  "hook":"前5次决赛全是亚军\n这次站上大师赛决赛",
  "_hook_why":"第一行是他的来路（五次决赛五次亚军），第二行是这一站走到哪一步（大师赛决赛）。8＋9 字符，零术语，不比总分，不写排名。",
  "narration":"前五次决赛全是亚军，这次站上大师赛决赛。","_narration_why":"念的就是海报上那句钩子，数字换成汉字给 TTS。",
  "topic":"福基纳：从五次亚军走到上海决赛",
  "_topic_why":"账号所有者 2026-10-15：「封面的副标题要用这个故事的内容，不要用比赛双方」；沿用 kartal-story-2026 他选定的「从……走到……决赛」句式。11 字。",
  "portrait":{"image":"assets/reel/fokina-story/cover-shanghai-sf.jpg","fit":"cover","focus":0.2,"focus_y":0.3,"zoom":1.0,
   "source_url":"https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/4593527",
   "_credit":"ATP Media 官方图库 photo 4593527「Alexander-ZVEREV-vs-Alejandro-DAVIDOVICH-FOKINA-0141」（2026 上海半决赛）",
   "_portrait_why":"ATP Media 照片接口本周上海的福基纳实拍（原图 3111×2074，存档缩到 2400 长边）：半决赛对兹维列夫，正脸、双眼睁大盯着来球、正手引拍，合焦；情绪是「咬住每一分」，对上「这一次站上决赛」。同一批 4593524（正手击球、球拍略挡下巴）次选；4593539 握手照留给收尾。",
   "_search_why":"2026-10-18 01:0xZ 在 runner 上翻 ATP Media 照片接口（沙箱代理挡 api.prod.atpmedia.pulselive.com），按标题与文件名认出 Davidovich 的上海、成都实拍 41 张，存进 research/fokina-story-2026/photos/。"},
  "scrim":"clear","_layout_why":"网球有故事讲一个人的来路，solo 版铺满。"},
 "push":{"auto":True,"_why":"账号所有者 2026-10-13 起所有 spec 默认自动推送；质检通过即合并推送。","summary":"这次他握得住吗","lead":"五次决赛五次亚军，五个冠军点一个没握住；今年先在马略卡、成都连拿两冠，又在上海逆转兹维列夫，站上了大师赛决赛。"},
 "editorial":{"mode":"match_review","question":"一个输掉五次决赛、五个冠军点一个没握住的人，怎么一路走到大师赛决赛？",
  "thesis":"以上海半决赛赛点为由头，倒回他的来路：2017 温网青少年冠军；2022 蒙特卡洛破德约九次发球局、首进决赛负西西帕斯（西西帕斯致辞：第一次，但不会是最后一次）；2025 德尔雷海滩握两个冠军点、阿卡普尔科、华盛顿被救三个冠军点、巴塞尔，五次亚军；2026 法网教练短信辞职、马略卡第六次决赛终于夺冠、温网五盘负阿利亚西姆后网前争执、背伤停赛两个多月；成都复出即夺冠、上海连赢蒂亚福和胡尔卡奇的决胜盘抢七、逆转兹维列夫，赛后说停赛让他想清楚了未来。",
  "beats":["冷开场：上海半决赛赛点、他笑着走到网前，解说原声","坐标：五次决赛五次亚军","01 温网少年：2017 青少年冠军发布会原声（跟着爸爸在海边开始）","02 五次亚军：蒙特卡洛胜德约、首个决赛、西西帕斯致辞；德尔雷海滩两个冠军点；阿卡普尔科；华盛顿三个冠军点被救；巴塞尔","03 最乱的夏天：教练短信辞职、马略卡终于夺冠、温网网前争执、背伤停赛","04 上海这一周：成都复出与夺冠、蒂亚福、胡尔卡奇、兹维列夫，赛后采访","收尾：决赛对霍达尔，一问"],
  "human_context":{"angle":"一个总在最后一步摔倒的人，这一年学会了站稳。",
   "facts":["ATP 上海赛前要点 PDF：头五次决赛 0-5，德尔雷海滩握 2 个冠军点、华盛顿错失 3 个；生涯最高第 14；与霍达尔首次交手。","ATP 华盛顿决赛报道＋Eastern Mirror（AFP）：决胜盘 5-3 发球胜赛 30-0 被破，德米纳尔 4-5 发球救 3 个冠军点，第三个冠军点挑高球擦线、离出界 16 毫米。","ATP 马略卡决赛报道＋Tennis Tour Talk：2026-06-27 7-6(4) 6-3 胜奎因，生涯首冠。","The Star（Reuters）＋Tennis Majors：温网第四轮对阿利亚西姆，对手 5-4 发球胜赛时他扭伤脚踝叫医疗暂停，赛后网前争执，阿利亚西姆称这条规则是耻辱。","Tennis Now＋DH Les Sports（法新社）：法网首轮后教练普埃尔塔短信辞职、飞去迈阿密，他说对方拉黑了他和妻子。","ATP 成都决赛报道＋Tennis Majors：背伤缺席北美硬地赛季与美网，复出即夺冠，全场没面对破发点，抢七 3-6 落后。","ATP 上海半决赛报道：5-7 6-4 6-3 逆转头号种子兹维列夫，在中国 9 连胜。"],
   "sources":["https://www.atptour.com/-/media/9722bcd371f145fdbe25acd1bb5af56b.pdf","https://www.atptour.com/en/news/davidovich-fokina-de-minaur-washington-2025-final","https://www.easternmirrornagaland.com/de-minaur-saves-3-championship-points-to-clinch-washington-title","https://www.atptour.com/en/news/davidovich-fokina-quinn-mallorca-2026-saturday","https://www.thestar.com.my/sport/tennis/2026/07/06/tennis-auger-aliassime-labels-injury-rule-a-disgrace-after-stormy-win","https://www.tennismajors.com/?p=855256","https://tennisnow.com/?p=65730","https://www.atptour.com/en/news/davidovich-fokina-hurkacz-chengdu-2026-final","https://www.tennismajors.com/?p=862142","https://www.atptour.com/en/news/zverev-davidovich-fokina-shanghai-2026-saturday"]}},
 "_owner_brief":"账号所有者 2026-10-18 上传《达维多维奇·福基纳总文档：上海大师赛决赛专题》，说「参考这个，然后做弗吉纳的介绍，以及它的整个的最近的跌宕起伏的生涯，以及这场比赛的一些历程。然后类似于这个卡塔尔的视频做一个」；看过提纲后说「没问题，做吧」。",
 "_corrections_vs_brief":"①中文名：仓库译名表写「达维多维奇·福基纳」，账号所有者口头与材料都叫「福基纳」，片中统一用福基纳。②材料里「今天下午四点半」改成「十月十八号的决赛」（网球有故事是常青栏目，不写相对日期）。③「大师赛史上第一次在硬地上的西班牙内战决赛」只有 ATP 一个站点的出处，不写全称断言，改成「两个西班牙人会师上海」。④成都停赛时长：ATP 西语 X 帖写 72 天、Tennis Majors 改正为两个月、Tennis TV 解说说两个半月，片中写「两个多月」，解说原声照录。⑤Tennis Channel、Diario AS、Tennis Actu 的视频不是官方源，不用；教练离队与温网网前争执没有官方视频，用字卡与旁白交代。",
 "_editing_why":"账号所有者 2026-10-17 叙事片口径：主线一句话、原声带情绪、最强对照进前 30 秒、渲前发提纲（10-18 已发，他回「没问题，做吧」）。冷开场是上海半决赛的赛点，第 2 段字卡就是对照（五次决赛五次亚军）。四章：01 温网少年（发布会原声）、02 五次亚军（每场决赛只留最后那一刻：蒙特卡洛的出界与西西帕斯致辞、德尔雷海滩两个冠军点、阿卡普尔科、华盛顿发球胜赛被破与三个冠军点、巴塞尔）、03 最乱的夏天（马略卡终于夺冠的解说原声、温网五盘）、04 上海这一周（成都复出与夺冠解说、蒂亚福、胡尔卡奇、兹维列夫、赛后采访）。旁白只放在两档 ASR 都无英文的空当里。",
 "_claims":{"打进过五次决赛，五次都":"头五次决赛 0-5（蒙特卡洛 2022、德尔雷海滩 2025、阿卡普尔科 2025、华盛顿 2025、巴塞尔 2025），第六次马略卡才夺冠：ATP 上海赛前要点 PDF https://www.atptour.com/-/media/9722bcd371f145fdbe25acd1bb5af56b.pdf ；ATP 马略卡决赛报道 https://www.atptour.com/en/news/davidovich-fokina-quinn-mallorca-2026-saturday ；Tennis Tour Talk https://tennistourtalk.com/?p=135356 ；Tennis TV 成都决赛集锦解说 After losing his first five tour level finals https://www.youtube.com/watch?v=9u2kSI8md88"},
 "_social_checked":"2026-10-18 查过：他背伤与复出期间没有本人开口的官方视频，ATP 西语 X 只发了引语图片帖；本人亲口的部分用 ATP 上海半决赛场上采访与 2017 温网青少年冠军发布会原声。",
 "_social_search_why":"不是当事人发声明类的选题：讲的是他公开的比赛与官方采访。",
 "sources":sources,
 "source_fallbacks":{k:f"https://github.com/robertyang87/tennislive/releases/download/source-{v}/{v}.mp4" for k,v in YT.items()},
 "mixed_fps":MIXED,
 "_no_probe_why":{k:{"why":f"{INFO[k][1]} 官方，download-video 存档后本地 ffprobe 1920×1080@{INFO[k][0]}；网球有故事按讲解剪片，窗口按两档 ASR 的静默区和本地抽帧定，不为它单开一趟 probe。","width":1920,"height":1080,"fps":INFO[k][0]} for k in YT},
 "_primary_why":"主源是 sources 的第一个键 wa（Tennis TV 官方 1080p25），输出 25 fps。",
 "_production_status":"spec_ready_for_render",
 "_why_sources":"比赛、颁奖和采访画面全部来自官方频道：Tennis TV（56wc7QQEwEw、TXmXxVJ3o_M、QEq571d-4_Q、IUIM1yIVFjA、r2K-9DFDzmM、Vx3B-kCQDTs、MLCcQ08dVaU、7JY8UtZrvFg、Y_cP9vjbIGk、9u2kSI8md88）、ATP Tour（NKFVL_lELNE、KHT6c3b6ecw、x2hTyMZ_k8k、OSnzyodnKdE）、Wimbledon（W98zNwzcSvk、vOrKPuPncdg）。照片来自 ATP Media 官方图库。",
 "segments":segs}
json.dump(spec,open('specs/reels/fokina-story-2026.json','w'),ensure_ascii=False,indent=1)
print("ok",len(segs))
