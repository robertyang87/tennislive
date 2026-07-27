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
| **转播方** | Eurosport Tennis | **78** |
| **团体赛** | United Cup 56、Laver Cup 26、Davis Cup 12 | **94** |
| **赛事方** | 温网 20、法网 18、Dubai 45、罗马 12、美网 11、巴黎 10、澳网 10 | **126** |

**转播方这一整个类别，第一版完全没想到。** Eurosport Tennis 一家就 78 条，
比任何赛事方都多，而且**比赛事方自己发的更长**（2–5 分钟 vs 1–2 分钟），
因为它保留了主持人的完整提问——对英语学习反而更有价值。

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
| `data/oncourt_sources.json` | 21 个源的注册表，逐源可配扫描深度与说明 |
| `tools/collect_oncourt_interviews.py` | 扫描、按类型分类、增量并库 |
| `.github/workflows/oncourt-interviews.yml` | 每周二 05:20（北京）跑一次 |
| `data/oncourt_interviews.json` | 累积产物 |

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
- 转播方只查了 Eurosport 一家有量。Sky Sports、Wide World of Sports、
  Amazon Prime Video Sport、TSN 各只搜到 1 条，**没有深扫过它们的频道**——
  按 Eurosport 的例子看，深扫可能还有
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
