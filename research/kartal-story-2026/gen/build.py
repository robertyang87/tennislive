import json
segs=json.load(open('research/kartal-story-2026/gen/segments.json'))
YT={"sf":"abL2j0xldOc","qf":"T22a9v9UZuk","r16":"LDXqFzdqVVk","r2":"1TKV_Ywr8J8","iw":"z8Sffkz5m8s","u10":"INkEB95UIa8","wb24":"mXnEXUPITgg","doc":"8u0X2vm7svU","lta22":"vqIpczMjb5I"}
INFO={"sf":(1920,1080,"25/1","WTA"),"qf":(1920,1080,"25/1","WTA"),"r16":(1920,1080,"25/1","WTA"),"r2":(1920,1080,"25/1","WTA"),"iw":(1920,1080,"25/1","WTA"),
 "u10":(1920,1080,"24000/1001","LTA（英国网协）"),"wb24":(1920,1080,"25/1","Wimbledon"),"doc":(3840,2160,"25/1","LTA（英国网协）"),"lta22":(1920,1080,"25/1","LTA（英国网协）")}
used={s.get("source") for s in segs if s.get("source")}
YT={k:v for k,v in YT.items() if k in used}
sources={k:f"https://www.youtube.com/watch?v={v}" for k,v in YT.items()}
MIXED={"u10":"LTA 存档 23.976 fps，升到 25 fps 每秒补一帧；广角远景、人很小，顿挫不明显"}
spec={
 "slug":"kartal-story-2026","date":"2026-10-17","_column":"网球有故事","title":"停了半年，回来第三站进了决赛",
 "cx":0.5,"track":False,"tts_backend":"edge",
 "_tts_backend_why":"与 swiatek-chwalinska-story-2026 同一把嗓子（edge 云健），不加情绪风格。",
 "_voice_why":"渲染传 --voice zh-CN-YunjianNeural --rate +18%。正文各段 pitch +10Hz；不写 style、lead_pause。",
 "cover":{
  "eyebrow":"网球有故事","layout":"solo","subject":"卡尔塔尔",
  "hook":"停赛半年掉到170\n复出第3站进决赛",
  "_hook_why":"第一行是她的来路（背伤停了半年、排名掉到 170），第二行是结果（复出第三站就打进一千赛决赛）。9＋8 字符，零术语，不比总分。",
  "narration":"停赛半年掉到一百七十，复出第三站进决赛。","_narration_why":"念的就是海报上那句钩子，数字换成汉字给 TTS。",
  "topic":"从拉杜卡努的对手走到武汉决赛",
  "_owner_words_topic":"账号所有者 2026-10-17：「应该是卡塔尔的来时路？相关的吧」——随后「我是说你把这个副标题润色下」——给了三个候选后他选「第一个吧。改到武汉决赛」——即候选「从拉杜卡努的对手走到决赛」改成「…走到武汉决赛」，一字不改照用。",
  "_topic_why":"账号所有者 2026-10-15：「封面的副标题要用这个故事的内容，不要用比赛双方」；2026-10-17 他点名「来时路」、选定措辞。14 字，本地渲封面核过墨迹不压脸。",
  "portrait":{"image":"assets/reel/kartal-story/cover-wuhan.jpg","fit":"cover","focus":0.53,"focus_y":0.25,"zoom":1.0,
   "source_url":"https://photoresources.wtatennis.com/wta/photo/2026/10/17/7878daa7-c5c9-466e-b455-084d83d626dc/Sonay_Kartal_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5-DSC_4105.jpg",
   "_credit":"WTA 官方图库 photo 4593547「Sonay_Kartal_-_Dongfeng_Voyah_Wuhan_Open_-_Day_5-DSC_4105」",
   "_portrait_why":"WTA 照片接口本周的卡尔塔尔实拍（4700×3000，Day 5＝10 月 16 日1/4决赛对斯维托丽娜那天，白色背心、浅绿帽与集锦一致）。正脸、双眼睁开、笑着——本期讲的是她熬过半年伤病回来，这张的情绪对得上「回来了」。同一趟检索里今天半决赛的 Day 6 DSC_7852（4700×3305，EXIF 当地 18:18）是侧头回看，脸不正，次选。",
   "_search_why":"2026-10-17 12:44Z find_cover_photo（WTA 照片接口、photo-resources、赛后稿头图）跑过：本周卡尔塔尔可用 4 张（R3 Jimmie、QF WZ、Day 5 DSC_4105、Day 6 DSC_7852），AP 被 Cloudflare 挡（未知，不是没有）。"},
  "scrim":"clear","_layout_why":"网球有故事讲一个人的来路，solo 版铺满。"},
 "push":{"auto":True,"_why":"账号所有者 2026-10-13 起所有 spec 默认自动推送；质检通过即合并推送。","summary":"她没急着回来","lead":"背伤停了半年、排名掉到 170，卡尔塔尔复出第三站，在武汉打进了生涯第一个一千赛决赛。"},
 "editorial":{"mode":"match_review","question":"一个停了半年、排名掉到 170 的人，怎么在复出第三站打进一千赛决赛？",
  "thesis":"以武汉半决赛赛点为由头，倒回她的来路：和拉杜卡努从小对打、看哥哥打球入门；2024 温网从资格赛打进第三轮、拿到首冠，最高世界第 44；2026 年 3 月背已经疼了还逆转凯斯，两天后退赛，背部应力性骨折停了半年、错过三个大满贯；美网时就能复出但没急；回来第三站，武汉连胜本西奇、保利尼、斯维托丽娜、奥斯塔彭科。",
  "beats":["冷开场：半决赛第二个赛点、她举拍、包厢起立，解说原声","坐标：排名 170，七个月前背伤退赛","01 和拉杜卡努一起长大：2011 U10 回合、她讲从迷你网球就对打、看哥哥打球入门","02 一场一场打上来：2024 温网资格赛打进第三轮，首冠、最高第 44，3 月带着背伤逆转凯斯","03 停下来的半年：退赛、应力性骨折、错过三个大满贯；她自己讲刷牙都疼、本可以美网就回来但没急","04 武汉的五场球：本西奇、保利尼、斯维托丽娜三段解说原声，半决赛救下六个盘点，赛后她说这是里程碑","收尾：决赛与排名，一问"],
  "human_context":{"angle":"被伤病按下暂停键的人，没急着回来；回来以后，一路打进了决赛。",
   "facts":["WTA 4593140：伤停六个月、排名从 54 掉到 170，1/4决赛 6-2 2-6 6-4 胜斯维托丽娜、半决赛 7-6(9) 7-6(5) 胜奥斯塔彭科；本赛季赢下首盘 13 胜 0 负；继康塔之后第二个打进 1000 赛决赛的英国人；八月底就能复出但没急。","The Independent（Yahoo）与 AOL：两盘都先落后，奥斯塔彭科两次发球胜盘都被破，救下全部 6 个盘点，抢七 11-9、7-5；保护排名；赛后排名升到第 50、成为英国一号。","Sky Sports、NBC Sports、WTA 武汉第二轮集锦解说：背部应力性骨折，缺席六个月，错过三个大满贯含温网。","tennismajors／puntodebreak：2026-03-11 印第安维尔斯第四轮对莱巴金娜 4-6 3-4 落后退赛；WTA 4465394：前一轮 2-6 6-2 6-3 逆转凯斯。","LTA 2022 专访与官网稿：和拉杜卡努从迷你网球就对打；看大五岁的哥哥打球入门。"],
   "sources":["https://www.wtatennis.com/news/4593140/kartals-comeback-gathers-pace-with-landmark-run-to-wuhan-semifinals","https://uk.sports.yahoo.com/news/sonay-kartal-makes-history-reaching-112128259.html","https://www.aol.co.uk/articles/sonay-kartal-causes-another-huge-112100000.html","https://www.skysports.com/tennis/news/13599803/sonay-kartal-brit-breaks-new-ground-by-upsetting-elina-svitolina-to-reach-wuhan-open-semi-finals","https://www.nbcsports.com/tennis/news/elina-svitolina-loses-to-resurgent-british-player-sonay-kartal-at-wuhan-open","https://www.tennismajors.com/?p=846471","https://www.wtatennis.com/news/4465394/kartal-stuns-keys-with-comeback-win-to-reach-indian-wells-fourth-round","https://www.lta.org.uk/news/2022/april/introducing-sonay/","https://en.wikipedia.org/wiki/Sonay_Kartal"]}},
 "_owner_brief":"账号所有者 2026-10-17 上传 Grok 整理的《卡塔尔（Sonay Kartal）调查与视频清单》，说「改做这个，再详细补充下内容，然后做一期网球有故事视频」。",
 "_corrections_vs_brief":"①中文名按仓库译名表写卡尔塔尔（材料写的「卡塔尔」是国名）。②「今年赢下首盘 12 胜 0 负」→ WTA 4593140 是 13-0。③「2009 年以来排名最低的 1000 赛决赛选手」：账号所有者 2026-10-17 第二份材料给出 WTA 半决赛 match notes 出处，runner 上取 PDF 核过原文，与 The Independent 两源对上，进片。④土耳其餐馆、LTA 教练邀哥哥上课、2024 年住院、父亲扔下她的比赛去看费德勒练球：检索都没有对得上的出处，不用；纹身只在 LTA 专访里她自己一句玩笑，不进片。⑤出生地：维基写伦敦出生、布莱顿长大，片中只说在布莱顿长大。⑥材料里半决赛只有 WTA X 短视频，现在 WTA 官方 YouTube 集锦（abL2j0xldOc）已经上线。",
 "_editing_why":"账号所有者 2026-10-17 叙事片口径：主线一句话、原声带情绪、最强对照进前 30 秒、渲前发提纲。冷开场是今天的赛点与包厢，第 2 段字卡就是对照（排名 170、七个月前退赛）。四章：01 从小的对手（LTA 存档回合＋她自己讲）、02 一场一场打上来（温网 2024、印第安维尔斯）、03 停下来的半年（LTA 复出专访里她自己讲伤和没急着回来，两段原声带情绪）、04 武汉五场（三段解说原声，半决赛一段旁白交代过程，赛后采访收住）。印第安维尔斯退赛没有官方画面，用字卡交代。莫纳斯提尔冠军集锦只有 720p，不用画面，一句旁白带过。旁白只放在两档 ASR 都无英文的空当里。",
 "_claims":{"排名最低的决赛选手":"WTA https://wtafiles.wtatennis.com/pdf/matchnotes/2026/1075_SF.pdf ；The Independent https://uk.sports.yahoo.com/news/sonay-kartal-makes-history-reaching-112128259.html",
  "第一个做到的英国女子资格赛球员":"LTA https://lta.org.uk/fan-zone/wimbledon-championships/news/2024-sonay-kartal-continues-dream-run-to-reach-third-round ；Tennis Majors https://www.tennismajors.com/?p=771267",
  "英国第一人":"LTA https://lta.org.uk/fan-zone/wimbledon-championships/news/2024-sonay-kartal-continues-dream-run-to-reach-third-round ；Tennis Majors https://www.tennismajors.com/?p=771267"},
 "_social_checked":"2026-10-17 查了她本人 Instagram 的伤病更新（tennishead、LTA、AOL 转述）：3 月退出比利·简·金杯、4 月放弃红土、6 月放弃温网（this one hurts）都是文字帖或快拍文字，没有她本人开口的视频；她亲口讲伤病的视频是 LTA 官方复出专访（8u0X2vm7svU），片中用它的原声。",
 "_social_search_why":"不是当事人发声明类的选题：讲的是她公开的比赛与官方采访；当事人亲口的部分全部用 LTA 官方专访与 WTA 场上采访原声。",
 "sources":sources,
 "source_fallbacks":{k:f"https://github.com/robertyang87/tennislive/releases/download/source-{v}/{v}.mp4" for k,v in YT.items()},
 "mixed_fps":{k:v for k,v in MIXED.items() if k in YT},
 "conform":{"doc":"LTA 官方复出专访只有 4K（3840×2160）上传，和主源同为 16:9，等比缩到 1920×1080，不裁边、不放大。"},
 "_no_probe_why":{k:{"why":f"{INFO[k][3]} 官方，download-video 存档后本地 ffprobe {INFO[k][0]}×{INFO[k][1]}@{INFO[k][2]}；网球有故事按讲解剪片，窗口按两档 ASR 的静默区和本地抽帧定，不为它单开一趟 probe。","width":INFO[k][0],"height":INFO[k][1],"fps":INFO[k][2]} for k in YT},
 "_primary_why":"主源是 sources 的第一个键 sf（WTA 官方 1080p25），输出 25 fps。",
 "_production_status":"spec_ready_for_render",
 "_why_sources":"比赛、颁奖和采访画面全部来自官方频道：WTA（abL2j0xldOc、T22a9v9UZuk、LDXqFzdqVVk、1TKV_Ywr8J8、z8Sffkz5m8s）、Wimbledon（mXnEXUPITgg）、LTA 英国网协（INkEB95UIa8、vqIpczMjb5I、8u0X2vm7svU）。照片来自 WTA 官方图库。",
 "segments":segs}
json.dump(spec,open('specs/reels/kartal-story-2026.json','w'),ensure_ascii=False,indent=1)
print("ok",len(segs))
