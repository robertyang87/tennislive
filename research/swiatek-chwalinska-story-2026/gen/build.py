import json
segs=[s for s in json.load(open('research/swiatek-chwalinska-story-2026/gen/segments.json')) if '_placeholder' not in s]
YT={"rgsf":"nuivYz2nq08","wuhm":"0-v-yZvYAk8","wuhs":"O8f_vcT29uY","pol15":"-Vsfptr_DC8","jfc16":"p9Xzx3vDPJw","rg20":"OwKaLdNEjlI","rgpc":"1ihxUf32bQk","rgsfi":"SdEjFtD4CTU","rgf":"WVWjACQ11-Y","rgfs":"LXRhlHKGKZc","uc25":"15fLzmh_o7A"}
INFO={"rgsf":(1920,1080,"50/1","Roland-Garros"),"wuhm":(1920,1080,"25/1","WTA"),"wuhs":(1920,1080,"25/1","WTA"),"pol15":(1920,1080,"25/1","Polsat Sport（波兰体育电视台）"),
 "jfc16":(1920,1080,"25/1","匈牙利网协 Magyar Tenisz Szövetség（2016 青少年联合会杯决赛东道主）"),"rg20":(1920,1080,"30000/1001","Roland-Garros"),"rgpc":(1920,1080,"50/1","Roland-Garros"),
 "rgsfi":(1920,1080,"50/1","Roland-Garros"),"rgf":(1920,1080,"50/1","Roland-Garros"),"rgfs":(1920,1080,"60000/1001","Tennis Channel（法网美国转播方）"),"uc25":(1920,1080,"25/1","United Cup")}
used={s.get("source") for s in segs if s.get("source")}
YT={k:v for k,v in YT.items() if k in used or k=="rgsf"}
sources={k:f"https://www.youtube.com/watch?v={v}" for k,v in YT.items()}
MIXED={"wuhm":"WTA 官方 25 fps，升到 50 fps 每帧整齐重复一次","wuhs":"WTA 官方 25 fps，升到 50 fps 每帧整齐重复一次",
 "pol15":"Polsat Sport 25 fps，升到 50 fps 每帧整齐重复一次","jfc16":"25 fps，升到 50 fps 每帧整齐重复一次；手持机位跟拍拥抱，动作不快",
 "rg20":"法网官方 29.97 fps，升到 50 fps 帧重复不均匀；冠军点广角与颁奖近景，横移慢，顿挫不明显",
 "rgfs":"Tennis Channel 59.94 fps → 50，颁奖台说话的近景，人基本不动","uc25":"联合杯官方 25 fps，升到 50 fps 每帧整齐重复一次"}
spec={
 "slug":"swiatek-chwalinska-story-2026","date":"2026-10-16","_column":"网球有故事","title":"波兰双子星：从青梅竹马到巅峰相见",
 "_title_why":"账号所有者 2026-10-16 上传的《波兰双子星：从青梅竹马到巅峰相见》策划案标题，一字不改。",
 "cx":0.5,"track":False,"tts_backend":"edge",
 "_tts_backend_why":"与 medvedev-not-villain-2026 同一把嗓子（edge 云健），不加情绪风格。",
 "_voice_why":"渲染传 --voice zh-CN-YunjianNeural --rate +18%。正文各段 pitch +10Hz；不写 style、lead_pause。",
 "cover":{
  "eyebrow":"网球有故事","layout":"solo","subject":"斯瓦泰克与赫瓦林斯卡",
  "hook":"波兰双子星\n从青梅竹马到巅峰相见",
  "_owner_words":"账号所有者 2026-10-16 策划案标题《波兰双子星：从青梅竹马到巅峰相见》，钩子按冒号拆成两行，一字不改。",
  "_hook_why":"第一行是谁（波兰双子星，封面上就是这两个人 15 岁时的合影），第二行是这条片子讲的十年：一起长大，明天在一千赛半决赛隔网。5＋10 字符，零术语。",
  "narration":"波兰双子星，从青梅竹马到巅峰相见。","_narration_why":"念的就是海报上那句钩子。",
  "topic":"从双打搭档到武汉半决赛",
  "_topic_why":"账号所有者 2026-10-15：「封面的副标题要用这个故事的内容，不要用比赛双方」。11 字。",
  "portrait":{"image":"assets/reel/swiatek-chwalinska/cover-ao2017.jpg","fit":"cover","focus":0.5,"focus_y":0.3,"zoom":1.0,
   "source_url":"https://photoresources.wtatennis.com/photo-resources/2022/06/24/4cb6065c-9ea4-437c-ba73-4dc22ffb9f63/Chwalinska-Swiatek-Andreescu-Branstine-AO-2017.jpg",
   "_credit":"WTA 官方图库 photo 2655257「Maja Chwalinska, Iga Swiatek, Carson Branstine, Bianca Andreescu - Australian Open 2017」",
   "_portrait_why":"本期讲的就是这两个人从小一起打球，这张是唯一一张两人同框的官方高清实拍：WTA 官方图库 4935×3290（取 width=4000 版本 4000×2667），说明原文「Left to right: 2017 Australian Open girls' doubles runners-up Maja Chwalinska and Iga Swiatek; and champions Carson Branstine and Bianca Andreescu」。裁左边两人 1800×2400（3:4，未放大，不补画）。两人正脸、睁眼、笑着端着亚军奖盘，脸在 15%–30% 高度，避开台头带和钩子带。",
   "_search_why":"2026-10-16 按 WTA 图库 references=TENNIS_PLAYER:325639（赫瓦林斯卡）全量 45 张翻过，两人同框的只有这一张；武汉本周两人各自的官方图都在，但没有同框。"},
  "scrim":"clear","_layout_why":"网球有故事讲两个人的十年，不印赛果；封面照片本身就是两人合影，solo 版铺满。"},
 "push":{"auto":True,"_why":"账号所有者 2026-10-13 起所有 spec 默认自动推送；质检通过即合并推送。","summary":"波兰双子星的10年","lead":"9 年前一起站上澳网青少年领奖台，10 月 17 日晚上，斯瓦泰克和月亮姐在武汉半决赛隔网相遇。"},
 "editorial":{"mode":"match_review","question":"明天在武汉隔网的两个人，十年前是怎样的一对搭档？",
  "thesis":"以武汉 1/4 决赛两人各自赢球为由头，倒回十年：2014 年 U14 第一次交手、2015/2016 欧青赛双打冠军、2016 青少年联合会杯一起为波兰夺冠、2016 斯德哥尔摩唯一一次职业赛交手、2017 澳网青少年女双亚军；之后一个 19 岁拿下法网、当上世界第一，一个 19 岁因为抑郁停下；2026 年月亮姐从资格赛打进法网决赛，两人又同在联合杯波兰队；武汉这一周各自过关，第一次在巡回赛相遇。",
  "beats":["冷开场：月亮姐武汉八强赛点与解说原声","斯瓦泰克同晚过关，解说点出半决赛对手","2017 澳网领奖台合影：九年前站在同一边","01 一起开始打比赛：2015 少年时代、2016 联合会杯夺冠、斯德哥尔摩、澳网亚军","02 一个登顶一个停下：2020 法网冠军；2021 抑郁停赛，2026 法网发布会原声","03 从资格赛到决赛：法网半决赛、场上采访、亚军致辞；联合杯队友；武汉这一周","收尾：一人一段展望，一问"],
  "human_context":{"angle":"十年前一起长大的两个人，明天只有一个能进决赛。",
   "facts":["WTA 4593212：两人 2015 年 U14、2016 年 U16 欧洲青少年锦标赛双打冠军，2017 澳网青少年女双亚军；2014 年波兰 Opalenica U14 八强第一次交手（斯瓦泰克 6-1 6-4）；唯一一次职业交手是 2016 斯德哥尔摩 W10 第二轮（斯瓦泰克 6-2 6-3）；一千赛半决赛第一次两个波兰人。","WTA 4593251：斯瓦泰克 6-4 6-1 胜李吉妮，2009 年以来第四人、现役唯一在全部 10 站 WTA1000 都进过半决赛；六座大满贯；场上采访 I'm really happy for Maja。","法网官方发布会（1ihxUf32bQk）：月亮姐讲停赛前起不了床、不知道还会不会回来。","2026 法网：世界第 114 的资格赛球员，法网历史上第一个打进决赛的资格赛球员，决赛 3-6 2-6 负安德烈耶娃（维基 2026 French Open – Women's singles，引 WTA 4514247、ESPN）。"],
   "sources":["https://api.wtatennis.com/content/wta/news/en/4593212","https://api.wtatennis.com/content/wta/news/en/4593251","https://www.youtube.com/watch?v=1ihxUf32bQk","https://www.wtatennis.com/news/4514247/chwalinska-breaks-new-ground-as-first-qualifier-to-reach-roland-garros-final","https://en.wikipedia.org/wiki/2026_French_Open_%E2%80%93_Women%27s_singles","https://en.wikipedia.org/wiki/2025_United_Cup"]}},
 "_owner_brief":"账号所有者 2026-10-16 上传《波兰双子星：从青梅竹马到巅峰相见》纪录片策划案（三幕：波兰小镇的网球梦、分叉的命运、顶峰重逢），说「参考这个做一期网球有故事讲述斯瓦泰克和赫瓦林斯卡的故事，为明天半决赛做预热」。策划案的素材表全是个人账号转载（DropShot Daily、Tennis366、TennisLegends 等），按 2026-10-04 全局「只用官方素材」一律不用，换成同内容的官方源：WTA、法网、联合杯、Tennis Channel、Polsat Sport、2016 青少年联合会杯东道主匈牙利网协。",
 "_corrections_vs_brief":"①策划案写「顶级巡回赛（如武汉等半决赛）历史性会师」与「赛前温情拥抱与赛后互相致敬」：比赛明天才打，片子只讲到赛前，不写还没发生的拥抱与致敬。②策划案说两人在「波兰小镇」长大：斯瓦泰克在华沙长大、月亮姐在达布罗瓦古尔尼恰，片子不说小镇。③「Maja 遭遇严重伤病折磨、心理低谷与抑郁症边缘」：片中只讲她本人在法网发布会说的停赛经历，不加「边缘」「严重伤病」这类没有一手出处的说法。④联合杯「Maja 对 Iga 的暖心照顾」那一幕只有个人账号的剪辑、检索摘要里轮次说法不一，不用，只讲两人同是 2025 联合杯波兰队成员。",
 "_editing_why":"冷开场是月亮姐武汉八强的赛点与解说原声，紧接斯瓦泰克同晚过关、解说点出半决赛对手——这就是本期由头。之后倒回十年，三个章节字卡（01~03）。整屏照片两张来自同一张 WTA 官方合影（2017 澳网领奖台），一张 2022 复出照（WTA 官方）。精彩原声配中英字幕：两场武汉八强解说、月亮姐法网发布会讲停赛、法网半决赛场上采访、亚军致辞、联合杯场边采访。旁白只放在两档 ASR 都无英文的空当里。",
 "_claims":{"第一次两个波兰人":"WTA https://api.wtatennis.com/content/wta/news/en/4593212 ；WTA https://api.wtatennis.com/content/wta/news/en/4593251（first all-Polish semifinal at a WTA-level event in the Open Era）",
  "法网历史上第一个":"WTA https://www.wtatennis.com/news/4514247/chwalinska-breaks-new-ground-as-first-qualifier-to-reach-roland-garros-final ；Wikipedia https://en.wikipedia.org/wiki/2026_French_Open_%E2%80%93_Women%27s_singles"},
 "_social_search_why":"不是当事人发声明类的选题：讲的是两人十年的公开比赛与采访；当事人亲口的部分全部用官方发布会、场上采访和颁奖致辞的原声，武汉这周两人的原话出自 WTA 官方稿。",
 "sources":sources,
 "source_fallbacks":{k:f"https://github.com/robertyang87/tennislive/releases/download/source-{v}/{v}.mp4" for k,v in YT.items()},
 "mixed_fps":{k:v for k,v in MIXED.items() if k in YT},
 "_no_probe_why":{k:{"why":f"{INFO[k][3]} 官方，download-video 存档后本地 ffprobe {INFO[k][0]}×{INFO[k][1]}@{INFO[k][2]}；网球有故事按讲解剪片，窗口按两档 ASR 的静默区和本地抽帧定，不为它单开一趟 probe。","width":INFO[k][0],"height":INFO[k][1],"fps":INFO[k][2]} for k in YT},
 "_primary_why":"主源是 sources 的第一个键 rgsf（法网官方 1080p50），输出 50 fps。",
 "_production_status":"spec_ready_for_render",
 "_why_sources":"比赛、颁奖和采访画面全部来自官方频道：WTA（0-v-yZvYAk8、O8f_vcT29uY）、Roland-Garros（nuivYz2nq08、OwKaLdNEjlI、1ihxUf32bQk、SdEjFtD4CTU、WVWjACQ11-Y）、Tennis Channel（法网美国转播方，LXRhlHKGKZc）、United Cup（15fLzmh_o7A）、Polsat Sport（波兰体育电视台，-Vsfptr_DC8，2015 年两人 14 岁时的采访）、匈牙利网协（2016 青少年联合会杯决赛东道主，p9Xzx3vDPJw）。照片来自 WTA 官方图库。策划案里的个人账号转载一条不用。",
 "segments":segs}
json.dump(spec,open('specs/reels/swiatek-chwalinska-story-2026.json','w'),ensure_ascii=False,indent=1)
print("ok",len(segs))
