# vibetennis EP12 抢七轮发：为什么是「一、二、二、二」· 资料包（2026-11-10）

> 所有者 2026-11-10 从选题库挑了 MAT-05「抢七 1-2-2-2 轮发与 Thue–Morse」，要求「一气呵成，不要再问我」。
> ✅ = 两个独立来源都读过原文且一致（或一个原文＋本仓库可复现的算式）；⚠️ = 单源，只定性说；❌ = 不用。
> 原文读过的：ITF《网球规则》2026 英文版 PDF（第 5、10 条）；Brams & Ismail 2018 预印本全文（MPRA 69714）；Cohen-Zada, Krumer & Shapir 预印本全文（IZA DP 10878）；
> Allouche & Shallit「The ubiquitous Prouhet-Thue-Morse sequence」全文；Sackmann 2015 博文全文；BBC 2019-07-14 赛报；Wikipedia「2019 Wimbledon men's singles final」源码；
> Inside World Football 2017-05-04、2018-11-23；Crossref 摘要：Apesteguia & Palacios-Huerta 2010 AER、Kocher, Lenz & Sutter 2012 Management Science、Palacios-Huerta 2012 Economic Inquiry、Brams & Ismail 2018 SIAM Review。

## 冲突（调研后定）
大家以为抢七「先发一分、之后每人两分」是为了公平——不让先发的人一路多发一个。**算一算：在「每分独立」的模型里，换成一人一分，输赢概率一模一样。**
真正让抢七公平的，是「净胜两分」：它让比赛的结果等于「把前 12 分全打完谁拿得多」，而这 12 分里两人各发 6 个；6 平之后每两分一组、两人各发一个。去掉它，先到 7 分就赢，先发的人就占便宜（不管哪种顺序）。
那「一、二、二、二」图什么？① 换手少（12 分里 6 次，一人一分要 11 次，Brams & Ismail 的原话）；② 如果「一直在追」本身会让人紧张（足球点球大战的争论），它让追的人轮流换——这是 Thue–Morse 序列的第一层。网球的真实数据：先发、后发的抢七胜率没有显著差别。

## 一、规则

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 抢七：轮到发球的人发第 1 分，对手发第 2、3 分，之后每人连发两分直到结束 | ITF《网球规则》2026 第 5 条 b（原文 "The player whose turn it is to serve shall serve the first point … The following two points shall be served by the opponent(s) … each player/team shall serve alternately for two consecutive points"） | Brams & Ismail 2018 第 5 节（"begins by serving once, followed by the other player then serving twice. Thereafter, the two players alternate, each serving twice"） | ✅ |
| 抢七每 6 分换一次场地 | ITF 2026 第 10 条（"During a tie-break game, players shall change ends after every six points"） | 同 PDF 附录不改此条；Brams 未提 | ⚠️→ 规则原文即一手，**上屏**（规则书本身就是规则） |
| 平时一局由同一人发，打完一局换发 | ITF 2026 第 14 条 Order of service | Brams & Ismail 2018 第 1 节 | ✅ |

## 二、2019 温网男单决赛（钩子）

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 德约 7-6(5) 1-6 7-6(4) 4-6 13-12(3) 费德勒 | BBC 2019-07-14 | Wikipedia「2019 Wimbledon men's singles final」 | ✅ |
| 总得分：费德勒 218、德约 204（费德勒多 14 分却输） | BBC 赛报数据表「Total points won 204 / 218」 | Wikipedia 统计表（引 wimbledon.com 官方统计） | ✅ |
| 三个抢七全被德约拿走（7-5、7-4、7-3） | BBC（"had won the match's previous two tie-breaks and he did so again"） | Wikipedia（"the only statistical categories Djokovic won … all the tiebreaks"） | ✅ |
| 第五盘 12 平打抢七：温网首次启用，这是第一场用上它的单打比赛 | Wikipedia（"the first final, as well as the first singles match, in which the new rule came into effect"） | BBC（"the new tie-break at 12-12"） | ✅ 片中只说「第五盘打到 12 平，用抢七决出冠军」，不说「史上第一」 |
| 发球赢分：德约 140/219＝64%，费德勒 139/203＝68.5% | Wikipedia 统计表：一发 136/219、101/136 胜；二发 39/83 胜；费德勒一发 127/203、100/127、二发 39/76 | BBC：一发得分 74% / 79%（与 101/136、100/127 一致）；总分 204/218 与「发球得分＋接发得分」反算一致 | ✅ 片中说「德约 64%，费德勒接近七成」 |

## 三、数学（模型：每分独立，发球方赢分概率固定）

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 两人一样强时，「一、二、二、二」先发者赢抢七的概率 = 1/2 | Brams & Ismail 2018 第 5 节（"equally skilled players have the same probability of winning under the Standard Rule"） | 本目录 `tiebreak_math.py`：p=0.65 → 0.5000 | ✅ |
| 一人一分（XY/XY…）同样公平——公平来自「每人发球次数相同」＋净胜两分，不是来自顺序 | Brams & Ismail 2018 第 6 节（"the strict alternation sequence XY/XY/XY/XY … [is] fair for the same reason that the tennis sequence, coupled with the Win-by-Two Rule, is fair"）；第 1 节 "primarily because of the alternation in serving and the Win-by-Two rule" | `tiebreak_math.py`：ABAB 0.5000；两人不一样强时两种顺序也逐位相同（0.662973 / 0.418383） | ✅ 片中「顺序根本没改变输赢的概率」限定在「这个模型里」 |
| 「补打不改结果」：6 平之前有人赢了，把前 12 分打完他仍拿到 7 分以上；反之亦然 → 6 平之前比的就是 12 分谁多 | 算术（拿到 7 分时对手 ≤5 ⇔ 12 分里 ≥7） | Brams & Ismail 第 5 节同一论证（"Because these scores sum to an even number (12), each player will have had the same number of serves"） | ✅ |
| 6 平之后每两分一组、两人各发一个，必须连赢一组两分才赢 | Brams & Ismail 第 5 节（"a player can win only by winning twice in a block—when it serves and when its opponent serves"） | `tiebreak_math.py` 序列（第 13、14 分：甲、乙） | ✅ |
| 去掉净胜两分、先到 7 分就赢：两人都赢 65% 的发球分时，先发者胜率 53.6%（两种顺序相同；最多 13 分，先发者发 7 个） | `tiebreak_math.py` | Brams & Ismail 第 5 节「6-5 落在一组中间，X 多发一个」的同一机制 | ✅ 留作算式；**11-10 第二版片中换成真实历史（见第七节）** |
| 12 分里换发球：一人一分 11 次，一、二、二、二 6 次 | `tiebreak_math.py` | Brams & Ismail 脚注 22（"maximizes the number of double repetitions … minimizes changeover time and thus the 'jerkiness' of switching serves"） | ✅ |
| 一人一分时，每到单数分先发者多发一个（后发者一直在追）；一、二、二、二时多发的人轮流换 | `tiebreak_math.py` 累计差序列 | Brams & Ismail 第 5 节（"being in the midst of this block puts X one serve ahead"）；Cohen-Zada 等引言（ABAB 造成不对称心理压力） | ✅ |

## 四、Thue–Morse

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 构造：从 0 开始，每次接上自己的反面：0 → 01 → 0110 → 01101001… | Allouche & Shallit 全文 Proposition 1 / 定义 | Palacios-Huerta 2012（摘要） | ✅ |
| 1851 年 Prouhet 的论文已隐含；1906 年 Thue 提出；1921 年 Morse 重新发现 | Allouche & Shallit 摘要原文 | Brams & Ismail 脚注 22（"originally proposed and analyzed by several scholars and is known as the Prouhet-Thue-Morse sequence"） | ✅ 年份只用 Allouche & Shallit；片中说「1851 年普鲁埃的论文里就藏着它」 |
| 经济学：两人轮流比赛，怎样排顺序才公平——答案之一是这条序列 | Palacios-Huerta 2012 *Economic Inquiry* 摘要 | Brams & Ismail 脚注 22（"taking turns taking turns taking turns"） | ✅ 片中说「经济学家用它回答……」，不说「证明了最公平」 |
| 网球顺序（甲乙乙甲甲乙乙甲…）前四位与它相同，第五位起不同 | `tiebreak_math.py` | 选题库 MAT-05 | ✅ |

## 五、足球点球大战（对照）

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 129 次点球大战，先踢一方约六成获胜（21 个百分点的优势） | Apesteguia & Palacios-Huerta 2010 *AER*（摘要：systematic first-mover advantage） | Kocher 等 2012 摘要（"They report a 21-percentage-point advantage … their sample of 129 shootouts"）；Inside World Football 2017（IFAB 会上通报 60%） | ✅ 片中说「赢了六成」 |
| 2017 年 IFAB 批准试行 ABBA，5 月欧洲 U17 锦标赛首用 | Inside World Football 2017-05-04 | ESPN「Germany win first ever ABBA penalty shootout」（搜索结果标题） | ✅ |
| 2018 年 11 月 IFAB 年度事务会议建议废除 ABBA、结束试验 | Inside World Football 2018-11-23（"abolishing the 'ABBA' format for penalty shootouts"；"IFAB is also ending trials"） | Euronews/Reuters 2018-11-22 标题「IFAB … gives thumbs down to ABBA」 | ✅ 片中说「2018 年又决定停掉」 |
| 样本扩大到 540 次，测不出显著的先踢优势 | Kocher, Lenz & Sutter 2012 *Management Science* 摘要 | Cohen-Zada 等引言（"using a significantly larger sample size"） | ✅ |
| 停掉的原因 | — | — | ❌ 不说（只有「太复杂」的二手说法） |

## 六、网球的真实数据

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 2012–2015 年「四个最高级别」赛事（原文 "all four top-tier tournaments"，72 站男子、135 站女子）的第一盘抢七：男子 1,701 个、女子 920 个（共 2,621）；先发对赢抢七没有显著影响，男女都一样 | Cohen-Zada, Krumer & Shapir 2018 *JEBO* 146:106（预印本全文 IZA DP 10878） | Sackmann 2015（不同样本，结论相近） | ✅ 片中说「2621 个抢七」「没有显著差别」 |
| ATP 5,200 多个抢七先发者胜 50.8%；WTA 2,500 个先发者胜 49.7% | Sackmann「Does Serving First in a Tiebreak Give You an Edge?」2015-10-14 | Cohen-Zada 等（同方向：无显著影响） | ⚠️ 单源（非同行评审），片中作为「另一份统计」并说明是博客统计；两个数都给，不挑 |

## 七、2026-11-10 补的数据与理论（所有者「找找足够多的数据和背后的理论」）

| 事实 | 出处 1 | 出处 2 | 状态 |
|---|---|---|---|
| 模型够不够真：每一分并不完全独立，赢了上一分、下一分发球胜率约高 1 个百分点（2015 四大满贯约 15 万分） | Kovalchik「Klaassen & Magnus's 22 Myths of Tennis — Myth 1」（on-the-t 博客，2016-02-14，读了原文） | Klaassen & Magnus 2001 *JASA* 96(454)（温网 1992–95 近 9 万分；摘要：「neither independent nor identically distributed … deviations from iid are small … good approximation」，经检索摘要转述，全文 403） | ✅ 片中说「大约高 1 个百分点，这点影响很小」 |
| 1970 年美网第一次在大满贯用抢七：9 分制、先到 5 分就赢（4 平一分定胜负），发球 2-2-2-3 | usopen.org 2020-09-02「The US Open introduced the tiebreak set 50 years ago today」（"alternating serves at 2-2-2-3"） | World Tennis Magazine 2024-07-19（Randy Walker：先发者发 2 分、对手 2 分、先发者 2 分，最后三分由第二个发球人发）；Wikipedia「Tennis scoring system」（1970 年美网起用九分制，用到 1974） | ✅ |
| 九分制下后发者发 5 个、先发者发 4 个；两人一样强、发球都赢 65% 时先发者胜率 45.7% | `tiebreak_math.py` 同法计算（序列 AABBAABBB，先到 5 分） | 与第三节「不看顺序、只看次数」的结论一致 | ✅ 片中标「按假设推算」 |
| 1975 年美网在球员的抱怨下换成 12 分制（净胜两分）抢七 | usopen.org 2020-09-02（"In 1975, the US Open finally gave in to the players' demands and replaced the sudden death tiebreak with the 12-point tiebreak"） | Wikipedia「Tennis scoring system」（"The seven-point tiebreaker format was introduced in 1975"） | ✅ 不说「为了公平」，只说「在球员的抱怨声里」 |
| 如果先后手本身影响得分，加赛（一球定胜负）阶段没有哪种循环顺序能绝对公平，Thue–Morse 也不行 | Lambers & Spieksma 2021 *IMA J. Management Mathematics* 32:411（全文） | Csató & Petróczy 2022 *J. Sports Sciences*（arXiv 2004.09225 全文：比较七种顺序，「ABBA|BAAB 最接近公平」，没有一种完全公平） | ✅ |
| 点球大战：1,623 次（顺序可查）先踢方胜 54.71%，p<0.0001 | Rudi, Olivares & Shetty 2020 *PLOS ONE* 15:e0243786（全文表 2） | Csató & Petróczy 2022 引用（「1635 penalty shootouts … 54.86%」） | ✅ 片中说「1600 多次，约 55%」 |
| 约 7,000 次点球大战、7.4 万脚：测不出先踢或后踢的优势，等效检验排除偏离 50% 超过 1.8 个百分点；冰球同样没有 | Pipke 2025 *J. Economic Psychology* 108:102816（IDEAS 摘要） | van Ours & van Tuijl 2026（Tinbergen DP 26-052，全文第 3 页综述：「around 7,000 penalty shootouts … no evidence of a first-mover advantage」） | ✅ 片中说「7000 多次，测不出区别」 |
| 另外几组：Palacios-Huerta 2014 扩到 1,001 次仍约 60.6%；Arrondel 等 2019（法国杯 239 次）、Santos 2023（663 次）、Csató & Petróczy 2026（268 次）均无优势；荷兰杯 1968–2007 年 63%、2008–2026 年 53% 不显著 | van Ours & van Tuijl 2026 综述与表 1 | Csató 2021 *4OR*（arXiv 1806.01114）综述 | ⚠️ 只进文案背景，不上屏 |
| 一盘、一场的胜率与谁先发球无关（每分独立的模型里） | Newton & Keller 2005 *Studies in Applied Math* 114:241（全文） | 选题库 MAT-04 已核 | ⚠️ 本集不展开（留给 MAT-04） |

## 不说
- 「1-2-2-2 是范阿伦（Van Alen）为了公平设计的」——没找到设计意图的原始出处
- 「ABBA 让抢七更公平」——模型里不改变概率；只说「换手少」「让追的人轮流换」
- 「足球停掉 ABBA 是因为太复杂」——二手说法
- 「Thue–Morse 被证明是最公平的顺序」——只说经济学家用它回答这个问题
