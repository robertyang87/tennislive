# 郑钦文—卡琳斯卡娅：已进行部分的完整比赛统计

核验日期：2026-10-03 UTC。a=郑钦文/Qinwen Zheng，b=卡琳斯卡娅/Anna Kalinskaya。中网 WTA1000 第二轮/R64，官方 match `LS035`、source_id `1020_2026_LS035`；TNNS `75051538`；Flashscore `nXXM7mbt`。结果 **郑钦文 6-7(4) 6-4 3-0 Ret.**，卡琳斯卡娅退赛。下表的“全场”指退赛前全部已打部分；第三盘仅三局，不能称打完决胜盘。

可直接消费的研究参数：[stats-spec.json](stats-spec.json)。它没有改动仓库正式 spec；用本 worktree 的 `tools/winners_ue_gate.py` 验证，`problem(spec) = None`。若制作端改 `cover.result` 的退赛拼写，需同步 `_match.winner_result` 与 W/UE evidence 的 `winner_result`。

| 指标 | 郑钦文 | 卡琳斯卡娅 | 来源 |
|---|---:|---:|---|
| ACE | 13 | 3 | WTA setnum0 / TNNS Match |
| 双误 | 6 | 3 | 同上 |
| 一发进球 | 52/85，61% | 60/85，71% | 同上 |
| 一发得分 | 41/52，79% | 40/60，67% | 同上 |
| 二发得分 | 15/33，45% | 11/25，44% | 同上，分母包含双误 |
| 破发 | 4/6，67% | 1/6，17% | 同上 |
| 总得分 | 90/170，53% | 80/170，47% | 同上 + 官方170点逐分 |
| 制胜分 W | 51 | 15 | TNNS 原生 API `Match` |
| 非受迫失误 UE | 19 | 9 | 同一个 TNNS `Match` 来源 |

W/UE 原始字段位于 `tnns-stats-decoded.json → data.data.Match → title="Key Stats"`，`players=["Zheng","Kalinskaya"]`，`winners.values=[51,15]`、`unforced_errors.values=[19,9]`，外层 `data.period="Match"`。原始响应 `tnns-stats.txt`，SHA256 `3c6d1ea687f354bfb25728ab79cd055fb41575d4eaf7872c08e25970e00bf6ea`。HTTP200，2026-10-03T19:35:03.489843+00:00 取得。没有把分盘数据当全场，也没有将缺失值填0。

核心整数来源：
- [WTA 全场与分盘 API](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches/LS035/stats)，原文件 `official-stats.txt`。取 `setnum=0`。二发赢分=总发球赢分减一发赢分，二发总数=发球总分减一发进球数：郑56−41=15、85−52=33；卡51−40=11、85−60=25。
- [TNNS 原生完整统计 API](https://api.tnnslive.com/v1/web?id=75051538&mode=match_info&submode=stats&web=true)，原文件 `tnns-stats.txt`、完整解码 `tnns-stats-decoded.json`。
- [WTA 逐分 API](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches/LS035/point-by-point)，原文件 `official-pbp.txt`。170个 point，pointWinner A90/B80，支持全场总分；逐局摘录 `pbp-game-summary.json`。
- [WTA 赛果与时长 API](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches)，原始全响应 `initial-0.txt`、目标摘录 `official-target-match.json`。`MatchTimeTotal="02:22:02"`；官方比赛时长卡片可显示 **2:22**。

身份、球场与时间：
- WTA 官方球员简介实时数据：郑现排名 **54**（WTA328120）、卡现排名 **22**（WTA323942），摘录 `profile-zheng-stats.json`、`profile-kalinskaya-stats.json`。卡本场15号种子不是现排名15，郑本场WC。
- [郑 WTA profile](https://www.wtatennis.com/players/328120/qinwen-zheng)；[卡 WTA profile](https://www.wtatennis.com/players/323942/anna-kalinskaya)。排名原字段 `data-player-stats → ytd.singles.rank`。
- [TNNS 元数据](https://api.tnnslive.com/v1/web?id=75051538&mode=match&web=true)，`tnns-meta.txt`及`tnns-meta-decoded.json`：`match_card.strings.top_left="R64 · Capital Group Diamond"`。中文钻石球场。
- 官方 country 字段郑CHN、卡RUS；TNNS卡 country="Neutral"/空 flag、Flashscore卡World。因此 research spec 保留 WTA 官方国家代码 RUS；赛事参赛标识与国籍不要混为一谈。制作端如遵循赛事中立参赛旗帜规范需不显示 RUS 国旗，不能据 TNNS 空旗声称国籍未知。
- 官方 PBP 第一分 **08:10:31Z=北京时间16:10:31**，最后一分10:30:37Z=北京时间18:30:37；适合写“10月3日下午”。官方赛果的 MatchTimeStamp07:50Z以及TNNS15:55北京时间是元数据时刻，不能当实际开赛。无需精确播报首分秒数。

分盘统计文件 `set-stats-official.json` 使用官方 setnum1/2/3。首盘ACE8/2，次盘4/1，第三盘已打部分1/0。官方次盘总分34/29、卡0/3破发；不能换成 TNNS 次盘35/30、卡0/4。

逐局转折（比分均郑在前，官方 PBP）：
- 首盘先互保至3-3；郑第7局15-40连救两破发点保至4-3，第8局破至5-3；第9局发球胜盘局四分全失、被love break，5-4→5-5；各保至6-6，抢七4-7输首盘。没有首盘盘点可称浪费盘点。
- 次盘卡先保0-1；郑第2局15-40救两破发点保1-1。郑1-2后保至2-2，第5局接发两破发点未转化，2-3；郑保3-3，第7局破4-3；第8局30-40救一个破发点保5-3，卡保5-4，郑love hold收6-4。
- 决胜盘郑破1-0；官方报道此后卡申请MTO；郑love hold2-0，再破3-0后卡退赛。最后一分是第三局破发点，**不是比赛赛点/完成决胜盘的赛点**。
- [WTA 官方赛报](https://www.wtatennis.com/news/4586072/sun-16-upsets-bucsa-in-beijing-zheng-advances-after-kalinskaya-retires)支持：首盘2-2那局郑五个ACE、首盘5-3领先未收盘、次盘破至4-3、决胜首局后MTO。五ACE需素材另核，如旁白使用可注明官方赛报。

必须保留的冲突记录：
1. Flashscore `https://global.flashscore.ninja/2/x/feed/df_st_1_nXXM7mbt`（正常请求 header x-fsign SW9D1eZo），原文件 `flash-stats.txt`，全场总分91/81（172点）以及卡破发1/7，次盘35/30、0/4，与官方/TNNS Match/PBP90/80和1/6冲突。采用官方整数，不混合。
2. TNNS Match 与官方核心一致，但 TNNS分盘次盘总分35/30、卡0/4及首末发球分拆有缺失。分盘优先官方。TNNS Set3没有两人完整UE行，不拿缺失当0。
3. TNNS 元数据比赛时长 **1:16** 明显冲突；使用官方02:22:02，不沿用。
4. 初次核读将 WTA赛报“争取2-0”的主语误读为郑，已纠正：原文主语是卡琳斯卡娅，确实卡在郑0-1时拿到两破发点可争取2-0，与PBP相符。郑第2局救两BP→1-1；1-2后第4局仅丢一分→2-2，无BP；第5局开局2-2时郑接发拿两BP未转化→2-3。不能将两个不同球员/不同局的BP合并。

来源状态与原文 SHA256 见 `stats-source-manifest.json`，所有抓取均普通公开 HTTP200，没有登录或限制突破。
