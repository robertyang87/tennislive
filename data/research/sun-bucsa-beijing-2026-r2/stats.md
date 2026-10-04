# 孙心然—布克沙 中网第二轮统计核验

核验UTC：2026-10-03T16:43:11.863539+00:00。资料均为本场 Xinran Sun（WTA335958）对 Cristina Bucsa（321158），未混入Lulu Sun或其他Sun球员。WTA Match LS041，TNNS75051548，FlashscoreKS24sykK。

## 比赛身份与口径

2026年10月3日北京中国网球公开赛WTA1000女单第二轮/R64，孙心然6–4、7–5胜27号种子布克沙。官方时长01:31:18；比分板展示1:31，不沿用Flashscore将两盘42/50分钟相加的1:32。HSBC Moon球场；中国/西班牙；即时排名孙心然582、布克沙35，27为种子不能当世界排名。下一轮为3号种子高芙（Coco Gauff），2024北京冠军。

[WTA完整比赛页](https://www.wtatennis.com/tournaments/china-open/scores/LS041)；[官方比赛记录API](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches)；[WTA官方赛报](https://www.wtatennis.com/news/4586072/sun-16-upsets-bucsa-in-beijing-zheng-advances-after-kalinskaya-retires)。中文名孙心然由身份代理实读中网[官方中文报道](https://www.chinaopen.com/cn/contents/281/1641.html)确认，用户口述孙欣然已纠正。

## 全场原始整数（孙心然／布克沙）

| 指标 | 孙心然 | 布克沙 |
|---|---:|---:|
| ACE |2|1|
| 双误 |4|1|
| 一发入球 |36/73（49%）|38/55（69%）|
| 一发得分 |26/36（72%）|25/38（66%）|
| 二发得分 |18/37（49%）|8/17（47%）|
| 破发点转化 |4/5（80%）|2/5（40%）|
| 总得分 |66|62|
| 制胜分，TNNS Match |13|17|
| 非受迫失误，TNNS Match |22|28|

核心整数直接来自[WTA官方stats API](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches/LS041/stats)中setnum=0，完整原始响应`official-full-and-set-stats.json`。WTA不提供W/UE字段，不能填0。W/UE来自正常公开可访问[TNNS统计API](https://api.tnnslive.com/v1/web?id=75051548&mode=match_info&submode=stats&web=true)，完整原始压缩响应`tnns-raw-stats-api.json`，解码`tnns-decoded-1.json`。API明确`data.period=Match`、Key Stats `players=[Sun,Bucsa]`、Winners `[13,17]`、Unforced Errors `[22,28]`。分盘W/UE相加也符合全场：首盘W8/6、UE10/12；次盘W5/11、UE12/16；没有拿分盘值替代全场。

[Flashscore全场及分盘feed](https://global.flashscore.ninja/2/x/feed/df_st_1_KS24sykK)与WTA核心值吻合，无W/UE。[Tennis.com](https://www.tennis.com/tournaments/china-open-wta/matches/x-sun-vs-c-bucsa-2026-10-03)二发排除双误分母33/16，显示55%/50%，与WTA含双误37/17的49%/47%不同；正式参数用官方口径，不混算。

## 比赛转折

首盘孙先2–0，布克沙回破追至2–2，随后各保发到5–4；孙在盘末破发6–4。次盘孙0–2落后后连赢三局3–2，随后各保发到5–5。5–5孙发球局面临30–40破发点，正手直线制胜球挽救，随后连得两分保发6–5；下一局正手穿越兑现赛点7–5。

WTA文字赛报和官方逐分[API](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches/LS041/point-by-point)共同支持5–5救BP及最终穿越。逐分原始`official-point-by-point.json`、关键局`official-point-keygames.json`已保留。121点为孙救5–5局BP，122/123连得保发；128点为结束。

## 不能略过的来源冲突

- WTA文字赛报说“first match point”；官方逐分最后局则124/125/126孙连得三分到40–0，127布克沙赢到40–15，128孙赢结束，等于第二次赛点兑现，TNNS亦标布克沙savedMP1。最终稿先不写第几个赛点；转播实画面复核前不能断言首赛点。
- 官方逐分总128点，但胜负逐点计数67/61，官方stats66/62；差异出在首盘逐分32/28对统计31/29。官方逐分的scoreAfterPoint.sets全部重复该盘最终盘分，也不能当每局比分读。全场整数采用官方stats，不从有差异的逐分反推。
- TNNS分盘核心部分错：首盘TotalPoints32/30合计62、破发4/7对3/3，与官方首盘31/29（60点）及2/2对1/2冲突；次盘Sun ACE1对官方0。分盘核心值只用官方API。TNNS Match核心所有本卡整数与官方一致，WUE有完整Match字段，作为单一完整WUE来源保存；若同场转播统计板有不同完整数据，整套复核替换，不能混抄。

## 官方分盘（只用WTA stats）

首盘42:13：孙ACE2、DF2，一发13/17，二发8/18，破发2/2，总分31；布克沙ACE0、DF0，一发10/15、二发5/10，破发1/2，总分29。

次盘49:01：孙ACE0、DF2，一发13/19，二发10/19，破发2/3，总分35；布克沙ACE1、DF1，一发15/23、二发3/7，破发1/3，总分33。

## 四类来源检索

官方stats/API和WTA赛后稿已成功取得200；同场Tennis.com编辑完整统计200；TNNS Match stats API200且WUE完整；Match Charting全量女子CSV与meta200，未列本场或XinranSun条目；不能因未列断言全网无。Flashscore同场ID和全场stats200，无WUE。Sofascore当日schedule403只记受阻。转播视频由另线程搜集，本代理没有冒称已核末尾统计屏。

`stats-spec.json`为正式参数片段，a=孙心然、b=布克沙，包含完整WUE证据、源哈希、日期和原始列序。本场无需任何省略豁免。不修改仓库、refs或已有作品。

## 排名、球场、北京时间的补核

布克沙35由[WTA官方球员页](https://www.wtatennis.com/players/321158/cristina-bucsa)服务器HTML内data-player-stats.ytd.singles.rank直接二核，解码`bucsa-official-player-stats.json`。孙心然582由官方同场赛报Currently ranked No.582核实。

HSBC Moon由本场Tennis.com和TNNS比赛metadata一致确认；WTA官方match API CourtID=3，网站Court显示空，无冒称该API直接提供HSBC Moon名字。

北京时间2026年10月3日晚：WTA match元数据MatchTimeStamp10:06:35.773UTC→18:06；官方逐分首点10:19:20UTC→18:19。两项差13分钟，因此采用自然时段，不报精确实际开赛分钟。
