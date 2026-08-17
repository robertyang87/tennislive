# 成品 spec 文案模式盘点（供《完整流程和要求》总文档）

> 数据源：`specs/reels/*.json`（113 条）、`specs/interviews/*.json`（34 条）、`specs/**/*.xhs.txt`（146 个）。
> 统计脚本：`tools/analyze_copy_patterns.py`（python3 一次性跑完，输出见各节）。
> 口径：字数为 `len()`（全角 1 字、半角 1 字符；push 的"字位"闸是另一套算法，全角 1 半角 0.5，见正文）。

---

## 一、reel 字段结构（113 条里长什么样）

### 1.1 顶层结构：两代并存

| 代 | 特征 | 数量 |
|---|---|---|
| **新格式**（含 `editorial`） | `slug / source_url / _column / _claims / _facts(_match) / _hit_data / _no_repeat / _voice / _topbar_why / _editing_why / cover / push / segments / stats / topbar` | 79 |
| **旧格式**（无 `editorial`，用 `_match`＋`_turning_points`） | `slug / source_url / _source / _match / _turning_points / _editing_why / _narration_why / _scorebox_why / _ear_checklist / cover / push / segments` | 34 |

旧格式靠 `_turning_points`（3 个事件点）代替 `editorial.beats`，靠 `_narration_why` 讲文案取舍；新格式把"这期讲什么、为什么"集中到 `editorial`。**总文档建议以新格式为主描述，旧格式作为过渡说明。**

### 1.2 `editorial` 子字段（79 条完全一致）

```
editorial:
  mode: "match_review"          # 79/79 全是这一个值
  question:  <一个问句>          # 全片要回答的问题（见 1.4）
  thesis:    <一段 200-400 字论证># question 的完整答案，含数字证据
  beats:     [3 个要点]          # 前段 / 中段 / 结局，各 1 句，用于排旁白
  human_context:
    angle:      <场外切口一段话>  # 为什么值得看，2-4 句
    facts:      [逐条可查的事实]  # 每条带出处或自证方式
    sources:    [URL]            # 38/79 还有 voice_label（旁白口吻标记）
```

- `human_context` 子字段两变体：`angle/facts/sources`（41 条）或 `angle/facts/sources/voice_label`（38 条）。
- `beats` 恒为 3 条，格式是"前段：… / 中段：… / 结局：…"（见 `djokovic-tirante`），或 3 条各自成句（见 `bencic-eala`）。

### 1.3 `push` 与 `cover` 字段

- `push`：只写 `summary`（推送标题，≤20 字位）+ `lead`（正文第一段）。`matchup/score/event` **不写**，由封面算——"一个数写两处必分叉"。一半以上带 `_why` 解释取舍。
- `cover`：`eyebrow / hook / winner / result / layout / subject / topic / matchup / portrait / scrim / scoreboard`，多数带 `_hook_why / _portrait_why / _scrim_why / _matchup_rank_why` 等"为什么这么选"注释。
- `cover.versus` 只出现在 13 条 cutout 双人版式里，是**抠图/背景的排版对象**（`names/background/top/bottom`），不是文案字段。

### 1.4 `editorial` 文案示例（10 条，摘原句）

**question（全片要回答的问题）：**

| slug | question 原文 |
|---|---|
| `arango-venus` | 四十六岁的大威廉姆斯，为什么六十六分钟就丢了这场球——而她已经多久没赢过了？ |
| `bartunkova-charaeva` | 一个刚刚第一次进入世界前四十的二十岁球员，正赛首战对上排名一百一十三的资格赛球员——为什么这场球会打掉两小时四十七分，还要七个赛点才结束？ |
| `boulter-volynets` | 小分少七个、局数少两个、Ace 少一个、破发点兑现少一个——每一栏都落后的那个人，怎么赢下了这场球？ |
| `bencic-townsend` | 两个抢七，一次决胜盘还被追平——本西奇是怎么把汤森德这场硬仗啃下来的？ |
| `gauff-sakkari` | 五比一领先，被萨卡里追到五比四、救下一个赛点——高芙怎么把这盘稳稳收回来的？ |
| `swiatek-rybakina-toronto-final` | 三大满贯的卫冕全部早轮出局，掉到世界第八的这个赛季，斯瓦泰克是怎么在多伦多把签表打穿、拿到本赛季第一冠的？ |
| `navarro-kalinina` | 一场只多赢一个小分的球，她是怎么从落后一盘里翻回来的？ |

规律：**"具体到一场球的数字/局面 + 怎么/为什么 + 悬念"**。数字一定带两个（"两小时四十七分 + 七个赛点"、"少七个 + 少两个"），悬念落在"怎么做到/为什么输"。

**thesis（答案，取开头一句）：**

| slug | thesis 开头 |
|---|---|
| `arango-venus` | 这场球从她这一侧看是一条线的延续：上一次赢球停在二〇二五年七月的华盛顿，此后连着输了十四场… |
| `bartunkova-charaeva` | 这场球从头到尾没有一个人真正占上风：两百零七分里巴尔通科娃只多拿了七分。 |
| `bencic-townsend` | 首盘她在自己发球局连救三个盘点，仍没能逃过抢七… |
| `swiatek-rybakina-toronto-final` | 这不是一场跌宕起伏的决赛——她只用了一小时十五分钟，全场只丢五局。真正的故事在这场比赛之外… |
| `boulter-volynets` | 因为她输的那一盘输得彻底，赢的两盘赢得刚刚好。 |
| `djokovic-tirante` | 因为这场球他扛住了对手，没扛住自己的身体。 |

规律：thesis 先给**一句话结论**（经常是反直觉的："输一盘输得彻底所以赢了"、"扛住了对手没扛住身体"），再展开 2-4 句带数字的论证，最后落一句比分或结果。

**human_context.angle（场外切口）：**

| slug | angle（节选） |
|---|---|
| `bencic-eala` | 七连胜怎么开始的就怎么被记住：华盛顿一周连过郑钦文、费尔南德斯、斯维托丽娜、大坂直美、佩古拉夺冠…一个月前她还在打资格赛，现在是世界第二十。 |
| `djokovic-tirante` | 这一场的场外切口是**时间**：不是「状态下滑」这种套话，是三个能查的时间刻度叠在一起。德约科维奇 1987 年 5 月 22 日出生，本场时三十九岁… |
| `boulter-volynets` | 这一场的场外切口是**一段连败的结束**，不是「以少胜多」的技术奇观。转播解说在 136.76 秒的原话是 `Finally, Katie Boulter snaps the five-match skid`… |
| `arango-venus` | 从大威廉姆斯这一侧看，这不是一场孤立的首轮出局：她**上一次赢球是二〇二五年七月的华盛顿**…而她并没有就此走人——**输完这场她留在辛辛那提，和小威廉姆斯搭档打双打**… |
| `bartunkova-charaeva` | 这场球之所以值得看，是因为它发生在她刚刚迈过一道线的第二个星期。…排名第一次进入前四十——WTA 官方的 Rankings Watch 用的就是『entered the Top 40 for the first time』。 |
| `gauff-sakkari` | 这是两人生涯第七次交手，高芙已经连赢四场——萨卡里成了她职业生涯里赢得最多的对手。 |

规律：angle 是 **"这场球在故事线上卡在哪儿"**——连败的结束、里程碑后的第一周、老将的告别线、生涯首次交手。必带可查出处（转播原话、WTA 官方用词、具体日期），不写套话。

**beats（3 条，排旁白的骨架）：**

| slug | beats 原文 |
|---|---|
| `bencic-eala` | ① 首盘伊埃拉两度被破两度破回：2-2、4-4，两次都追平。② 4-4刚追上，下一局她的发球局第三个破发点被撬开——4-5，随后本西奇6-4拿下首盘。这是全场的转折。③ 第二盘28分钟本西奇6-0跑开（33分里伊埃拉只拿8分）；最后一局伊埃拉0-40救回三个赛点，第四个才交出比赛。 |
| `djokovic-tirante` | 前段：第一盘四十五分钟六比二，四个发球局一个没丢，看着还是那个他 / 中段：第二盘一比一那个发球局九次平分、四个破发点、十七分五十一秒——守住了，然后开始呕吐… / 结局：第三盘四比四连救三个破发点，第四个没救成… |

### 1.5 钩子（cover.hook）写法：上句挖坑、下句翻转

- **格式**：两行，每行 ≤10 字符（solo 版式硬闸 `HOOK_MAX_CHARS`），用 `\n` 换行。
- **结构规律**（从 `_hook_why` 注释直接摘）："上句先给坑、下句给翻转，顺序不能反"。旧栏目存货四例被反复引用：

```
连输普汀塞娃七次 / 三十七岁，她赢了
两次只差一个发球局 / 两次都没保住
六个破发点全丢 / 他等到了第七个
决胜盘二比五落后，五个赛点 / 他一个没给，掀翻世界第十六
```

- **全量钩子抽样**（113 条里的 50+，见统计脚本）：

```
[alexandrova-sabalenka] 苦守三个赛点，才拿下这一分 / 萨巴伦卡硬地14连胜就此终结
[arango-venus] 上次赢球是去年七月 / 这是第十四场连败
[bartunkova-charaeva] 六个赛点被救下 / 第七个才落地
[bencic-eala] 七连胜停在了这里 / 最后一局她还救了三个赛点
[boulter-volynets] 她少赢了七个小分 / 比分却是她赢
[djokovic-tirante] 一局守了十七分钟 / 三十九岁他扛不住了
[eala-pegula] 她还没拿过一个冠军 / 对面有十一个
[fonseca-van-de-zandschulp] 第二盘四比一领先 / 被追成五平
[kenin-lys] 第一盘只赢一局 / 总分却是七十一平
[medvedev-zandschulp] 九个双误，两次零比四十丢掉发球局 / 世界第六，两盘出局
[navarro-kalinina] 一百六十九个小分 / 她只多赢了一个
[nishikori-shang] 六个破发点全丢 / 他等到了第七个
[gauff-samsonova] 第一盘三十一分钟丢了 / 后面两盘她只丢五局
[zverev-griekspoor] 他救下盘点，拿下第一盘 / 然后，头号种子出局
```

- **两条铁律（来自 `_hook_why`）**：① 钩子讲**过程**（几比几、救几个赛点），不讲**身份**（排名/年龄/冠军数——海报赛果行已经印着，重复即浪费 27 字位）；② "五个赛点"这类数必须**逐分核过**才能写进钩子。

---

## 二、旁白（segments narration）字数规律

- 统计样本：113 条 reel，带旁白的段共 **1429 段**（全部片子都有旁白，0 条纯音乐片）。
- **每段字数**：

| 指标 | 值 |
|---|---|
| 中位数 | **28 字** |
| 均值 | 30.6 字 |
| P10 / P25 / P75 / P90 | 15 / 21 / 36 / 49 |
| 最短 | 3 字（`kovacevic-khachanov` seg17「抢七。」） |
| 最长 | 167 字（`swiatek-rybakina-toronto-final` seg7） |

- **每条片子的段数**：segments 总数中位 **12 段**（min 5 / max 38）；带旁白的段数中位也是 12（个别段只放画面/现场声，无旁白）。
- **最短旁白示例**：`medvedev-zandschulp`「第一盘丢了。」（6字）／`tsitsipas-royer`「第四个赛点。」（6字）／`eala-story`「最后一分。」（5字）／`kovacevic-khachanov`「抢七。」（3字）——**最短那几段全是"悬念的铡刀"：报一个转折点，不给评论。**
- **最长旁白示例**（`swiatek-rybakina-toronto-final` seg7，167字，节选）：
  > 但莱巴金娜没有轻易放弃——她稳住了自己的发球局，把比分反超到二比一，这场看似一边倒的决赛突然有了悬念。轮到斯瓦泰克发球，这一局她打得格外艰难…看台上的加拿大观众也跟着屏住了呼吸。斯瓦泰克还是顶住了这波压力，一分一分把这个艰难的发球局拿了下来。
- **旁白句长**：一句 20-40 字（按逗号切），长段靠 3-5 个短句堆节奏，不会出现 60+ 字不加标点的句子。
- **收尾一问**：最后一段旁白几乎必以问句收（见第五节"悬念"），如 `alexandrova-sabalenka`「掀翻世界第一之后，这一次，她能走多远？」、`baez-dimitrov`「决胜盘四比一领先还能输掉，这样的球你见过几次？」、`fritz-jodar-final`「二十八岁的前世界第四，还回得去吗？」

---

## 三、interview spec 文案示例（34 条）

### 3.1 字段结构

- 必含：`slug / url / source_title / start / end / column(赛后开麦) / event / interview_kind / winner / push / cover / zh / transcript_verified / _verified_clean`。
- `push` 写全 `matchup / score / event / summary / lead`（与 reel 不同——interview 的 `summary` 是标题、`lead` 是第一段，`event` 常留空因为标题字位不够，见 `eala-svitolina-dc2026-qf._why`）。
- `cover`：`frame_at / title[2行] / sub / tag`，title 两行是"上句事实、下句原话"结构。
- **`zh`**：逐字幕条的中文翻译列表（如 `rybakina-osaka-tor2026-qf` 62 条、`eala-pegula-dc2026-final` 71 条）；34 条共 3076 条字幕，**每条字幕中位 8 字（1-19 字）**，即"一次一句、短句上屏"。
- **`takeaway`**（26/34 条有）：`{close: {point: <一句话总结>, ask: <问观众的一句话>}}`，部分有 `open: {lead/point/facts}`。**这就是 interview 版的"收尾一问"。**

### 3.2 金句（human_quote，6 条有）示例

| slug | 金句原文 |
|---|---|
| `rybakina-osaka-tor2026-qf` | I was just trying to fight. The first game of the match was really tough because it cost me the set, and then in the second I was just trying to stay closer to the score… just fight, and I'm super happy that I won this match. |
| `rybakina-gauff-tor2026-sf` | I feel like I stayed so many hours on the court that maybe some shots are just coming out from my racquet. …I was just trying to fight. |
| `shang-rublev-mtl2026-r2` | Andrey is a great friend, a great competitor and a good champion. …But more happily, I'm healthy. I'm definitely playing my best tennis and just happy to be in Montreal. |
| `shelton-mensik-mtl2026-qf` | It was a great night for me. I think days like this when everything is clicking is a little bit easier… It is a lot tougher on the days where you are struggling. |

金句的用途：`cover.title` 第二行、xhs"值得抄下来的几句"、以及 sub 的原话引用。每条 `human_quote` 带 `url`（赛事官方稿/权威媒体的**人工转写**，比 ASR 硬）和 `human_quote_ok`（人工核对过的词）。

### 3.3 cover.title 写法（上句事实、下句原话）

```
[alexandrova-sabalenka-tor2026-r16] 十二天前她被轮椅推离球场 / 十二天后她掀翻世界第一
[eala-pegula-dc2026-final] 第一次拿到冠军 / 而她说 这不会是最后一次
[djokovic-cincinnati-2026-return] 过去两年 每个大满贯后都带着伤 / 「这次是最好的一次」
[rybakina-swiatek-tor2026-final] 「今天油箱只剩一半」 / 她还是站到了决赛最后一刻
[sabalenka-zhang-tor2026-r3] 世界第一发球胜赛 被逼出破发点 / 她说 那种时候你只想回去休息
[shang-rublev-mtl2026-r2] 五个赛点 他一个没给 / 掀翻 10 号种子
[tirante-djokovic-cincinnati-2026-r2] 十五个破发点 他只兑现了两个 / 「我现在整个人松下来了」
```

规律：第一行是**这场采访/致辞最扎眼的事实**，第二行是**当事人原话**（带引号）；sub 再给赛事坐标＋一句补充。

### 3.4 takeaway 的收尾一问（26 例抽样）

```
[rybakina-swiatek-tor2026-final] 拼到极限却没能拿下冠军 值得吗？
[gauff-samsonova-cincinnati-2026-r2] 陪你打球的人 你谢过他吗？
[noskova-boulter-cincinnati-2026-r2] 下一座 会不一样吗？
[sabalenka-zhang-tor2026-r3] 世界第一为什么先夸张帅？
[swiatek-rybakina-tor2026-final] 冠军之外 她还想说给谁听？
[arango-venus-cincinnati-2026-r1] 你的偶像 也在电视里吗？
```

---

## 四、小红书正文（.xhs.txt）示例

146 个文件（reel 79 个、interview 55 个、其他 12 个）。结构：**开头钩子段 → 坐标行 → 正文（reel 用叙事/数字段，interview 用①②③ 分段＋金句）→ 结尾问句 → 话题标签**。

### 4.1 reel 完整例：`specs/reels/zhang-sabalenka.xhs.txt`

> 世界第一发球胜赛的那一局，三十七岁的张帅拿到了一个破发点。再赢一分，第二盘就是五平。
>
> 📍2026 多伦多 WTA1000 女单第三轮
> 🎾 萨巴伦卡 6-3 6-4 张帅｜1 小时 16 分
>
> 先说结果：她输了。但这场球值得看的地方不在比分上。
> …（叙事三小段，按比分推进）…
>
> 一小时十六分钟。
>
> 几个数放在一起看会更清楚这场球是什么样子：
> · 双误：萨巴伦卡 4 ｜ 张帅 0
> · 非受迫失误：萨巴伦卡 14 ｜ 张帅 1
> · 制胜分：萨巴伦卡 29 ｜ 张帅 8
> · 一发成功率：萨巴伦卡 59.7% ｜ 张帅 66.1%
> · 破发点：萨巴伦卡 2/3 ｜ 张帅 0/2
>
> 世界第一发了四个双误…差距在制胜分那一栏——二十九比八…
>
> 那一分差在哪儿？评论区聊聊。
>
> #网球 #张帅 #萨巴伦卡 #WTA #多伦多站

### 4.2 interview 完整例：`specs/interviews/eala-pegula-dc2026-final.xhs.txt`

> 生涯第一个冠军，她第一个感谢的是刚输给她的人
>
> 📍华盛顿 WTA500 决赛 · 赛后捧杯致辞
> 🎾 伊埃拉 4-6 6-4 6-0 佩古拉
> 🎤 全程中英双语字幕
>
> 先丢一盘，再连下两盘，末盘 6-0。对面是这站的头号种子。…
>
> ① 她夸对手夸得很具体 … ② 感谢名单的顺序值得看 … ③ 最好的一句留在了最后 …
>
> 值得抄下来的几句：
> Where do I start? 我该从哪儿说起
> I definitely learned so so much. 我真的学到了太多
> I'm not enduring alone. 我不是一个人在扛
> …
>
> 刚拿到首冠的人，先讲对手，再讲团队，最后才讲自己。
> 你觉得这是性格，还是练出来的？
>
> #网球 #伊埃拉 #佩古拉 #网球英语 #网球时差

### 4.3 结构规律统计

- **开头第一行**：一个悬念句或金句句（46 个文件开头各不相同），如「十二天前她被轮椅推离球场，十二天后她掀翻了世界第一」「苦战 2 小时 39 分，一度丢掉一盘，伊埃拉说这场她是『扛过来的』」。
- **坐标行**：reel 用 `📍赛事`＋`🎾 比分`；interview 用 `📍`＋`🎾`＋`🎤 全程中英双语字幕`。
- **正文**：reel = 叙事段落＋"· "数据列表；interview = ①②③ 分段（26 个文件用）＋"值得抄下来的几句"（中英对照）。
- **结尾**：一个问句（不一定要"？"结尾，常有"评论区聊聊/评论区站队"），然后一行 5-6 个话题标签，**标签永远在最后一行**（146 个文件全部如此，median 1 行）。
- **签名**：部分带"这一站我们一共做了三条…"这类栏目内互链（`eala-pegula-dc2026-final`）。

---

## 五、手法例句库（各 3 条＋出处）

### 5.1 数字反差（账面上的"反直觉"）

| slug | 例句 |
|---|---|
| `boulter-volynets`（hook） | 她少赢了七个小分 / 比分却是她赢 |
| `baez-dimitrov`（narration seg12） | 多拿五分的那个人输了这场球。决胜盘四比一领先还能输掉，这样的球你见过几次？ |
| `bartunkova-charaeva`（narration seg11） | 两小时四十七分，两百零七分她只多拿七分。这样熬下来的一场胜利，算好还是不算？ |
| `navarro-kalinina`（question） | 一场只多赢一个小分的球，她是怎么从落后一盘里翻回来的？ |
| `zhang-sabalenka`（hook） | 三十七岁，一个非受迫失误 / 世界第一双误四个，却赢了 |

规律：**把"谁该赢/谁赢了"的账算给观众看**——总数几乎持平、制胜分更少、双误更多的那边赢了。数字必须逐分核过（`boulter-volynets` 的 175 小分 84:91 在 `push.lead` 里全部列出）。

### 5.2 悬念（收尾一问为主）

| slug | 例句 |
|---|---|
| `alexandrova-sabalenka`（question） | 世界第一在硬地上赢了十四场，是怎么在这一场输掉的？ |
| `eala-pegula-final`（narration 末段） | 那一夜要是没下雨，冠军还会是她的吗？ |
| `fritz-jodar-final`（narration 末段） | 五比四，弗里茨发球胜赛局。四个赛点，霍达尔一个一个救掉。二十八岁的前世界第四，还回得去吗？ |
| `bencic-eala`（narration seg8） | 一个月前还在打资格赛，现在是世界第二十。这场六比零，是警报，还是七连胜后正常的账单？评论区站队。 |
| `djokovic-tirante`（narration 末段） | 这一场输在天气，还是输在年纪？ |
| `baez-dimitrov`（narration 末段） | 决胜盘四比一领先还能输掉，这样的球你见过几次？ |

规律：问句只开一扇门不替观众收尾（`zhang-sabalenka._hook_why`："钩子该开一扇门，不是替读者收尾"）；句式集中在"还能走多远/还回得去吗/值得吗/算不算/差在哪儿"。

### 5.3 一句带过背景（来路只给一句，不铺开）

| slug | 例句 |
|---|---|
| `shang-rublev`（narration seg6） | 去年他脚伤停了五个月，排名掉到两百七十。这一站是靠保护排名进的正赛。 |
| `bencic-townsend`（narration seg2） | 十一年前，18岁的本西奇，就是在这里拿下生涯第一座冠军。 |
| `anisimova-bartunkova`（narration seg2） | 两年前，她还是世界第132的资格赛球员，一路杀进了这里的决赛。 |
| `bencic-eala`（narration seg3） | 世界第二十的伊埃拉，生涯第一次碰上世界第十四的本西奇——华盛顿夺冠以来，她已经连赢七场。 |
| `eala-story`（narration seg3） | 而这一切开始得很早。四岁，因为哥哥每天都在打。 |

规律：背景**限一句、带数字、贴这场球**（"脚伤停了五个月"、"十一年前"、"两年前"）。这条正是 CLAUDE.md 里"看不懂这场球所必需的来路→一句带过，别展开"的实现样例——`shang-rublev` 那段在 spec 里明确写着"伤停只留一句带过（第 ② 屏）"。

---

## 附：统计数字汇总（脚本输出原值）

```
reel specs: 113
含 editorial: 79（mode 全部 = match_review）；无 editorial 旧格式: 34
human_context: angle/facts/sources（41）| +voice_label（38）
push 键: summary/lead 为主（+auto/_why 变体）
cover 键: eyebrow/hook/winner/result/layout/subject/topic/matchup/portrait/scrim/scoreboard（多数带 *_why）
segments 总数: 1572；带旁白: 1429；每条中位 12 段（min 5 / max 38）
旁白每段字数: 中位 28 / 均值 30.6 / min 3 / max 167（P10 15 · P25 21 · P75 36 · P90 49）
interview specs: 34；zh 字幕条 3076 条，每条中位 8 字（1-19）
含 human_quote: 6；含 takeaway: 26
cover.title 两行式: 25+ 条；cover 键: frame_at/title/sub/tag
xhs 文件: 146；话题标签恒为最后一行，median 1 行；26 个用 ①②③ 编号
```
