# 等官方高清封面的 spec 放这儿

`specs/reels/*.json` 是**非递归**扫的（`tests/` 里两处都是 `Path("specs/reels").glob("*.json")`），
所以放进这个子目录的 spec **不参与那批判据**，也不会被 `auto-push-reel` 认领。

**它不是废稿箱，是候车室。** 进来的唯一理由是
`build_match_reel.cover_photo_problem` 那道闸说的那件事——

> 「还没发就**等**：片子可以先渲，封面最后定，图一落地换上去再推」

也就是**这一场的官方高清实拍还没上线**，而抽帧已经不许再当封面
（账号所有者 2026-08-17：「还是要找到对应比赛的高清大图是最重要的**前置条件**」）。

⚠️ **不许拿同一站别的日子的图顶上**——那是 CLAUDE.md 反复记过的「资料图」坑
（同一个 Getty 编号挂在两个日期目录下那次）。四道闸门第一道要时间、地点、人物**三样都对**。

## 现在住在这儿的

- **`tirante-landaluce`**（辛辛那提 ATP1000 第三轮，2026-08-17，蒂兰特 7-6(5) 7-6(4) 兰达卢塞）
  - 片子**已经渲完并提交**：`output/2026-08-18/reel/tirante-landaluce/`
  - 缺的只有封面：`cover.portrait` 现在还是 `frame_at: 52.85`（抽帧）
  - 四类源 2026-08-18 03:25Z 又查了一遍，**这一场一张都没有**：
    - 赛事官网 WordPress 媒体库：8/17 只上了 4 张，`CincyOpen8.17.26BJ_{13,103,159,187}`，
      **四张全是科博利**；蒂兰特名下最新的是 **8/15** 那三张（`CincyOpen8.15.26BJ_357/378`、
      `CincinnatiOpen_20260815_JM021551_LS2`）——那是他赢德约科维奇那一场，**不是这一场**
    - The Enquirer 8/17 那一辑 28 张，逐条读过说明：斯瓦泰克–萨卡里 14 张、
      莱巴金娜–弗雷赫 6 张、**科博利–布洛克斯 6 张**，蒂兰特 0 张
    - ATP 官方：8/17 那一批只发了 Fery–de Minaur 和 Blockx–Cobolli，这一场没稿也没集锦
    - AP 通讯社：这一场没有
  - **判据是「还没发」不是「没有」**：赛事图库当天那一辑的规律是次日 UTC 00:00~03:00 上线，
    而 8/17 这一批到 03:25Z 只上了四张——还没上全。
  - **接回来怎么做**：把两个文件 `git mv` 回 `specs/reels/`，把 `cover.portrait` 换成
    `{"image": "assets/reel/tirante-cincinnati-2026-r3.jpg", ...}`，**重渲整条片子**
    （成片开头那 1.2 秒就是海报本身，只跑 `mode=cover` 换出来的海报和成片里那一屏会对不上），
    然后照常合并 → `mode=push` ＋ `push=true`。

- **`cirstea-kalinskaya`**（辛辛那提 WTA1000 第三轮，2026-08-17，科斯蒂亚 6-7(4) 6-1 5-0 Ret. 胜卡林斯卡娅，因伤退赛）
  - 账号所有者直接给出 YouTube 链接授权制作（`_match._match_day_why` 里记了这条例外）
  - **片子还没渲染**——`cover.portrait.image` 一直是字面量 `"PENDING"`，`validate_spec`
    在 `cover_photo_problem` 那道闸直接拦下，连下源片都没走到（和 `tirante-landaluce`
    不同：那条已经渲完，这条连 render 都没跑过，`probe.json` 是唯一落地的产物）
  - probe 已经跑过：`output/2026-08-18/reel/cirstea-kalinskaya/`（缩略图墙、逐分/记分板
    对照表、captions 全在），spec 的 segments／旁白已经写完并跑过 `--check-narration`
    真实语音校验（12 段全部装得下，无哑场），小红书正文 651 字也写好了——**唯一缺的
    就是这一格**
  - 四类源 2026-08-18 05:31Z 又查了一遍，**这一场一张都没有**：
    - 赛事官网 WordPress 媒体库：8/17 只上了 4 张 `CincyOpen8.17.26BJ_{13,103,159,187}`，
      **四张全是科博利**（和 `tirante-landaluce` 那条查到的是同一批）
    - WTA `photo-resources`（Match Reaction 稿头图／集锦视频页头图）：`sweep_wta` 查
      "Cirstea"／"Kalinskaya" 都是空，这场还没有对应的赛后稿
    - AP 通讯社：命中的三张全是资料图（2026 罗马、2026 马德里、2025 美网），没有一张
      是这一站；Kalinskaya 零命中
    - The Enquirer：8/17 那一辑没有这两个人（和 `tirante-landaluce` 记录的 28 张核对一致）
  - **判据是「还没发」**：这场因雨延误跨了近 5 小时（`MatchTimeStamp` 到 `LastUpdated`
    相差 4:51:54），素材大概率还在摄影师手里整理，和 `tirante-landaluce` 是同一批
    「还没上全」的批次
  - **接回来怎么做**：把两个文件 `git mv` 回 `specs/reels/`，把 `cover.portrait.image`
    换成真实图片路径（`fit`/`focus`/`focus_y`/`zoom` 按实际图片重新量，当前写的
    `focus_y: 0.4` 只是占位猜测），跑一次完整 `mode=render`（这条从来没渲过，不是
    重渲），`check_reel_landed` 0 项不合格后合并 → `mode=push` ＋ `push=true`。

- **`noskova-tauson`**（辛辛那提 WTA1000 第三轮，2026-08-17，诺斯科娃 7-6(3) 6-2 胜陶森）
  - 账号所有者直接给出 YouTube 链接（`https://m.youtube.com/watch?v=oEXAA3TvUbs`）
    授权制作，同为「previous match day」例外（`_match._match_day_why` 里记了）
  - **片子还没渲染**——`cover.portrait.image` 一直是字面量 `"PENDING"`，卡在
    `cover_photo_problem` 那道闸（和 `cirstea-kalinskaya` 一样，`probe.json` 是唯一
    落地的产物）
  - probe 已经跑过：`output/2026-08-18/reel/noskova-tauson/`（6 张缩略图墙、
    逐分／记分板对照表、captions 全在），16 段 spec 全部写完，`--dry-run` 和
    `--check-narration`（zh-CN-YunjianNeural +6%）都过了——15 段全部装得下、
    单段最长哑场 2.89s（门槛 4.0s），小红书正文 619 字也写好了——**唯一缺的
    就是这一格**
  - `stats` 块已经补全：flashscore 十二项和 WTA 官方 `LS024/stats` 逐项对过，
    TNNS 制胜分/非受迫失误（`tnns-stats.yml` run 32104235533，match id 73466998，
    「选手顺序 ['Noskova', 'Tauson']」自证，分盘合计＝全场两项都对）
  - 四类源 2026-08-18 05:4x Z 查过一遍，**这一场一张都没有**：
    - WTA `photo-resources`：`sweep_wta("Noskova")` 唯一命中是
      `Linda_Noskova_-_National_Bank_Open_2026_-_Day_1-DSC_4072.jpg`——**多伦多站
      Day 1 的资料图，不是辛辛那提、不是这一场**（时间地点都不对，典型的
      「资料图」坑）；`sweep_wta("Tauson")` 空
    - 赛事官网 WordPress 媒体库：`search=Noskova`／`search=Tauson` 只命中各自
      **2024 年**的标准头像图（492×656），按日期 `2026-08-17` 扫全量媒体库也没有
      这两个人（和另外两条撞的是同一批「还没上线」）
    - AP 通讯社：两人都零命中
    - The Enquirer：8/17 那一辑没有这两个人
  - **判据是「还没发」**：三条同一天（08-17）的辛辛那提片子
    （`tirante-landaluce`／`cirstea-kalinskaya`／这一条）全撞在同一个媒体库更新窗口上
  - **接回来怎么做**：把两个文件 `git mv` 回 `specs/reels/`，把
    `cover.portrait.image` 换成真实图片路径（`fit`/`focus`/`focus_y`/`zoom` 按实际
    图片重新量，当前写的 `focus_y: 0.35` 只是占位猜测），跑一次完整 `mode=render`
    （这条从来没渲过，不是重渲），`check_reel_landed` 0 项不合格后合并 →
    `mode=push` ＋ `push=true`。

## 曾经住在这儿、现在已经挪出去的

- **`anisimova-eala`**（辛辛那提 WTA1000 第三轮，2026-08-17，阿尼西莫娃
  4-6 6-4 6-2 逆转伊埃拉）——**2026-08-18 已经不在这个目录里了，也不再需要
  等图**。经过：账号所有者先要求「先渲染伊埃拉的」，被封面闸拦下后当面批准
  破例（「破例，先用抽帧渲」），一度用抽帧（`frame_at: 270.0`）顶上、
  `anisimova-eala` 显式挂进 `LEGACY_SOFT_COVERS`。**同一轮搜索里另外发现
  阿尼西莫娃（赢家）有一张当天刚发布的官方实拍**（WTA 视频页内嵌 CMS JSON，
  `photo-resources/2026/08/18/…/Amanda-Anisimova-Cincinnati-2026.jpg`，
  4000×2422，发布时间比赛后仅约一小时）——账号所有者选了「换回阿尼西莫娃，
  用现成官方图」，于是封面主体、钩子、`push.summary/lead`、结尾几段旁白、
  小红书正文全部改成阿尼西莫娃视角，`cover.portrait` 换成
  `assets/reel/anisimova-cincinnati-2026-r3.jpg`，`LEGACY_SOFT_COVERS`
  里那条破例豁免也删掉了（用的是真官方图，不再需要它）。
