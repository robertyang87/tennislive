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

- **`anisimova-eala`**（辛辛那提 WTA1000 第三轮，2026-08-17，阿尼西莫娃 4-6 6-4 6-2 逆转伊埃拉）
  - 世界第 10 的阿尼西莫娃在决胜盘 0-2 落后的情况下连赢六局，逆转世界第 20 的
    伊埃拉——两人首次交手。真正的分水岭是数据：阿尼西莫娃的非受迫失误三盘从
    25→13→7 一路收窄，制胜分稳定在 15~16 个
  - **片子还没渲染**——`cover.portrait.image` 一直是字面量 `"PENDING"`，卡在
    `cover_photo_problem` 那道闸（和另外两条一样，`probe.json` 是唯一落地的产物）
  - probe 已经跑过：`output/2026-08-18/reel/anisimova-eala/`（6 张缩略图墙、
    逐分／记分板对照表、captions 全在），13 段 spec 全部写完，`--dry-run` 和
    `--check-narration`（zh-CN-YunjianNeural +6%）都过了——12 段全部装得下、
    单段最长哑场 3.68s（门槛 4.0s），小红书正文 632 字也写好了——**唯一缺的
    就是这一格**
  - `stats` 块已经补全：flashscore 十二项和 WTA 官方 `LS025/stats` 逐项对过
    （break points 两源不一致，取 WTA 官方），TNNS 制胜分/非受迫失误
    （`tnns-stats.yml` run 32106507506，match id 73467000，「选手顺序
    ['Eala', 'Anisimova']」自证，分盘合计＝全场两项都对）
  - 四类源 2026-08-18 06:2x Z 查过一遍，**这一场一张都没有**：
    - WTA `photo-resources`：没有对得上的
    - AP 通讯社：两条命中都是资料图（2025 温网夺冠、2025 中网夺冠），不是这一场
    - 赛事官网 WordPress 媒体库：8/17 最新一批 4 张全是科博利，上传时刻
      22:57:55 UTC——**早于这场比赛开始**（这场当地 8:30 PM 后才开打，
      02:06 UTC 08-18 才结束）
    - The Enquirer：这一辑按比赛日出，当天的往往次日才上线
  - **判据是「还没发」**：这场是当晚 P&G Stadium Court 的第 6 场（night session
    主赛事），比赛结束时间晚于赛事媒体库当天最后一次更新，图大概率要等下一批
    才会上线
  - **接回来怎么做**：把两个文件 `git mv` 回 `specs/reels/`，把
    `cover.portrait.image` 换成真实图片路径（`fit`/`focus`/`focus_y`/`zoom` 按实际
    图片重新量，当前写的 `focus_y: 0.4` 只是占位猜测），跑一次完整 `mode=render`
    （这条从来没渲过，不是重渲），`check_reel_landed` 0 项不合格后合并 →
    `mode=push` ＋ `push=true`。
