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

> 踩点记录：我第一次扫澳网频道近 100 条，`on-court` 零命中，差点写成"澳网没有"。
> 实际是频道当时在发休赛期内容，1 月的采访早被挤出前 100 条。
> **零命中先看自己的取样窗口。**

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
  所以**不能说它们没有发布会**——只能说我没找到入口）
- ASAP Sports 早年（1992–2006）网球条目的密度，只确认了年份存在
- 各大满贯官网视频页与 YouTube 的内容是否完全重合，只做了抽样比对
- **美网完整颁奖礼的字幕质量**：`--list-subs` 确认有自动字幕，但连续退避后仍撞 429，
  正文没实际读到。按温网/澳网同为全英文推断应该干净，**但这是推断不是实测**
- ASAP 只收发布会这一条，是抽 6 条得出的，没有穷举全部 280 条
