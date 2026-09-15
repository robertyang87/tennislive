# tennislive 🎾 · 网球时差

一个网球内容账号的**生产线**：从赛程赛果数据出发，选题、写稿、配音、剪辑、质检、
推送，整条链跑在 GitHub Actions 上。底层是一套 WTA / ATP 巡回赛的北京时间
赛程赛果 CLI——它现在是这条线的取数底座，不再是这个仓库的主业。

> ⚠️ **动手之前先读 [`CLAUDE.md`](CLAUDE.md)**，不是这份。那里是协作约定：
> 授权边界、不可逆动作的闸、选题与栏目口径、方法论；更深一层的档案按主题分在
> `.claude/skills/`（封面、源片、流水线、版式、出片手艺、文案、开发实践七份，
> 撞上那类工作时才加载）。
>
> 这份 README 只回答一件事：**这个仓库里有什么，怎么跑起来。**

## 栏目

栏目名印在每张卡的片头、封面小标签和小红书落款上。它是**对读者的承诺**，
所以哪条片子归哪个栏目是内容问题，不是排版问题。锚点只有一个动作——**握手**：

| 栏目 | 相对握手 | 承诺 | 单位 | 生产线 |
|---|---|---|---|---|
| **赛场之上** | 打到握手为止 | 比赛本身：集锦画面 ＋ 配音讲清走势、转折和回应 | 一场 | 集锦视频 |
| **赛后开麦** | 话筒递过来 | 打完的人自己怎么说 | 一句话 | 采访视频 |
| **昨日好球** | —— | 昨夜官方剪出来的那一个回合 | 一分 | 单分视频 |
| **网球有故事** | —— | 一个人人见过、没人讲得清的网球现象，讲清它的来历和现在 | 一个现象 | 解说视频 |
| **历史上的今天** | —— | 这一天发生过的那件事 | 一个日子 | 图文知识帖 |
| ~~**开球之前**~~ | 之前 | ~~还没开打的比赛，把两边这几年的来路摆在一起~~ **2026-08-17 起不做新的**（判据 `test_解说视频的栏目只剩网球有故事一个`） | 一场 | 解说视频 |

栏目怎么选、撤掉过哪些、为什么只留这几个，见 [`docs/columns.md`](docs/columns.md)；
日常运营口径见 [`docs/column-operations.md`](docs/column-operations.md)。

## 快速开始（本地 CLI）

```bash
pip install -e .

tennislive today                    # 今日总览：赛果 + 进行中 + 赛程（北京时间）
tennislive results --date yesterday # 昨日赛果
tennislive schedule --date tomorrow # 明日赛程
tennislive live                     # 进行中的比赛
tennislive coverage                 # 数据源与赛事覆盖报告（一张 coverage.txt）
tennislive brief                    # 网球热点简报：扫新闻 → 聚热点 → 中文要点 → 一条推送
tennislive content                  # 内容雷达：赛前焦点的完整小红书内容包
```

所有时间均为北京时间；`--date` 支持 `YYYY-MM-DD` / `today` / `yesterday` /
`tomorrow` / `±N`，`--json` 输出原始 JSON。渲卡片图要中文字体
（Ubuntu：`sudo apt install fonts-noto-cjk fonts-noto-color-emoji`）。

还有几条底层命令，日常不直接用：`topic-radar` / `flash-radar`（只出候选队列，
日常走 `brief`）、`flash-card`（单图快讯卡）、`knowledge-adhoc`（单篇知识帖）、
`explainer`（解说视频）、`video`（已授权素材中文化）、`publish`（发布）。

> `tennislive digest` 已删除：它的产物没人用，覆盖率报告抽成了 `coverage` 自己一条。

## 三条视频生产线

片子的内容写在 `specs/` 里的一份 JSON（**spec 是内容的唯一真相**：窗口、旁白、
封面、比分、推送文案都在里面），工作流按 spec 出片。

| 线 | 工作流 | spec | mode |
|---|---|---|---|
| **赛场之上**（集锦复盘） | `match-reel.yml` | `specs/reels/<slug>.json` | `probe` 下源片出缩略图墙和死球切点 → `cover` 只出封面 → `narration` 只查旁白装不装得下 → `render` 出成片 → `push` 推已落库的成片 |
| **赛后开麦**（采访） | `interview-clip.yml` | `specs/interviews/<slug>.json` | `subs` 取字幕切行 → `cover` → `render` → `push` |
| **网球有故事**（解说） | `explainer.yml` | 脚本在 `video/explainer.py` 的 `_SCRIPTS` | 直接 `slug` 出片 |

配套的小红书正文是同名的 `.xhs.txt`（改文案不用重渲，它不在渲染那条哈希链上）。

出片之前**先在本地把便宜的闸跑满**，别拿 runner 当第一道检查：

```bash
python3 tools/build_match_reel.py --slug <slug> --dry-run           # 0.2 秒，查 spec 形状
python3 tools/build_match_reel.py --slug <slug> --check-narration   # 约 1 分钟，真 TTS 量每段余量
pytest -q -n auto                                                    # 全量，约 2 分钟
```

⚠️ `--dry-run` 报「第 N 段落在估算的误差里」＝**判不了**，不是没问题——那时必须
补跑 `--check-narration`。一趟 render 是 7~15 分钟，本地这几秒买的是不用重来。
整条快路的账（为什么慢的是趟数不是渲染）见
[`docs/thirty-minute-pipeline.md`](docs/thirty-minute-pipeline.md) 和
[`docs/video-production-fast-path.md`](docs/video-production-fast-path.md)。

## 无人值守编排

`orchestrate.yml` 每 10 分钟扫一次赛果赛程，打分、路由、去重，再自动 dispatch
probe 并备料；候选报告写进 job summary，不用翻日志。往下接
`reel-auto-ready.yml`（草稿转正）、`reel-dispatch-queue.yml`、
`auto-push-reel.yml` / `auto-push-interview.yml` / `auto-push-explainer.yml`
（合进 main 之后按 `push.auto` 自动推送）。

状态看板和复制页共用一个 GitHub Pages 部署（`pages.yml`），
观测口径见 [`docs/orchestration-observability.md`](docs/orchestration-observability.md)。

仓库里一共 50 条工作流，其余多是一次性的补救、探测和自检（`probe.yml`、
`source-health.yml`、`pipeline-health.yml`、`pushplus-selftest.yml`…）。

## 发布链路

一条片子的默认终点是**发出去**，不是等指示：

    渲（push=false，在分支上）→ 质检 → 合进 main → 自动推送微信

顺序不能反：**推必须排在合并之后**，GitHub Pages 只服务 `main`，复制页那个按钮
在分支上永远是 404。质检清单（`check_reel_landed` 0 项不合格、全量绿、旁白装得下、
切词没假词、成片链接探得到）写在 `CLAUDE.md`「渲完 → 质检 → 直接推微信」那一节。

产物各走各的通道，别混：

| 东西 | 去哪儿 | 为什么 |
|---|---|---|
| 成片 mp4 | **GitHub Release** | 不进 git（仓库里 0 个 mp4）；git 的 100 MiB 限制不该拿片长去换 |
| 卡片图 / 海报 | **jsDelivr**（`src/tennislive/cdn.py`） | 钉在 commit 上、永久可取；主机名一个地方定，用 `TENNISLIVE_JSDELIVR_HOST` 换镜像 A/B |
| 复制页 / 看板 | **GitHub Pages** | 手机上一键复制标题和正文 |

### PushPlus 推送到微信

1. 在 [pushplus.plus](https://www.pushplus.plus) 微信扫码注册，复制 token
2. 仓库 Settings → Secrets and variables → Actions → 新建 Secret：`PUSHPLUS_TOKEN`
3. 仓库 Settings → Pages 选择 `main` 分支根目录发布（复制页要它）

⚠️ **不要配 `PUSHPLUS_SECRET_KEY`**（这里原来教人配，是反的）。配上它就走 PushPlus
自己的图床，而那条路：①图片 **30 天后自动删**，老推送到期变裂图；②要会员；
③开放接口默认禁用，开完还有一道安全 IP 白名单，而 GitHub runner 的出口 IP 每趟
都不一样。实测配着它反而每趟先吃一个 `code=401`，再退回 jsDelivr。
不配＝直接走 jsDelivr，严格更好。判据 `test_不许再给工作流配PUSHPLUS_SECRET_KEY`。

### 公众号 API（可选，存草稿 / 发布）

**前提**：已认证的公众号（个人未认证订阅号没有草稿/发布接口权限）。

| Secret | 说明 |
|---|---|
| `WECHAT_APPID` / `WECHAT_APPSECRET` | 公众号 AppID / AppSecret |
| `WECHAT_API_PROXY` | 固定出口 IP 的 HTTP 代理，如 `http://user:pass@1.2.3.4:8080`（见下） |
| `ATP_PROTENNISLIVE_TOKEN` | ATP ProTennisLive Bearer JWT（需 Tournament Claims），用于官方逐场技术统计 |
| `SPORTRADAR_API_KEY` | Sportradar Tennis API key，技术统计备用源 |

Variables：`WECHAT_MODE` = `off`（默认，只生成文件）/ `draft` / `publish`（慎用）；
`SPORTRADAR_ACCESS_LEVEL`（试用账号默认 `trial`）；`TENNISLIVE_VISUAL_FETCH` =
`on`（默认，多源检索图片，授权信息仅记录）/ `off`。

> ⚠️ **IP 白名单**：微信取 access_token 要求调用方 IP 在公众号后台白名单内，而
> GitHub Actions 出口 IP 不固定。两种解法：①自建固定 IP 代理，配
> `WECHAT_API_PROXY` 并把代理 IP 加进白名单；②不走 API——用 PushPlus，或直接把
> `wechat.html` 粘进公众号编辑器（1 分钟的事）。

### 小红书

小红书**没有对个人创作者开放发帖 API**，第三方自动发帖有封号风险，所以这里只生成
「复制即发」的内容包：`xiaohongshu.txt` 第一行是标题、其余是正文，`cards/` 里的
竖版图按顺序配图。不使用模拟登录或第三方群控。
写法口径见 [`docs/xiaohongshu-playbook.md`](docs/xiaohongshu-playbook.md)。

## 数据源

| 源 | 角色 | 说明 |
|---|---|---|
| ESPN 公开比分接口 | **赛程赛果主源** | 无需鉴权，聚合 ATP/WTA；适合在 Actions 里跑 |
| flashscore feed | **逐分与赛果交叉源** | 一次请求管两个巡回赛；比赛用时不要只信它（实测偏长过） |
| WTA / ATP 官方接口 | **排名、签表、技术统计** | WTA `players/ranked`（参数少一个就 400）、ATP 走 protennislive posting |
| 大满贯官方 feed | **轮次、场地、逐场** | `official_schedule.py` / `official_stats.py`；runner 上通，沙箱恒 403 |
| TNNS Live | **统计补源** | 单独一档，不塞进常规链 |
| SofaScore | 赛程赛果备用 | 数据较全但可能限制数据中心 IP；失败原因进覆盖报告 |
| Sportradar Tennis v3 | 授权技术统计 | 配了 key 才启用，补总得分、发球、Ace/双误、破发点 |
| Google News 官方域名索引 | 媒体热点信号 | 只读官方域名与白名单媒体的标题、来源、时间，不复制正文 |
| Google Trends / 中文平台热搜 | 搜索升温信号 | 用于加权选题，不作为比赛事实 |

程序会聚合可用的比分源，按球员、项目和北京时间日期跨源去重。`coverage.txt` 列出
各级别赛事命中场次、每个源的健康状态、专业统计有没有授权——**不静默降级**。

⚠️ **空结果 ≠ 不存在**：限流、分类名猜错、解析层级写错，看起来和「没有」一模一样。
查空要先自证是真空，判据和踩过的坑在 `.claude/skills/tennis-media-sources/`。

本项目不在 Actions 里自动抓取 ATP、WTA、TDI 或大满贯的**网站页面**。官网适合人工
核查，批量自动访问需遵守各站条款；要稳定可发布的逐场技术统计，请配置有使用权的
供应商 API。

## 模型通道

中译、要点提炼、字幕翻译共用一条通道（`research/brief.py` 的 `Chat`）：

| 通道 | 密钥 | 默认模型 | 要装什么 |
|---|---|---|---|
| **DeepSeek**（默认） | `DEEPSEEK_API_KEY` | `deepseek-v4-pro` | **什么都不用装**，走 OpenAI 格式的 HTTP |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-5` | `pip install -e ".[brief]"` |

两个都配走 DeepSeek，反过来用 `TENNISLIVE_BRIEF_PROVIDER=anthropic`；换模型用
`TENNISLIVE_BRIEF_MODEL`。**跑了哪条会写进产物**（`brief.json` 的 notes、推送正文
底部、字幕的审计文件）——判据是「走了哪条」，不是「配了什么」。两个都没配不会让它
失败，简报退回「只有英文标题和热度」并照实写出来。

⚠️ **不是 `GITHUB_MODELS_TOKEN`**：`models.github.ai/inference` 2026-08-05 实测返回
HTTP 410 `github_models_retirement_brownout`，已退役。
⚠️ **也不要改走 DeepSeek 的 Anthropic 兼容端点**（`/anthropic`），哪怕那样两条路能
共用一个 SDK：`output_config` 只支持 `effort`（json_schema **收下就忽略**），不认识
的模型名会**自动映射成 `deepseek-v4-flash`**，两件事都不报错。判据
`test_不许改走DeepSeek的Anthropic兼容端点`。

⚠️ **译名不交给模型判断**：模型会把 Rybakina 译成「里巴金娜」（表里是**莱巴金娜**），
而且每次译法还可能不一样。先扫出名字当硬约束塞进 prompt（`research/glossary.py`）。

## 中文化

- 球员译名 **1126 条**：`zh/player_names_top500.json`（ATP/WTA 各 500，
  按官方排名快照生成，**它说了算**）＋ `zh/players.py` 的 `PLAYER_ZH` 452 条兜底
- 赛事中文名 **225 站**、级别 219 条（大满贯 / 1000 / 500 / 250，合办站按巡回赛区分）
- 轮次、场地、项目术语，国家中文名与旗帜 emoji
- 未收录的名字自动回退英文原名，不影响运行；欢迎 PR 补充

⚠️ **写稿时人名不要手打，先查表**；改译名**两张表都要看**，判断改没改对直接调
`player_zh()`，别看文件内容。判据 `test_人名要以译名表为准`。

## 项目结构

```
src/tennislive/
├── cli.py            # 命令行入口
├── models.py         # 统一数据模型
├── timeutil.py       # 北京时间工具
├── cdn.py            # jsDelivr 主机名（一个地方定）
├── qa.py             # 质检
├── sources/          # ESPN / flashscore / SofaScore / TNNS / 官方赛程与统计 / 排名
├── zh/               # 中文化：球员 / 赛事 / 轮次 / 国家
├── research/         # 新闻聚类、正文抓取、模型通道、选题雷达、配图检索
├── render/           # 终端表格 / 公众号 / 小红书 / 卡片图 / 推送 / 封面
├── video/            # 解说视频、TTS、字幕、示意图、水印、片尾
└── publish/          # 公众号草稿 API / PushPlus

specs/                # 片子的内容真相：reels 239 / interviews 100 / explainers 2
tools/                # 181 个脚本：出片、探测、质检、编排（别每次现搓）
tests/                # 161 个测试文件——仓库里几乎每条规矩都在这儿有判据
docs/                 # 栏目、快路、版式、取材、复盘
.claude/skills/       # 七份主题档案，按需加载
.github/workflows/    # 50 条：生产线、自动推送、编排、探测与自检
```

## 开发

```bash
pip install -e ".[dev,webrender,visualqa]" "yt-dlp[default]"   # 和 ci.yml 那行对齐
pytest -q -n auto
```

`ruff` 不用单独跑：它是**由测试调起来的**（`test_match_reel.py` 里那条
`ruff check --select F821`，整个仓库不许有未定义的名字）。`pytest` 就是唯一入口。

⚠️ `pytest -n auto` 的**退出码会骗人**——判据是输出最后那行统计
（`N failed, M passed`），不是 `exited with code 0`。

⚠️ `yt-dlp` 必须装 `[default]`，它才带 `yt-dlp-ejs`。少了它不报「装少了」，而是
`n challenge solving failed` + `Only images are available`，**看起来像「这个视频没有
格式」或者「cookie 过期了」**。判据 `test_装yt_dlp一律要带default`。

Claude Code on the web 的一次性容器由 `.claude/hooks/session-start.sh` 自动配齐
（项目依赖、中文字体、ffmpeg），装的东西和 `ci.yml` 对齐，判据
`test_会话启动钩子装的东西要和CI对齐`。

**规则要落成测试，别只写在文档里**——而且写完要**反向验证**：把错误放回去，确认
那条测试真的会红。恒真的断言和绿灯长得一模一样。

## 权利与合规

**图片**：来源以来源自己的描述/分类为准，**不靠看图推断**；时间、地点、人物三样都要
对得上。许可名、作者、来源 URL 全程记录（缺失记 `unknown` / `unverified`），检索不以
授权状态过滤，发布前的权利判断由人工检验环节负责。画面上不烧录署名，出处记在
`assets/**/credits.json` 和 `visual_sources.json`。

**外媒内容**采用「研究后入库、Action 只消费」：只保存标题、媒体名、发布日期、原文
链接、报道角度，以及可核验的共识 / 分歧 / 数据点，**不保存媒体文章正文**。

**视频中文化**不改变原视频的版权状态。只有自有素材、明确书面授权、公共领域素材，或
许可条款明确允许改编并在目标平台再发布的素材，才可以进入流程；每条在处理前留下权利
记录（原始链接、权利人、取得方式、许可名称与适用范围、是否允许下载/改编/翻译/再发布、
必须展示的署名与限制）。权利不清时只输出原创文字摘要和原文链接，不下载、不烧字幕、
不导出成片。ATP/WTA、赛事方、转播商和媒体账号「公开可看」不等于「允许搬运」，翻译和
加字幕也不能替代授权。

授权确认后，在仓库里准备视频、原文 SRT 和授权清单，手动跑
`.github/workflows/video-localize.yml`；它会生成中文字幕、带字幕成片、署名文本和
`rights-audit.json`。清单格式与本地命令见
[`docs/video-localization.md`](docs/video-localization.md)。**该工作流没有下载器**，
也不会绕过平台水印或访问控制。

## 免责声明

公开比分仅供个人学习与资讯参考，请以赛事官方信息为准；技术统计仅在配置授权 API 后
启用。发布到社交平台时请遵守平台规则、供应商许可与数据来源的使用条款。
