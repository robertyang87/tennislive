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

## ⭐ 找图渠道两条并行，各有各的产出

账号所有者 2026-08-18：「多找找其他图片库啊，不能一棵树上吊死啊」。同一天有两条
路各自在扩渠道，互不冲突，产出也不重叠：

**① 市场本地化新闻搜索**（Bing 新闻限定 `mkt=<球员国籍对应语种>`）——
`jodar-tabilo` / `tirante-landaluce` / `fery-deminaur` / `zverev-atmane` /
`lehecka-fils` 靠这条找到了官方高清实拍，`git mv` 回了 `specs/reels/`。五条
**全部渲完**（`tirante-landaluce` 中途踩过一次哑场闸——第 8 段窗口收窄 0.5
秒解决，见该 spec 的 `_why`）。找图方法和逐条验证记录见各自 spec 的
`cover.portrait._frame_why`。

⚠️ `lehecka-fils` 值得单记一笔：第一次查到的 L'Équipe 那张（浅蓝 Lacoste polo
对得上，但背景是红色扶手＋红色花丛，翻遍我们自己拍到的辛辛那提画面都没见过）
**没敢用**，换了西语体育媒体（`mkt=es-ES`）才找到一张背景带 `CreditOne`／
`W&S` 广告板、四要素对得上的 Getty 供图——只是分辨率只有 1120×1120
（fill=0.78×），写了 `_low_res_why` 认领这个取舍。**「查到一张像的」和「查到
对的那张」不是一回事**，背景对不上就换源，不能因为衣服对了就将就。

**② WTA 官方集锦视频页自己的 CMS 数据**——之前查 WTA 那半边的图，一直只走
`sweep_wta(player_name)`：直接搜 `photo-resources` 这个 CDN 里挂没挂这个人的
名字。这条路对 `cirstea-kalinskaya`／`noskova-tauson`（还有 `anisimova-eala`）
当时都是空的，但**同一批照片其实已经存在**，只是没被这条搜索命中——真正拿到手
的渠道是**这场比赛自己的官方集锦视频页**：

    https://www.wtatennis.com/videos/<id>/<slug>

页面的 `<meta property="og:image">` 和内嵌 CMS JSON 里直接挂着这场比赛的官方
实拍（`photo-resources/YYYY/MM/DD/<uuid>/<Player-Name>-Cincinnati-2026.jpg`，
带 `?width=4000` 能拿到接近原图的分辨率）。视频 id 从
`https://www.wtatennis.com/videos/highlights` 页面里按标题关键词
（球员姓氏）用正则 `/videos/(\d+)/([a-z0-9-]+)` 找。

⚠️ **这条路和 `sweep_wta` 不是互相替代，是互相补充**——`sweep_wta` 搜的是
「这个人名下有没有图」，这条搜的是「这场比赛自己的内容页挂没挂图」，两者的
索引窗口和覆盖范围不一样，一条空了要去试另一条，不能只查一条就下"没有"的
结论。`cirstea-kalinskaya`／`noskova-tauson` 靠这条渠道找到了 2026-08-18 才
发布的官方实拍，已经 `git mv` 回 `specs/reels/` 并渲完，见下面「曾经住在这儿」
那节。

**③ 当地报纸（The Enquirer）的同日图集，走 sitemap 找入口**——2026-08-19 挖出来的，
对 ATP 比这条线原有的两条都更快（当天就发，不用等次日 UTC 00:00~03:00 那个
官方图库批次窗口）：

    https://www.cincinnati.com/sitemap/2026/august/<日>/
      → 找 href 里带 picture-gallery 的那条（当天可能只有一条，覆盖当天多场比赛）
    打开那条 gallery 页，正文里 `<script type=application/ld+json>` 是个数组，
    `data[0]['image']` 就是这一天全部照片，每条自带 `url`／`caption`／`copyrightHolder`

⚠️ **图不按选手分文件夹，是同一个 gallery 混着当天好几场球**——2026-08-18 那一条
一次给了 32 张，覆盖了 Rublev-Borges／Fritz-Aguilar(Merida)／Andreeva-Tjen／
Gauff-Li／Nakashima-Medvedev 五场（含 WTA），**Musetti-Zheng 一张都没有**——
这一站的摄影师显然没有拍全部球场，查到"这个 gallery 里没有"就是真的没有，
不用怀疑是解析漏了（已经把整份 32 条 caption 过了一遍，没有第二处漏网）。

⚠️ **原图直连要换域名，`www.cincinnati.com/gcdn/authoring/...` 本身 406**：
去掉 `/gcdn` 换成 `www.gannett-cdn.com/authoring/...`（同一路径的其余部分不变），
带 `Accept: image/*`。实测拿到 2697×4042~8170×5447，EXIF 里带
`copyright=2026 - The Cincinnati Enquirer/USA Today Network`，caption 本身就是
四要素自证（球员、对手、赛事、场馆、日期，往往还带着这场的比分）。

## 现在住在这儿的

- **`tirante-mensik`**（辛辛那提 ATP1000 1/8决赛，2026-08-19，蒂兰特
  5-7 6-4 6-4 逆转14号种子门西克，两小时十六分，生涯首进大师赛1/4决赛）——
  内容已经全部做完（editorial、逐分核实、旁白、xhs 文案）。赛事官方 WP
  媒体库 `?search=tirante` 仍然只有 8/15 的旧照片和一张 2025 年头像；
  The Enquirer 8/19 同日 gallery（135 张）逐条查过，一张蒂兰特都没有。
  - 下一步：等 8/21 前后赛事官方图库补上这批，或 Enquirer 隔天再发一批
    gallery；也可以按 `mkt=es-ES`（阿根廷球员）试一次西语体育媒体渠道
    （`lehecka-fils` 那次就是靠换语区找到的）

- **`tiafoe-tien`**（辛辛那提 ATP1000 第三轮，2026-08-19，蒂亚福 6-4 4-6 6-4 胜
  勒纳·钱，两小时十分）——这场比赛就发生在 2026-08-19（当天），赛事官方图库照惯例要到
  次日 UTC 00:00~03:00 才批量上线，所以今天必然是空的。四类源逐条跑过：
  `tools/fetch_atp_cover_photo.py --site cincinnatiopen.com --match-date 2026-08-19`
  报「2026-08-19 那一辑还没发」（媒体库 379 条 ＋ 图库页 279 张，日期戳等于今天
  的 0 张）；`tools/find_cover_photo.py --player Tiafoe --event Cincinnati
  --site cincinnatiopen.com --date 2026-08-19` 四条渠道全跑过（WTA
  `photo-resources` 不适用于 ATP、AP 通讯社搜了球员名只有默认占位分享图、
  The Enquirer 同日 gallery 没有这场、`cincinnatiopen.com` WP 媒体库 `?search=
  Tiafoe` 命中 23 张全是 2025 年及更早的旧照片）。
  - ⚠️ **2026-08-20 复查过一轮，仍然是空的**。当时预计的「北京时间 8/20 上午前后」
    那个窗口没能兑现——真正的原因是 **`day-N-best-of-photos` 这个编号和日历日期
    之间的滞后比想的更大**：`day-8-best-of-photos` 那篇文章 2026-08-19T16:26 才
    发布，可里面的图文件名却是 `081726` 和 `CincinnatiOpen_20260817_`——也就是说
    它装的是 **8/17** 那天的内容，不是它自己的发布日期暗示的 8/18。按这个滞后量
    推算，覆盖 8/19（Tiafoe-Tien 这场）的那一批大概率要到 **8/21 前后**才会出现。
    `?search=Tiafoe` 这次多出一张 `Frances-Tiafoe_20260812_001_1.jpg`
    （2000×1333，上传于 8/15）——**文件名日期戳是 8/12，不是 8/19**，是另一场
    比赛的资料图，不能用（四道闸门第一道：时间不对）。
  - 这条片子的看点是蒂亚福赛前十二天（8/7）刚在蒙特利尔因伤退赛做完手术，
    赛后网前被勒纳·钱打趣「你没受伤，你在说谎」，蒂亚福赛后采访自己澄清是玩笑——
    源片（Tennis TV YouTube 官方单场集锦，标题就叫「Fun Match」）自带完整原声
    收音，不是二手转述，`editorial.human_context` 和 `_claims` 里逐条记着来源。
  - 下一步：**8/21 之后**再查一次；这次学到的教训是判断"批次上线了没有"要看
    **批次内部图片的日期戳**，不能只看这篇 gallery 文章自己的发布时刻——文章发布
    时刻和它装的内容日期之间隔着这个可变的滞后量。
  - ⚠️ 顺带修了一个真 bug：`tools/build_match_reel.py` 的
    `segments_straddling_cuts()` 在段落用新版 `quote: [{"at":...,"text":...}]`
    （按真实时刻声明的原声字幕）格式、又跨了镜头切点时会 `TypeError` 崩溃——
    诊断代码试图用 `"／".join()` 拼一个字符串列表，而 `quote` 给的是字典列表。
    改用已有的 `_quote_text()` 辅助函数（本来就是为了兼容两种写法而存在的），
    这条片子第 11 段（采访 quote，跨了 168.96s 那个切点）就撞上了这个坑。

- **`musetti-zheng`**（辛辛那提 ATP1000 第三轮，2026-08-18，穆塞蒂 6-1 6-3 胜郑瑞）
  - 2026-08-19 系统查过一轮：赛事官方图库四种日期戳搜索（`CincinnatiOpen_20260818_`／
    `081826`／`CincyOpen8-18-26`／`CincyOpen8.18.26`）全部 0 命中，`day-8-best-of-photos`
    那篇文章还没发；The Enquirer 8/18 的同日 gallery（见上面③）32 张逐条查过，
    没有一张是这场；AP 搜了球员名也只有旧闻（温网退赛、法网退赛这类）
  - ⚠️ **2026-08-20 复查过一轮，仍然是空的**——`?search=Musetti` 命中 5 张，
    全部是 2023~2025 年的旧照片，没有一张日期戳落在 2026-08。按上面
    `tiafoe-tien` 那条挖出来的滞后量估计，覆盖 8/18 这场的那一批大概率也要
    等到 8/20~8/21 之间。
  - 下一步：**8/21 之后**再查一次（等赛事官方图库的下一批，或 The Enquirer
    隔天可能补发另一批 gallery）

- **`paul-vallejo`**（辛辛那提 ATP1000 第三轮，2026-08-17 夜场，保罗 3-6 6-3 6-4 巴列霍）
  - 开球美东 22:40，很晚的夜场；Tennis TV 短集锦已经有了（`source_url` 能下），
    但赛事媒体库到 2026-08-18 02:57Z 那一批只有科博利，AP／英语媒体连一篇赛后稿都
    还没发——这是「夜场图要等 24 小时」那条的标准形状，不是查漏了
  - 下一步：等下一批赛事图库上线（次日 UTC 00:00~03:00 那个窗口再晚几个小时）或
    英语媒体赛后稿出来再查

- ⚠️ **`swiatek-sakkari.draft.json`——这一条是另一个理由，别按上面那套读**。
  这不是「等官方高清图」——它是另一位会话/流程留下的**在制品草稿**
  （`assemble_spec.py` 那批自动化 2026-08-18 22:31 UTC 写的，`_draft: true`，
  flashscore 统计、破发点密度、H2H、近况全是机器抓的真数据，**但 `editorial`
  的 question/thesis/beats/human_context、`cover.layout`/`eyebrow`、
  国旗排名、headshot、结尾一问、小红书文案全部没填**——这些需要真的看过源片、
  写过判断，我没做过这场球的任何研究，不该替它编。
  它在 `specs/reels/` 根目录里放了 2 个多小时（main 那批提交是 22:30~22:57 UTC
  「赛后开麦自动链」那三条），main 的 CI 因此一直红，挡住了所有 PR（含这个仓库
  当天其他会话渲完的三条片子）。等到 2026-08-19 01:xx UTC 仍无新提交，判断是
  会话已经停了，不是还在写。`specs/reels/*.json` 是非递归扫的、这个子目录不参与
  那批判据，机制上和「等封面图」是同一个豁免，只是理由不同——**先 `git mv` 挪
  进来把 main 的 CI 解开，内容一个字没动**（`assemble_spec.py`／
  `draft_interview_spec.py` 之类的自动化没有任何一处按路径依赖它继续留在
  `specs/reels/` 根目录，扫过全部工作流和工具确认过）。谁要接着写，
  `git mv` 回 `specs/reels/` 就行，草稿本身原封不动。

## 曾经住在这儿、现在已经挪出去的

- **`nakashima-borges`**（辛辛那提 ATP1000 1/8决赛，2026-08-19，中岛纳赛马
  6-3 6-7(5) 6-3 逆转博尔热斯，两小时二十二分）——**2026-08-20 挪出去了**。
  The Enquirer 8/20 发布的 8/19 同日 gallery（`round-of-16-continues-at-
  cincinnati-open-see-photos/91372587007/`）里找到三张实拍，挑了正手击球、
  脸部表情清晰的那张（`Brandon Nakashima, of United States, returns to
  Nuno Borges`，Albert Cesare/The Enquirer，6418×4279）——另两张一张背身
  低反应看不清脸、一张拍的是博尔热斯不是本条封面主体，都弃用了。
  ⚠️ **顺手修了一个真 bug**：`stats.a`/`stats.b` 填反了——`cover.matchup[0]`
  是中岛，但 `stats.a` 存的是博尔热斯的数字，spec 自己的 `_source` 注释还
  编了一条『a/b 跟 home/away 走』的『最新更正版本』规矩来自圆其说，实际
  `render_stat_card.py` 第19行明确写着 a 对应 matchup[0]。已互换数据并改对
  注释，正是 CLAUDE.md 点名过的 `tsitsipas-royer` 那类错误的又一次。

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
  里那条破例豁免也删掉了（用的是真官方图，不再需要它）。**已经推送**
  （流水号 `30b415ca1f46447da63f79161ec6c4e9`）。

- **`cirstea-kalinskaya`**（辛辛那提 WTA1000 第三轮，2026-08-17，科斯蒂亚
  6-7(4) 6-1 5-0 Ret. 胜卡林斯卡娅，因伤退赛）——**2026-08-18 挪出去了**。
  按上面第②条渠道（WTA 集锦视频页 `cirstea-into-cincinnati-last-16-as-
  kalinskaya-retires` 的 CMS 数据），找到 2026-08-18 才发布的官方实拍
  （4700×3026，反手双手过肩击球），`sweep_wta("Cirstea")` 当时还是空的，
  说明这条渠道确实比直接的名字搜索更早/更全。

  ⚠️ **顺带挖出一个真实的渲染器 bug**：`result` 字段是 `"6-7(4) 6-1 5-0 Ret."`，
  「赛场之上」solo 封面唯一在用的那套比分板（`_scoreboard_sets`）遇到末尾的
  `Ret.` 词元直接 `SystemExit`——而 VS 版式那条老路（`_sets_html`）的
  docstring 早就写着「退赛写法（`2-1 ret.`）同样落到这条退路上，只是不上色，
  不会渲错」。两个渲染器对同一种输入的容忍度不该分叉，已经把 `_scoreboard_sets`
  改成识别一个可选的退赛/弃权词元（`ret.`／`ret'd`／`w.o.`／`def.` 等），
  在比分板头部加一个小号中文注脚（"退赛"／"弃权"），不影响正常的三盘/两盘
  比分。这不是给这一条 spec 单独打的补丁，是所有退赛比分的「赛场之上」
  以后都用得上的路。**已经渲完并推送**（流水号
  `d93cca65bca8468082cdb07f54ac94ad`）。

- **`noskova-tauson`**（辛辛那提 WTA1000 第三轮，2026-08-17，诺斯科娃
  7-6(3) 6-2 胜陶森）——**2026-08-18 挪出去了**。同一批新渠道找到的，
  视频页 `noskova-sets-up-fourth-round-clash-against-anisimova-in-cincinnati`
  的 CMS 数据挂着 2026-08-18 发布的官方实拍（3930×2619，正手上网截击前的
  引拍动作），`sweep_wta("Noskova")` 当时命中的是一张多伦多站的资料图
  （已经排除），这条视频页给出的才是真正对得上这场比赛的图。**已经渲完并推送**
  （流水号 `f0d7e9ef205346e9b8a96419ef73b339`）。

- **`nakashima-medvedev`**（辛辛那提 ATP1000 第三轮，2026-08-18，中岛 6-7(3) 7-6(4)
  6-1 胜梅德韦杰夫）——**2026-08-19 挪出去了**。按上面第③条渠道（The Enquirer
  同日 gallery）找到官方实拍，`render_cover_local.py` 本地渲过确认无裁切问题。

- **`borges-rublev`**（辛辛那提 ATP1000 第三轮，2026-08-18，博尔热斯 6-3 6-4
  爆冷卢布列夫）——**2026-08-19 挪出去了**。同一批 The Enquirer gallery 找到的，
  封面放卢布列夫（大名字例外，他是输的那一方）。

- **`fritz-merida`**（辛辛那提 ATP1000 第三轮，2026-08-18，弗里茨 6-3 6-4 胜梅里达）
  ——**2026-08-19 挪出去了**。同一批 The Enquirer gallery 找到的。
