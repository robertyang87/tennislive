# 佩古拉：美网之后与年终资格独立复核

核对截止：2026-10-22T05:28:49.778988+00:00。本表只记录真实已完成比赛与已公布的状态；退赛和未来报名不进入“实际参赛16站”、场次胜负或积分求和。

## 年终官宣

- 确证公示日为**2026年10月14日**，连续第五年入围。[WTA公告](https://www.wtatennis.com/news/4591678/jessica-pegula-and-coco-gauff-qualify-for-wta-finals-in-indian-wells)正文写Wednesday。
- [WTA官方X](https://x.com/WTA/status/2110339830022385710)创建于**10月14日11:59:58 UTC＝武汉当地/北京时间19:59:58**，公开syndication原文、官方海报均已保存。
- WTA网页/API的datePublished是10月14日10:00 UTC＝北京时间18:00；publishFrom却是10月13日13:33 UTC。后台字段与对外日期不一致，不能把18时或publishFrom称作最早实际公示时间。使用“北京时间10月14日，WTA正式公布”即可。
- **最早数学锁定时刻、哪一场触发锁定，均未证实。**不能写她击败奥斯塔彭科拿到门票；当天比赛是失利。

## 美网之后真正打了什么

新取官方player API共76条，仍只见美网后的**武汉一场已完成单打**，首轮轮空不计胜场。10月14日第二轮（她的首秀），佩古拉**6-2、6-7(7)、3-6负奥斯塔彭科**。

[官方赛事API](https://api.wtatennis.com/tennis/tournaments/1075/2026/matches)LS031的MatchTimeStamp为10月14日08:06:33 UTC＝武汉/北京时间16:06:33；LastUpdated10:46:27 UTC，不称作精确完赛时刻。当地比赛日与北京时间均为**10月14日**。

[官方赛报](https://www.wtatennis.com/news/4592311/in-the-moment-ostapenko-saves-three-match-points-stuns-pegula-in-wuhan)确认第二盘抢七三个赛点：①空场简单截击下网；②对手二发形成service winner化解，不能直接叫Ace；③对手在多次左右调动后使出全场唯一一次放短直接得分。赛报没写三个赛点的各自小分，不能由最终7-6(7)反推坐标。官方嵌入[WTA Instagram候选](https://www.instagram.com/reel/DeeNRKSR_sC/)尚未解码，不批准画面覆盖或时码。

[WTA10月20日专题](https://www.wtatennis.com/news/4592575/wta-finals-is-all-about-consistency-how-jessica-pegula-turned-her-once-worst-trait-into-her-best)明确写全季**50-14**；profile50-13与武汉前记录一致，不能覆盖最新一负，也不确定后台不同步原因。

## 退赛与尚未开赛

独立可合表canonical文件为[withdrawals-upcoming.json](withdrawals-upcoming.json)，另有可读[withdrawals-upcoming.md](withdrawals-upcoming.md)。

| 赛事 | 已确认状态 | 官方报道口径（UTC／北京） | 原因边界 |
|---|---|---|---|
| 新加坡 | 赛前退出 | 9/16 13:16／9/16 21:16 | 本人IGStory由WTA引述：美网后身体消耗大、尚未恢复到要求的竞争水平；没有具体诊断 |
| 北京 | 赛前退出 | 9/25 21:41／**9/26 05:41** | 伤势未说明；左腕伤是阿尼西莫娃，不是佩古拉 |
| 宁波 | 赛前退出，10/16指南已列Withdrawals | 10/16 13:30／10/16 21:30 | 没公布原因；illness括号只跟卡林斯卡娅 |
| 东京 | 10/26才开赛；初始10/1名单含她，但**10/22最新WTA名单已无她** | 尚无她的新赛果 | 没拿到正式退出公告、决定时间或原因，不保证她仍会参赛 |
| 年终 | 已获资格，11/8–11/15尚未进行 | 官宣10/14 | 不预写年终战绩，不声称赛季已结束 |

上表的报道时间不等于退赛决定的精确时间。新加坡原IGStory仅由WTA描述为周二晚，缺原帖时区，不能擅自换算成北京时间某日某时。

10月11日UTC的[武汉复出报道](https://www.wtatennis.com/news/4590642/back-to-normal-pegula-ready-for-late-season-push-in-wuhan)说她healthy again/back to normal；北京时间已是10月12日03:22。这只适用于武汉前状态，不能据此解释后来宁波退赛。

## 证据与未知

所有原始API、页面、官方X元数据、海报、官方PDF已保存在raw/，逐份SHA256与来源见[raw/manifest.json](raw/manifest.json)。东京赛事自站两地址HTTP502，失败原文保留；公开X/IG检索没有找到可支持东京具体退赛原因的声明，不能把没取得声明写成不存在。未修改共享Git或主spec。
