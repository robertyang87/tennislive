# 一场比赛的走势 · 关键分 · 集锦，从哪儿拿

> 2026-07-27 从沙箱逐条实测的结果，附状态码。**没实测过的不写进这张表**——
> 上一轮就是拿"记得有这么个接口"排过优先级，结果全是 401/403。

## 一句话结论

| 要的东西 | 现在拿得到吗 | 走哪条路 |
|---|---|---|
| WTA 巡回赛逐分（走势 + 关键分） | ✅ 免鉴权，当天就有 | `api.wtatennis.com` 的 `point-by-point`，见 `tools/fetch_match_pbp.py` |
| 四大满贯逐分 | ❌ | WTA 那条接口对大满贯一律 404；赛会自己跑计分系统 |
| ATP 巡回赛逐分 | ❌ | 三条路今天全堵（见下） |
| 拍数 / 球速 / 落点 / 击球类型 | ⚠️ 部分 | Match Charting Project（志愿者标注，滞后约两个月） |
| 集锦 | ✅ | 官方 YouTube 频道，`yt-dlp` 直接列 |

## 一、WTA：官网自己的逐分接口，免鉴权

```
https://api.wtatennis.com/tennis/tournaments/{eventId}/{year}/matches/{matchId}/point-by-point
```

实测（2026-07-27）：

| 场次 | 结果 |
|---|---|
| 华盛顿 R1 Cocciaretto–Tauson `1045/2026/LS025` | 200，243 分 |
| 华盛顿 R1 Kasatkina–Smith `1045/2026/RS005` | 200，183 分 |
| 华盛顿 R1 Navarro–Kenin `1045/2026/LS024` | 200，152 分 |
| 罗马 125 决赛 Bronzetti–Brancaccio `1130/2026/LS003` | 200，181 分 |
| 罗马 125 双打 `1130/2026/LD005` | 200，90 分 |
| 温网女单决赛 Muchova–Noskova `904/2026/LS72320496` | **404** |

**当天就有**：华盛顿首轮 UTC 18:13 打完，同一天就能拉到完整逐分。**双打也有**。

每一分给这些字段：

```json
{"pointNumber": 1, "setNumber": 1, "gameNumber": 1, "server": "A",
 "pointWinner": "A",
 "scoreAfterPoint": {"sets": [...], "gameScore": {"teamAScore": "15", "teamBScore": "0"}},
 "timestamp": "2026-07-18T14:13:04Z"}
```

够算出来的：累计得分差折线（走势图）、每一局的发球方与胜方、保发/被破、
破发点局面、最长连得分、每分的真实时刻（能算出"这一局打了十一分钟"）。

**算不出来的**：拍数、球速、落点、正反手、主动失误/制胜分。这些字段接口里没有。

### 坑，一个都不能少

- **`ScoreString` 是赢家视角，不是 A 视角。这条最要命，会把赢家写反。**
  华盛顿资格赛 `RS008` 的 A 是**张帅**，`ScoreString` 写着 `6-4,1-6,6-1`——
  照着念就成了"张帅先下一盘、最后 6-1 拿下"。可同一条记录里
  `ScoreSet1A=4 / ScoreSet1B=6`，逐分数出来局数是 4-6 / 6-1 / 1-6，
  最后一分归 B：**实际是克努特松赢的，张帅输了**。
  谁赢一律看 `pointWinner` 或 `ScoreSetNA/B`，别读 `ScoreString`
- **一局的赢家要看这一局最后一分，不能盯 `gameScore` 里的 `G`**。
  抢七局根本不出 `G`（比分一路是 `7-2` 这样的数字），盯 `G` 会把整个抢七局丢掉，
  7-6 数成 6-6。Cocciaretto–Tauson 那场两盘抢七，一开始就数错了
- **`scoreAfterPoint.sets` 不是"打到这一分时的盘分"，是那一盘的终局比分**。
  第 1 分就写着 `6-4`
- **双打逐分一分都不写发球方**（`server` 全是空串，实测三场 144/111/121 分全空）。
  保发、破发、破发点在双打上**算不出来**——工具要说"算不出来"，
  不能照样印 `0/0`，那读起来是"一次都没被破"
- 单打也有空的：**抢七局的 `server` 是空串**，保发统计要跳过
- **破发点要按发球方视角判**（0/15/30-40、40-AD）。直接比 teamA/teamB 会串边
- **进行中的比赛，逐分落后实时比分好几分钟**。实测：比分那条记录 `LastUpdated`
  已经走到 `00:23`、盘分从 3-4 变成 4-4，三场比赛的逐分却一起卡在 `00:16:5x`，
  连拉 275 秒纹丝不动。**赛后拉是完整的，别拿它做直播**
- **大满贯不在这条路上**。同一个 eventId 下 `/stats` 有（只有 `setnum=0` 一行汇总），
  `/point-by-point` 404。这是"这条路对大满贯不通"，不是"这场没数据"——
  两条都试过才敢这么写

## 二、ATP：三条路今天全堵

| 路 | 状态（2026-07-27） |
|---|---|
| `api.protennislive.com/feeds/...` | **401**，要 Tournament Claims token |
| `atptour.com/-/Hawkeye/MatchStats/Complete/...` | **403**，Cloudflare |
| `itp-atp-sls.infosys-platforms.com/...` | **403** |
| 真 Chromium 走 `tools/probe_atp_browser_stats.py` 那条 | **过不去**：Turnstile 挂了 150 秒没放行，连 `results-archive` 都没清掉 |

`probe_atp_browser_stats.py` 的注释里记着 2026-07-25 这条路是通的，两天后就不通了
——**这条路是看运气的，不能写进日更流程**。而且它拿到的也只是**逐场汇总**，
ATP 从来没有公开过逐分。

### ATP 拿不到逐分，但赛报要的骨架有两条路

**逐分和发球统计确实没有**，可"这场发生了什么"不是只有逐分能讲。以锦织圭 d. 商竣程
（2026-07-27 华盛顿首轮）为例，这两条实测都通：

| 源 | 拿到了 |
|---|---|
| **赛事自己的站点** `mubadaladcopen.com/en/scores/mens-results` | 服务端渲染，**ATP 官网那层 Cloudflare 拦不到这里**。轮次、球场（John Harris）、**用时 02:31:36**、双方的参赛身份（锦织圭 `(WC)` 外卡、商竣程 `(PR)` 受保护排名）。页面上那个 `Match Stats` 链接是**空的**，技术统计没公开 |
| **TennisExplorer** `tennisexplorer.com/match-detail/?id=…` | 完整交手记录（这场之后 3-2）、逐年胜负、分场地战绩。**没有发球统计**（`Aces` 在页面上出现 0 次） |

赛事官网这条和「赛事官方图库按命名规律直接探」是同一个道理：**ATP 总站封，
办赛的自己的站反而是通的**。以后 ATP 场次的赛报，先去这一站的官网翻。

其它试过的：

- **SofaScore**（`api.sofascore.com` / `api.sofascore.app` / `www.sofascore.com`）
  三个域名全 **403**。它的 `/point-by-point` 和 `/graph` 是最好的第三方走势源，
  但对数据中心 IP 一律封，GitHub Actions 同样风险
- **ESPN** `site.api.espn.com/.../tennis/{atp,wta}/scoreboard`：200，但只有
  `linescores`（含抢七小分），没有逐分、没有 `plays`。够做"逆转/抢七/爆冷"的
  戏剧性检测，不够写走势
- **Sportradar Tennis v3**：付费，`/matches/{id}/timeline.json` 有逐分，
  两个巡回赛和大满贯都覆盖。仓库里 `sources/sportradar.py` 已经接好了统计部分，
  逐分要另写。这是目前**唯一能同时覆盖 ATP 和大满贯**的路

## 三、拍数/落点这一层：Match Charting Project

`JeffSackmann/tennis_MatchChartingProject`（raw.githubusercontent 可达，实测 200）：

- `charting-m-matches.csv` 男子 **7566** 场，最新 20260521
- `charting-w-matches.csv` 女子 **4080** 场，最新 20260524
- 2026 年男子 184 场、女子 205 场
- `charting-{m,w}-points-2020s.csv` 是逐分，带击球编码：
  `4b37y1r3n#` 这样一串记的是发球落点、每一拍的拍面和方向、怎么结束的

**志愿者标注，所以两件事要认**：只有被人标过的比赛才有（大牌和大场次优先），
而且**滞后**——7 月底能拿到的最新一场是 5 月底的。写当天赛报指望不上，
写"这些年"类的片子很有用。

同一账号下的 `tennis_atp` / `tennis_wta` / `tennis_slam_pointbypoint` 三个仓库
**本环境取不到**（`master`/`main` 分支、多个路径、仓库首页都试了，全是 404/403）。

## 四、集锦

官方频道逐场发，`yt-dlp --flat-playlist` 直接列，实测都通：

| 频道 | 实测拿到的 |
|---|---|
| `@atptour` | `Taylor Fritz vs Zizou Bergs Highlights \| 2026 DC Open Round 1`（2 分 21 秒） |
| `@TennisTV` | `Luca Van Assche vs Alexander Blockx For A First ATP Title! 🏆 \| Estoril 2026 Final Highlights`（8 分 14 秒） |
| `@wta` | `Emma Navarro vs. Sofia Kenin \| 2026 Washington, DC Round 1 \| WTA Match Highlights`（7 分 50 秒） |
| `@Wimbledon` | `An ICONIC battle \| Stan Wawrinka v Matteo Berrettini \| Full Match Replay \| Wimbledon 2026` |

**男子赛事的集锦看 `@atptour`，不是 `@TennisTV`。** 华盛顿开打当天，
`@atptour` 已经发了三条 DC Open 首轮集锦，而 `@TennisTV` 最新的还停在上一周的
埃斯托里尔和基茨比厄尔——一条华盛顿都没有。只盯 Tennis TV 会得出"集锦还没出"
的错误结论。**同一场的集锦也不是打完就有**：锦织圭那场结束两小时后仍未上架，
排在当天更早结束的几场后面。

**标题本身就是四要素自证**——球员、赛事、年份、轮次都由发布方自己写在标题里，
不靠看画面推断。和赛事官方图库按命名规律探图是同一个道理。

仓库里已经有一套现成的频道扫描器（`tools/collect_oncourt_interviews.py` +
`data/oncourt_sources.json`），采访和集锦走的是同一条管子，换一组频道和
标题规则就能用。注意 `scan()` 里那条：**一条都没取到时只能报"疑似句柄错"，
不能报"这个频道没有"**。

## 五、所以赛报怎么写

1. **WTA 场次**：`tools/fetch_match_pbp.py` 出走势和关键分，
   `sources/official_stats.py` 出逐场技术统计，两份拼起来就够了
2. **ATP 场次**：目前只有比分级数据（ESPN linescores + 赛会赛果）。
   要走势得上 Sportradar，或者接受"这一场不做走势图"
3. **大满贯**：两个巡回赛的接口都不覆盖，同样落到 Sportradar 或人工
4. **集锦**：官方频道抓链接，不搬运
