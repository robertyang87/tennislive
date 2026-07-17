# tennislive 🎾

WTA / ATP 巡回赛每日赛程与赛果同步工具（北京时间）：

- **终端 CLI**：随时查询今日赛程、实时比分、昨日赛果
- **手动内容任务**（GitHub Actions）：抓取 → 生成微信公众号文章 + 小红书图文内容包（含卡片图）→ 提交回仓库，可选推送/存草稿

## 快速开始（本地 CLI）

```bash
pip install -e .

tennislive today                    # 今日总览：赛果 + 进行中 + 赛程（北京时间）
tennislive results --date yesterday # 昨日赛果
tennislive schedule --date tomorrow # 明日赛程
tennislive live                     # 进行中的比赛
tennislive digest                   # 生成今日内容包到 output/YYYY-MM-DD/
```

所有时间均为北京时间；`--date` 支持 `YYYY-MM-DD` / `today` / `yesterday` / `tomorrow` / `±N`。
`--json` 输出原始 JSON。生成卡片图需要中文字体（Ubuntu：`sudo apt install fonts-noto-cjk`）。

## 内容生成任务

`.github/workflows/daily.yml` 由 Actions 页面手动触发，不绑定固定发布时间；生成后先人工检查文案与图片，再决定是否发布：

1. 抓取昨日赛果 + 今日赛程（含凌晨刚结束的欧美比赛）
2. 生成内容包并提交到仓库 `output/YYYY-MM-DD/`：

| 文件 | 用途 |
|---|---|
| `wechat_title.txt` | 公众号文章标题（自动挑亮点：中国球员优先） |
| `wechat.md` | 公众号文章 Markdown（配合 md2wechat 等工具排版） |
| `wechat.html` | 内联样式 HTML，可直接粘贴进公众号编辑器或走 API 发草稿 |
| `xiaohongshu.txt` | 小红书文案（标题 ≤20 字、正文 ≤1000 字、话题标签） |
| `copy.html` | 手机文案复制页（标题、正文可分别一键复制） |
| `cards/*.png` | 1080×1440 竖版卡片图：封面 + 赛果页 + 赛程页 |
| `coverage.txt` | ATP/WTA 赛事覆盖与每个数据源的健康状态 |
| `digest.json` | 当期原始数据 |

3. 按配置执行发布（见下节）。

## 发布渠道配置（GitHub Secrets / Variables）

### 方案 A：PushPlus 推送到微信（最简单，推荐起步）

把排版好的内容推到你自己的微信：点击按钮复制标题/正文，卡片图逐张保存后导入发布：

1. 在 [pushplus.plus](https://www.pushplus.plus) 微信扫码注册，复制 token
2. 仓库 Settings → Secrets and variables → Actions → 新建 Secret：`PUSHPLUS_TOKEN`

推送里的复制按钮由 GitHub Pages 承载；仓库需在 Settings → Pages 中选择 `main` 分支根目录发布。

### 方案 B：公众号 API 自动存草稿 / 发布

**前提**：已认证的公众号（个人未认证订阅号无草稿/发布接口权限）。

Secrets：

| 名称 | 说明 |
|---|---|
| `WECHAT_APPID` | 公众号 AppID |
| `WECHAT_APPSECRET` | 公众号 AppSecret |
| `WECHAT_API_PROXY` | （见下方 IP 白名单说明）固定出口 IP 的 HTTP 代理，如 `http://user:pass@1.2.3.4:8080` |
| `SPORTRADAR_API_KEY` | Sportradar Tennis API key，用于焦点赛专业技术统计；未配置时自动使用比分结构复盘 |

Variables（非敏感）：`WECHAT_MODE` = `off`（默认，只生成文件）/ `draft`（自动存草稿箱，后台一键群发）/ `publish`（直接发布，慎用）；`SPORTRADAR_ACCESS_LEVEL` = API 套餐级别，试用账号默认为 `trial`。

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

## 数据源

| 源 | 角色 | 说明 |
|---|---|---|
| Sportradar Tennis v3 | **授权技术统计** | 配置 API key 后为焦点复盘补齐总得分、发球、Ace/双误、破发点及套餐支持的击球统计 |
| ESPN 公开比分接口 | **赛程赛果主源** | 无需鉴权，聚合 ATP/WTA 的赛程、比分与赛果，适合在 GitHub Actions 中运行 |
| SofaScore | **赛程赛果备用** | 数据较全但可能限制数据中心 IP；失败原因会显示在覆盖报告中 |

程序会聚合可用的比分源，并按球员、项目和北京时间日期跨源去重。`coverage.txt` 会列出 ATP/WTA 各级别赛事命中场次、每个源的健康状态，以及专业统计是否已授权，避免静默降级。

本项目不在 GitHub Actions 中自动抓取 ATP、WTA、TDI 或大满贯网站页面。官网适合人工核查，批量自动访问需遵守各站条款；需要稳定、可发布的逐场技术统计时，请配置有相应使用权的供应商 API。

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
├── daily.yml         # 手动生成内容包（无固定发布时间）
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
