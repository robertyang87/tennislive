import json
segs=json.load(open('research/medvedev-not-villain-2026/gen/segments.json'))
YT={"mc26":"yNxzL-8i9NU","us19":"9CQYJlU5_Ew","md21":"SXCs4vTWo_s","ci21":"Rv0Q9jXIz-M","us21":"MEFpXBwnyQA","ao22":"uWxN2lH2Fa0","ao22r":"xH4R5HNq-6s","us23":"6q9HMdjYpVg","ao25":"MWNZOZr_uMU","ws26":"l7F7uLC-GGM","us25e":"oXmpP1kLyxQ","us25":"p2lgExFvcug","cik":"5PSCTOsUYho"}
WSC="https://github.com/robertyang87/tennislive/releases/download/reel-src-medvedev-not-villain-2026/ws_c.mp4"
INFO={"us19":(1280,720,"30000/1001","US Open"),"md21":(1920,1080,"60/1","Tennis TV"),"ci21":(1920,1080,"60/1","Tennis TV"),
 "us21":(1280,720,"30000/1001","US Open"),"ao22":(1920,1080,"25/1","Australian Open"),"ao22r":(1920,1080,"25/1","Wide World of Sports（Nine，澳网主转播方）"),
 "us23":(1280,720,"30000/1001","US Open"),"ao25":(1920,1080,"25/1","Australian Open"),"mc26":(1920,1080,"50/1","Tennis TV"),"ws26":(1920,1080,"60000/1001","Tennis TV"),
 "wsc":(1920,1080,"50/1","Tennis TV"),"us25e":(1920,1080,"25/1","ESPN（美网美国主转播方）"),"us25":(1920,1080,"60000/1001","US Open"),"cik":(1920,1080,"60/1","Tennis TV")}
LOW={"us19","us21","us23"}
sources={k:f"https://www.youtube.com/watch?v={v}" for k,v in YT.items()}; sources["wsc"]=WSC
spec={
 "slug":"medvedev-not-villain-2026","date":"2026-10-15","_column":"网球有故事","title":"梅德韦杰夫：不是反派，只是太真实",
 "cx":0.5,"track":False,"tts_backend":"edge",
 "_tts_backend_why":"与 fault-not-out-2026、medvedev-tsitsipas-feud-2026 同一把嗓子（edge 云健），不加情绪风格。",
 "_voice_why":"渲染传 --voice zh-CN-YunjianNeural --rate +18%。正文各段 pitch +10Hz；不写 style、lead_pause。交接文档的旁白音频是 +10%，按仓库网球有故事现行口径用 +18%。",
 "cover":{
  "eyebrow":"网球有故事","layout":"solo","subject":"梅德韦杰夫",
  "hook":"梅总不是反派\n他只是太真实",
  "_hook_why":"交接文档的标题《梅德韦杰夫：不是反派，只是太真实》拆成两行：第一行是关键内容（被叫作反派的那个人），第二行是这条片子给的答案。6＋6 字符，零术语。",
  "narration":"梅总不是反派，他只是太真实。","_narration_why":"念的就是海报上那句钩子。",
  "topic":"梅德韦杰夫的那些名场面",
  "_topic_why":"账号所有者 2026-10-15：「副标题不要 11，就说梅德韦杰夫的那些名场面」。封面副标题写故事内容，不写比赛对阵，也不写件数。",
  "portrait":{"image":"assets/reel/medvedev-real/cover-montecarlo-2026.jpg","fit":"cover","focus":0.2,"focus_y":0.35,"zoom":1.0,
   "source_url":"https://resources.prod.atpmedia.pulselive.com/atpmedia/photo/2026/04/08/77c161c8-fadf-445f-874d-a40d7be52b42/GettyImages-2270362315.jpg",
   "_credit":"ATP Media 官方图库「2026 Monte Carlo Medvedev」（Getty Images / Julian Finney）",
   "_portrait_why":"账号所有者 2026-10-15：「选一个比较好的名场面，且有高清大图的做封面」。片中蒙特卡洛第二轮 0-6 0-6 负贝雷蒂尼那一场：ATP Media 官方图库原图 4403×2618（等比缩到 3000×1784 入库，未裁未补画），EXIF 2026-04-08 12:48；Getty 说明「Daniil Medvedev against Matteo Berrettini of Italy during day five of the Rolex Monte-Carlo Masters … April 08, 2026」，与片中 Tennis TV 集锦同一身橙色球衣。反手击球中，正脸、睁眼、龇牙皱眉，情绪对得上「太真实」。",
   "_search_why":"2026-10-15 把 ATP Media 图库 54208 张全量翻了一遍（1334 张梅德韦杰夫），片中各事件里有高清原图的只有蒙特卡洛 2026（这一张）和温斯顿-塞勒姆 2026（一张俯拍握手）；马德里 2021、辛辛那提 2021 只有 1920 的视频海报；美网图片接口天花板 1280×720。"},
  "scrim":"clear","_layout_why":"网球有故事讲一个人的九年，不印赛果，solo。"},
 "push":{"auto":True,"_why":"账号所有者 2026-10-13 起所有 spec 默认自动推送；质检通过即合并推送。","summary":"不是反派只是太真实","lead":"撒硬币、踢摄像机、冲主裁吼，也在颁奖台上让全场笑：梅德韦杰夫的那些名场面。"},
 "editorial":{"mode":"match_review","question":"梅德韦杰夫为什么总被叫作反派？九年里那些名场面，到底是什么样的人？",
  "thesis":"以 2022 澳网冲主裁怒吼为由头，按时间串起梅德韦杰夫九年里的 10 个名场面：2017 温网撒硬币、2019 美网被嘘到决赛又在颁奖台上道歉、2021 马德里「不想在这片场地打」到「爱红土」、辛辛那提撞摄像机、美网死鱼式庆祝拦下年度全满贯、2022 澳网对主裁怒吼、2023 美网调侃德约、2025 澳网砸摄像机、2026 蒙特卡洛生涯首次双蛋、温斯顿-塞勒姆匹克球自嘲。情绪从不掩饰，坏事也认，所以不是反派，是太真实。",
  "beats":["冷开场：2022 澳网半决赛换边时冲主裁吼（Are you stupid? 原声）","由头与问题：反派还是太真实","01 被嘘的那几年：2017 温网硬币（字卡）、2019 美网被嘘与颁奖致辞原声","02 冠军也一样真：马德里、辛辛那提、2021 美网、2022 澳网怒吼原声","03 低谷里的梅总：2023 美网调侃与纪念日、2025 澳网砸摄像机、蒙特卡洛双蛋、温斯顿-塞勒姆匹克球","收尾：2019 颁奖台的笑，一问"],
  "human_context":{"angle":"同一个人既撒硬币，也在颁奖台上认错；他从来不演。",
   "facts":["2017 温网第二轮负贝梅尔曼斯 4-6 2-6 6-3 6-2 3-6，朝主裁椅扔硬币，扔硬币罚 7500 美元、全场共 14500 美元；他说 In the heat of the moment, I did a bad thing。","2019 美网第一周对看台竖中指被嘘；决赛 5-7 3-6 7-5 6-4 4-6 负纳达尔；颁奖致辞原声见 9CQYJlU5_Ew。","2021 马德里第二轮 4-6 6-4 6-2 胜达维多维奇·福基纳，第一次在马德里赢球、止住红土六连败，镜头上写 Love clay :)。","2021 辛辛那提半决赛 6-2 3-6 3-6 负卢布列夫，撞上场边摄像机，说手差点撞断，后来踢了一脚镜头。","2021 美网决赛 6-4 6-4 6-4 胜德约科维奇，阻止年度全满贯；死鱼式庆祝学自 FIFA 游戏。","2022 澳网半决赛 7-6(5) 4-6 6-4 6-1 胜西西帕斯；换边时对主裁怒吼（Wide World of Sports 原声），被罚 1.2 万美元，事后说完全后悔。","2023 美网决赛 3-6 6-7(5) 3-6 负德约科维奇；颁奖致辞原声调侃、说当天又是结婚纪念日。","2025 澳网首轮五盘胜世界第 418 的萨姆雷吉，球拍砸向网上摄像机；前两轮共被罚 7.6 万美元。","2025 美网首轮负邦齐 6-3 7-5 6-7(5) 0-6 6-4（邦齐视角），第三盘 5-4 邦齐赛点时摄影记者走进场地，主裁 Greg Allensworth 判重发一发，梅德韦杰夫煽动看台、停赛六分多钟；赛后砸拍，罚 42500 美元（30000 违反体育道德＋12500 砸拍）；发布会说 I expressed my emotions。","2026 蒙特卡洛第二轮 0-6 0-6 负贝雷蒂尼，49 分钟，生涯第一次双蛋，砸拍后扔进垃圾桶。","2026 温斯顿-塞勒姆第二轮 5-7 3-6 负外卡达姆（达姆首胜前十），自嘲该去打匹克球。"],
   "sources":["https://prod.tennis.com/news/articles/medvedev-fined-for-bizarre-coin-tossing-wimbledon-incident","https://www.malaymail.com/news/sports/2017/07/06/bad-boys-tomic-and-medvedev-receive-wimbledon-fines/1415213","https://www.cbssports.com/tennis/news/us-open-2019-daniil-medvedev-thanks-booing-crowd-for-helping-him-win-after-appearing-to-put-up-a-middle-finger","https://www.tennismajors.com/?p=337420","https://tennishead.net/?p=114379","https://www.tennis.com/news/articles/daniil-medvedev-crashes-into-camera-loses-to-rublev-first-time-cincinnati","https://gulfnews.com/sport/tennis/i-almost-broke-my-hand---medvedev-collides-with-camera-in-shock-semi-final-loss-to-rublev-1.81737518","https://africa.espn.com/tennis/story/_/id/32200987/us-open-2021-daniil-medvedev-beats-novak-djokovic-own-game-lock-first-slam-title","https://www.news4jax.com/sports/2025/01/13/daniil-medvedev-might-skip-the-video-game-celebration-if-he-wins-a-2nd-slam-title-in-australia/","https://tennishead.net/medvedev-fined-12000-for-explosive-australian-open-court-side-outburst/","https://www.freemalaysiatoday.com/category/sports/2022/01/29/medvedev-fined-for-are-you-stupid-rant-at-umpire","https://tennismajors.com/australian-open-news/medvedev-fined-76000-for-unsportsmanlike-conduct-at-australian-open-plus-cost-of-new-net-camera-804741.html","https://www.si.com/tennis/daniil-medvedev-fined-whopping-76k-australian-open-broken-camera","https://www.flashscore.com/news/tennis-monte-carlo-atp-singles-medvedev-fails-to-win-a-single-game-in-humiliating-defeat-to-berrettini-in-monte-carlo/bFfa1iCC","https://www.aljazeera.com/sports/2026/4/8/medvedev-thrashed-6-0-6-0-by-berrettini-in-monte-carlo-zverev-battles-on","https://www.foxsports.com/articles/tennis/daniil-medvedev-is-fined-42500-for-unsportsmanlike-conduct-and-racket-abuse-for-us-open-outburst","https://www.aljazeera.com/sports/2025/8/25/daniil-medvedev-exits-us-open-after-photographer-incident-on-match-point","https://news.bet365.com/en-gb/article/i-just-expressed-my-emotions-daniil-medvedev-on-us-open-meltdown/2025082509184152994","https://tennis.com/news/articles/daniil-medvedev-benjamin-bonzi-us-open-mayhem","https://www.atptour.com/en/news/winston-salem-2026-tuesday-report","https://www.tennismajors.com/atp/maybe-i-should-start-a-career-in-pickleball-medvedev-jokes-after-damm-becomes-his-fourth-loss-in-five-matches-859436.html"]}},
 "_owner_brief":"账号所有者 2026-10-15 上传《梅德韦杰夫《网球有故事》11场面 - 制作交接文档》并说「接手做这个梅德韦杰夫的历史名场面视频」：3:4 竖屏、右上角事件字卡（日期／赛事轮次／对阵／比分）、英文原声中英双语、现场声不压、不烧 BGM、片尾只要品牌页；如确认有脏话要消音并在中英字幕里打星号；2017 那段不许用定格硬撑。",
 "_corrections_vs_brief":"⓪账号所有者 2026-10-15：「中网的名场面其实不是有意的，可以不放进来」——事件 11（北京失格）整件拿掉，冷开场换成 2022 澳网争执。①2017 温网的源（UKZnd1EliAY）不是官方频道，按 2026-10-04 全局「只用官方素材」改成两张字卡＋旁白，也就不存在定格硬撑。②辛辛那提换成 Tennis TV 官方单条（Rv0Q9jXIz-M，1080p60，撞摄像机全程），2025 澳网换成澳网官方加长集锦（MWNZOZr_uMU，砸摄像机那一下是近景）。③温斯顿-塞勒姆那场按当地日期是 8 月 25 日（交接文档写 8.26，是北京时间）。④蒙特卡洛第二轮即 64 签的 R32，字卡写第二轮。⑤四段脏话风险片段（马德里、辛辛那提、2025 澳网、蒙特卡洛）两档 ASR 逐词转写里都没有脏话，按交接文档「如果确认有脏话」的条件，不消音。⑥右上角字卡受仓库屏幕文案合同约束（show_for 最多 4.2 秒），每个事件第一段出现，不能全程常驻。",
 "_editing_why":"冷开场是 2022 澳网冲主裁吼的前半段原声，正文按时间走 10 件事（讲到澳网时接上后半段），三个章节字卡（01~03）。每件事第一段贴右上角 story_text 字卡。精彩原声配中英字幕：2019、2023 两段颁奖致辞，马德里「不想在这片场地打」与「爱红土」，辛辛那提「You okay, sir?」，2021 美网冠军点比分，2022 澳网怒吼（含 small cat），2025 澳网与蒙特卡洛解说，温斯顿-塞勒姆匹克球自嘲。旁白只放在两档 ASR 都无英文的空当里。",
 "_claims":{"生涯第一次吃到双蛋":"flashscore https://www.flashscore.com/news/tennis-monte-carlo-atp-singles-medvedev-fails-to-win-a-single-game-in-humiliating-defeat-to-berrettini-in-monte-carlo/bFfa1iCC ；Al Jazeera https://www.aljazeera.com/sports/2026/4/8/medvedev-thrashed-6-0-6-0-by-berrettini-in-monte-carlo-zverev-battles-on","第一次在马德里赢球":"Tennis Majors https://www.tennismajors.com/?p=337420 ；Tennishead https://tennishead.net/?p=114379（first ever Madrid victory）","达姆第一次赢下世界前十":"ATP https://www.atptour.com/en/news/winston-salem-2026-tuesday-report ；Wikipedia https://en.wikipedia.org/wiki/Martin_Damm_(born_2003)"},
 "_social_search_why":"不是当事人发声明类的选题：讲的是九年里的公开比赛与颁奖台；当事人亲口的部分全部用官方集锦和颁奖仪式的原声，温斯顿-塞勒姆那句来自 Tennis TV 官方竖版短片。",
 "sources":sources,
 "source_fallbacks":{k:f"https://github.com/robertyang87/tennislive/releases/download/source-{v}/{v}.mp4" for k,v in YT.items()},
 "conform":{k:"美网官方频道这条最高 1280×720 @29.97，等比放大到主源 1920×1080，不另裁原始内容。" for k in LOW},
 "source_quality_exceptions":{sources[k]:{"min_height":720,"approved_by":"user","reason":"账号所有者 2026-10-15 交接文档点名的美网官方源，官方频道这条最高 720p。" } for k in ["us19","us23"]},
 "mixed_fps":{
  "us19":"美网官方 29.97 fps，颁奖致辞近景，人基本不动，升到 50 fps 帧重复不均匀看不出",
  "us21":"美网官方 29.97 fps，冠军点一分的广角与倒地庆祝，横移慢，顿挫不明显",
  "us23":"美网官方 29.97 fps，颁奖致辞近景，人基本不动",
  "md21":"Tennis TV 60 fps → 50，每六帧丢一帧；用到的是局间近景、广角回合和签名镜头，丢帧看不出",
  "ci21":"Tennis TV 60 fps → 50，撞摄像机与场边交涉，丢帧看不出",
  "ws26":"Tennis TV 59.94 fps → 50，广角回合配旁白",
  "ao22":"澳网官方 25 fps，升到 50 fps 每帧整齐重复一次",
  "ao22r":"Wide World of Sports 原片 25 fps，升到 50 fps 每帧整齐重复一次",
  "ao25":"澳网官方 25 fps，升到 50 fps 每帧整齐重复一次",
  "cik":"Tennis TV 60 fps → 50，场边近景，丢帧看不出",
  "us25e":"ESPN 25 fps，升到 50 fps 每帧整齐重复一次；停赛中的近景与看台",
  "us25":"美网官方 59.94 fps → 50，第五盘最后一分的广角与近景配旁白，丢帧看不出",
  "wsc":"规整后 50 fps（原片 30 fps 竖版），场边与发布会说话头，人基本不动"},
 "_no_probe_why":{k:{"why":f"{INFO[k][3]} 官方，download-video 存档后本地 ffprobe {INFO[k][0]}×{INFO[k][1]}@{INFO[k][2]}；网球有故事按讲解剪片，窗口按两档 ASR 的静默区和本地抽帧定，不为它单开一趟 probe。"+("（9aqUxco0bqo 原片 720×1280 竖版，tmp 工作流 crop 720:960:0:160 → 810×1080 → 左右黑边垫成 1920×1080、50 fps、音轨原样拷贝，见 research/medvedev-not-villain-2026/normalize.sh；3:4 居中窗口正好取到原画面。）" if k=="wsc" else ""),"width":INFO[k][0],"height":INFO[k][1],"fps":INFO[k][2]} for k in sources},
 "_tennistv_trim":"Tennis TV 源（SXCs4vTWo_s、Rv0Q9jXIz-M、5PSCTOsUYho（只用 91.4–95.55，片尾板约 231 秒起）、yNxzL-8i9NU、l7F7uLC-GGM、9aqUxco0bqo）：16:9 的几条 cx 0.5 居中，角上的台标在 3:4 取景窗外；蒙特卡洛片尾板 156.3 秒起，末段收在 156.0；竖版短片 ws_c 的台标在画面内，crop_zoom 1.08＋fill_y 1.0 裁掉；马德里那条片尾板 156.3 秒起，末段收在 156.0；辛辛那提、温斯顿-塞勒姆集锦离片尾 30 秒以上。",
 "_primary_why":"主源是 sources 的第一个键 mc26（Tennis TV 1080p50）；北京那条拿掉之后沿用同一个 50 fps 输出。",
 "_production_status":"spec_ready_for_render",
 "_why_sources":"比赛与颁奖画面全部来自官方频道：Tennis TV（SXCs4vTWo_s、Rv0Q9jXIz-M、5PSCTOsUYho、yNxzL-8i9NU、l7F7uLC-GGM、9aqUxco0bqo）、US Open（9CQYJlU5_Ew、MEFpXBwnyQA、6q9HMdjYpVg）、Australian Open（uWxN2lH2Fa0、MWNZOZr_uMU），以及澳网主转播方 Nine 的 Wide World of Sports（xH4R5HNq-6s，2022 澳网怒吼的原声只有它有）、美网美国主转播方 ESPN（oXmpP1kLyxQ，2025 美网停赛六分钟的全过程；美网官方加长集锦 p2lgExFvcug 把这段剪掉了）。2017 温网撒硬币没有官方画面，用字卡和旁白讲。",
 "segments":segs}
spec["source_quality_exceptions"][sources["us21"]]={"min_height":720,"approved_by":"user","reason":"账号所有者 2026-10-15 交接文档点名的美网官方源，官方频道这条最高 720p。"}
json.dump(spec,open('specs/reels/medvedev-not-villain-2026.json','w'),ensure_ascii=False,indent=1)
print("ok")
