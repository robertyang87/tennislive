# tennislive 🎾

WTA / ATP 巡回赛每日赛程与赛果同步工具（北京时间）：

- **终端 CLI**：随时查询今日赛程、实时比分、昨日赛果
- **自动内容任务**（GitHub Actions）：晨报定时生成；热点雷达全天检测并生成小红书单场待发布包

## 快速开始（本地 CLI）

```bash
pip install -e .

tennislive today                    # 今日总览：赛果 + 进行中 + 赛程（北京时间）
tennislive results --date yesterday # 昨日赛果
tennislive schedule --date tomorrow # 明日赛程
tennislive live                     # 进行中的比赛
tennislive digest                   # 生成今日内容包到 output/YYYY-MM-DD/
tennislive content                  # 自动选题并生成完整待发布内容包
```

所有时间均为北京时间；`--date` 支持 `YYYY-MM-DD` / `today` / `yesterday` / `tomorrow` / `±N`。
`--json` 输出原始 JSON。生成卡片图需要中文字体（Ubuntu：`sudo apt install fonts-noto-cjk`）。

## 内容生成任务

⚠️ **日报（`daily.yml`）已于 2026-07-31 停产并删除**——形式落后、任务重且没收益。
下面这段留作历史说明；现在还在跑的自动内容是 `news-brief.yml`（热点简报）、
`flash.yml`（内容雷达）、`match-reel.yml`（赛场之上 / 网球有故事）和
`explainer.yml`（知识解说视频）。

<details><summary>已停产：每日晨报（历史说明）</summary>


1. 抓取昨日赛果 + 今日赛程（含凌晨刚结束的欧美比赛）
2. 生成内容包并提交到仓库 `output/YYYY-MM-DD/`：

| 文件 | 用途 |
|---|---|
| `wechat_title.txt` | 公众号文章标题（自动挑亮点：中国球员优先） |
| `wechat.md` | 公众号文章 Markdown（配合 md2wechat 等工具排版） |
| `wechat.html` | 内联样式 HTML，可直接粘贴进公众号编辑器或走 API 发草稿 |
| `xiaohongshu.txt` | 小红书文案（标题 ≤20 字、正文 ≤1000 字、话题标签） |
| `copy.html` | 手机文案复制页（标题、正文可分别一键复制） |
| `pinned_comment.txt` | 小红书置顶评论，可在复制页单独一键复制 |
| `cards/*.png` | 1080×1440 竖版卡片图：封面 + 赛果页 + 赛程页 |
| `source_manifest.json` | 本期来源清单：比分、人物背景和外媒分析各自用于什么 |
| `fact_ledger.json` | 可机械回查的赛果、媒体共识、分歧、数据点和编辑判断 |
| `editorial_decision.json` | 头条与今晚焦点的选择理由、评分拆解和内容约束 |
| `media_synthesis.json` | 外媒多源原创摘要及原文链接，不保存或复制媒体正文 |
| `coverage.txt` | ATP/WTA 赛事覆盖与每个数据源的健康状态 |
| `digest.json` | 当期原始数据快照 |

首次运行还会生成 `output/profile/`：主页简介 `bio.txt`、品牌背景图
`background.png` 和三篇置顶规划 `pinned_plan.md`。这些是一次性主页配置物料，
不会自动修改或提交小红书账号设置。

每次日报通过质量检查后，系统会把头条人物与结果追加到
`data/editorial_memory.json`。后续同一球员再次出现时，文案会把最近一次已发布
记录与已核验的球员/赛事档案接起来；所有历史数字仍需通过事实闸门。

3. 按配置执行发布（见下节）。

</details>

### GitHub Actions 自主产出边界

（已停产）无人参与时，`daily.yml` 曾自动完成比分抓取与跨源去重、规则选题、已审核背景库与媒体摘要的匹配、原创文案、卡片渲染、事实/版式质检、证据包归档，以及按配置推送到微信或公众号草稿箱。Action 会显式检查上述四个 JSON 证据文件；缺失任一文件即视为生成失败。

知识帖配图会先读取 ATP/WTA/赛事或史料来源页的公开元数据用于核对，再从官方媒体、Wikimedia Commons、Openverse 等多源检索高清图。来源与署名全程记录——许可名称、作者、来源 URL 写进 `visual_sources.json` 与 credits（缺失记 `unknown` / `unverified`），检索不以授权状态过滤；发布前的权利判断由人工检验环节负责。球员故事还要求照片标题/分类匹配具体赛事锚点，例如美网、法网或奥运会；只匹配到“球员名 + 年份”的泛相关照片会被拒绝。没有同时通过分辨率、去重和事件相关性检查时，该页自动改用主题专属时间轴或规则示意图。每次生成都会输出 `knowledge/visual_sources.json` 与 `knowledge/visual_qa.json`，Action 在推送前强制检查。

它不会在运行时自由浏览新闻并把未经审核的说法写进正文，也不会在小红书自动发帖。图片检索不以授权状态过滤，但每张图的许可、作者与来源 URL 全程记录；发布前的权利判断由人工检验环节负责。某日没有匹配的已审核媒体摘要时，内容会降级到比分、赛程和已核验档案，不会让模型补写“权威评价”。最终发布前仍建议人工核对事实、观感和素材权利。

## 发布渠道配置（GitHub Secrets / Variables）

### 方案 A：PushPlus 推送到微信（最简单，推荐起步）

把排版好的内容推到你自己的微信：点击按钮复制标题/正文，卡片图逐张保存后导入发布：

1. 在 [pushplus.plus](https://www.pushplus.plus) 微信扫码注册，复制 token
2. 仓库 Settings → Secrets and variables → Actions → 新建 Secret：`PUSHPLUS_TOKEN`
3. 为保证微信稳定显示卡片图，在 PushPlus「开发设置」启用开放接口并设置
   `secretKey`，再新建 GitHub Secret：`PUSHPLUS_SECRET_KEY`。配置后 Action
   会把每张成图先上传至 PushPlus 原生图片 CDN；未配置时使用带版本戳的
   GitHub Pages 图片地址。

推送里的复制按钮由 GitHub Pages 承载；仓库需在 Settings → Pages 中选择 `main` 分支根目录发布。

### 方案 B：公众号 API 自动存草稿 / 发布

**前提**：已认证的公众号（个人未认证订阅号无草稿/发布接口权限）。

Secrets：

| 名称 | 说明 |
|---|---|
| `WECHAT_APPID` | 公众号 AppID |
| `WECHAT_APPSECRET` | 公众号 AppSecret |
| `WECHAT_API_PROXY` | （见下方 IP 白名单说明）固定出口 IP 的 HTTP 代理，如 `http://user:pass@1.2.3.4:8080` |
| `ATP_PROTENNISLIVE_TOKEN` | ATP ProTennisLive Bearer JWT（需 Tournament Claims）；用于 ATP 焦点赛官方逐场技术统计 |
| `SPORTRADAR_API_KEY` | Sportradar Tennis API key，作为 ATP/WTA 焦点赛技术统计备用源 |

Variables（非敏感）：`WECHAT_MODE` = `off`（默认，只生成文件）/ `draft`（自动存草稿箱，后台一键群发）/ `publish`（直接发布，慎用）；`SPORTRADAR_ACCESS_LEVEL` = API 套餐级别，试用账号默认为 `trial`；`TENNISLIVE_VISUAL_FETCH` = `on`（默认，多源检索图片，授权信息仅记录）/ `off`（完全使用本地图片与程序生成信息图）。

> ⚠️ **IP 白名单**：微信获取 access_token 要求调用方 IP 在公众号后台白名单内，而 GitHub Actions 出口 IP 不固定。两种解法：
> 1. 购买/自建一个固定 IP 的 HTTP 代理，配置 `WECHAT_API_PROXY` 并把代理 IP 加入白名单（公众号后台 → 基本配置）；
> 2. 不走 API：用方案 A 或直接复制 `wechat.html` 到公众号编辑器（1 分钟的事）。

流程：上传封面卡片为素材 → 上传赛果/赛程卡片进正文 → `draft/add` 存草稿 →（`publish` 模式下）`freepublish/submit`。

### 小红书

小红书**没有对个人创作者开放发帖 API**，第三方自动发帖工具有封号风险，因此本项目生成"复制即发"的内容包：

1. 手机打开仓库（或 Actions artifact）里的 `output/日期/`
2. `xiaohongshu.txt` 第一行是标题，其余是正文（复制粘贴）
3. `cards/` 里的竖版卡片图按顺序作为配图（封面图放第一张）

配合 PushPlus，内容生成后可直接推到微信里，发帖前人工确认一次即可。

### 网球热点简报（`news-brief.yml` → `tennislive brief`）

**一份简报，一条推送。** 2026-08-05 之前这条线一天发**两条**微信——
「场外网球快讯候选」（8 条英文标题 + 链接）和「今日选题候选」（大多数日子是空的），
两条合起来的信息量等于一份英文标题列表，想知道发生了什么得逐条点开英文页面。

现在一趟做完：

1. **扫**：官方 RSS（ATP/WTA/四大满贯，经 Google News）+ 发布方原生 RSS
   （BBC / Guardian / Sky Sports / Tennis Majors）+ Google Trends + 中文平台热搜
2. **去噪**：摘掉官网的常青导航页（`What is the Washington schedule?` 这类
   永远不是新闻），摘掉几条也写进产物
3. **聚类排热度**：几家在报 / 连着第几天 / 撞上哪条中文热搜
4. **深挖前 N 条**：把原文抓下来，出**中文标题 + 3~5 条中文要点 + 为什么值得知道
   + 可做的角度**；撞上人工角度表（`research/topic_radar.ANGLES`）的还会带上
   「底下压着的常青线」和去哪儿核实
5. **其余至少给中译标题**，原标题留在下面一行供核实
6. **渲成一条 HTML** 推到微信——读者不点开任何链接也知道今天发生了什么

⚠️ **发现和阅读走两路**：Google News 覆盖广（含 ATP/WTA 官网）但它给的 `link` 是
JS 包装页，正文永远抓不到；发布方原生 RSS 源少但链接是真地址。两路一起进聚类，
同一件事自然并成一簇。详见 `research/newsfeeds.py`。

⚠️ **中译和要点要 `ANTHROPIC_API_KEY`**（`pip install -e ".[brief]"`）。
没配不会让它失败，简报退回「只有英文标题和热度」，并在推送正文底部照实写出来——
每一层退化都出声，不静默降级。

定时**没有开**（2026-08-02 停的，改内容形态没有推翻那个决定），手动
`workflow_dispatch` 跑一趟。

### 内容雷达（`flash.yml` → `tennislive content`）

赛前焦点的**完整小红书内容包**（文案 + 4~5 张 1080×1440 卡片），和上面那条简报
不是一回事：简报是「今天有什么」，这条是「一条可以直接发的稿」。同样只留手动。

- 实时热度合并：比赛价值 + ATP/WTA/大满贯官方域名近期报道 + 主流媒体白名单报道 + Google Trends 搜索升温
- 高关联门槛：完整姓名、双方球员或“球员 + 赛事”获得高权重；短姓名和只有城市重合的泛热搜不会触发选题
- 时效衰减：官网/媒体报道只保留 72 小时，搜索趋势只保留 36 小时，越新权重越高
- 赛前焦点：只取开赛前 45–210 分钟的高价值单打，每天最多 1 条
- **完赛热点这一半已关**（`RESULT_DAILY_LIMIT = 0`）——账号所有者 2026-07-31：
  「可以用命令查赛果，但没必要做卡片图然后推送微信了」
- 内容包提交到 `output/YYYY-MM-DD/queue/`，同时上传 Actions artifact 并推送到微信

晨报在无强热点时仍会按现有规则自动选取赛事知识/场馆故事，承担常青内容供给。
人只需在微信或 artifact 中检查事实与观感，然后在小红书确认发布；不使用模拟登录
或第三方群控，避免账号风险。

## 数据源

| 源 | 角色 | 说明 |
|---|---|---|
| Sportradar Tennis v3 | **授权技术统计** | 配置 API key 后为焦点复盘补齐总得分、发球、Ace/双误、破发点及套餐支持的击球统计 |
| ESPN 公开比分接口 | **赛程赛果主源** | 无需鉴权，聚合 ATP/WTA 的赛程、比分与赛果，适合在 GitHub Actions 中运行 |
| SofaScore | **赛程赛果备用** | 数据较全但可能限制数据中心 IP；失败原因会显示在覆盖报告中 |
| Google News 官方域名索引 | **媒体热点信号** | 只读取 ATP/WTA/四大满贯官方域名及主流媒体白名单的标题、来源和发布时间，不复制文章正文 |
| Google Trends Trending Now | **搜索升温信号** | 读取官方 RSS 中香港、美国、英国、澳大利亚的实时趋势；用于加权选题，不作为比赛事实 |

程序会聚合可用的比分源，并按球员、项目和北京时间日期跨源去重。`coverage.txt` 会列出 ATP/WTA 各级别赛事命中场次、每个源的健康状态，以及专业统计是否已授权，避免静默降级。

本项目不在 GitHub Actions 中自动抓取 ATP、WTA、TDI 或大满贯网站页面。官网适合人工核查，批量自动访问需遵守各站条款；需要稳定、可发布的逐场技术统计时，请配置有相应使用权的供应商 API。

## 外媒摘要与视频中文化

外媒内容采用“研究后入库、Action 只消费”的方式：人工或受控研究流程先把同一事件的多篇报道整理为原创中文摘要，只保存标题、媒体名、发布日期、原文链接、报道角度，以及可核验的共识/分歧/数据点；不保存媒体文章正文。每日任务命中对应比赛时，才把这些信息加入图文卡和证据包。

视频翻译、中文字幕和剪辑不改变原视频的版权状态。只有自有素材、明确书面授权、公共领域素材，或许可条款明确允许改编并在目标平台再发布的素材，才可以进入视频中文化流程。每条视频在处理前都应留下权利记录：

- 原始链接、权利人和素材取得方式；
- 许可名称或书面授权凭证，以及适用平台、地域、期限；
- 是否允许下载、改编、翻译、加字幕和再次发布；
- 必须展示的署名、许可链接和其他限制。

权利不清时只输出原创文字摘要和原文链接，不下载、不烧录字幕、不导出待发布视频。ATP/WTA、赛事方、转播商和媒体账号“公开可看”的视频不等于“允许搬运”；翻译和加字幕也不能替代授权。

已确认授权后，可在仓库内准备视频、原文 SRT 和授权清单，手动运行
`.github/workflows/video-localize.yml`；Action 会生成中文字幕、带字幕成片、署名文本和
`rights-audit.json` artifact。授权清单格式与本地命令见
[`docs/video-localization.md`](docs/video-localization.md)。该工作流没有下载器，也不会绕过平台水印或访问控制。

## 中文化

- 球员译名 300+（`src/tennislive/zh/players.py`，中国球员全覆盖）
- 全年 200+ 赛事中文名与级别（大满贯/1000/500/250，合办站按巡回赛区分）
- 轮次/场地/项目术语、国家中文名与旗帜 emoji
- 未收录的名字自动回退英文原名，不影响运行；欢迎 PR 补充

## 项目结构

```
src/tennislive/
├── cli.py            # 命令行入口
├── digest.py         # 每日摘要组装（昨日赛果+今日赛程）
├── models.py         # 统一数据模型
├── timeutil.py       # 北京时间工具
├── sources/          # ESPN / SofaScore 比分聚合 + 可选授权技术统计
├── zh/               # 中文化：球员/赛事/轮次/国家
├── render/           # 终端表格 / 公众号 / 小红书 / Pillow 卡片图
└── publish/          # 公众号草稿 API / PushPlus
.github/workflows/
├── news-brief.yml    # 网球热点简报（扫新闻 → 抓正文 → 中文要点 → 一条微信）
├── flash.yml         # 内容雷达（赛前焦点的完整小红书包）
├── ci.yml            # 测试 + 真实抓取冒烟
└── probe.yml         # 数据源诊断（手动触发）
```

## 开发

```bash
pip install -e ".[dev]"
pytest -v
```

## 免责声明

公开比分仅供个人学习与资讯参考，请以赛事官方信息为准；技术统计仅在配置授权 API 后启用。发布到社交平台时请遵守平台规则、供应商许可与数据来源的使用条款。
