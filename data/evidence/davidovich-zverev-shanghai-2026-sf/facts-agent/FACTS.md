# 上海半决赛事实核实

本文件只核事实与统计；未查看用户源视频，不认领原声、剪辑时间码或画面覆盖。

- 身份：2026-10-17，ATP1000上海半决赛，Stadium Court，MS002；达维多维奇·福基纳5-7、6-4、6-3逆转兹维列夫。
- 时间口径：北京时间10月17日下午。官方赛程为不早于16:30，不冒称实际开球分钟。
- 排名：兹维列夫仍是世界第2，已提前锁定年终第一；不写“现世界第一”或“下周就登顶”。USTA10月15日报道最早11月2日升第1。达维多维奇赛前世界26、第25种子，赛后即时15；不要混淆种子与排名。

## 原生完整比赛统计

| 项目 | 兹维列夫 | 达维多维奇 |
|---|---:|---:|
| ACE | 18 | 5 |
| 双误 | 2 | 2 |
| 一发进球 | 75%（71/95） | 82%（68/83） |
| 一发得分 | 73%（52/71） | 85%（58/68） |
| 二发得分 | 46%（11/24） | 40%（6/15） |
| 破发 | 1/3 | 2/6 |
| 挽救破发点 | 4/6 | 2/3 |
| 总得分 | 82 | 96 |

原生接口由赛事官网 stats 页 hidden input 找到，响应200、MatchStatus F、Winner DH50，并有各盘分项。全部数值原件：`native-match-stats.json`；适配汇总：`verified-facts.json`。

## 主线与关键转折

1. 首盘达维多维奇第11局被破，兹维列夫7比5先赢一盘。AS明确11局；原生分盘只记一次破发。
2. 第二盘前九局保发，达维多维奇5比4领先时在接发局打出奔跑反拍穿越，以6比4扳平。官方报道确认穿越为扳平一拍，Cadena SER确认4比5兹维列夫被破，原生确认第二盘唯一破发。
3. 决胜盘开局兹维列夫双误送破发，达维多维奇取得领先。具体第几局、30-40等点比分须视频代理逐帧确认，不由本文补猜。
4. 达维多维奇5比2接发时错过两个赛点；随后自己发球结束，6比3。官网明确，须保留完整终局与反应。

补充：达维多维奇第2次进大师赛决赛，上次为2022蒙特卡洛（负西西帕斯）；对赛由1-6变2-6；中国赛场9连胜，本季首次胜前5、生涯第6次胜前5。只在主线有用时取用。

## 发现的冲突与取舍

- 耗时：官网新闻写2小时6分；同官网原生接口02:02:30、AS2小时2分。内部取原生，正片无须讲耗时。
- 一二发统计：Tennis.com页面部分分母及百分比与原生不符。ACE、双误、破发相同，其余使用完整原生接口，不拼接两个统计口径。
- 排名日期：部分媒体把已锁定年终第一说成当前/下周第一，与USTA当前第2、最早11月2日口径冲突。只用已锁定年终第一和当前第2。
- ATP主域 Hawkeye MS002、MS003、赛果、统计页均403，真实尝试见`http-attempts.json`及response。随后通过独立赛事官网正常页面发现其公开原生接口并取到200；未绕过访问控制。

## 来源

- [赛事官方本场报道](https://en.rolexshanghaimasters.com/en/media/news/zverev-davidovich-fokina-shanghai-2026-saturday)
- [赛事官方赛程](https://en.rolexshanghaimasters.com/en/scores/schedule)
- [赛事原生统计页面](https://en.rolexshanghaimasters.com/en/scores/match-stats/2026/ms002)
- [赛事原生完整统计API](https://en.rolexshanghaimasters.com/-/tournaments/matchStatsApi/MatchStats?year=2026&eventId=5014&matchId=ms002)
- [USTA官方排名报道](https://www.usopen.org/amp/en_US/news/articles/2026-10-15/alexander_zverev_clinches_year-end_no_1_ranking.html)
- [AS本场过程](https://as.com/tenis/masters_1000/davidovich-acerca-el-sueno-de-una-final-espanola-f202610-n/)
- [Cadena SER本场过程](https://cadenaser.com/nacional/2026/10/17/davidovich-desmonta-a-zverev-para-pasar-a-la-final-de-shanghai-en-el-mejor-partido-de-su-carrera-cadena-ser/)
- [Tennis.com交叉核对](https://www.tennis.com/tournaments/rolex-shanghai-masters/matches/a-zverev-vs-a-davidovich-fokina-2026-10-17)

## 后续补齐：制胜分与非受迫失误

Flashscore本场 `rZ1iEDSa`，原始主/客明确为Zverev A./Davidovich Fokina A.；全场发球、破发与总分均和官方MS002一致。

| 项目 | 兹维列夫 | 达维多维奇 |
|---|---:|---:|
| 制胜分 | 28 | 36 |
| 非受迫失误 | 20 | 21 |
| 第一盘制胜分 / UE | 10 / 6 | 14 / 11 |
| 第二盘制胜分 / UE | 12 / 8 | 10 / 5 |
| 第三盘制胜分 / UE | 6 / 6 | 12 / 5 |

逐盘合计全部等于全场。原始feed：`fs-match-stats-raw.raw`；解析：`flashscore-full.json`；身份：`fs-match-identity.raw`、`flashscore-current-match-identity.txt`；已完成状态与盘局摘要：`fs-match-summary.raw`。

可直接复制 `spec-ready-stats-zverev-first.json` 的统计块，已按 **a=兹维列夫、b=达维多维奇** 摆放；赢家及赢家比分仍为达维多维奇5-7 6-4 6-3，不随列序倒置。证据单独在`winners-ue-evidence.json`。

TNNS当天API在本地返回403Forbidden，真实响应和尝试已保存，不继续此站绕行；本场制胜分/UE的来源明确写Flashscore，不冒称TNNS结果。
