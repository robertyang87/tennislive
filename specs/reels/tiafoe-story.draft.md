# 网球有故事 · 蒂亚福（Frances Tiafoe）草稿

## 触发事件
2026-08-23 辛辛那提 ATP1000 决赛：蒂亚福 vs 菲斯（Arthur Fils）。
- 官方/多家媒体确认：**历史上第一次两位黑人球员打进 ATP1000 决赛**（ATP 原话，
  Yahoo Sports / ESPN / TSN / benrothenberg.com 等多家转载）。
- 无论谁赢，冠军将成为史上**第三位**拿到 ATP1000 冠军的黑人球员，
  前两位是 Ben Shelton（两次，均在加拿大站）和 Jo-Wilfried Tsonga
  （2008 巴黎、2014 加拿大）。
- 蒂亚福本人：这是他生涯**第二次**辛辛那提决赛（第一次 2024 输给辛纳
  7-6(4) 6-2），也是**第二次**大师赛决赛。
- 菲斯：法国人，22岁（2004-06-12生），生涯首个大师赛决赛，
  2026赛季30胜10负，巴塞罗那夺冠，迈阿密/马德里进四强。

## 已核实事实（_claims 待补 URL）
1. 蒂亚福 1998-01-20 生，父母均为塞拉利昂移民；父亲 Constant（Frances Sr.）
   在 JTCC（Junior Tennis Champions Center，马里兰）建设工地打工，
   工程完工后留用为维护/驻场看管员，一家人住在场馆一间约120平方英尺的小屋。
   —— Spyscape / Olympics.com / EssentiallySports / BBC(2018)
2. 蒂亚福和双胞胎兄弟 Franklin 小时候常年睡在场馆的按摩床上；
   八岁时被教练 Mikhail Kouznetsov 发掘。—— Spyscape
3. 生涯最高排名世界第10（2023-06-19）。当前排名区间：本站赛事页
   本周登记为23（tiafoe-nakashima-cincinnati-2026-sf.json 已核实）。
4. 2018年 Delray Beach 夺得生涯首个ATP冠军。
5. 2019年美网四强（生涯大满贯最好成绩之一），当时其父亲的故事被广泛报道。
6. 2024年辛辛那提决赛：0-1不敌辛纳，7-6(4) 6-2。
7. 2026年辛辛那提：1/4决赛胜穆塞蒂7-6(2) 7-5、半决赛胜中岛布兰登7-5 6-3，
   晋级决赛（已有赛场之上分片，spec: tiafoe-musetti-cincinnati-2026-qf.json /
   tiafoe-nakashima-cincinnati-2026-sf.json）。

## 候选源片（2026-08-23 已 probe，产物在
output/2026-08-23/reel/tiafoe-story-father/ 和 .../tiafoe-story-2024final/）

- **r_father**: https://www.youtube.com/watch?v=setraNSmB7A
  本地新闻台（DC 地区，98.7 主持）2022 年美网四强前的专题，179.14s / 1920×1080
  / 29.97fps，**有完整 captions.txt**。
  - 0–58s 是演播室+集锦（2022美网路上的庆祝画面）
  - 66.5s / 72.5–75.5s：**真实童年打网球画面**（红衣男孩挥拍、少年穿USTA外套）
  - 78.5–90.5s：**父亲本人接受路采**（举着话筒），原声（已转写）：
    「Well, it's just unbelievable... I dreamt for this, but it came quicker
    than I expected. Who is this little guy right here? That's the younger
    bro. Being a little kid, he wanted this moment so bad and he would be
    insanely happy. And now he's now he's living it.」
    ——父亲看着老照片回忆，「他小时候就渴望这一刻，现在他真的活成了这样」，
    这就是这条片子最好的落点素材，直接用 quote 段真实原声。
  - 63.81–69.07s 记者旁白原声：「Francis Tiafoe was only five years old when
    he first picked up a racket after his father, Francis senior, introduced
    him to the sport.」——起源事实，画面正好对应66.5s童年打网球镜头。
  - ⚠️ 这条视频本身是"2022年专题回顾"，不是当年原始素材——里面混着不同年份的画面
    （童年/少年/2022美网），但父亲这段路采是这条视频独有、可用的真实素材。

- **r_2024final**: https://www.youtube.com/watch?v=htsVOPFaaQ8
  《Jannik Sinner vs Frances Tiafoe For The Crown | Cincinnati 2024 Final
  Highlights》Tennis TV官方频道，490.38s / 1920×1080 / 25fps，无字幕
  （captions_debug.txt：无自动字幕）。
  - 记分条确认：SINNER 7 6 / TIAFOE 6 2（辛纳直落两盘夺冠）
  - 441.5s：辛纳双臂举起庆祝制胜分（赛点落地）
  - 450–465s：网前握手（辛纳浅蓝、蒂亚福荧光黄绿）
  - 465–480s：颁奖典礼，辛纳举起冠军奖杯；蒂亚福（红色外套）作为亚军
  - 480.32s后进入Tennis TV訂閱卡片，严格不用

- **r_qf2026**: https://youtu.be/CLXw7um5Y4o （已由
  tiafoe-musetti-cincinnati-2026-qf probe 过：365.62s/1920×1080/25fps，
  350.64s前收）—— 蒂亚福7-6(2) 7-5胜穆塞蒂
- **r_sf2026**: https://www.youtube.com/watch?v=ovD4bsNlNVA （已由
  tiafoe-nakashima-cincinnati-2026-sf probe过：369.73s/1920×1080/25fps，
  359.68s前收）—— 蒂亚福7-5 6-3胜中岛布兰登，4-5落后连救三个盘点
- **r_final2026**: 待定——决赛尚未开打（辛辛那提当地下午4:30后开打，
  即北京时间大约8/24 04:30起，best of 3 预计1.5–3小时打完），
  需等比赛结束后找 Tennis TV/ATP官方单场集锦，probe后补进sources。

## ⚠️ 菲斯背景已核实：他父亲是海地裔——「两个黑人球员打进大师赛决赛」这句话
不取决于谁赢，两人都是。蒂亚福父母是塞拉利昂移民，菲斯父亲Jean-Philippe
Fils是海地裔、母亲Anne是法国人。所以这句历史事实**在决赛开打前就已经成立**，
可以放进片子里不必等结果。（来源：essentiallysports.com关于Fils父母的报道，
以及ATP/Yahoo/ESPN/TSN多家对"first Black-Black ATP1000 final"的报道）

## 叙事结构（草案，⑨⑩待决赛结果填）
① 冷开场：全片最强画面——**待定，大概率用今天决赛的画面**（赢球庆祝/关键分），
   不确定决赛前是否有更强候选，倾向于等结果出来再定这一格，不用父亲quote当①
   （父亲那段适合放在中段当情感落点，不适合当无声开场）
② 一句话：他是蒂亚福，正在辛辛那提打他生涯第二次大师赛决赛
③ 起源：童年画面 + 记者旁白事实（五岁拿起球拍，父亲带他入门）
④ 父亲quote段（真实原声，78.5–90.5s，中英双语字幕，不配中文旁白）
⑤ 转场：中间生涯（简短带过，不展开——避免变成平铺直叙的年表）
⑥ 2024年这里：输给辛纳的赛点+颁奖礼亚军画面——"他在这里输过一次决赛"
⑦ 2026回归：QF胜穆塞蒂、SF救三个盘点胜中岛布兰登，重新杀回决赛
   （复用已probe的r_qf2026/r_sf2026，各取一两个关键分镜头，不重复赛场之上
   已经讲过的全部细节）
⑧ 现在：两年后，同一座球场，同一个决赛——而对面的菲斯，和他一样，父亲也来自
   非洲/加勒比移民家庭——今天无论谁赢，都是史上第一次两个黑人球员打进大师赛
   决赛
⑨ 决赛结果（待定）
⑩ 收尾一问（待决赛结果定基调）

## 待办
- [x] probe 两条候选源片确认内容、真实时长、能否下到captions
- [x] 核实"两个黑人球员打决赛"这句是否要等决赛结果才能用——不用等，两人身份
      在赛前已定
- [ ] 等辛辛那提决赛结果（预计北京时间8/24凌晨，已排定检查时间）
- [ ] probe决赛集锦源片
- [ ] 写完整 segments/narration，--dry-run 校验，本地看封面/听旁白
- [ ] 触发render，check_reel_landed质检，合并推送
