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

## 现在住在这儿的

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
