import json
let=json.load(open('specs/reels/let-not-net-2026.json'))
segs=json.load(open('research/fault-not-out-2026/gen/segments.json'))
YT={"bu":"PYnZo-nL6Hk","ao":"VwN4Bm3liL0","ky":"o1Ad7ZL7AuU","md":"FhSymjai5hM","rb":"I_vN3qoxO8Q","wb":"GeMppP-gRKc"}
FPS={"bu":("50/1","Tennis TV"),"ao":("25/1","Australian Open"),"ky":("25/1","Wimbledon"),"md":("30000/1001","Tennis TV"),"rb":("25/1","Australian Open"),"wb":("25/1","Wimbledon")}
spec={
 "slug":"fault-not-out-2026","date":"2026-10-15","_column":"网球有故事","title":"发球失误为啥喊Fault",
 "cx":0.5,"track":False,"tts_backend":"edge",
 "_tts_backend_why":"不用情绪风格；与 let-not-net-2026 同一把嗓子（edge 云健 +18% +10Hz），两期是一组。",
 "_voice_why":let["_voice_why"],
 "cover":{
  "eyebrow":"网球有故事","layout":"solo","subject":"司线",
  "hook":"发球为啥喊Fault\n司线喊的是没做到",
  "_hook_why":"和 let-not-net-2026 同一个句式（账号所有者 2026-10-15 选定的「擦网为啥喊Let／主裁喊的是阻碍」）：第一行是问题，第二行直接给答案的翻转（fault 本义是缺失、做不到，不是出界），「司线」对上画面里正在判罚的司线。10＋8 字符，零术语。",
  "narration":"发球为啥喊 fault？司线喊的是没做到。","_narration_why":"念的就是海报上那句钩子。",
  "topic":"发球失误喊的是 Fault 不是 Out",
  "_topic_why":"账号所有者 2026-10-15：封面副标题要用这个故事的内容；与上一期「擦网喊的是 Let 不是 Net」同一个说法。",
  "portrait":{"image":"assets/reel/faultout/fault-cover-linejudge.jpg","fit":"cover","focus":0.6,"focus_y":0.5,"zoom":1.0,
   "source_url":"https://wtop.com/wp-content/uploads/2025/05/French_Open_Tennis_81224.jpg",
   "_credit":"AP Photo/Lindsey Wasson，经 wtop.com（AP 会员站）媒体库；2025-05-25 法网第一轮",
   "_portrait_why":"AP 原图 3200×2133，说明原文：「A line judge makes a call as Russia's Anastasia Pavliuchenkova plays China's Zheng Qinwen during their first round match of the French Tennis Open at the Roland Garros stadium, in Paris, Sunday May 25, 2025.」画面里只有坐在场边、伸臂判罚的司线（两位球员都不在画面里），正是「司线喊」的场景。司线正脸偏侧、睁眼、合焦，脸在台头带和钩子带之间；3:4 裁切用到 1600×2133，不放大。说明没写这一下判的是发球还是回合，片中和文案都不说这一下是 fault。",
   "_search_why":"2026-10-15 查过：Commons 司线类 40 余张（多为站立盯线、无判罚动作）；AP 经 16 个会员站 WordPress 媒体库按说明全文搜「line judge makes a call / linesman gestures / foot fault」等，判罚手势的只有这张和 2011 澳网那张（2000×1106、说明写的是判出界），见 research/fault-not-out-2026/sources.md。"},
  "scrim":"clear","_layout_why":"网球有故事讲一件事，不印赛果，solo。"},
 "push":{"auto":True,"_why":let["push"]["_why"],"summary":"Fault不是出界","lead":"Fault 不是出界，是没做到。"},
 "editorial":{"mode":"match_review","question":"发球没进，司线为什么喊 Fault 而不是 Out？",
  "thesis":"fault 来自古法语 faute（缺失、做不到），与 fail、default 同出拉丁 fallere；它宣布的是「这一发没做到」，不是「球出界」。发球的目标是斜对面的发球区，落在发球线后、底线前的球还在场内，喊 out 说不通；所以回合球出界喊 out，发球没进喊 fault，2025 温网的电子司线也照样分成 out、fault、foot fault 三句。规则里的 fault 还包括脚误、挥空、碰网柱、砸到自己搭档；两次 fault 丢一分，2009 美网小威的一次脚误正好送出赛点。",
  "beats":["冷开场：2025 澳网电子司线对汤普森连喊脚误。","01 词源：faute／fail／default；发球区与场地的区别；温网电子司线三句话。","02 不出界也是 fault：克耶高斯脚误、梅德韦杰夫二发脚误与原话、脚误规则字卡、布勃利克中点脚误。","03 双误：卢布列夫；2009 美网小威；库尔尼科娃 31 次双误。","延伸：羽毛球、壁球、UTS。","收尾：out 说落点，fault 说没做到；落在一问。"],
  "human_context":{"angle":"和上一期 let 是一组：一个天天听到、几乎没人细想的词，fault 原意是没做到，所以它管的从来不只是出界。",
   "facts":["Etymonline/Wiktionary：fault 来自古法语 faute，拉丁 fallere；default、fail 同源。","ITF Rule 17/18/19/24；WTA VII.H.1.c。","温网 2025 官方：电子司线报 out、fault、foot fault。","2009 美网半决赛小威脚误→双误→罚分即赛点（ESPN、CBS/AP）。"],
   "sources":["https://www.etymonline.com/word/fault","https://en.wiktionary.org/wiki/fault","https://www.etymonline.com/word/default","https://www.itftennis.com/media/7221/2026-rules-of-tennis-english.pdf","https://www.wimbledon.com/en_GB/news/articles/2025-07-03/the_precision_operation_introducing_electronic_line_calling.html","https://www.espn.com/sports/tennis/usopen09/news/story?id=4468762","https://www.cbsnews.com/news/clijsters-stuns-serena-at-us-open"]}},
 "_facts":{
  "etymology":"Etymonline「fault」：Old French faute（earlier falte），Vulgar Latin *fallita，Latin fallere；Wiktionary 同链。Etymonline「default」：Old French defaute，*defallita，de- + fallere；fail 亦出 fallere。Oxford Learner's「default」同。网球用法约 1600 年（Etymonline 单源）不进旁白。",
  "rules":"ITF Rules of Tennis（WTA 2026-07-27 规则书 Appendix N，本地 research/sun-gauff-replay-2026/wta-2026-july27.pdf）：Rule 17 发球落进斜对面发球区；Rule 18 脚误（含踩中点假想延长线）；Rule 19 发球失误（违反 16–18 条、挥空、碰永久设施/单打支柱/网柱、碰发球方或搭档）；Rule 24a 连续两次失误丢分。WTA VII.H.1.c：击球前喊脚误须判 let。WTA 规则书 Line Umpires：各线司线喊 Out 与 Fault。",
  "elc":"2025 温网：18 块比赛场首次全部电子司线，司线员角色结束（备用人员留场外），预录人声报 out、fault、foot fault（wimbledon.com 2025-07-03；AP 2025-07-03 图片说明「Line judges are on standby」）。2021 澳网：全部比赛无司线，Hawk-Eye Live 报 out、fault、foot fault（ESPN、Greek City Times）。",
  "serena":"2009 美网女单半决赛：小威 5-6、15-30 二发被判脚误→双误，15-40；冲司线怒吼被罚一分（违反体育道德），正好是赛点，克莱斯特尔斯 6-4 7-5 胜（ESPN、CBS/AP、CNN）。无官方画面，用字卡。",
  "kournikova":"1999 澳网，库尔尼科娃 31 次双误，1-6 6-4 10-8 胜佐伯美穗（tennishead、BNP Paribas wearetennis）；轮次各源不一，不报。",
  "medvedev":"Tennis TV『Foot Fault: Yes Or No? Controversy In Medvedev vs Zverev | Nitto ATP Finals 2021』：解说「In the second set tiebreak, there was the foot fault call」，主裁 Mohamed Lahyani 看视频回放维持原判；梅德韦杰夫赛后原话见第 16 段。",
  "bublik":"Tennis TV『Bublik Foot Fault Confusion in Beijing』（2026 中网，对手门希克）：被判踩中线（中点延长线）脚误。",
  "kyrgios":"Wimbledon『Nick Kyrgios and umpire James Keothavong have comical exchange | Wimbledon 2018』：被司线判脚误，解说：司线只能在击球之后喊。",
  "rublev":"Australian Open『Rublev's double fault his breaking point | Australian Open 2018』（对季米特洛夫）：解说「Double fault from Rublev, another turnaround 5-4 deep in the third」。第三盘不是决胜盘（大满贯男单五盘三胜），旁白只说第三盘。",
  "other_sports":"羽毛球 BWF Law 13 Faults；壁球 World Squash 单打规则只有一次发球、失误即输掉回合；UTS 一分一次发球（tennismajors UTS4 规则、tennishead）。"},
 "sources":{k:f"https://www.youtube.com/watch?v={v}" for k,v in YT.items()},
 "source_fallbacks":{k:f"https://github.com/robertyang87/tennislive/releases/download/source-{v}/{v}.mp4" for k,v in YT.items()},
 "primary":"bu",
 "segments":segs,
 "_no_probe_why":{k:{"why":f"{FPS[k][1]} 官方 YouTube，download-video 存档后本地 ffprobe 1920×1080@{FPS[k][0]}；网球有故事按讲解剪片，窗口按两档 ASR 的静默区和本地抽帧定，不为短片单开一趟 probe。","width":1920,"height":1080,"fps":FPS[k][0]} for k in YT},
 "mixed_fps":{
  "ao":"Australian Open 官方 YouTube 原片即 25 fps，升到 50 fps 每帧整齐重复一次，看不出顿挫",
  "ky":"Wimbledon 官方 YouTube 原片即 25 fps，升到 50 fps 每帧整齐重复一次，看不出顿挫",
  "rb":"Australian Open 官方 YouTube 原片即 25 fps，升到 50 fps 每帧整齐重复一次，看不出顿挫",
  "wb":"Wimbledon 官方 YouTube 原片即 25 fps，升到 50 fps 每帧整齐重复一次，看不出顿挫",
  "md":"Tennis TV 原片 29.97 fps，升到 50 fps 帧重复不均匀；用到的是远景、慢镜回放、主裁近景和赛后采访，没有快速横移，顿挫不明显"},
 "_production_status":"spec_ready_for_render",
 "_why_sources":"比赛画面全部来自官方频道：Tennis TV（PYnZo-nL6Hk、FhSymjai5hM）、Australian Open（VwN4Bm3liL0、I_vN3qoxO8Q）、Wimbledon（o1Ad7ZL7AuU、GeMppP-gRKc）；全部经 download-video 存进 Release。2009 美网小威脚误、1999 澳网库尔尼科娃没有官方画面，用字卡和旁白讲。"}
# primary first in sources order
spec["sources"]={k:spec["sources"][k] for k in ["bu","ao","ky","md","rb","wb"]}
json.dump(spec,open('specs/reels/fault-not-out-2026.json','w'),ensure_ascii=False,indent=1)
print("ok")
