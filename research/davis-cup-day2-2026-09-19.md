# 戴维斯杯 2026-09-19 第二日：核过的事实

> 这一轮沙箱里 **flashscore / ITF tieCentre / daviscup.com / ESPN / StayLive 全被出口策略 403**
> （`local-global.flashscore.ninja` 等在 `recentRelayFailures` 里逐条记着）。所以下面每条
> 都不是从仓库常用的那几个接口取的，是**两个互相独立的编辑稿交叉核过**的，出处逐条写在后面。
> 真要写 spec 时，`_match` 仍然要按老规矩回 flashscore 拿 `flashscore_id` 和逐分再核一遍。

## 一、挪威 4-0 中国（世界一组 第一轮，特隆赫姆 Spektrum，室内红土）

| 场次 | 比分（中国视角） | |
|---|---|---|
| 第一日 单打① | 特日格乐 1-6 6-7(1) 鲁德 | 仓库已做 `ruud-te-davis-cup-2026-wg1` |
| 第一日 单打② | 崔杰 6-4 4-6 4-6 布德科夫-谢尔 | |
| **第二日 双打** | **张之臻/特日格乐 7-6(6) 4-6 6-7(2) 久拉索维奇/布德科夫-谢尔** | **这一场定了整条 tie** |
| 第二日 反轮单打 | 尼敦坚赞 2-6 0-6 鲁德 | |
| 第五场 | 取消（死盘） | |

**双打那一场的落点，两个源都写着**：中国队**决胜盘 5-4 领先时拿到过一个赛点**，没兑现，
最后 6-7(2) 输掉。挪威晋级明年 2 月的资格赛；**中国队明年上半年打世界一组附加赛保组**。

- 中文源：腾讯新闻「戴维斯杯世界一组中国男网0-4不敌挪威 无缘世界组总决赛资格赛」
  `https://news.qq.com/rain/a/20260920A031J300`（逐场比分、第五场取消、附加赛去向）
- 挪威源：VG「Norge videre i Davis Cup – avgjorde uten Ruud」
  `https://www.vg.no/sport/i/xro86p/norge-videre-i-davis-cup-avgjorde-uten-ruud`
  （双打 6-7(6-8) 6-4 7-6(7-2)、**5-4 那个赛点**、场馆 Trondheim Spektrum、
  鲁德本来留着打决胜单打、没用上）
- 首日 0-2 另有腾讯 `https://news.qq.com/rain/a/20260919A02V5E00` 印证
- 场地与阵容背景：lastwordonsports 赛前预测稿（室内红土、鲁德世界第 18、特日格乐 835）

⚠️ VG 写的是「3-0 晋级」，腾讯写的是「0-4」——**两个都对，只是时刻不同**：双打拿下时是 3-0，
打完那场反轮单打才是 4-0。别把这当成两个源打架。

⚠️ 译名：**久拉索维奇（Durasovic）两张表里都没有**，写 spec 之前要补进
`player_names_top500.json`（规矩见 CLAUDE.md「人名不要手打」）。其余六个都在表里。

## 二、捷克 3-2 美国（资格赛第二轮，布拉格）

| 场次 | 比分 | |
|---|---|---|
| 第一日 | 勒纳·钱 6-2 6-4 门西克 | 仓库已做 `mensik-tien-davis-cup-2026-q2` |
| 第一日 | 莱赫奇卡 6-4 6-4 谢尔顿 | 仓库已做 `lehecka-shelton-davis-cup-2026-qualifiers` |
| 第二日 双打 | 哈里森/克拉吉塞克 5-7 6-3 7-6(8) 帕夫拉塞克/里克尔 | 美国扳回，2-1 |
| 第二日 反轮① | 门西克 5-7 6-4 6-3 谢尔顿 | 2-2；门西克第一日输了这次赢回来 |
| 第二日 反轮② | 莱赫奇卡 6-3 7-5 勒纳·钱 | **捷克 3-2**，美国出局 |

美国明年初打资格赛第一轮。源：Inside American Tennis
`https://insideamericantennis.substack.com/p/2026-davis-cup-qualifying-second-410`
（day-2 逐场）＋ tennistourtalk `https://tennistourtalk.com/137552/...`（day-1 逐场）。

## 三、源片下载：22:54Z 那趟的报错是**限流**，不是 cookie 过期（2026-09-20 复核）

我第一轮看 run 35474565225（09-19 22:54Z）的日志，读到
`The provided YouTube account cookies are no longer valid` ＋ `Sign in to confirm you're not a bot`，
就下了「秘钥过期、只有账号所有者能换」的结论，**那是错的**。

判据是产物不是报错：**run 35477192677（23:50Z）的 `mode=cookies` 那一步是绿的**
（步骤 24「cookies — 只验 YouTube 还能不能下」，23:51:40→23:51:58 success），
而那一步是真去取 3 秒媒体流、再按 51200 字节的下限卡一道的，**同一份 secret 一个字没改**。

根因和处置全写在 `docs/youtube-cookies-refresh.md` 第 0 节：yt-dlp **分不出**
「这份 cookie 死了」和「这个机房这一阵子被限流」，两者打出同一句 WARNING。
那天 17:20 起连红四趟、什么都没改，五小时后自己好了。
**所以顺序是：先隔一个钟头重跑一次 `mode=cookies`，两次都红、而且中间换过 runner，
才轮到真去重导。** CLAUDE.md「排除了 A 和 B 不等于就是 C」是同一个形状，
这次多出来的第三个候选是「等一等」。

⚠️ 非 YouTube 的那条路（StayLive，`tools/staylive_bjk.py`，戴维斯杯 2026 频道
7078/7079/7080，集锦 720p 不锁地域）**这一轮没有接**，也不需要接——下载本来就是通的。

## 四、今天这条片子最后落在哪：**门西克 5-7 6-4 6-3 谢尔顿**（2026-09-20 定）

⚠️ **挪威 v 中国那场双打否掉了，两个互相独立的原因，任一个都足够：**

1. **官方没发这场双打的集锦。** 借 runner 上的 yt-dlp（沙箱够不着 YouTube，runner
   够得着）搜 `ytsearch8:Davis Cup 2026 Norway China doubles highlights Kjaer Durasovic`
   → `Downloading 0 items`（run 35478525370）。
   **空结果自证过**：同一条路子搜 `ytsearch5:Casper Ruud v Rigele Te Highlights…`
   是绿的、真下到媒体流（run 35478824827），所以方法没问题，零条是真的零条。
   而且**第二日的片子本身在发**——同一晚 ITF 官方频道挂了两条门西克对谢尔顿
   （`bXbK9H5f6fI` 完整集锦、`XTrJDT3G1cA` 最后二十分钟），所以不是「还没到时候」，
   是双打很少单独出片。
2. **这条线结构性地不支持双打。** 全库 206 条带 `cover.matchup` 的 spec
   **无一例外都是两个人**；`build_match_reel` 里的判据写着「`cover.matchup`
   必须包含两位不同球员，才能生成顶栏比分行」，`versus_poster` 的比分板、国旗、
   即时排名，以及 `stats.a`/`stats.b` 的单人头像全是照 1v1 建的。
   做双打是**功能改动**，不是写稿，这一轮没动。

**所以改做捷克对美国那条 tie 的第二日反轮单打**：门西克第一日刚 2-6 4-6 输给
勒纳·钱，回头 5-7 6-4 6-3 拿下谢尔顿把大比分扳成 2-2；谢尔顿两场单打全输。
源片 `https://www.youtube.com/watch?v=bXbK9H5f6fI`。

两个独立源：Inside American Tennis（day-2 逐场）＋ AP 经 local10
`https://www.local10.com/sports/2026/09/19/shelton-loses-again-in-davis-cup-as-czechs-level-series-with-us-zverev-wins-for-germany/`
（同样 5-7 6-4 6-3、布拉格、谢尔顿两连败、捷克进 Final 8）。

⚠️ **口径要交代**：这条不是中国球员，按选题优先级是第二档。中国队第二日只剩
鲁德 6-2 6-0 尼敦坚赞那场死盘，2 和 0 撑不起一条片子——**是今天做不了，不是没排**。
⚠️ 和已发的 `lehecka-shelton-davis-cup-2026-qualifiers` 不是同一场，但都带谢尔顿，
写的时候 `_no_repeat` 要认领：那条讲的是美网决赛五天后一次破发都没有，这条讲的是
第二场再输、美国出局。
