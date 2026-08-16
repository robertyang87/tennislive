# snigur-keys 素材笔记（2026-08-16 查的，等封面官方图）

## 卡在哪
封面主体只能是基斯（赢家 + 大名字），而 **8/16 Day 6 的官方实拍还没出**：
- WTA `/videos/highlights`、`/news`、`/tournament/1017/cincinnati/2026`：Day 6 那批只有
  Swiatek / Rybakina / Xinyu Wang / Sara Bejlek 四张，没有 Keys
- WTA 她的球员页只有 `Madison_Keys_-_Australian_Open_2025_-_Day_12`（澳网 2025）和
  `Madison-Keys-Toronto-2026`（多伦多）—— 时间地点都对不上，过不了第一道闸
- `tools/fetch_atp_cover_photo.py --site cincinnatiopen.com --match-date 2026-08-16`：
  图库只有 day-3/4/5，**day-6 那一辑还没发**（扫 166 张，日期戳 8/16 的 0 张）
→ 等图库上线再取；抽帧要放大 1.33 倍，撞「封面一律用官方高清实拍」，不走。

## 源片
- `https://www.youtube.com/watch?v=gKwNj8kPBaA`（WTA 官方频道，oEmbed author_name=WTA）
- 1920×1080 / 25fps / **306.36s** → 压不住 310s 基线？**306 < 310，尾巴没有场上采访**；
  实际 296.24 之后是 WTA 绿色片尾板 + 订阅卡（contact_05），窗口收在 295.5 以内
- probe 已在 main：`output/2026-08-17/reel/snigur-keys/`
- 认人：**基斯 = 酒红背心 + 粉短裙 + 黑色 Nike 帽**（20.5 / 146.5 / 178.5 / 256.5 近景）；
  **斯尼古尔 = 浅紫连衣裙 + 白色遮阳帽**（36.5 / 158.5 / 142.5）

## 赛事数据
- flashscore `82tvst95`（home=Snigur, away=Keys）；WTA `LS037`，RoundID 2，**CourtID 4（新码位，未标定）**
- MatchTimeStamp `2026-08-16T16:15:29Z` → 北京 **8/17 凌晨 00:15**
- MatchTimeTotal `02:07:51`；settime 45:18 + 37:50 + 44:39 = 2:07:47（差 4 秒，自洽）
- ResultString `[20]M. Keys d D. Snigur 4-6,6-3,6-3`；SeedB=20（基斯），斯尼古尔非种子
- 排名（rankedAt 2026-08-10）：基斯 **24**（1814 分），斯尼古尔 **45**（1163 分）
- 生日：基斯 1995-02-17（本场 31 岁），斯尼古尔 2002-03-27（24 岁）
- 基斯：**2025 年澳网单打冠军**（决赛胜萨巴伦卡那年），维基/WTA 两个源
- **首次交手**：flashscore 交手段 0:1（只有本场）；WTA 官方赛历翻完斯尼古尔全部 **449** 场，
  出现 Keys 的 **0 场** —— 两个源一致

## 狠数据（match_stat_hooks 82tvst95）
- **总分 95 : 99，净差 4 分** ← 两小时零八分，只多赢四分
- 基斯 **一发得分率 64% → 77% → 80%**（分盘，逐盘往上走）
- **Ace 14 : 0**
- 破发点：斯尼古尔 3/10，基斯 5/12
- 基斯连续保发 7 个发球局
- flashscore 没有制胜分/UE → 已发 `tnns-stats.yml`（who=Keys,Snigur date=2026-08-16），要回读

## 逐分要点（df_mh_1_82tvst95，home=Snigur）
第一盘 6-4 斯尼古尔：基斯先破发 4-2 → 斯尼古尔立刻破回 3-4 →
  **3-4 自己发球局打到第四次平分、救下三个破发点**（画面 58.5–86.5，角标 DEUCE #4）→ 4-4 →
  **破基斯**（88.5–102.5，角标 BREAK POINT #2）→ 5-4 →
  **三个盘点，第三个拿下**（104.5–110.5，角标 SET POINT #3）→ 6-4（120.5 出赛果图形）
第二盘 6-3 基斯：0-2 基斯破 → 1-2 斯尼古尔破回（**这两局不在集锦里**，160.5 之后直接跳 1-2）→
  2-2 → 3-3（196.5–210.5 基斯占先保发，救两个破发点）→ **3-5 基斯破到零**（不在集锦里）→
  212.5–224.5 基斯发球胜盘，角标 SET POINT → 6-3
第三盘 6-3 基斯：1-1 斯尼古尔发球局 **打到第四次平分、四个破发点**，基斯破（238.5–254.5，DEUCE #4）→
  1-2 …（4-8 局不在集锦里）→ 3-5 斯尼古尔发球，**两个赛点，第二个拿下**（256.5–276.5，MATCH POINT #2）

## 画面时间轴
| 秒 | 内容 |
|---|---|
| 0.5 | 教练席特写（Player Coaches & Guests Only） |
| 2.5–10 | 第一盘早段回合 |
| 20.5 | **基斯近景**（黑帽） |
| 36.5 | **斯尼古尔近景**（白色遮阳帽） |
| 40.5–56.5 | 第 7 局，记分条 2-4（基斯发球，被破回） |
| 58.5–86.5 | 第 8 局马拉松保发，DEUCE #4，救三个破发点 |
| 88.5–102.5 | 第 9 局，BREAK POINT #2，斯尼古尔破发 5-4 |
| 104.5–110.5 | 第 10 局，SET POINT #3 |
| 120.5 | 第一盘赛果图形 6-4 |
| 122.5–128.5 | 斯尼古尔在球员席 |
| 130.5 | 基斯发球 115 MPH |
| 160.5 | 第二盘 0-0 |
| 162.5–190.5 | 第二盘 1-2 / 2-2 |
| 196.5–210.5 | 3-3，基斯占先 |
| 212.5–224.5 | 基斯发球胜盘，SET POINT → 6-3 |
| 232.5–236.5 | 第二盘赛果图形 |
| 238.5–254.5 | 第三盘 1-1 马拉松局，DEUCE #4 |
| 256.5–276.5 | 3-5 斯尼古尔发球，MATCH POINT #2 |
| 278.5–280.5 | 观众 |
| 282.5–288.5 | 网前握手 + 赛果图形 `DARIA SNIGUR 6 3 3 / MADISON KEYS 4 6 6` |
| 290.5–294.5 | 基斯向看台致意 |
| 296.24+ | WTA 片尾板 + 订阅卡 |

## 钩子草稿（每行 ≤10）
「全场只比对手多四分」(9) / 「丢掉首盘之后连赢两盘」(10)

## push.summary 草稿（≤13，且剥掉名字和赛果动词之后要剩东西）
「两小时零八分只多赢四分」(11)

## TNNS 制胜分 / 非受迫失误（run 31968054865，hasExtendedStats=True，分盘合计＝全场 ✅）
选手顺序 `['Snigur', 'Keys']`
- 全场：制胜分 **17 : 43**，非受迫失误 **41 : 61**
- Set 1：制胜分 [7, 17]　非受迫失误 [15, 30]
- Set 2：制胜分 [4, 10]　非受迫失误 [11, 14]
- Set 3：制胜分 [6, 16]　非受迫失误 [15, 17]

→ 基斯 **43 个制胜分 + 61 个非受迫失误**，Ace 14 比 0，而两小时零八分**只多赢四分**。
   这是「大开大合换来四分」的一场，钩子和文案的主线就是它。

## flashscore stats 块（match_stat_hooks 82tvst95 --stats-block，a=Snigur b=Keys）
a(Snigur): aces 0, df 6, first_in 73, first_won 44, second_total 29, second_won 13,
           bp_conv 3, bp_chances 10, pts_won 95, pts_total 194, first_total 102
b(Keys):   aces 14, df 6, first_in 55, first_won 40, second_total 37, second_won 14,
           bp_conv 5, bp_chances 12, pts_won 99, pts_total 194, first_total 92
⚠️ cover.matchup[0] 会是**基斯**（封面主体、赢家），所以 **a/b 要整块对调**。
⚠️ 头像：`assets/players/headshots/wta-316959.jpg`（Keys）/ `wta-327845.jpg`（Snigur）——两个都还没取，
   走 `wtafiles.blob.core.windows.net/images/headshots/<id>.jpg`（492×656 那一版）。
