# ATP / WTA 赛后采访素材来源清单

给"拿英语原声当学习语料"这个用途做的一次全量遍历。2026-07-27 逐个实测，
凡是写了「实测」的都亲自访问 / 下载验证过，没验证的标了「未验证」。

## 一句话结论

**"赛后采访"是四种不同的东西，选错一种，找的地方和拿到的材料都不一样。**
想学**场上获胜发言**（刚赢球对着观众讲的那段）看第二节；想学**发布会问答**看第三节起。

两句话概括各自的可得性：

- **场上采访 / 冠军致辞**：只有视频＋自动字幕，**没有任何人工文字稿**。
  但字幕质量反而比发布会好，因为音频走转播调音台。罗马把每一轮都单发一条，命名最规范
- **发布会**：视频免费但不在 ATP / WTA 中央频道，在每个赛事自己的频道上（四大满贯 +
  六个大师赛全部实测命中）；文字稿有 ASAP Sports，1992–2026 全归档，可与视频配对

> 这份清单改过两次方向，两次都记在文里：
> 初稿写"巡回赛层面只有短片段"（错在只查了中央频道）；
> 第二版重心全放在发布会上，漏了"场上发言"才是要找的东西。

## 一、"赛后采访"其实是四种东西，别混为一谈

写在最前面，因为这决定了该拿哪一类当教材。**场上那两种（前两行）和媒体间那两种
（后两行）是完全不同的语料**，来源、时长、语言难度、有没有文字稿都不一样：

| 类型 | 时长 | 场合 | 语言特征 |
| --- | --- | --- | --- |
| **On-court interview**（场上采访） | 40 秒–4 分钟 | 刚赢球还在场上，对着观众 | 主持人问 2–3 个问题，球员站着答。短、情绪化、套话密集 |
| **Trophy ceremony / 冠军致辞** | 3–25 分钟 | 决赛后颁奖礼 | 冠亚军各讲一段，感谢对手/团队/家人/赞助商/观众。**高度程式化** |
| **Press conference**（发布会） | 6–17 分钟 | 赛后媒体间 | 各国记者完整提问，信息密度最高 |
| **Media day / pre-event** | 10–20 分钟 | 开赛前 | 同上但更从容，语速慢 |

### 想学"获胜发言"就看前两种，它们各有各的好处

**场上采访**是最好的入门材料，理由是实测出来的（罗马 2026 决赛后辛纳那条，1 分 32 秒，
255 词）：

- **音频是转播调音台直给的**，比媒体间还干净——媒体间开头那段环境噪音会被 ASR
  识别成 `What?` / `Can't` 这类碎片，场上采访没有这个问题
- **主持人的问题是完整的英式/美式书面句**，比如罗马那条：
  "What means more to you, to complete the set of Masters so soon or to give,
  well, yourself but also all of Italy this title today?" ——这种长问句本身就是好教材
- **短到一次能学完**。1–2 分钟，255 词左右，正好一个单元

**颁奖致辞**程式化程度极高，是学"套路化表达"的理想材料：感谢对手 → 感谢团队 →
感谢家人 → 感谢赛事和观众，每一环都有固定说法。学会一套，所有冠军演讲都听得懂。

### 但颁奖礼有个大坑：非英语国家的赛事是双语的

实测罗马 2026 冠军致辞（6 分 02 秒），辛纳自己在台上说：

> "I speak English for Casper for a moment, then I go back to Italian."

后半段转意大利语，YouTube 的英文 ASR 直接崩了——冒出泰文字符、把 congratulate
识别成 `conrat`、连续输出 `for for for for`。

所以按语言把赛事分开挑：

| 全英文，放心用 | 会转本地语，要挑段落 |
| --- | --- |
| 温网、美网、澳网 | 罗马（意）、马德里（西）、法网（法）、蒙特卡洛（法） |

### 球员英语水平差别极大

辛纳、兹维列夫、莱巴金娜是流利但带口音；高芙是纯正美音；
阿尔卡拉斯的英语在进步中，语法不总是标准。**主持人的提问永远是标准英语**，
所以哪怕挑了口音重的球员，那几个问句仍然值得学。

## 二、场上采访与冠军致辞：去哪儿拿

**没有任何人工文字稿，只有视频 + 自动字幕。** ASAP Sports 抽样 6 条全部标着
`Press Conference`，它不收场上内容（见第七节）。所以这一类只能靠 YouTube。

### 罗马是标杆：每一轮都有，命名最规范

罗马频道（[UCxJDHLvJsuGNHbZPUjFDCNA](https://www.youtube.com/channel/UCxJDHLvJsuGNHbZPUjFDCNA/videos)）
把每一轮的场上采访都单发一条，标题格式死板到可以直接写正则：

```
球员 On-Court Interview | 轮次 | Rome 2026     # 40 秒 – 2 分钟
球员 Trophy & Speech | Rome 2026               # 6 分钟，决赛专有
```

实测抓到的（部分）：`Jannik Sinner On-Court Interview | Final`（1:32）、
`Casper Ruud On-Court Interview | Semifinal`（1:48）、
`Luciano Darderi On-Court Interview | Quarterfinal`（0:39）。
**想批量建语料库，从罗马开始最省事**——一条正则就能把场上、发布会、颁奖礼分干净。

### 场上采访的来源：三类，别只盯着赛事官方

我在这里错过一次，教训值得单独写。**第一版只按"赛事自己的频道"建注册表，
扫出 82 条，就下结论说"只有四大满贯 + 罗马 + 巴黎，其余赛事基本为零"。**
被一句"再去看看其他源啊"打回来，换成**从 YouTube 搜索反推频道**（而不是
猜赛事句柄），一轮就翻倍还多。

来源实际有三类：

| 类别 | 代表 | 实扫场上采访条数 |
| --- | --- | --- |
| **赛事方** | Dubai 89、法网 89、温网 75、澳网 74、美网 53、罗马 34、巴黎 31、印第安维尔斯 1、华盛顿 1 | **447** |
| **团体赛** | United Cup 84、Hopman Cup 79、Laver Cup 42、Davis Cup 14 | **219** |
| **转播方** | Eurosport 81、TNT Sports 44、Nine 2 | **127** |
| **ATP 官网库** | tennistv.com/library/interviews | **16** |
| **各国网协** | FFT 2、USTA 1 | **3** |

**合计 812 条**（2026-07-27 实测）。

**转播方这一整个类别，第一版完全没想到，而它现在是最大的一类。**
Eurosport 78 条、TNT Sports 44 条（同系，格式一样但内容不完全重叠），
而且**比赛事方自己发的更长**（3–5 分钟 vs 1–2 分钟），因为它保留了主持人的
完整提问——对英语学习反而更有价值。

### 综合体育频道要过"网球闸"，否则灌进来的是足球

TNT Sports、Wide World of Sports、Amazon Prime Video Sport 都是**综合**体育频道，
而 `post-match interview` 是**通用体育说法**。Amazon 深扫 500 条命中 25 条，
**全是 UEFA 欧冠的足球采访**，一条网球都没有。

所以这类源要打 `require_tennis`，标题里必须出现网球标记（赛事名、`tennis`、
`ATP`/`WTA`、`on-court` 等）才收。加闸后 Amazon 从 25 条降到 **0**，
TNT 保留 44、Nine 保留 2。

两点设计上的讲究：

- **闸只给综合频道开，网球专频不开。** 罗马那条
  `Jannik Sinner On-Court Interview | Final | Rome 2026` 里没有 `tennis` 字样，
  全局开闸会误伤（虽然 `on-court` 本身也是标记，但别依赖这种巧合）
- **赛事名这张表必然不全。** 踩过：`Venus Williams Post Match Interview |
  2025 Mubadala DC Citi Open` 一度过不了闸。新增综合频道时要顺手补它转播的赛事名

测试里把两件事**分开**断言：足球标题**照样判成 `oncourt`**（正则只看格式，
这是对的），拦下它的是网球闸。混在一起测，改坏任何一边都发现不了。

### 取样深度：栽过三次，每次都是同一个误判

**把"我扫得不够深"当成"这家不发采访"。** 频道按时间倒序返回，赛事集中在
一年里某几周，深度不够就一条都扫不到——**和"这家没有"长得一模一样**。

三次的数字，一次比一次说明问题：

| 轮次 | 源 | 深度变化 | 条数变化 |
| --- | --- | --- | --- |
| 第一次 | 澳网 | 100 → 400 | 0 → 10 |
| 第二次 | 法网 | 200 → 700 | 18 → **89** |
| | 温网 | 200 → 700 | 20 → **75** |
| | 美网 | 300 → 600 | 11 → **53** |
| 第三次 | 美网 | 600 → 1200 | 53 → **129** |
| | 法网 | 700 → 1500 | 89 → **162** |
| | 温网 | 700 → 1500 | 75 → **154** |
| | 澳网 | 800 → 1500 | 74 → **144** |

**每次加深几乎都翻倍**，说明前两次的"修好了"都是错觉。

Eurosport 是唯一探到底的：频道总共 972 条，扫满得 92 条——**这才叫扫完了**。

结论：**建基线时给到频道总量，别猜一个数**。判断扫没扫到底的办法是看
`--flat-playlist` 实际返回条数有没有小于 `--playlist-end`；相等就说明还有更深的。
日常增量另有 `DAILY_DEPTH=60`，与此无关，不受影响。

### 转播方：只有三家有量，其余全 0

把能找到的转播方都深扫过了，结论列全，省得以后重查：

| 频道 | 深扫 | 场上采访 |
| --- | --- | --- |
| Eurosport Tennis | 600 | **78** |
| TNT Sports | 600 | **44** |
| Wide World of Sports（澳洲九号台） | 500 | 2 |
| Sky Sports（主频道） | 400 | **0** |
| ESPN | 400 | **0** |
| TSN（加拿大） | 500 | **0** |
| Sportsnet（加拿大） | 500 | **0** |
| Stan Sport（澳洲） | 500 | **0** |
| beIN SPORTS Asia | 400 | **0**（45 条网球内容，全是集锦） |
| beIN SPORTS Australia | 257 | **0**（73 条网球内容，全是集锦） |
| SuperSport | 400 | **0** |
| Star Sports（印度） | 400 | **0** |
| DAZN Canada | 400 | **0** |
| Amazon Prime Video Sport | 500 | **0**（25 条命中全是足球） |

beIN 那两家值得注意：**有大量网球内容（45 / 73 条）但一条采访都没有**——
它们只发 `Match Highlights`。这是"有网球 ≠ 有采访"的干净例子，
所以扫的时候要把两个数分开统计，否则会误判成"这频道没网球"。

**团体赛是另一个盲区**：United Cup 每场（含双打）都发，实扫 300 条命中 56 条，
是单一赛事里最多的。Laver Cup 按 `Match N` 编号，也是每场都发。

还有一条推翻了我先前的判断：**Dubai Duty Free（ATP 500）逐轮发 45 条**
`Post-Match Interview: 球员 after R2/QF/SF`，格式极规整。
所以"只有大满贯才有稳定场上采访"是错的，500 级别一样可以有。

**唯一保留的结论**：Tennis Channel 覆盖 32 项赛事那条只对**致辞**成立。
深扫它 700 条，场上采访**一条都没有**（两条疑似命中是 `on-court emergency`、
`on Court Differences` 的误匹配）。小站（Kitzbuhel、Gstaad、Bastad、Prague）
确实只有冠军致辞，没有场上采访。

> **方法论上的教训**：找源不要靠猜句柄，靠**搜索反推**。
> `yt-dlp "ytsearch12:<关键词>" --print "%(channel)s ||| %(title)s"`
> 按频道汇总，谁在发一目了然。我猜句柄猜错过四个（蒙特卡洛、迈阿密、
> 加拿大、Queen's），而搜索一轮就找出了四个我根本没想到的源。

### Tennis TV 要分两个东西：YouTube 频道没有，**站上的库有，而且免费**

这是最容易搞混的一处，也是 ATP 250 那块空白的答案。

| | 场上采访 |
| --- | --- |
| YouTube [@tennistv](https://www.youtube.com/@tennistv) | 深扫 800 条 → **0** |
| 站上 [tennistv.com/library/interviews](https://www.tennistv.com/library/interviews) | 20 条里 **16 条**，逐轮 |

**而且不在付费墙后面。** 页面内嵌 JSON 里有 `entitlement` 字段，实测：

| entitlement | 条数 |
| --- | --- |
| `free` | 16 |
| `freemium`（注册即可） | 4 |
| `premium` | **0** |

内容是 Estoril、Bastad、Kitzbuhel、Gstaad 这些 **ATP 250**，逐轮发
（`metadataRound` 为 R1/QF/SF/Final），时长 0:56–3:27。

**怎么确认真是场边而不是媒体间**：标题是编辑体（`Merida Elated to Win First
ATP Tour Title`）看不出格式，所以下载缩略图**亲眼看**——Darderi 八强那条，
球衣未换、还在出汗、身后是 Estoril 看台和场边广告牌；Van Assche 决赛那条，
手持场上麦、身后是穿西装的赛事官员。媒体间是坐着、桌前、logo 背景板，
一眼能分。

采集时**不用标题正则**，直接认 `videoType == "interviews"` 且有
`metadataRound`——字段比标题可靠。

一个限制：只给 20 条最新，`page` / `offset` / `p` 参数都返回同一批。
但按周跑正好，一个赛事周产出的采访远少于 20 条。

### ATP / WTA 的中央渠道确实不产出场上采访（深扫 800 条验证）

这三家一开始按 150 深度扫是 0，为排除"取样太浅"的可能，**各深扫到 800 条**，
结论不变：

| 渠道 | 深扫 | 场上采访 | 它实际在发什么 |
| --- | --- | --- | --- |
| Tennis TV | 800 | **0** | 集锦 + `球员 Reacts To/After …` |
| ATP Tour | 800 | **0** | 集锦、hot shots、企划片 |
| WTA | 800 | **0** | 宽口径只命中 1 条发布会 |

Tennis TV 那批 `Reacts` 值得单说：`Jannik Sinner Reacts To Victory Over
Rafael Jodar | Madrid 2026` 是 **10 分 06 秒**（发布会），
`Jannik Sinner Reacts After Completing Golden Masters | Rome 2026` 是
**3 分 34 秒**（像场上）。标题分不出，全归待定档——**时长是比标题更可靠的
线索**：场上采访 40 秒–4 分钟，发布会 6 分钟起。

所以这一类内容在**赛事方和转播方**手里，不在 ATP / WTA 中央渠道。

### 其他视频平台：全部查过，只有 YouTube 有

为回答"覆盖够不够"做过一次大范围平台扫描，结论列全省得重查：

| 平台 | 能否枚举 | 场上采访 |
| --- | --- | --- |
| **YouTube** | ✅ | 唯一有量的 |
| **Dailymotion** | ✅ 按账号（**搜索坏了**） | **0** |
| **TikTok** | ✅ 按账号（无需登录） | **0** |
| X / Twitter | ❌ 只能取单条 | — |
| Instagram | ❌ 提取器已 broken | — |
| Vimeo / Rumble / Odysee | ❌ 403 / 不支持 | — |

两处值得单独记，都是"空结果先自证是真空"的实例：

- **Dailymotion 的搜索返回 0 且不报错**，看着像平台没内容。但换成账号页
  `dailymotion.com/rolandgarros` 立刻取到内容——**是搜索坏了，不是没有**。
  用账号页深扫 rolandgarros 200、eurosport 93、beinsports 200、canalplus 200、
  lequipe 200、tennisactu 200，**连含 `interview` 字样的都是 0**。
  这才是真空：法国那边的 Dailymotion 只放集锦和新闻
- **TikTok 官方号能枚举但没有采访**：@atptour / @wta / @wimbledon / @usopen
  共扫 475 条，场上采访 0，`interview` 字样也 0。全是短集锦和花絮

区域转播方也扫了一圈（SuperTennis、Canal+、Movistar、SporTV、WOWOW、
Sony Sports、SPOTV、Nova Sports、Digi Sport、Fox Sports Australia），
搜索几乎全空——只有已收录的 Eurosport / TNT 两家有量。

### X（推特）与 Instagram：一个能取单条不能列表，一个完全取不到

两个都实测过，结论不一样，别一概而论：

| | 单条 | 列时间线 |
| --- | --- | --- |
| **X / Twitter** | ✅ 能取（yt-dlp `twitter` 提取器） | ❌ `Unsupported URL` |
| **Instagram** | ❌ `Instagram API is not granting access` | ❌ `instagram:user` 已标记 broken |

**X**：拿真实推文 `x.com/atptour/status/1054755723463270401` 测，
成功解析出 uploader。但 `x.com/atptour`、`/atptour/media`、`/i/user/atptour`
三种写法全部 `Unsupported URL`——**没法枚举，就没法做成采集源**，
除非你已经知道每一条的 URL。

**Instagram**：连单条都要 cookies。`instagram:user` 提取器在当前版本
（2026.07.04）已被 yt-dlp 自己标记为 broken。

**而且这两个平台对英语学习是降级的**，就算能取也不该优先：

- 内容是**剪过的短片**（Reels 15–60 秒），场上采访本来就只有 1–3 分钟，
  再剪就只剩一两句
- 竖版裁切，主持人常被裁出画面
- **没有自动字幕**——YouTube 那套 `--write-auto-sub` 在这里没有对应物

同样的素材在 YouTube 上是完整的、免费的、带自动字幕的。
所以这两个平台记为"查过、不用"，不进注册表。

### 国内平台（央视 / 腾讯 / 优酷 / 咪咕 / 爱奇艺）：有版权，但拿不到这一类

2026 赛季的中国区版权是分散的：

| 平台 | 持有权利 |
| --- | --- |
| 优酷体育 | ATP 巡回赛独家（2024–2026） |
| 腾讯体育 | WTA + 温网独家新媒体（2025–2027） |
| 咪咕体育 | WTA 250–1000 及年终总决赛 |
| 爱奇艺体育 | 澳网独家 |

**但持的是「直播权」，不是「切片发布」。** 逐个实测下来，都拿不到场上采访：

- **咪咕、腾讯视频：yt-dlp 根本没有提取器**（`qq` 前缀下只有 qqmusic）。
  优酷、爱奇艺、B 站、CCTV 有提取器，但优酷的频道页 `yt-dlp` 报
  `Unsupported URL`
- **央视**：`sports.cctv.com/tennis/` 实际渲染出来**没有网球视频**，
  排行榜全是 F1、足球、环法。CCTV / CGTN 在 YouTube 上的网球内容是
  《开讲啦》《面对面》这类访谈节目和坐着的专访，**不是场上采访**
- **B 站**：搜「网球 场边采访」返回的是 UP 主搬运和二创，
  混着「ATP 合酶合成机制」这种生物课视频。有个别中英双字的搬运
  （如 `@Determination207` 的华盛顿站赛前采访），但不成体系、授权不明

**而且对英语学习来说方向本身就是反的**：国内平台会叠中文解说、要会员、
按整场比赛而不是按采访切片组织。想要的那段英文原声，
在上面表格的英文源里是免费、成条、带自动字幕的。

### 小赛事没有自己的频道，但 Tennis Channel 收了致辞

这是覆盖"所有巡回赛赛事"的关键。ATP / WTA 各有六十来站，**250 级别的赛事大多
没有自己的 YouTube 频道**——一开始按"一个赛事一个频道"去建注册表是走不通的。

实扫 [Tennis Channel YouTube](https://www.youtube.com/@tennischannel/videos) 近 250 条，
命中 16 项赛事，命名统一：

```
球员 Championship Speech | 年份 赛事      # 冠军
球员 Finalist Speech | 年份 赛事          # 亚军也有
```

覆盖到的小站：Kitzbuhel、Gstaad、Bastad、Prague、Athens、Bad Homburg、
Strasbourg、Eastbourne、Halle、Berlin、Hamburg——**这些只有这里能拿到**。
大满贯和大师赛它也发，所以它是主源，赛事自己的频道是补充。

注意它的**网站**（tennischannel.com）发布会是订阅内容，$11.99/月；
**YouTube 频道上的致辞是免费的**，两回事。

### 各家叫法不一样，零命中先怀疑自己的正则

按 `on-court interview` / `speech` 去扫，印第安维尔斯、马德里、上海都是 0 命中。
深扫到 500 条仍是 0——**但这不是"它们没有"，是它们不这么叫**：

| 赛事 | 实际用的叫法 |
| --- | --- |
| 上海 | `Valentin Vacherot Reacts After Becoming The Shanghai Champion` |
| 马德里 | 西语 `Entrevista con Jannik Sinner, campeón del #MMOPEN 2026` |
| 印第安维尔斯 | 只有 `Champion's Press Conference` —— 这家**确实**只发发布会 |

麻烦在于 `Reacts After` 这类叫法**分不出是在场上还是在媒体间**：上海那条
11 分 07 秒的多半是发布会，1 分 48 秒的 `Holger Rune Reacts To Victory Over Baez`
才像场上。所以采集脚本把它们单列成**待定**档，人工看一眼再归类，
不混进"确定"里（见下一节）。

### 四大满贯：颁奖礼是完整长视频

| 赛事 | 场上采访 | 颁奖礼 / 致辞 | 备注 |
| --- | --- | --- | --- |
| 温网 | [与发布会同一播放列表](https://www.youtube.com/playlist?list=PLwx9gNibGUz54qMsOgwA-aI_zsEGnCVS7)（标题写 `Post-Match Interview`，约 3:54） | 颁奖礼、阳台展示杯、**Champion's Dinner Speech**（3–4 分钟，正式讲稿） | **全英文**，最适合学习 |
| 美网 | 频道有 `On-Court Interview` | [完整颁奖礼](https://www.youtube.com/watch?v=HyKTXynnI9c)（Alcaraz 2025） | **全英文** |
| 澳网 | `球员 On-Court Interview \| Australian Open 2026 Final` | `FULL ... Trophy Ceremony & Speeches` | **全英文**，主持人常是 Jim Courier |
| 法网 | 有 | `Men's/Women's singles final post-match ceremony`，**18–23 分钟完整版** | 法英混说 |

温网独有的 **Champion's Dinner Speech** 值得单独点名：是冠军在晚宴上的正式致辞，
有讲稿、语速慢、句子完整（如 `"Mum left a couple of times!" | Jannik Sinner
Champion's Dinner Speech | Wimbledon 2026`，4:02）。**这是全部素材里最接近"标准英语
演讲"的一类。**

> 需要说明：**推荐它是基于体裁判断，不是基于字幕实测**——查它字幕正文时
> YouTube 已经开始 429 限流，没读到。已知的是温网频道的视频都只有自动字幕
> （`--list-subs` 实测），且温网全程英文，没有罗马那种转本地语的问题。
> 但"字幕干净到能直接当教材"这句，对这一条我没验证过。

> 踩点记录：我第一次扫澳网频道近 100 条，`on-court` 零命中，差点写成"澳网没有"。
> 实际是频道当时在发休赛期内容，1 月的采访早被挤出前 100 条。深度调到 400 之后
> 一次扫出 27 条，含 32 分 57 秒的男单完整颁奖礼。**零命中先看自己的取样窗口。**

### 这条线已经做成自动采集了

不用每次手搓。注册表 + 脚本 + 每周定时：

| 文件 | 作用 |
| --- | --- |
| `data/oncourt_sources.json` | 27 个源的注册表，逐源可配扫描深度、网球闸与说明 |
| `tools/collect_oncourt_interviews.py` | 扫描、按类型分类、增量并库 |
| `.github/workflows/oncourt-interviews.yml` | 每天两轮：北京 05:00 与 11:00 |
| `data/oncourt_interviews.json` | 累积产物，当前 4241 条 |
| `tools/verify_oncourt_sample.py` | 抽样看图验证「是不是真在场上」＋探可达性 |
| `data/oncourt_verify.json` | 看图判定的结果，逐条记 oncourt / press / other / unknown |

**默认只收"赛后直接在场上接受采访"这一类。** 按类型分三档：

| 类型 | 是什么 | 默认 |
| --- | --- | --- |
| `oncourt` | 主持人拿麦上场问、球员站着答，40 秒–4 分钟 | ✅ 收 |
| `ceremony` | 颁奖礼致辞、冠军演讲、晚宴致辞——也在场上，但是"讲"不是"接受采访" | ❌ `--include-ceremony` |
| `maybe` | 各赛事自己的叫法，既分不出场上/媒体间，也分不出采访/致辞 | ❌ `--include-maybe` |

```bash
python tools/collect_oncourt_interviews.py --dry-run              # 看看有什么，不落库
python tools/collect_oncourt_interviews.py --only "Tennis Channel" # 只扫某个源
python tools/collect_oncourt_interviews.py --include-ceremony      # 连致辞一起收
```

**被跳过的会按类型汇总打印**——不列的话，"这周只有 3 条"看着像没比赛，
其实是二十条致辞被默默筛掉了。

有个顺序陷阱：`post-match ceremony`（法网 18–23 分钟的完整颁奖礼）和
`post-match interview`（温网场上那 3 分钟）只差一个词，**必须先判 ceremony
再判 oncourt**，否则颁奖礼会被当成场上采访收进来。测试里钉住了。

脚本把三种"看起来一样"的空结果**分开报**，这是踩出来的：

- `handle-error`（一条都没取到）＝频道句柄写错了，**不是频道没内容**
- `ok` 但命中 0 ＝这批里确实没有，正常
- `rate-limited` ＝ 429，跟"没有"毫无关系，退避重试

**跑在 Actions 不跑本地**：沙箱下 YouTube 对连续请求返 429，退避到 240 秒都拿不到；
Actions 的出口没这个问题。

### 标题正则分不出发布会，只有画面能分——两次写正则两次都错

**这是这条线上最贵的一个教训，而且我在同一个坑里栽了两次。**

库涨到两千多条时，把握全建立在标题正则和时长代理上，只亲眼看过四张缩略图。
一验就抓出系统性混入：法网和巴黎大师赛（同属法网协会 FFT）把**新闻发布会**
也写成 `post-match interview`，跟真正的场上采访一个词。

两次想从标题里找规律，两次都错：

| 版本 | 规律 | 结果 |
| --- | --- | --- |
| 第一版 | 法网 2024 的 post-match 一律是发布会 | 61 条里**错杀 4 条** |
| 第二版 | 巴黎标题不写 on-court 的一律剔 | 25 条里**错杀 7 条** |

第二版的反例最要命——巴黎有三条标题**一字不差**：

```
IOLtTF-PzZ8  Jannik Sinner post-match interview | Rolex Paris Masters  → 在场上
bWTTWu_uA_I  Jannik Sinner post-match interview | Rolex Paris Masters  → 在场上
p8z5dEVgXck  Jannik Sinner post-match interview | Rolex Paris Masters  → 媒体背景板前
```

所以现在**一条正则都不留**，法网 160 条、巴黎 31 条全部逐条看过画面，
结论按 id 记进 `data/oncourt_sources.json` 的 `deny_ids`（共 136 条），
逐条证据记在 `data/oncourt_verify.json`，测试查两者一一对应、且库存与之一致。

### 怎么"看画面"：用视频自动帧，别看封面

封面是上传者自己传的，可以是任何东西。Eurosport、TNT Sports、温网、Nine
的封面全是纯文字引语卡，画面信息为零——第一轮 14 条判不出来的，11 条栽在这。

**YouTube 除了封面，还会自己在 25% / 50% / 75% 处各截一帧**，存成
`hq1.jpg` / `hq2.jpg` / `hq3.jpg`。那是视频里的真实画面，上传者改不了：

```bash
python tools/verify_oncourt_sample.py --per-source 4 --sheets      # 按来源抽样看封面
python tools/verify_oncourt_sample.py --recheck-unknown            # 封面看不出来的调自动帧
python tools/verify_oncourt_sample.py --per-source 2 --reach       # 逐条探可达性
python tools/verify_oncourt_sample.py --report                     # 汇总每源置信度
```

判据是画面本身：

| 看到什么 | 判定 |
| --- | --- |
| 球场地面、场边广告牌、身后看台、手持话筒 | 场上 |
| BNP Paribas 背景板 + 长桌 + 绿瓶矿泉水 | 新闻发布厅 |
| ATP Masters 1000 背景板、一圈手机怼着 | 媒体混合区 |

**三帧要一起看**，别挑一帧：发布会片头常先切一段比赛集锦，只看第一帧会判成
场上；场上采访结尾常摇到看台，只看最后一帧判不出人。

那 14 条判不出来的，全部调自动帧验完——**14/14 都在场上**。
引语卡挡住的是我，不是内容有问题。举几个自己证明自己的：

- Osaka 那条画面里带着字幕条 `NAOMI OSAKA JPN DEFEATED C. GARCIA 6-3 3-6 6-3`
- Rybakina 那条带 `THROUGH TO SEMIFINALS`
- 德约那条三帧全是场上主持人，法网标话筒 + 红土 + Emirates 广告牌 + `2:51` 比赛计时

还有一条反向教训：**小图会看错**。Nine 那条 Zverev 在联络表里像发布会，
调 `maxresdefault` 复看，看得见 AO 蓝话筒和看台，其实在场上。判不准就调大图。

累计逐条看过 **297 条**，其中 159 条确认在场上、125 条是发布会 / 媒体区、
12 条是颁奖礼致辞、1 条不是采访（场上求婚）。**法网这个源已经逐条看完**——库里剩的 56 条每一条都亲眼过过。

法网看完这一遍又推翻了一个结论。此前靠缩略图判断「2025 那批大多在场上」，
调自动帧一看**正好相反**：99 条里 49 条是发布会。**封面画的是场上的动作照，
片子里是发布厅**——又一次同样的教训。

看下来法网的两套场景在画面上其实分得很干净：

| | 场上 | 新闻发布厅 |
| --- | --- | --- |
| 背景 | 深色 BNP 背景板 / 红土 / 看台 | 白底 BNP Paribas 重复标背景板 |
| 话筒 | 红色手持 | 绿色台麦 |
| 其他 | 站着，画面常带 `ADVANCES TO…` 字幕条 | 长桌 + 绿瓶矿泉水，坐着 |

两条 2026 决赛的短片是唯一需要多想一步的：白底背景板前站着答，
67 秒和 91 秒，而同年 23 条真 on-court **全部 ≥138 秒**、标题一律写
`| … on-court Interview |`。三个信号（标题格式、时长、背景板）一致，判为媒体区。

顺带剔掉了一条中国球员的：`Zheng Quarter-final post-match interview |
Roland-Garros 2025` 是发布会。中国球员条目 14 → 13。

### 华盛顿：赛事页已经开了，但还只有赛前预告

`tennistv.com/tournaments/418_2026/washington` **7 月 27 日当天实测是活的**
（89 KB），但只挂着一条 `washington-2026-musetti-preview-interview`——赛前预告，
不是赛后采访。合理：当天才开赛，还没有比赛打完。

对照 2025 那一届的同一个页面（954 KB），逐轮都有：
`washington-2025-final-de-minaur-interview`、`washington-2025-sf-de-minaur-interview`、
`washington-2025-sf-davidovich-fokina-interview`……**所以这条路是通的，只是要等**。
按上一届的形态，本周内应该会逐轮填上。

### 一个赛事能拿到几条，是**级别决定的**，不是采集能力决定的

被问「布拉格才 4 条，一共那么多场比赛，太少了吧」。查下来 4 条不是漏了，
是 WTA 250 的行情。库里按级别一算，落差非常整齐：

| 级别 | 平均每赛事 | 明细 |
| --- | --- | --- |
| 大满贯 | **144** | 澳网 190、温网 163、美网 160、法网 62 |
| 1000 | **63** | 罗马 125、马德里 117、迈阿密 99、蒙特卡洛 60…… |
| 500 | **40** | 迪拜 131、斯图加特 29、华盛顿 19、柏林 12 |
| 250 | **4** | 雅典 6、布拉格 4、诺丁汉 2 |

布拉格 2026 逐个源查过，**英语的场上采访全网就是那 4 条**：

| 源 | 布拉格 2026 | 是什么 |
| --- | --- | --- |
| Tennis Interviews（搬运号） | 4 | 英语，转播画面。2 条采访 + 2 条颁奖礼致辞 |
| ČESKÝ TENIS（捷克网协） | 25+ | **捷克语**，蓝色赞助商背景板前的**混合区**，不在场上 |
| CANAL+ CZ&SK（实际转播方） | 0 | 场上采访是它拍的（画面上有 CANAL+ LIVE 角标），但**不往 YouTube 传** |
| WTA 官网 | ~10 | 全是 highlights / hot shots，一条采访都没有 |

结构性原因：**250 级别没有自己的赛事频道，转播方也不上传场上采访**。
大满贯和 1000 有官方频道逐轮发，落差就是这么来的。所以「后续关键场次
都能拿到」这句话，**在 250 级别上要打折**——能拿到的基本只有决赛前后那几条。

（顺带一个踩点：`@CANALCZSK` 扫出来是 0 条，看着像「这个频道没有布拉格内容」，
其实句柄写错了，正确的是 `@canalplusczsk`，120 条里有 4 条布拉格。
又一次「句柄猜错 ≠ 频道没内容」。）

### 颁奖礼致辞混在里面，判据是**话筒**

搬运号的 `Champion / Finalist` 那 18 条，逐条看下来 **12 条是颁奖礼致辞**，
只有 6 条是采访。标题上完全看不出来：

```
Lilli Tagger Champion Prague 2026    落地支架麦，捧着奖杯独自对着观众讲  → 致辞
Petra Marcinko Champion Rabat 2026   WTA TOUR 手持话筒，有人在问        → 采访
```

**判据是话筒**：落地支架麦＝独自讲＝致辞；手持话筒（WTA TOUR 或转播方标）＝
有人在问＝采访。两者都在场上，但用户要的是「接受采访」，致辞明确排除。
12 条已剔，判定记的是 `ceremony` 而不是 `press`——人在场上，
只是没在接受采访，和发布厅是两回事。

### WTA 侧：500/1000 有，但完整度全看搬运号

被问「WTA 500 和 1000 里有完整的场上采访么？至少中心球场应该有」。查下来
**有，但很不完整，而且赛事之间落差极大**。关键轮次（决赛/半决赛/八强）实测：

| 赛事 | 女子条数 | 决赛 | 半决 | 八强 |
| --- | --- | --- | --- | --- |
| 多哈 1000 | 9 | 2 | 3 | 3 |
| 迪拜 1000 | 30 | 2 | 8 | 4 |
| 马德里 1000 | 28 | 3 | 4 | 2 |
| 罗马 1000 | 19 | 1 | 3 | 4 |
| 迈阿密 1000 | 20 | 1 | 2 | 2 |
| **印第安维尔斯 1000** | 20 | 2 | **0** | **0** |
| 斯图加特 500 | 24 | 1 | 1 | 6 |
| 柏林 500 | 11 | 1 | 2 | 4 |
| 查尔斯顿 500 | 6 | 1 | 2 | 2 |
| 阿布扎比 500 | 8 | 1 | 1 | 0 |
| 林茨 500 | 7 | 1 | 0 | 1 |
| 女王杯 500 | 3 | 2 | 0 | 0 |
| **巴德洪堡 500** | 4 | **0** | **0** | **0** |

结构性原因和 250 那条是同一个：**WTA 官网没有 tennistv 那套按赛事的视频页**。
实测 `wtatennis.com/tournaments/{id}/{slug}` 打得开（26 万字节），
但**一条 `/videos/` 链接都没有**；`/videos/interviews` 全站只有 3 条，且全 404。
对比 ATP：`tennistv.com/tournaments/{id}_{year}/{slug}` 每个赛事挂 40–45 条。

所以 WTA 侧的覆盖**全靠搬运号**（`Tennis Interviews`、`Tennis x Tennis`、
`ICONIC CHANNEL TENNIS`），它们跟着热门球员走，不逐场搬——这就是为什么
罗马 8/8、印第安维尔斯只有决赛那 2 条。**这一层没法靠采集能力补，
只能靠多挂几个搬运号。**

### 结果词：搬运号写 Winner，不写 Final

查上面那张表时发现的一个**真 bug**：搬运号写
`Elena Rybakina Winner Porsche GP '26`，而轮次解析只认 `final`——
**冠军那条采访，最该推的一条，一直没被算进关键场次**。
十三个 WTA 赛事里只有一个能认出决赛。

补了三个结果词，但每个都带前缀排除，反例全是从库里逐条挑出来的：

```
Defending champion Sinner up and running in Shanghai    刚开赛，不是决赛
Former champion Evans stuns Musetti                     描述对手
Sonay Kartal beats Grand-Slam Winner                    描述对手
2022 finalist Ruud advances in Miami                    描述对手
Cerundolo conquers last year's finalist Jarry           描述对手
Bergs stuns former finalist Rublev                      描述对手
```

最要命的是 `Championship`：**迪拜赛事全名就叫 `Dubai Duty Free Tennis
Championships`**——库里 126 条含 champion 的有 116 条是它，
`\bchampions?\b` 不加 `(?!ship)` 就全成决赛了。

顺带把 `R32/R64/R128` 标成 `早轮`——签表大小不写在标题里，
换算不出第几轮（R32 在 128 签是第三轮、64 签是第二轮），所以给个诚实的粗标签。

效果：判不出轮次 468 → **339**，关键轮次 454 → **480**，推送口径 467 → **493**。
测试是**全量校验不抽样**——库里每一条含结果词的标题都过一遍，
描述对手的写法一条都不许被判成决赛。

### 补 WTA 缺口：Edimator，以及它带出来的两个轮次 bug

上一节测出 WTA 500/1000 覆盖不全之后去找搬运号，找到 **Edimator**：
321 条里 155 条是 `Player interview after Nth round win at YYYY Event`
这种固定写法，轮次 / 赛事 / 年份全在标题里。抽 12 条调视频自动帧，
**12/12 都在场上**（草地、看台、温网紫麦 / HSBC / WTA Tour 手持麦，
有几条画面里还带 `Beat Nao Hibino 2-6 7-6 6-2` 这种字幕条自证）。

**不能开 `assume_oncourt`**：另外 157 条是致辞、好球集锦、西语采访，
还混着**一条田径和一条足球**。所以给全局加了第三条标题模式
`\binterview\s*(?:\([^)]*\)\s*)?after\b`——拿库里 2025 条全量试过，
额外命中 0 条、不扰动现有分类，四条真实发布会标题也都不中。

放宽入口就得在出口补门闩，于是 `exclude` 加了 `press conference` 和
`\bpress\b(?!ure)`。搬运号用 `Press` 当发布会标记——
`Alex Eala Press R32 Win vs Linette Miami '26` 画面是迈阿密背景板加台麦，
库里这样的 3 条已剔。`(?!ure)` 不能省，库里有 `Staying Calm Under Pressure`。

收进来 159 条，同时**炸出两个一直存在的轮次 bug**：

| bug | 症状 | 影响 |
| --- | --- | --- |
| `final round qualifying` 里有 final | 温网**资格赛末轮**被判成温网**决赛** | 9 条 |
| 只认 `second round`，不认 `2nd round` | 序数写法整个认不出 | 84 条里漏 69 条 |

资格赛现在排在 `_ROUNDS` **最前面**先拦下来，单列 `资格赛` 标签（不进关键轮次）；
序数 `1st/2nd/3rd/4th` 一并补上。

效果（女子，关键轮次）：

| 赛事 | 加之前 | 加之后 |
| --- | --- | --- |
| 女王杯 500 | 3 条 / 决 2 半 0 八 0 | **8 条 / 决 2 半 1 八 3** |
| 加拿大 1000 | 统计里没有 | **11 条 / 决 0 半 2 八 2** |
| 伊斯特本 500 | 1 条 / 全 0 | 2 条 / 半 1 |

Edimator 偏草地赛季和加拿大站，**印第安维尔斯和巴德洪堡的缺口它补不上**——
那两个还得再找源。

### 扩大搜索：十个候选里只有两个能用，其余的问题各不相同

十组查询词批量搜、按频道出现频次排、滤掉已登记的，得到 13 个候选。
逐个看画面之后**只收了 2 个**。不能用的都记在注册表的 `_rejected_note` 里，
免得下次重查——**「查过了不合格」和「没查过」在注册表上长得一模一样**：

| 频道 | 为什么不收 |
| --- | --- |
| ANTI GOSU EATING CLUB | 片子本身是真场上采访（WTA Tour 话筒、球场），但 41 条里 16 条是「Sweating moment」「SWEATY at Ningbo」这类女子球员出汗合集，连采访都 retitle 成 `McCartney "Sweaty" Kessler`。**推送会把人导到那个频道，不收** |
| QualityShot Tennis | 不是场上画面——庆祝定格照配音，中间插球机广告 |
| Karendoms Tandem | 画中画叠加加字幕条，单球员粉丝号，发布会与场上混着 |
| Sportiva Arena | 二次上传，加装饰边框和 `@sportivaArena` 水印，画面被缩进边框里 |
| The Tennis Tribe | 25–30 分钟的播客式长访谈，不是场上 |
| LTA | 主要是发布会（14 条），场上的只有 3 条温网双打 |

**Dribble Drive Diaries** 收了：以 Alex Eala 为主，满画幅原始转播画面，
没有画中画和水印。抽 6 条看帧，4 条在场上、2 条是发布会——但它**自己在标题里
写 `Press Conference`**，被上一节新加的 exclude 直接挡住，不用额外规则。
补的是印第安维尔斯和迈阿密。

**顺带的收获：中国球员条目 13 → 17。** Edimator 标题里直接带中文名
（`Yunchaokete Bu 布云朝克特`、`Xiyu Wang 王曦雨`、`Zhang Shuai 张帅`、
`Zhizhen Zhang 张之臻`），这四条是别处一条都没有的。

### 「250 级别没有自己的赛事频道」是错的——是我没逐个探

这条结论写进文档之后，**赛果反查一轮就把它推翻了**：拿巴斯塔德那几场没采访的
比赛去搜，撞见 `Nordea Open` 官方频道，27 条 `Player - Round - Winner interview`，
72–138 秒，抽 8 条看帧全在红土场上，字幕条写着 `DEFEATED S. OFNER 6-4 6-4` 自证。

所以把 60+ 个 250/500 赛事逐个探了一遍官方频道。结果是**有，但极不均匀**：

| 有量 | 没量 |
| --- | --- |
| Nordea Open 27、安特卫普 5、德尔雷比奇 2 | Croatia Open Umag（6 条全是阿加西/费雷罗这类传奇专访）、阿拉木图（4 条都是比莉·简·金杯）、成都（只有 2017 年 3 条）、斯德哥尔摩（瑞典语为主）、Palermo（2 条采访的是赛事副主席） |

**教训不是「250 有频道」，是「没逐个探就别下结论」**——这和「空结果先自证是真空」
是同一条，只不过这次的空结果是我自己没去查。

### assume_oncourt 会灌爆，allow_by_source 才是对的

给 Nordea 打 `assume_oncourt` 的后果：**300 条全进来了**，其中大半是 16–35 秒的
`Hot shot` 好球集锦和赛前预告，多收 273 条。

问题在于官方赛事频道的标题**极简**——`Filip Misolic Interview - Nordea Open 2025`，
只有一个光秃秃的 `interview`，全局模式够不着；但把 `\binterview\b` 加进全局，
发布会、播客、专访会一起灌进来。

所以加了第三种机制 `allow_by_source`：**这个源上**标题长这样就算场上采访。
不豁免 `exclude` 和 `deny_ids`，两道出口闸照旧。三者的分工：

| 机制 | 用在什么源 |
| --- | --- |
| 全局 `patterns_oncourt` | 标题写 on-court / post-match / interview after 的 |
| `allow_by_source` | 标题极简的官方赛事频道，逐源验过才加 |
| `assume_oncourt` | 整个频道**只发**场上采访的（`Tennis Interviews`） |

顺带修一个刚引入的 bug：`winner interview` 是**体裁标签**不是轮次。
巴斯塔德写 `Andrea Pellegrino winner interview at Nordea Open 2026`（赢家采访），
搬运号写 `Elena Rybakina Winner Porsche GP '26`（冠军）——**同一个词，
隔一个 interview 就换了意思**，后视否定分开。

### 画面有瑕疵但内容对题的，收下并标 degraded

判据松了一档，起因是一句话：「虽然需要完整的 on court interview，
但后续可以裁剪高光的时刻」。既然要裁，**水印 / 画中画 / 边框就不再是否决理由**，
只有「根本不是场上采访」和「频道性质有问题」才是。

所以上一轮因画面拒掉的两个改收了，并在注册表里标 `degraded`——
裁之前人得知道这条素材是什么成色：

| 源 | degraded |
| --- | --- |
| Karendoms Tandem | `picture-in-picture`，加了画中画小窗和字幕条 |
| Sportiva Arena | `border+watermark`，画面被缩进装饰边框，带 @sportivaArena 水印 |

**但 ANTI GOSU EATING CLUB 仍然不收**，而且理由不受这次放宽影响：它的片子确实是
真场上采访（还正好能补巴德洪堡和郑钦文的缺口），但 41 条里 16 条是
「Sweating moment」「SWEATY at Ningbo」这类女子球员出汗合集，连采访都 retitle 成
`McCartney "Sweaty" Kessler`。**那是频道性质问题，不是画面瑕疵问题**——
推送会把人导到那个频道去。

### 按赛历逐站对账——之前的覆盖率统计，分母是错的

一直用手搓的赛事清单统计覆盖率。问题是**漏掉的赛事在报表上根本不出现**，
看着一片绿，其实半张日历没查过。把完整赛历落成 `data/tour_calendar_2026.json`
（106 站，含 ATP/WTA 各级别与团体年终），再用 `tools/oncourt_coverage.py` 对账，
缺口才看得见。

对账要过三关，每一关都是踩出来的：

| 关 | 不做会怎样 |
| --- | --- |
| **标题 + URL 一起匹配** | tennistv 的 42 条辛辛那提标题里一个 `Cincinnati` 都没有，赛事名只在 `/tournaments/422_2025/cincinnati` |
| **正则容忍连字符下划线** | `indian wells`（空格）匹配不上 slug 里的 `indian-wells`，一次漏 85 条（印第安维尔斯 60 + 巴黎 25） |
| **按源归属（`srcs`）** | 汉堡官方频道写 `HEO2021 /// ATP QF ///`、迪拜写 `Post-Match Interview: Roger Federer`——标题里一个赛事名都没有，但**频道本身就说明了赛事** |

三关做完，归不到赛事的条目从 423 → **237**（占库 11%），
其中 118 条霍普曼杯是 2026 日历上本来就没有的赛事（已被联合杯取代），
78 条 Eurosport / TNT 是标题里真的没有赛事名的转播条目——**都是可解释的残余**。

**孤儿报表还能反推赛历的缺口**：埃斯托里尔、基茨比厄尔、乌马格、安特卫普
四站是这么撞出来的——库里有条目却归不到任何赛事，说明赛历漏了它们。

### tennistv 的赛事页要用 ATP 官方赛事 ID——之前漏了全部 ATP 500

注册表里 tennistv 长期只挂着九个大师赛加华盛顿，**一个 ATP 500 都没有**，
于是鹿特丹、哈雷、女王杯、东京、巴塞尔、维也纳、慕尼黑、巴塞罗那、达拉斯
这一整层在报表上全是 0%。**缺的不是内容，是我不知道 URL 怎么拼。**

赛事页的 ID 就是 **ATP 官方赛事 ID**（atptour.com 的 `/tournaments/<slug>/<id>/`
里那个数字），而且 **slug 写什么都行，服务端只认 ID**（`414_2025/x` 照样返回汉堡）。
站上没有索引页（JS 渲染），所以是逐个探出来的。判据很干净：

| | 页面大小 | videoId 数 |
| --- | ---: | ---: |
| 无效 ID | ~69 KB | 0 |
| 有效 ID | 800 KB+ | 130 |

探 300–570 与 700–760 共 340 个 ID，43 个有内容、其中 **24 个有采访**，
一次补进 34 个赛事页，**新增 378 条**。

探到有页面但**确实没有采访**的（别再重探）：奥克兰、格斯塔德、巴斯塔德、
基茨比厄尔、斯图加特、香港、布里斯班、梅斯、马拉喀什、蒙彼利埃、斯德哥尔摩、
乌马格、斯海尔托亨博斯、马赛、德尔雷比奇、布宜诺斯艾利斯、休斯顿。

### 「80% 不可达」我说错了两次，两次都是**扫得不够深**

被要求「500 及以上覆盖度 80%」时，我先后两次断言做不到。两次都错，
而且错法一样：**把「库里没有」当成了「官方没发」**。

判据一直摆在那儿——**扫到的条数等于 `--playlist-end` 就说明还有**。
大满贯频道在 1800、4500、6000 三次触底，我却只在文档里记了一句
「历史还有，但只影响语料完整度」就放过了。把 scan_depth 提到 14000 重扫：

| | 1800 时 | 14000 时（只算单打） |
| --- | ---: | ---: |
| 澳网男单 | 64% | **100%** |
| 澳网女单 | 61% | **99%** |
| 美网男单 | 63% | **84%** |
| 美网女单 | 63% | **85%** |
| 温网男单 | 50% | 58% |
| 温网女单 | 45% | 54% |

**「只算单打」这四个字是被抓出来的。** 覆盖率工具一开始没滤双打，
澳网深扫新增的 835 条里有 **213 条是双打**（`Kostyuk/Ruse On-Court Interview`
这种斜杠配对），美网也有 55 条。分母是单打签表、分子混着双打，
报出来的美网「91%」实际是 84%。轮椅、青少年、传奇表演赛同理。
现在 `is_main_singles()` 统一滤，测试钉住。

库存 2230 → **4241**。**澳网和美网都过了 80%。**

### 挖到底的判据：扫到的数 < 上限

同样一轮深扫，四个大满贯频道的结局完全不同，而**判据只有一个**——
返回条数有没有顶到 `--playlist-end`：

| 频道 | 上限 14000 时扫到 | 到底了吗 | 新增 | 覆盖率上限 |
| --- | ---: | --- | ---: | --- |
| 澳网 | **14000** | **没有，还有** | +835 | 已 100% |
| 美网 | 9363 | 到底了 | +10 | 91% |
| 温网 | 6340 | 到底了 | **0** | **58% / 54%** |
| 法网 | 4428 | 到底了 | 0 | **31% / 7%** |

所以：**温网和法网的官方频道已经挖尽**，58%/54% 和 31%/7% 就是它们的
发布量上限，不是我的采集问题。同样是大满贯，温网第一轮只发 23/64，
澳网发 69/64（多届累计）——**官方发布密度差三倍**。

法网女单 7% 尤其极端：法网频道把发布会和场上采访混着发，
逐条看图剔掉 105 条发布会之后，女单只剩 9 场。**法网基本不发女单场上采访。**

要把温网和法网推到 80%，只剩一条路：**找把外场转播信号搬出来的第三方**。
但那类源极稀少——搜了三轮，能用的只有 Edimator 一个，
**而它那 99 条温网里 75 条是资格赛，不在正赛口径内**（详见下面两节）。

（这里原本写的是「现场拍外场的第三方」，而且拿 99 这个数当过论据。
**两处都说错了，下面两节各纠正一处。**）

### 覆盖率的天花板是**赛事方做不做采访**，不是采集能力

被要求「500 及以上覆盖度 80%」。实测下来这个目标**只在大满贯这一档可达**，
往下是硬天花板。证据是逐轮分布：

**ATP 1000**（马德里 2026 / 印第安维尔斯 2026，96 签 95 场）：

| 轮次 | 该轮场次 | 马德里 | 印第安维尔斯 |
| --- | ---: | ---: | ---: |
| 半决赛 | 2 | 2/2 | 2/2 |
| 八强 | 4 | 4/4 | 4/4 |
| 十六强 | 8 | 7/8 | 8/8 |
| 第三轮 | 16 | 10/16 | 8/16 |
| 第二轮 | 32 | 11/32 | 10/32 |
| **第一轮** | **32** | **2/32** | **1/32** |

**ATP 500** 更极端：有覆盖的 15 站里，15 站都有决赛/半决/八强，
**十六强只有 1 站、第二轮只有 1 站、第一轮 0 站**。
32 签的 500 一共 31 场，官方只发八强起的 7 场——**天花板就是 23%**。

tennistv 是 ATP 自己的出口。**它没有的，多半是没做，不是没发。**
所以各级别的天花板大致是：

| 级别 | 实测最好 | 天花板 | 80% 可达？ |
| --- | --- | --- | --- |
| 大满贯 | 美网 / 澳网 **91%** | 90%+ | **可达**，温网 69%、法网 33% 是真缺口 |
| ATP 1000 | 罗马 53% | ~55% | 不可达（一轮 3–6%） |
| ATP 500 | 迪拜 35% | ~23% | 不可达（官方只发八强起） |
| WTA 1000/500 | 迪拜 45% / 斯图加特 42% | 更低 | 不可达 |

要在 1000/500 往上走，只有一条路：**找把外场转播信号搬出来的第三方**（Edimator 那一类）。
但那类源极稀少——搜了两轮，能用的只有 Edimator 一个。

### 持权转播商：思路对，但他们上传集锦不上传采访

「找官方授权直播商，他们直播时有赛后场上采访」——这条思路对，直播信号里确实有。
但落到 YouTube 上，两轮实测都说不行。

**先说这一轮学到的正确入口：播放列表，不是频道。** 综合体育频道的 `/videos`
会被本地热门项目淹掉——Stan Sport 798 条里网球被 AFL/NRL 埋着，
它的 `Wimbledon on Stan Sport` 播放列表只有 88 条，一眼就见。

| 轮次 | 做法 | 结果 |
| --- | --- | --- |
| ① | 14 家转播商频道 `/videos` 深扫，约 16000 条 | 网球场上采访 **5 条** |
| ② | 改用播放列表：ESPN 18 个、SuperSport 4、TSN 2、Sky 4 | 含 interview **31 条**，绝大多数不是场上采访 |

那 31 条里：ESPN 是演播室长访谈（532 秒 Alcaraz、1015 秒 Djokovic + McEnroe），
甚至有一条 23 秒是「**德约拒绝接受场上采访**」；Sky 那两条 600–871 秒是颁奖礼全程；
SuperSport 命中的是标题里带 interview 的 highlights。

**最硬的一条对照**：ESPN 的 `2026 Wimbledon`（197 条）、`2025 Wimbledon`（241 条）、
`2026 Australian Open`（125 条）三个列表，**含 interview 的是 0**——
那正是温网早轮缺口该在的地方。

唯一收下的是 Stan Sport 温网列表那 4 条（`Wimbledon First/Second Round Interview`），
而它的**法网列表 247 条里 0 条采访**。同一家转播商、两个大满贯，一个 4 条一个 0 条
——说明这不是政策，是随手。

顺带补出第四条标题模式「轮次 + Interview」：Stan Sport 写
`Wimbledon First Round Interview 🎙️`，前三条模式一条都不认，88 条取到 0 条。

### scan_depth 骗了我：14 个源没扫到底，合计漏 350 条

「多找一些信息源检索」——找了一轮，最大的收获**不是新源，是旧源没扫完**。

线索来自 WTA 官方频道。注册的是 `scan_depth=800`，看着不小；全量扫下来
**13791 条**，而分类器判为场上采访的 86 条**全部排在第 800 名之后**——
按注册深度一条都拿不到。而报表上它只显示「这个源贡献 0 条」。

**不够深的时候采集器不报错，它只是没走到那里。** 这是「空结果 ≠ 不存在」里
最隐蔽的一种：没有异常、没有告警，数字看着就是真的。判据只有一条硬的——
`--playlist-end N` 返回的条数**正好等于 N**，就说明后面还有。
写成了 `tools/check_scan_depth.py`，顺着查完所有 YouTube 源：

| 源 | 注册 | 实测 | 深度外漏掉 |
| --- | ---: | ---: | ---: |
| Tennis TV | 800 | >3000 | 大量 |
| 印第安维尔斯 | 500 | 2148 | |
| Tennis Channel | 250 | >3000 | |
| 联合杯 | 800 | 1622 | |
| TNT Sports | 1200 | 2316 | 1 |
| FFT | 400 | 2547 | 1 |
| 迪拜 | 800 | 1059 | 2 |
| 辛辛那提 | 500 | 960 | 2 |
| 巴斯塔德 | 300 | 1090 | 1 |
| …另有 5 个 | | | |

**14 个源不够深，合计漏 350 条场上采访。**

**Tennis Channel 那条最要命。** 我在这份文档里写过「它不发场上采访，只发颁奖礼致辞——
深扫 700 条，on-court / post-match interview 一条都没有」。那个结论是在
**只扫了不到四分之一**的前提下得出的，**不作数**。同理，测试里那句
「Tennis TV 的 YouTube 频道深扫 800 条是 0 条场上采访」也已经划掉。

现在每个源都记了 `measured`（实测条数），配一条测试：**注册深度不许低于实测条数**。
故意留浅的必须写 `depth_exempt` 说明理由——**「查过了那里没有」和「没查」
在报表上长得一模一样，只有那段字能分开。**

### 新源只找到一个：迈阿密赛事官方频道

同一轮按查询词扫搜索、按播放列表扫官方频道、按搜索反推赛事频道句柄，
真正能收的只有 **Miami Open**（382 条，37 条命中，**逐条看帧：14 条在场上，
23 条在赞助商背景板前**）。迈阿密 WTA 那侧因此从 6% 到 9%。

判据不在标题里——`on-court` 有的写有的不写：普伊格两条只写 `Post-Match Interview`
却在场上，伊斯内尔写了 `Post-match` 却在背景板前。所以那 23 条只能按 id 拉黑。
**`TENNISTV` 台标也不代表场上**：TennisTV 同样拍媒体区，同一个台标下两种画面都有。

拒掉的（详见 `_rejected_note`）：

- **WTA 官方频道深处那 86 条**——逐批看帧，「2020 Rome Post-Match Interview」28 条是
  **发布会**（长桌、BNL 背景板、台式麦），「2016 WTA Finals Singapore」和 2016 亚洲赛季
  是**演播室专访**（黑底、赛事 logo 角标、领夹麦）。真在场上的只有 2–3 条。
  **这一条最值得记：源不是没有，是那个源发的不是这个东西。**
- **WTA 官方频道的逐赛事播放列表**（2026 印第安维尔斯 97 条、2025 辛辛那提 52 条、
  2025 武汉 38 条）——装的是集锦、全场重播和**发布会**，场上采访 0 条。
  这解释了 WTA 1000 覆盖只有 1–13% 的结构性原因：**WTA 自己不发这个东西。**
- **C Squad 1 / The Cabanting Squad**——两个斯瓦泰克粉丝号，各 37 条，是这一轮体量最大的，
  但画面和已拒的 Karendoms Tandem 一模一样：烧录标题卡、竖屏放大后补镜像侧栏、贴订阅按钮。
- Tennis Canada（2353 条 → 1 条可用）、Cincinnati Open（960 条 → 0 条，一条标题自己写着
  `Off-Court Interview`）、Mr.THANGLO / Good Energy / ONE FILIPINO TV（各 2–4 条，量太小）。

**赛事频道的句柄不要猜。** nationalbankopen / mutuamadridopen / cincinnatiopen /
wuhanopentennis / chinaopentennis / ningbowtaopen 六个我猜的句柄全部不存在，
而用搜索反推，Cincinnati Open 的频道**是存在的**。猜错 ≠ 不存在——这条在前面
第二节末尾已经栽过一次，这次又栽了一次。

### 覆盖率被「认不出性别」虚高了——WTA 1000 是被男子条目撑起来的

回头再查 1000 和 500，先怀疑那两个最好看的数：**澳网男单 100%、女单 99%**。
一查就塌了。

场次覆盖率是按签表分男女两侧算的，而分侧靠 `side()` 认球员。老规则是
「**认不出性别的两边都算**」——理由是「宁可多算也别把真条目丢在报表外面」。
那句话在 `oncourt_coverage.py` 里成立（它报的是「有没有覆盖」），
**在算百分比的地方是灾难**：澳网男单进入统计的 847 条里 365 条认不出性别，
女单 799 条里也是 365 条——**同一批**，把两个 127 的分母同时填了。

老的 `side()` 是两串手搓正则，249 个词，认出率 78%。改成读仓库里现成的
**ATP / WTA 各 500 人官方排名快照**（`src/tennislive/zh/player_names_top500.json`）
之后认出率 88%，剩下认不出的一律不算进任何一侧。

快照的两个性质是量出来的，不是假设：**全名零重叠**（1000 人里没有一个同名，
所以全名命中即可定案）、**姓氏有 10 个两边都有**（Zhang / Zheng / Sun / Smith /
Jones / Alves / Krueger / Pieri / Shimizu / Brancaccio，共用姓一律不作数）。

顺手炸出手搓正则的一个老 bug：**它没有词边界**。

| 词 | 本意 | 实际匹上了 |
| --- | --- | --- |
| `Paul` | 汤米·保罗（男） | `against **Paul**a Badosa` |
| `Lys` | 伊娃·利斯（女） | `Quentin Ha**lys**` |
| `Jovic` | 伊娃·约维奇（女） | `Dusan La**jovic**` |
| `Cristian` | 雅克琳·克里斯蒂安（女） | `Cristian Garín` |

还有一类词边界救不了：`Day` 是凯拉·戴的姓，**在快照里也是 WTA 独占姓**，
匹上了 `Sinner: 'Today was a very difficult day in the office'` ——
于是这条被判成「男女都命中」，算不出性别。判据是大小写：**人名在标题里
一定不是全小写的**。不用「首字母大写」而用「不全小写」，因为标题常常整句大写
（`WORLD NO.1 IGA SWIATEK ON COURT INTERVIEW`）。

修正前后（同一个库，只换了认人的方式）：

| 赛事 | 改前 | 改后 | 差 |
| --- | ---: | ---: | ---: |
| 澳网男单 | 100% | **91%** | −9 |
| 澳网女单 | 99% | **89%** | −10 |
| 美网男单 | 84% | **71%** | −13 |
| 美网女单 | 85% | **77%** | −8 |
| 温网男单 | 61% | **57%** | −4 |
| 温网女单 | 54% | **48%** | −6 |
| 罗马 / 马德里 / 迈阿密 / 印第安维尔斯（ATP 1000） | 45–53% | **45–52%** | 0 ～ −3 |
| **辛辛那提（WTA 1000）** | 8% | **1%** | **−7** |
| **加拿大（WTA 1000）** | 18% | **8%** | **−10** |
| **马德里（WTA 1000）** | 16% | **8%** | **−8** |
| **罗马（WTA 1000）** | 16% | **9%** | **−7** |
| **迈阿密（WTA 1000）** | 13% | **6%** | **−7** |
| **印第安维尔斯（WTA 1000）** | 12% | **7%** | **−5** |
| 华盛顿（WTA 500） | 4% | **0%** | −4 |

**规律很清楚：ATP 1000 几乎没动，WTA 1000 全部腰斩。** 原因是这些赛事男女同城同名
（`pat` 是同一个 `cincinnati`），而条目绝大多数来自 tennistv 这类 ATP 出口——
认不出性别时，男子条目就流进了 WTA 那一侧。

辛辛那提是最干净的例证：WTA 那一侧原本 40 条，逐条看下来**只有 1 条是女子**
（斯瓦泰克半决赛），另外 35 条全是男子（Fonseca、Opelka、Rune、Tsitsipas、
Sinner、Tien…），4 条判不出。8% 是这么来的，真值是 1%。

**所以「WTA 侧结构性偏弱」这个结论不但没变，还比原来严重得多。**
WTA 1000 的真实覆盖是 1–13%，不是原来报的 8–18%。

### 「Edimator 贡献了 99 条温网」——其中 75 条是资格赛

被问了一句「这是温网资格赛的吧」。是。而且比抽样看到的更极端：

| Edimator 温网 99 条 | 条数 |
| --- | ---: |
| **资格赛** | **75** |
| 第一轮 | 9 |
| 第二轮 | 9 |
| 第三轮 | 4 |
| 十六强 | 2 |

**76% 是资格赛。** 我在上一节拿「99 条」当过「第三方能补温网早轮」的论据，
那个数虚了三倍——真正落在正赛口径里的是 **24 条**。

**好消息是覆盖率没被污染。** `oncourt_match_coverage.py` 里分子的判据是
`if rd in tbl`，而 `rounds_of()` 生成的轮次表只到「第一轮」，`资格赛` 不在表里，
所以一条都没混进去。分母（127 场）本来就是正赛签表。这一条现在有测试盯着
（`test_qualifying_never_counts_toward_main_draw_coverage`）——**因为它看着像个疏漏**：
`parse_round` 明明会返回「资格赛」，很容易有人觉得轮次表里漏了一项就顺手补上。

那 24 条的密度反而不错，边际贡献实测：

| | 含 Edimator | 去掉 Edimator | 边际 |
| --- | ---: | ---: | ---: |
| 温网男单 | 78/127 **61%** | 65/127 51% | **+13** |
| 温网女单 | 68/127 **54%** | 59/127 46% | **+9** |

24 条里 22 条是别处没有的。**结论不变但论据要换**：第三方确实能补温网早轮，
只是能补的量是 24 不是 99。

**但推送那头漏了。** 资格赛不是关键轮次，进推送口径只有一条路——中国球员赢了球，
实际漏进去三条（布云朝克特、王曦雨 2026 温网资格赛一轮，张帅二轮）。
问题不在于它们进来了，在于**卡片标签写的是「中国球员就只显示名字」**，
推出去只有一个「张帅」，和正赛长得一模一样。**推的时候当正赛、算的时候不算数，
两边对不上。** 现在由 `tag_of()` 统一加后缀：`张帅 · 资格赛`。

只给资格赛加、正赛轮次不加，这个不对称是故意的：正赛轮次每条都跟在名字后面就成了噪音，
而资格赛不写就是误导。

### 我把「搬运号」当成了「现场拍摄者」——十一个源没有一个是自己拍的

被要求「肯定不能用现场拍摄者，肯定要用官方的直播的视频或者记录的视频，
不然清晰度和角度根本达不到要求」。按这条去删源之前先核了一遍，**发现前提是我编的**。

Edimator 那 158 条，我在这份文档里写过两次「现场拍外场的第三方」。
把自动帧拼成联络表看了十条，**每一条都带着转播信号才有的东西**：

| 条目 | 画面里的转播要素 |
| --- | --- |
| 布云朝克特 2026 温网资格赛 | 温网紫绿图形包的**下方字幕条**：`BU YUNCHAOKETE bt. H. DELLIEN 6-4 6-0` |
| 亚里 2023 上海 | 右上角 **prime 台标**——上海站的持权方 |
| 拉杜卡努 2025 加拿大 / 博尔赫斯 2025 温网 | **切到了采访者**：反打机位，看台上拍不出来 |
| 其余六条 | ATP 500 / Masters 1000 / 温网 的**官方话筒旗**，场内机位，满幅 16:9 |

按同一套判据把另外十个非官方源全看了一遍（27 条自动帧）——
**没有一个是自己拍的**，全是搬运官方转播信号。「粉丝号 = 手机拍的」
这个假设从头到尾就没成立过，我只是没查就写下来了。

走过的一段弯路值得记：我先用 `yt-dlp --print %(resolution)s` 量分辨率，
Edimator 出来 592x360 / 508x360 / 562x360，不是 16:9，看着就像被裁过；
Wimbledon 官方一律 640x360。**这个怀疑不成立**——`maxresdefault.jpg` 量出来
所有源都是 1280x720、比例 1.78，那几个怪数字是 yt-dlp 选流的产物，不是画面的。
**又是拿间接信号当结论**，直接查产物（这里就是帧本身）才靠得住。

结论落成了注册表里的 `provenance` 字段（official / broadcaster / rehost），
配一条测试：**每个源进库之前必须回答「这段画面是谁拍的」**，答不上来不能进。
判据只认画面里的转播要素，频道名字看着像不像官方不作数。

### 但确实有不合格的——判据是「画面被二次加工毁掉」，不是「非官方」

同一轮看下来三个源出局，**理由分两类，不能混为一谈**：

| 源 | 条数 | 出局理由 |
| --- | ---: | --- |
| European Open Antwerp | 5 | **不是场上**：五条 `post match interview` 全在赞助商拼贴背景板前（PSA / Emirates / ATP 250 / Port of Antwerp；2019 那两条背景板上直接印着赛事名和日期） |
| Sportiva Arena | 3 | **画面毁了**：转播画面缩成小窗，套红橙装饰边框和 ONE FILIPINO TV 横幅，`@sportivaArena` 水印铺满，可用画幅不到一半；其中一条还是柏林站颁奖礼 |
| Karendoms Tandem | 6 | **画面毁了**：竖屏放大后左右用镜像/虚化侧栏补满，加烧录字幕和角落画中画；一条（东京十六强）根本不在场上，是室内暗背景 |

**安特卫普这一条最值得记：它是官方赛事频道。** 这一轮唯一栽在「官方」两个字上的源——
官方 ≠ 场上，官方频道一样会把媒体区采访写成 post match interview。

另外单剔两条：Dribble Drive Diaries 有一条画面缩成居中小窗（同源其余 5 条是满幅的），
Edimator 有一条是**田径**（2025 世锦赛铜牌赛后 BBC 采访，撞的是 `interview after` 这个词）。

分界线划在这里，写进了注册表的 `_picture_note`：

- **台标、轻微放大裁切 → 记在源的 `picture` 字段里，照收。**
  裁高光的时候裁出来还是转播画质。ICONIC CHANNEL TENNIS 和 Tennis x Tennis
  在角上烧了自己的台标，Queenlenka 轻微放大导致边缘发虚——三个都留着
- **缩窗、补边、画中画、烧录字幕 → 不收。** 这些裁不出转播画质来

判定新增第四档 `degraded`：**内容合格、画面不合格**。它没有并进 `oncourt`，
是为了守住那条老规矩——拉黑名单上不许出现 `oncourt`。画面不合格要说成
画面不合格，不能借「不是场上采访」的名义悄悄剔掉。

**顺带炸出一个存量 bug。** 新加的「库里的源必须在注册表里」这条测试一跑就红：
`Tennis TV 媒体库 (tennistv.com)` 有 16 条，注册表里却只有
`Tennis TV 站 (库页 + 各赛事页)`——是早先改过源名，旧名的条目留在库里没跟着改。
这 16 条和新名下的 898 条**没有一条重复**（巴斯塔德、埃斯托里尔、格斯塔德的 250 站），
所以是改名不是删除。两份文件各改一半，报表上看不出来。

### 可达性：列表页挂着链接 ≠ 详情页打得开

抽 59 条实探：55 条能取到，2 条已删，2 条拿不准（YouTube 要求登录验证）。

其中 **WTA 官网那三条全是 404**。而同一张列表页上另外八条视频 **8/8 都是 200**
——不是整站坏了，是这几条下架了、链接没撤。这是「空结果 ≠ 不存在」的反面：
**非空的链接列表 ≠ 内容还在**。`scan_wta` 现在逐条探过再收，
且**只把 404 当死**（超时 / 403 / 429 都算「没问过」，要放过去）。

结果是 wtatennis.com 这个源当前贡献 **0 条**。WTA 的覆盖实际靠的是
`Tennis Interviews`（搬运号）加转播方，不是 WTA 官网。

## 三、视频：四大满贯发布会（免费、整场、有播放列表）

四家官方 YouTube 频道都把**整场发布会单条上传**，标题格式统一
（`球员名 | 轮次 Press Conference | 赛事年份`），非常好检索。

| 赛事 | 频道 | 发布会播放列表 | 实测 |
| --- | --- | --- | --- |
| 澳网 | [@australianopen](https://www.youtube.com/c/australianopen/videos) | [Press Conferences \| 2026](https://www.youtube.com/playlist?list=PL2RR--XMozwUREDAIK81mpeGj2nKvs3ai)、[Press Conferences & Interviews](https://www.youtube.com/playlist?list=PLJD4rQB4jpGADKyh1DF3V1epET95DuIF-) | ✅ |
| 法网 | [@rolandgarros](https://www.youtube.com/@rolandgarros) | 按视频标题检索 `Press Conference \| Roland-Garros 2026` | ✅ |
| 温网 | [@Wimbledon](https://www.youtube.com/@Wimbledon) | [2025 Press Conferences and On-Court Interviews](https://www.youtube.com/playlist?list=PLwx9gNibGUz54qMsOgwA-aI_zsEGnCVS7) | ✅ |
| 美网 | US Open 官方频道 | [Press Conferences \| 2025](https://www.youtube.com/playlist?list=PL_2A0MxHOgdZzEALKi7lKc_Lp5YyOgOfU) | ✅ |

官网也各有一个视频页，内容与 YouTube 大致重合：
[wimbledon.com/en_GB/video/press.html](https://www.wimbledon.com/en_GB/video/press.html)、
[ausopen.com/interviews](https://ausopen.com/interviews)。
温网这一层还包括赛前发布会（Pre-Championships Press Conference），语速更慢，适合入门。

## 四、视频：大师赛 / 1000 级别（这一层被严重低估）

**每个大师赛都有自己的 YouTube 频道，都在发整场发布会，都免费。**
关键是它们不出现在 ATP / WTA 中央频道里，得一个个去找。

用 `yt-dlp --flat-playlist` 逐个实测过，全部命中：

| 赛事 | 频道 | 实测样本 | 时长区间 |
| --- | --- | --- | --- |
| 罗马 | [UCxJDHLvJsuGNHbZPUjFDCNA](https://www.youtube.com/channel/UCxJDHLvJsuGNHbZPUjFDCNA/videos) | `Jannik Sinner Press Conference \| Final \| Rome 2026` | 6–17 分钟 |
| 印第安维尔斯 | [@bnpparibasopen](https://www.youtube.com/@bnpparibasopen/videos) | `Jannik Sinner \| Champion's Press Conference` | 7–12 分钟 |
| 马德里 | [@MMOPEN](https://www.youtube.com/@MMOPEN/videos) | `Press conference with Jannik Sinner // #MMOPEN 2026` | 6–12 分钟 |
| 辛辛那提 | [@cincyprotennis](https://www.youtube.com/@cincyprotennis/videos) | `Iga Swiatek \| Quarterfinals Press Conference \| 2025` | 8–9 分钟 |
| 上海 | [@RolexShanghaiMasters](https://www.youtube.com/@RolexShanghaiMasters/videos) | [专门的发布会播放列表](https://www.youtube.com/playlist?list=PLlrMo4wMQ3Zgg--bnfQwQkPNr7KYHuxh8)（31 条） | 3–10 分钟 |
| 巴黎 | [@RolexParisMasters](https://www.youtube.com/@RolexParisMasters/videos) | 近 40 条里 10 条含采访 | — |

几条实用观察：

- **罗马的命名最规范**，`球员 Press Conference \| 轮次 \| Rome 2026` 和
  `球员 On-Court Interview \| 轮次 \| Rome 2026` 分得清清楚楚，
  想按"场边 vs 发布会"分类建语料库，从罗马开始最省事
- **马德里同一场发英西两版**（`Press conference with...` / `Rueda de prensa con...`），
  球员讲西语时会发西语版——挑英文那条
- 大师赛发布会普遍**比大满贯短**（6–12 分钟 vs 10–15 分钟），因为在场记者少。
  但辛纳罗马决赛后那条有 **17 分 27 秒**，比不少大满贯的还长
- 蒙特卡洛、迈阿密、加拿大、Queen's 的频道句柄我没猜对（取到 0 条视频＝句柄错，
  **不等于没有发布会**）。按这六个的规律，它们大概率也在发，自己去 YouTube 搜赛事全名即可

## 五、视频：ATP / WTA 中央渠道（反而受限）

反直觉的一点：**中央官方渠道给的东西比赛事自己给的少。**

- **Tennis TV**（ATP 官方流媒体）——[tennistv.com/library/interviews](https://www.tennistv.com/library/interviews)
  实测：**只有短采访，56 秒到 7 分 07 秒**，不是整场发布会。部分条目标着 "Register"，
  要注册才能看。覆盖 ATP 250 级别（Estoril、Kitzbühel、Båstad、Gstaad、Umag、Eastbourne 等）。
  YouTube 频道 [@tennistv](https://www.youtube.com/@tennistv) 偶尔发发布会合辑
  （如 ATP 年终总决赛后辛纳与兹维列夫的发布会），但不成体系。
- **ATP Tour 官方**——[atptour.com/en/video](https://www.atptour.com/en/video)、
  [@ATPTour](https://www.youtube.com/@ATPTour)：以 hot shots、集锦、球员专访为主，
  发布会不是常规栏目。另有 [Daily Media Notes](https://www.atptour.com/en/media/daily-media-notes)，
  是给记者的赛事简报，文字材料。
- **WTA**——[wtatennis.com/videos/press-conferences](https://www.wtatennis.com/videos/press-conferences)
  实测：条目显示 6–10 分钟，但**每条下面都写着 "Register to view press conference"**，
  要建账号。覆盖 Queen's、柏林、罗马等 2026 赛季赛事。
  YouTube [@wta](https://www.youtube.com/user/wta) 上以集锦和球员 vlog 为主。
  **同一场罗马的发布会，去罗马赛事频道看是免费的**——绕开注册墙的办法就是找赛事自己的频道
- **ATP Challenger Tour**——2026 年新开的
  [YouTube 频道](https://www.atptour.com/en/news/atp-challenger-2026-youtube-launch)，
  以集锦为主。（未验证是否含采访）

## 六、视频：团体赛

- [Laver Cup](https://www.youtube.com/LaverCupTV) —— 有团队发布会（如
  `Team Europe Press Conference | Laver Cup 2025 Pre-Event`）。团队发布会是**多人同台**，
  有互相打趣，语料风格和单人发布会很不一样，练对话节奏不错。
- [Billie Jean King Cup](https://www.youtube.com/@BJKCup) —— 有赛前队伍发布会。
- Davis Cup / United Cup —— 官方频道存在，发布会覆盖程度未验证。
- 各国协会也发：如 [LTA](https://www.lta.org.uk) 会发英国队发布会的 best moments。

## 七、文字稿：ASAP Sports 是唯一的系统性来源

[asapsports.com](http://www.asapsports.com/showcat.php?id=7) —— 网球分类 `category=7`。
这是全网唯一把职业网球发布会**逐字稿系统化归档**的地方，也是所有学术研究引用的源头。

> **只收发布会，不收场上内容。** 抽阿尔卡拉斯页面的 6 条逐一打开，类型标签
> 全是 `Press Conference`，没有一条 `On-Court Interview` 或 `Trophy Ceremony`。
> 所以想要场上采访/冠军致辞的文字，**只能用自动字幕，没有人工稿可配**。

**实测数据：**

- **年份跨度 1992–2026**，35 年
- 2025 年收录 **43 项赛事**，四大满贯齐全（温网在站内叫 `THE CHAMPIONSHIPS`），
  加上五个大师赛、戴维斯杯、比莉·简·金杯、拉沃尔杯、联合杯、资格赛
- 2026 年截至 7 月已收 17 项
- 单篇结构：**赛事 / 日期 / 球员 / 地点 / 比分 / `THE MODERATOR:` / `Q.` / `球员名:`**，
  自带比赛比分和括号舞台提示（`(Laughing.)`、`(Laughter.)`）
- 纯 HTML，`curl` 直接 200（实测 21 KB / 页），ID 连续递增，好抓

URL 规律（实测可用）：

```
按年:    /show_year.php?category=7&year=2025
按球员:  /show_player.php?id=39503        # Carlos Alcaraz
单篇:    /show_interview.php?id=211239    # 2025 美网决赛后阿尔卡拉斯
```

### 视频与文字稿可以配对（已实测）

2025 美网男单决赛后阿尔卡拉斯的发布会，两边都有，内容对得上：

- 视频：<https://www.youtube.com/watch?v=YwqPdnG2qk8>
- 文字稿：<http://asapsports.com/show_interview.php?id=211239>

这是这份清单里最有价值的一条：**同一场，一份"能听"，一份"能读"。**

## 八、字幕：只有自动生成的，没有人工字幕

四大满贯各抽一条发布会用 `yt-dlp --list-subs` 实测，结论一致：

```
en-orig  English (Original)    vtt, srt, ttml, srv3, srv2, srv1, json3
en       English               vtt, srt, ttml, srv3, srv2, srv1, json3
<video_id> has no subtitles          ← 没有任何人工字幕
```

`en-orig` 与 `en` 都是 YouTube ASR 自动生成的。实测下载 2025 美网决赛后
阿尔卡拉斯那条，问题很具体：

- **口头语和重复词全部保留**：`that I that I had in the`、`achieve achieve that once again`、
  满篇 `uh`
- **说话人只有 `>>` 符号**，分不清是记者还是球员，更没有名字
- **时间轴滚动重叠**（前后两条 cue 时间范围交叉），是两行滚动字幕的产物，
  文本本身连贯，但直接当字幕文件用会闪
- 开头一段是媒体间环境噪音，被识别成 `What?` / `Can't` 这类碎片

### 但场上采访的字幕质量明显更好

同样是自动字幕，**场上采访比发布会干净得多**。实测罗马 2026 决赛后辛纳那条
（1:32 / 255 词），整段几乎可以直接拿来用：

> "The reaction says it all. You're the champion of Rome. Many congratulations.
> What means more to you, to complete the set of Masters so soon or to give,
> well, yourself but also all of Italy this title today?"

原因是**音频走转播调音台**，主持人和球员各有一支麦克风直给，没有媒体间那种
开场环境噪音。缺点仍在：口头语照留（`uh`、`perfect perfect`、`really, really happy`），
说话人切换只有 `>>`。

**颁奖礼要看赛事语言**：罗马那条 6 分 02 秒的冠军致辞，辛纳中途转意大利语，
英文 ASR 立刻崩坏（冒泰文字符、`conrat`、`for for for for`）。
温网 / 美网 / 澳网的颁奖礼是全英文，没有这个问题。

### 所以两种材料的分工是这样的

| | 自动字幕 | ASAP 文字稿 |
| --- | --- | --- |
| 忠实度 | **逐字，含口头语** | 清理过：补标点、去 `uh`、修重复词 |
| 可读性 | 差 | 好，有说话人标签 |
| 适合 | **跟读、听写、精听对答案** | 泛读、抄句式、查表达 |

想练听力就用自动字幕对答案（它更接近真实说的话）；
想学句式和表达就读 ASAP（它更接近规范英语）。**两个都下，别只下一个。**

## 九、现成的研究语料库

如果要做量化分析而不是逐条看，不用自己爬：

**Cornell ConvoKit `tennis-corpus`** ——
[convokit.cornell.edu/documentation/tennis.html](https://convokit.cornell.edu/documentation/tennis.html)

- **6,467 场**大满贯单打赛后发布会，2007–2015
- 163,948 条 utterance / 81,974 组对话 / 359 位发言人
- 每条标注了 question / answer、说话人、赛事、双方排名、胜负、轮次、对手
- 附带 SpaCy 解析结果
- 文字稿源自 ASAP Sports，比赛元数据来自 Tennis-Data

```python
from convokit import Corpus, download
corpus = Corpus(filename=download("tennis-corpus"))
```

出自论文 Fu, Danescu-Niculescu-Mizil & Lee (2016),
*Tie-breaker: Using language models to quantify gender bias in sports journalism*。
顺带一提，这篇论文本身就是"用发布会语料做语言研究"的范例，
它关心的是记者对男女球员的提问差异——如果你的"研究英语学习"也想带一点分析视角，
可以直接接着做。

## 十、付费 / 受限来源

- **Tennis Channel**（[tennischannel.com](https://www.tennischannel.com/en-us/page/press-conferences)）——
  press conferences 属订阅内容，$11.99/月起；免费层不含发布会。美国以外有地区限制。
- **Tennis TV 订阅**——ATP 全场比赛回放为主，采访是附带。
- **各转播商**（ESPN、Eurosport / TNT、Sky Sports）——发布会片段散在新闻报道里，不成archive。

## 十一、二手引述站（不建议当语料）

Sportskeeda、Tennis Majors、tennis365、Punto de Break、heavy.com 这类站会写
"Everything X said after..."，看着像文字稿，实际是**摘录 + 记者转述**，
有删改、有拼接、不标注省略。查事实可以，**当英语语料不行**——
你会把记者的转述当成球员的原话学进去。

## 十二、动手抓取的注意事项

```bash
pip install yt-dlp

# 只要字幕不要视频（学习用，体积小）
yt-dlp --write-auto-sub --sub-lang en --sub-format srt --skip-download \
  -o "%(title)s" "https://www.youtube.com/watch?v=VIDEO_ID"

# 整个播放列表的字幕
yt-dlp --write-auto-sub --sub-lang en --sub-format srt --skip-download \
  "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

先摸清一个频道有多少发布会，别上来就下：

```bash
# 列标题和时长，不下载任何东西
yt-dlp --flat-playlist --playlist-end 60 \
  --print "%(duration>%H:%M:%S)s  %(title)s" \
  "https://www.youtube.com/@cincyprotennis/videos" | grep -i "press conference"
```

三个坑（实测踩到）：

- 沙箱里 yt-dlp 会警告 `No supported JavaScript runtime could be found`
  和 `no impersonate target is available`，**拿字幕不受影响**，但拿视频流可能缺格式
- **频道句柄猜错和频道没内容，长得一模一样**：两种情况 `--flat-playlist` 都返回空。
  分辨办法是先不加 grep 数一下总条数——取到 0 条视频就是句柄错了，
  取到 60 条但 grep 命中 0 才是真没有。我在蒙特卡洛、迈阿密、加拿大、Queen's
  上就是这么被骗过一次的
- **`--playlist-end` 的取样窗口会骗人**：扫澳网近 100 条搜 `on-court` 零命中，
  但澳网在 1 月、扫的时候是 7 月，采访早被休赛期内容挤出去了。
  **按赛事日期决定取样深度**，别用固定的 60/100
- **YouTube 会对连续下字幕返 429**。实测连续第 4 次退避（15/30/60 秒）才成功。
  429 和"没有字幕"在输出上完全不同（前者是 `HTTP Error 429`），但如果脚本吞了
  stderr 就分不出来了——**别吞 stderr**
- ASAP Sports 用 `curl` 直接拿就行（实测 200 / 21 KB），不需要浏览器。
  注意事件页是 `show_events.php`（**复数**）加 `event_id`，
  写成 `show_event.php` 会返回一个 200 的空壳页，看起来像"这场没有条目"

**关于授权**：本仓库 `docs/video-localization.md` 定下的规矩是不从 YouTube 抓视频、
翻译不自动取得转载权。这份清单里的素材，**个人学习性质的下载与本仓库的发布管线是两回事**——
如果哪天想把发布会内容做成对外的内容产品，授权要另外单独判断，
不能因为"字幕是公开的"就默认可用。

## 附：还没验证的

诚实记一下，这几条没自证：

- ATP Challenger 新频道是否含采访
- Davis Cup / United Cup 官方频道的发布会覆盖程度
- 蒙特卡洛、迈阿密、加拿大、Queen's 的正确频道句柄（我猜的四个全错，
  所以**不能说它们没有发布会**——只能说我没找到入口）。
  正确做法见第二节末尾：用搜索反推，别猜句柄
- 转播方这条线已挖尽：14 家全部深扫并记录（见上表），不必再查
- 亚洲赛季（北京、武汉、东京）、巴塞尔、维也纳、鹿特丹、多哈、Queen's、
  哈雷、加拿大、ATP/WTA 年终总决赛——搜索只返回粉丝搬运号，
  **没找到它们自己发的场上采访**。但这是"搜索没找到"，不是"确认没有"
- 各国网协只查了 FFT / USTA / LTA，德国、意大利、西班牙、澳洲网协没查
- ASAP Sports 早年（1992–2006）网球条目的密度，只确认了年份存在
- 各大满贯官网视频页与 YouTube 的内容是否完全重合，只做了抽样比对
- **美网完整颁奖礼的字幕质量**：`--list-subs` 确认有自动字幕，但退避到 240 秒仍撞 429，
  正文没实际读到。按温网/澳网同为全英文推断应该干净，**但这是推断不是实测**
- **温网 Champion's Dinner Speech 的字幕质量**：同样被 429 挡住。
  它是第二节里推荐的首选素材，推荐依据是体裁（有讲稿、全英文、语速慢），
  不是字幕实测——**下次网络宽裕时第一个补验这条**
- ASAP 只收发布会这一条，是抽 6 条得出的，没有穷举全部 280 条

> 实测过字幕正文的只有三条：2025 美网决赛后阿尔卡拉斯**发布会**、
> 罗马 2026 决赛后辛纳**场上采访**、罗马 2026 辛纳**冠军致辞**。
> 其余关于字幕质量的说法都是从这三条外推的。
