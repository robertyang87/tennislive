# tennislive 🎾

WTA / ATP 巡回赛每日赛程与赛果同步工具（北京时间）：

- **终端 CLI**：随时查询今日赛程、实时比分、昨日赛果
- **每日定时任务**（GitHub Actions）：自动抓取 → 生成微信公众号文章 + 小红书图文内容包（含卡片图）→ 提交回仓库，可选自动推送/发文

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

## 每日自动任务

`.github/workflows/daily.yml` 每天 **北京时间 09:10** 运行（GitHub 定时可能有 10~30 分钟延迟，也可在 Actions 页面手动触发）：

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
| `digest.json` | 当期原始数据 |

3. 按配置执行发布（见下节）。

## 发布渠道配置（GitHub Secrets / Variables）

### 方案 A：PushPlus 推送到微信（最简单，推荐起步）

每天把排版好的内容推到你自己的微信：点击按钮复制标题/正文，卡片图逐张保存后导入发布：

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

Variables（非敏感）：`WECHAT_MODE` = `off`（默认，只生成文件）/ `draft`（自动存草稿箱，后台一键群发）/ `publish`（直接发布，慎用）。

> ⚠️ **IP 白名单**：微信获取 access_token 要求调用方 IP 在公众号后台白名单内，而 GitHub Actions 出口 IP 不固定。两种解法：
> 1. 购买/自建一个固定 IP 的 HTTP 代理，配置 `WECHAT_API_PROXY` 并把代理 IP 加入白名单（公众号后台 → 基本配置）；
> 2. 不走 API：用方案 A 或直接复制 `wechat.html` 到公众号编辑器（1 分钟的事）。

流程：上传封面卡片为素材 → 上传赛果/赛程卡片进正文 → `draft/add` 存草稿 →（`publish` 模式下）`freepublish/submit`。

### 小红书

小红书**没有对个人创作者开放发帖 API**，第三方自动发帖工具有封号风险，因此本项目生成"复制即发"的内容包：

1. 手机打开仓库（或 Actions artifact）里的 `output/日期/`
2. `xiaohongshu.txt` 第一行是标题，其余是正文（复制粘贴）
3. `cards/` 里的竖版卡片图按顺序作为配图（封面图放第一张）

配合 PushPlus，每天早上内容直接推到微信里，发帖 1 分钟完成。

## 数据源

| 源 | 角色 | 说明 |
|---|---|---|
| ESPN 公开接口 | **主源** | 无需鉴权，覆盖 ATP/WTA 赛程比分赛果，GitHub Actions 实测可用 |
| SofaScore | 备用 | 数据全但封数据中心 IP，本地网络可用，CI 中通常 403 |

主源失败自动切换备用源。ATP/WTA 官网（含球员头像）有 Cloudflare 防护，无法在 CI 中直接抓取；
球员头像可用 ESPN CDN（`a.espncdn.com/i/headshots/tennis/players/full/{id}.png`，数据里已带 URL 字段）。
数据为非官方公开接口，可能变更；`probe.yml` 工作流可手动触发以诊断数据源健康状态。

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
├── sources/          # 数据源（espn 主源 / sofascore 备用，自动回退）
├── zh/               # 中文化：球员/赛事/轮次/国家
├── render/           # 终端表格 / 公众号 / 小红书 / Pillow 卡片图
└── publish/          # 公众号草稿 API / PushPlus
.github/workflows/
├── daily.yml         # 每日定时任务（北京时间 09:10）
├── ci.yml            # 测试 + 真实抓取冒烟
└── probe.yml         # 数据源诊断（手动触发）
```

## 开发

```bash
pip install -e ".[dev]"
pytest -v
```

## 免责声明

数据来自公开比分接口，仅供个人学习与资讯参考，请以 ATP/WTA 官方为准；
发布到社交平台时请遵守平台规则与数据来源的使用条款。
