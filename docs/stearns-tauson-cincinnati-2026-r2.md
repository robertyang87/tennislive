# 陶森 7-6(7) 1-6 7-5 斯特恩斯（辛辛那提 2026 女单第二轮）

**这条还没写 spec。** 缩略图墙和切点已经落库（`output/2026-08-16/reel/stearns-tauson/`），
下面是已经查证过的全部事实——**下一次做这条片子直接从这儿接着走，别重查**。

## 为什么这条够格做

按 CLAUDE.md「没话题、排名又不高的，不做」那道闸，**两个条件占一个就行**：

- **排名够高**：陶森是本站 **27 号种子**（记分条整场烧着 `C. TAUSON [27]`，
  WTA 官方 `ResultString` 写作 `[27]C. Tauson d P. Stearns`）。和今天已发的
  `navarro-kalinina`（25 号种子）同一档
- ⚠️ **它不是 `boulter-volynets` 那个「数据反常不是话题」的坑**：那条是世界第 71
  对第 89、两个人都没话题；这条一边是种子，另一边是**美国本土球员在美国主场**
  （WTA 官网标题原话 `home favorite`）

## 源片

    https://www.youtube.com/watch?v=8dDecMRVlkw
    WTA 官方频道（oEmbed 的 author_name = WTA）
    Peyton Stearns vs. Clara Tauson | 2026 Cincinnati Round 2 | WTA Match Highlights
    1920×1080 · 25 fps · **381.48 秒**

⚠️⚠️ **超过 310 秒，尾巴上挂着场上采访——整段不进片子（画面和原声都不收）。**
边界是量出来的，不是推的：

| 时刻 | 画面 |
|---|---|
| ~262s | 赛点落地（解说 `It was just one step too far. Match point.`） |
| 278.5 / 280.5s | 网前握手（夜场，泛光灯） |
| 292.5–296.5s | `CONGRATULATIONS!` / `WTA 1000` / `CLARA TAUSON` 图形 |
| **298.5s** | 全屏赛果台标 `ROUND 2 / PEYTON STEARNS 6 1 5 / CLARA TAUSON 7 6 7` |
| **300.08s** | ⚠️ **采访提问第一句**（`>> 4-1 in the third, but you mustered up enough energy…`） |
| 300.5s 起 | 画面已经是采访（主持人 + 陶森手持 WTA TOUR 话筒，背景 `CLARA TAUSON`） |
| 371.36s 起 | WTA 片尾订阅卡 |

**所有窗口收在 295.5 秒以内**（`scene_cuts` 在 **295.64** 有一刀，正好是干净的边界）。
⚠️ 295.64 之后到 371.36 之间**探不到切点**（阈值 0.35 没认出「走动 → 图形卡 → 采访」
这几刀），所以**不能靠切点兜底**，必须按上面这张表手动卡死。

## 这场球是什么形状

WTA 官网自己的标题就是落点：

> **Tauson flips 4-1 deficit in decider to oust home favorite Stearns**
>
> Clara Tauson closed out Saturday's slate in Cincinnati with a thrilling
> 7-6 (7), 1-6, 7-5 win over American Peyton Stearns, coming from 4-1 down in
> the third before emerging from a 2-hour, 50-minute battle.

**两次被逼到墙角，两次翻回来**：

| | 落后到 | 结果 |
|---|---|---|
| 第一盘抢七 | **二比五**（记分条 126.5s：`STEARNS 6\|5 / TAUSON 6\|2`；144.5s 是 5-3） | 9-7 拿下 |
| 决胜盘 | **一比四**（逐分：1:0 2:0 2:1 3:1 4:1 → 之后七局赢六局） | 7-5 拿下 |

抢七回合在记分条上一路可读：7-7（156.5s `TIE BREAK`）→ 8-7 陶森（162.5–180.5s
`SET POINT #4`）→ 9-7。

⚠️ **「斯特恩斯手握三个盘点」这句话先别写。** 逐分算出来她在 6:3 领先（需要 1 分，
之后连丢三分），推出来是三个盘点；**可记分条的 `SET POINT #N` 徽标编号对不上**
（6-7 时显示 `#3`、7-8 时显示 `#4`，若斯特恩斯真有三个，陶森的第一个该是 `#4`）。
两个源打架，按 CLAUDE.md「全称断言要两个独立源」这条**不许印**。
**能印的是「抢七二比五落后」**——记分条和逐分两个源都直接给，不用推。

## 数据（两个源对过）

`python3 tools/match_stat_hooks.py CUDy2d3L --stats-block`

⚠️ **flashscore 的 home 是斯特恩斯**，而封面主体／`cover.matchup[0]` 是陶森，
**所以 `stats` 的 a/b 要对调**（和 `pegula-waltert`、`parry-mertens` 同一个坑）：

```
a = 陶森      aces 13, df 10, first_in 82, first_won 50, second_total 44,
              second_won 16, bp_conv 5, bp_chances 9, pts_won 114,
              pts_total 228, first_total 126
b = 斯特恩斯  aces  8, df  6, first_in 57, first_won 37, second_total 45,
              second_won 17, bp_conv 7, bp_chances 19, pts_won 114,
              pts_total 228, first_total 102
```

**全场小分 114:114，完全打平**，而陶森赢了。

⚠️ **但这个数今天不能当落点**：`navarro-kalinina`（8.16 同一天同栏目）的钩子就是
「一百六十九个小分她只多赢了一个」，同一个形状再来一次就是自我重复。
**落点用「两次翻盘」那条过程线**（CLAUDE.md：钩子要有剧情的跌宕，不要只摆身份／数字）。

同理躲开的：**连丢五个发球局**（`pegula-waltert` 刚用过）、**破发点兑现**
（`noskova-boulter` 用过）、**一发得分率曲线**（`parry-mertens` 用过）。

斯特恩斯 **19 个破发点只兑现 7 个**、陶森 9 个兑现 5 个——可以进正文当佐证，不当钩子。

## 用时：以 WTA 官方为准，不是 flashscore

    WTA 官方 /tennis/tournaments/1017/2026/matches/LS049/stats
      setnum 1  01:14:39      ← 第一盘一小时十四分钟
      setnum 2  00:43:08
      setnum 3  00:52:35      合计 2:50:22
      MatchTimeTotal 02:50:27   ← 和三个分盘互相印证（差 5 秒）

    flashscore df_sui_1  1:11 + 0:44 + 0:53 = 2:48    ← **偏短 2 分钟，别用**

第三个源：源片 **264.5s 那一格的 Rolex 场地时钟读数就是 `2:50`**（画面自证）。
WTA 官网正文也写 `2-hour, 50-minute battle`。

## 两个人

| | 中文名 | 生日 | 本场年龄 | 国别 | 本站 |
|---|---|---|---|---|---|
| Clara Tauson | **陶森** | 2002-12-21 | **23 岁** | DEN | **27 号种子** |
| Peyton Stearns | **斯特恩斯** | 2001-10-08 | **24 岁** | USA | 非种子 |

⚠️ 两个中文名都是跑 `from tennislive.zh import player_zh` 拿的，不是手打
（⚠️ 入口在 `tennislive.zh`，**不是** `tennislive.zh.players`）。
生日出自 WTA 官方球员接口 `api.wtatennis.com/tennis/players/?name=…`
（id：陶森 327793、斯特恩斯 327573）。

⚠️ **当期世界排名还没查到**：WTA 球员页 HTML 里扒不出 `singlesRank`，
ESPN 那条路 403。**写 spec 之前必须补上**——种子号不是排名（CLAUDE.md 明令）。

## 场上采访里的场外料（⚠️ 只能用事实，画面和原声都不收）

主持人在采访里点了下一轮：

> Before you go, taking on **Linda Noskova** — you've beaten her a couple times.
> **She just won Wimbledon.** You've beaten her twice, I think, last year.
>
> 陶森：Linda is one of my very good friends. We played a lot of doubles together
> and I was so happy for her when she won Wimbledon. I texted her right away and
> she actually responded right away as well.

**这是很好的收尾线**：下一轮对手是刚拿温网的诺斯科娃，两个人是好朋友、一起打过双打，
而陶森去年赢过她两次。⚠️ **「赢过两次」是主持人说的、陶森没否认**，写的时候要
**记成「转播说」**，别当成自己核过的全称断言（CLAUDE.md：编辑稿的引语可以抄、结论要复核）。

⚠️ 顺带：`noskova-boulter` 是本栏目已发的一条（诺斯科娃以温网冠军身份的首胜），
所以这条收尾**和它有呼应，但不许重讲**它铺开过的东西。

## 封面

**官方实拍，不是抽帧**：

    https://photoresources.wtatennis.com/photo-resources/2026/08/16/
      57a476bb-1390-4d5c-b509-1ea34eb65edc/GettyImages-2290118693.jpg?width=4000
    → 4000×2700，双手反拍击球中，**球就在拍面前**，夜场，
      场边 P&G / Credit One 广告板

⚠️ 取原图**必须带 `?width=4000`**，不带参数是 **HTTP 400**（不是 404，别读成「没有」）。

⚠️ **文件名是 `GettyImages-…`，不自证四要素**（和 `pegula-waltert` 那张
`Jessica_Pegula_-_Cincinnati_Open_2026_-_Day_5-…` 不一样）。所以自证靠另外三条：

1. **CMS 引用关系**——它就是这场比赛那条集锦页（`videos/4560466`）的
   schema.org `thumbnailUrl`，路径日期 `2026/08/16`
2. **球衣对得上**——照片里是浅蓝背心 + 浅蓝短裙 + 藏青 adidas 遮阳帽；
   源片里陶森正是这一套（42.5s 近景、360.5s 采访都能看清）
3. **场地对得上**——同一批广告板（P&G / Credit One / Western & Southern / Kroger）

⚠️ **两个人靠球衣分得很开，不会认错**：**斯特恩斯粉色连衣裙 + 粉色遮阳帽**，
**陶森浅蓝 + 藏青帽**。

**头像两个都现成**（492×656 JPEG，不用像 `wta-325771` 那样从 PNG 抠）：

    wtafiles.blob.core.windows.net/images/headshots/327793.jpg   陶森
    wtafiles.blob.core.windows.net/images/headshots/327573.jpg   斯特恩斯

## 球场

WTA 给的是 **`CourtID 1`**，而 CLAUDE.md 的标定表里 **1 号还没标定过**
（已知：6 → Court 4、5 → Court 10、3 → Stadium 3、2 → 有争议）。

线索：这是**当天最后一场**（解说 `closed out Saturday's slate`、
`It's a late one`），而且看台规模明显比 `zhang-day`（Court 4）大——
**多半是中心球场**，但**没查实之前别印球场号**。
转写里 `court` 一次都没出现，画面里也没有写着球场名的牌子。
按 `pegula-waltert` / `cirstea-bartunkova` 的先例印场馆名
`Lindner Family Tennis Center`，或者等哪一天 `CourtID 1` 被别的片子标定出来。

## 开场三格（CLAUDE.md：画面爆点 → 落点 → 坐标）

- ① **不配旁白**，走现场声：赛点落地那一下（~262s）或者网前握手（278.5s）
- ② 落点：两次翻盘
- ③ 坐标：**北京时间八月十六号上午八点**开打（WTA `MatchTimeStamp`
  `2026-08-16T00:07:58Z` → 北京 08:07），辛辛那提第二轮
  ⚠️ 说到点不说分；⚠️ 轮次写「第二轮」不写「三十二强」

## 钩子（solo 封面，每行 ≤ 10 字）

建议：

    抢七二比五落后
    决胜盘一比四

两行都是**过程**不是身份（排名、种子、比分海报别处已经印着）。
⚠️ 别写「三个盘点」——见上面那条，两个源打架。
