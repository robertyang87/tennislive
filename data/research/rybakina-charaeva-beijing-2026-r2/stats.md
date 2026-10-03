# 莱巴金娜—查拉耶娃 中网R64独立核验

核验UTC：2026-10-03T17:46:13.329327+00:00。独立研究；未修改孙心然作品、repo或refs，未渲染/发布。

## 身份与背景

2026年10月3日晚北京WTA1000女单第二轮/R64，24岁、世界118位查拉耶娃（AlinaCharaeva，ARM亚美尼亚）3–6、6–4、6–3逆转27岁、新世界第一莱巴金娜（ElenaRybakina，KAZ哈萨克斯坦）。WTA官方LS032、TNNS75051532、Flash0Epw9iu2，官方2:11:50，封面展示2:11。球场CapitalGroupDiamond（首创集团钻石球场），下一轮首次对阵SonayKartal（卡塔尔）。排名1/118、国籍、出生日期1999-06-17/2002-05-27由官方球员profile直接核验；莱巴careerNo1达成日期14Sep2026。

元数据MatchTimeStamp12:24:16.1UTC=北京时间20:24，官方首点12:40:06UTC=20:40，末点14:51:25UTC=22:51。开头写北京时间10月3日晚；元数据与首点差16分钟，不报精确实际开球时间。

[WTA官方赛报](https://www.wtatennis.com/news/4586105/charaeva-upsets-new-world-no-1-rybakina-in-beijing-second-round)；[官方MDS](https://wtafiles.wtatennis.com/pdf/draws/2026/1020/MDS.pdf)；[官方QS](https://wtafiles.wtatennis.com/pdf/draws/2026/1020/QS.pdf)。MDS第4行Charaeva未标Q，QS不列她，官方eventplayers.entryType空；中网中文1640称“资格赛球员”与这些官方draw证据冲突，稿里不称资格赛选手。TennisMajors图片字幕旧称Russia也不替代本场WTA国家ARM；WTAprofile国籍Armenia、官方matchcountryARM、FlashArmenia、ReutersRussian-bornArmenian均支持ARM。

## 全场完整整数（官方原始列序莱巴／查拉）

| 指标 | 莱巴金娜 | 查拉耶娃 |
|---|---:|---:|
| ACE |3|6|
| 双误 |7|4|
| 一发入球 |53/93（57%）|50/78（64%）|
| 一发得分 |32/53（60%）|38/50（76%）|
| 二发得分 |20/40（50%）|9/28（32%）|
| 破发点转化 |4/6（67%）|5/8（63%）|
| 总得分 |83|88|
| 制胜分，TNNS Match |33|17|
| 非受迫失误，TNNS Match |48|17|

核心全部来自[WTA官方stats setnum0](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches/LS032/stats)，TNNSMatch与Flash核心原始整数一致。WTAstats没有W/UE字段，来自[TNNS真实公开完整API](https://api.tnnslive.com/v1/web?id=75051532&mode=match_info&submode=stats&web=true)，原始响应`tnns-raw-stats-api.json`、解码`tnns-decoded-2.json`。TNNS明确`data.period=Match`、KeyStats.players=[Rybakina,Charaeva]、winners=[33,17]、unforced_errors=[48,17]。TNNS元数据/日feed却winner-first Chara/Ryb，不能把那个顺序套入stats。

TennisNow同场报道给W30/16、UE48/17。UE可双源支持，但W存在差异，统计卡完整采用TNNS那一套，不混抄。Tennis.com一发入球55/93和54/78、二发剔双误分母32/21，与官方及TNNS/Flash不同，因此核心采用官方。

## 转折与逐局

首盘按查拉／莱巴列序：查拉开局破1–0，莱巴立即回破1–1；双方各保至2–2，莱巴连下两局使查拉2–4落后；查拉回破3–4，莱巴再破使查拉3–5，随后莱巴lovehold，以6–3收盘。官方新闻说开局莱巴4UE；5–3破发收尾反手接发制胜。统计首盘Ryb3/5破发、Chara2/3，与官方逐分破发局一致。

次盘按查拉／莱巴列序：查拉先保1–0，莱巴保1–1并破发使查拉1–2落后；查拉立即回破2–2。随后各保至查拉5–4，她在第10局30–40的破发点以反手穿越拿下6–4（具体球型官方赛报明确，应与视频画面再匹配）。

决胜盘查拉先保1–0，莱巴2–1落后时发球救一次BP保2–2。查拉保3–2后，莱巴反手出界遭破到查拉4–2；查拉lovehold巩固5–2，莱巴保5–3，查拉发球胜赛6–3。官方逐分169点=莱巴15/查拉40，170莱巴赢到30/40，171查拉赢结束。稿不必强调第几个赛点，待实际片尾比分核对。

逐分全部保存`official-point-by-point.json`，关键局`official-point-keygames.json`。逐点胜者计数84/87与官方stats83/88差1点，差异仅首盘37/24vs36/25；其次盘25/31、决胜22/32一致。逐分scoreAfterPoint.sets重复最终盘分，不能当每局动态局分。本报告逐局比分是按每局winner累计，并与官方赛报交叉。全场数值只用stats。

## 易懂且有来源的旁白数字

查拉一发得分38/50=76%，莱巴32/53=60%；莱巴UE48、查拉17两源一致。数字说明本场稳定性差异，不单凭这些统计给具体回合编球路或擅推受伤因果。查拉决胜盘UE1属于分盘，不能冒称全场1。

## 历史口径（全部保留限定）

1. 据WTA统计，莱巴金娜为第2位在世界第一身份首场单打失利的球员；第1位大阪直美2019Dubai负Mladenovic。官方首段逐字onlyone...Makeittwo；TennisMajors同场二核。不能改称世界第一历史第二次输球。
2. 据WTA统计，自1975年排名公布起，查拉为第9位排名Top100外击败当时No1的球员。统计的是球员数，不是第9场冷门。
3. 据WTA/Reuters/OptaAce统计，她为1975年以来排名最低的先丢一盘后逆转世界第一者。必须保留先丢一盘/逆转限定，不能缩成排名最低击败No1。

此外WTA写她第17场巡回赛正赛、首次对Top10即胜、首次WTA1000进第三轮、之前最佳排名胜利No31王欣瑜。这些为官方报道口径，未独立枚举其全部生涯赛历。

[Reuters经StraitsTimes](https://www.straitstimes.com/sport/tennis/rybakinas-first-match-as-world-number-one-ends-in-china-open-defeat-by-charaeva?ref=latest)支持最低排名逆转No1及Russian-bornArmenian；[TennisNow](https://tennisnow.com/armenias-charaeva-ranked-118-stuns-no-rybakina-in-beijing/)引用OptaAce，并提供48/17UE；[TennisMajors](https://www.tennismajors.com/wta-tour-news/no-118-charaeva-stuns-rybakina-in-her-first-match-as-world-no-1-862445.html)支持第2位No1首战失利。

## 交付与边界

`match-packet.json`包括country/rank/age/round/court/time/next、历史具体来源与冲突。正式消费`stats-spec.json`为赢家a=查拉,b=莱巴；`stats-spec-winner-first.json`同为赢家优先；`stats-spec-official-order.json`保留官方原序a=莱巴,b=查拉研究备份，两者WUE证据保留原始Ryb/Chara列序供闸门映射。尚无头像；不修改已有作品、不渲染/发布。

官方/API、编辑稿、TNNS已实取200；MCP全量女子CSV/meta200未列本场（不能宣称全网不存在）；FlashMatchstats200无WUE。国际视频代理正在核同场YouTube源，本代理未冒称已目视转播全场统计板。
