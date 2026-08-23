# 无人值守流水线：耗时 / 并行 / 稳定性 / 自愈 现状盘点

2026-08-23 复盘并执行整改；2026-08-24 增补 10 分钟成片 SLO。目标（账号所有者）：
自动化，多场并行，时效性高不能卡住，稳定性高，能自我修复。

## 1. 一条片子的时间账（实测）

match-reel run 实测耗时（按 mode 分）：

| mode | 做什么 | 实测耗时 |
|---|---|---|
| push | 只发微信 | 41s |
| cookies | 只验 YouTube 能不能下 | 51s |
| narration | 只查旁白装不装得下 | ~110s |
| probe | 下源片 + 缩略图墙 + 切点 + 字幕 + 备料草稿 | 128~409s |
| render | 分段 + TTS + 混音 + 编码 | 271~831s（片长越长效） |

2026-08-23 的两条线上基线（GitHub Actions 公共 run 的 step 时间）：

| 生产线 | 样本 | 链接/任务接收 → MP4 落盘 | 最大单项 |
|---|---|---:|---:|
| 赛场之上 | run 32648021397，131.6s 成片 | **约 7m10s** | render step 5m11s |
| 赛后开麦 | run 32629170762 | **约 10m09s** | 第二份 ASR 5m44s |

第二条已经越过 600 秒，根因不是编码画质，而是每趟重下 faster-whisper 模型，且
采访线没有复用已有 Chromium 缓存。本轮已按模型名缓存 Hugging Face 目录，并与
match-reel 共用 Playwright Chromium 缓存；不改 ASR 模型、不降编码 preset/CRF。

### 10 分钟口径

- 起点：生产可用的视频链接与正式 spec 已确认、dispatch 的 UTC 时刻。自动链路用
  `received_at` 原样传到 render；手动没传时从 runner 第一秒起算，不能装完依赖再起表。
- 终点：我们自己的非空 MP4 已落盘。Release、git 提交、Pages、微信属于发布 SLO，
  不混进成片耗时。
- 产物：`render.json.production_sla` 记录起止时刻、总秒数、准备秒数、render 秒数、
  600 秒目标和 `met`；Actions summary 同步显示 PASS/FAIL。
- 超线策略：**告警但不一刀切**。内容完整、L2 质检合格的片子继续自动发布；warning
  留作下一轮定点性能修复，不能因慢而丢片或砍内容。

原来的 probe / 备料 / 编辑闭环仍单独计发现与准备延迟，不能拿 10 分钟生产 SLO
掩盖。长片（306s 源片）历史 render 仍可能到 14~17 分，是明确的超线性能债。

## 2. 并行性：哪里并行、哪里串行

| 环节 | 并行/串行 | 证据 |
|---|---|---|
| probe/render 跑起来 | ✅ **天然并行** | `concurrency: group: match-reel-${{slug}}`，即使 render 请求 `push=true` 也不占发布锁 |
| 不同栏目（reel/interview/explainer） | ✅ 并行 | 各是独立 workflow |
| 编排器「探测集锦」 | ✅ 已并行（2026-08-17 改） | ThreadPoolExecutor，N 场探测时间压成最慢那一场 |
| 编排器「dispatch run」 | ⚠️ 串行 | gh workflow run 每场 1~2s，N 场串行 ~N×2s，可接受 |
| 同一 slug 的 probe/render | ⚠️ 串行（设计如此） | concurrency cancel-in-progress，防互相覆盖 output |
| 赛后开麦候选转写 | ✅ 逐场 matrix | `oncourt-interviews` 每 15 分钟扫描，一场一个 runner，`max-parallel: 4` |
| 赛后开麦多来源扫描 | ✅ 4 路有界并行 | 最新串行采集 16m15s；不同来源并行、结果仍按注册表顺序处理，参数硬限 1..8 |
| 赛后开麦冷开场搜索/翻译 | ✅ 并行 | `attach_interview_lead_in.py` ThreadPoolExecutor，默认 4 |
| 赛后开麦 render / publish | ✅ 按 slug 并行 | 两条 workflow 的 concurrency 都按 slug 分组 |

**关键结论**：多场的搜索、probe、render 都已并行。只有三类动作串行：同 slug
防覆盖、dispatch 后逐条写 state，以及不可撤回的微信发送。生产 render 质检落库后
另派轻量 `mode=push`，所以发布锁不再把前面的 6–14 分钟渲染一起串行。

## 3. 稳定性：哪些地方会静默失败

| 风险点 | 现状 | 会静默吗 |
|---|---|---|
| YouTube 正常空结果 | 返回 []，打印“尚未发布”，下一班重探 | 不静默 |
| YouTube 超时/429/非零退出 | 抛 `HighlightSourceError`；其他比赛继续，整班最终红灯 + PushPlus | 不再冒充空结果 |
| Tennis TV 备选源异常 | 保持降级，但打印 `source-warning`（WTA 不因不适用的 ATP 备选源变红） | 不静默 |
| 探测到**错的**集锦（别的站/别的场） | 标题同时卡双方、赛事、年份、单场形状、官方频道、≤12 分钟、1080p | ⚠️ 仍缺下载后的比分板/球员名 L0 复核 |
| probe 跑起来后失败（下载失败/无字幕） | 失败步骤把 slug 从 state 摘掉，下班重探重发 | 已自愈 |
| cron / 资源探测 / dispatch 失败 | run 红灯并 PushPlus 通知；成功派发的 state 用 `always()` 先落库 | 不静默 |
| 封面抓到却未落库 | 官方头图现在随草稿单独 `git add` | 已修 |
| 封面抓不到官方实拍 | 草稿留空出声，render 前 `cover_photo_problem` 硬拦 | 不降级发糊图 |

## 4. 自愈：失败会不会自己重来

| 场景 | 会不会自愈 | 缺口 |
|---|---|---|
| 集锦还没上传（探测没搜到） | ✅ 会 | 探测失败**不记 state**，下次 cron 重探 |
| probe 失败（下到一半/无字幕） | ✅ 会 | 失败 run 摘 state，下一班重探 |
| render 失败 | ⚠️ 部分 | concurrency cancel 了旧 run 不重跑，要人手动 re-run |
| cron 本身失败 | ✅ 会再跑 + 立即告警 | 10 分钟后下一班；当班 PushPlus 报故障 |
| render 质检通过 | ✅ 自动继续 | 成片/Release/提交成功后派 `mode=push`；发布任务全局串行 |

## 5. 已修 / 待修清单

**已修（2026-08-17）**：
- 编排器探测集锦并行化（ThreadPoolExecutor）

**已修（2026-08-23，赛后开麦）**：
- 每 15 分钟扫描，候选同时写生产清单和来源待复核清单。
- L0 先证明“本场获胜后的场上话筒采访”；发布会、演播室、unknown 不制作。
- 多比赛逐场 matrix 并行转写；词级时间码与正式切行器同源后逐行翻译。
- 独立采访自动配同场官方集锦末段、原声解说和中英字幕，找不到不降级。
- L2 生成绑定 spec/source/正文 ASS/冷开场 ASS/film 的 QC attestation；正文和
  原解说都逐 cue 核对中英字幕，通过即自动推送。
- 同姓球员的赛果匹配同时核对名字首字母、赛事和轮次；仍有歧义就停产，不猜首条。
- 发送前独立 ledger 预占，成功/状态不明都有持久记录，重渲不能擦除。
- render dispatch 超过 3 小时仍无 `render.json` 会自动释放重投并刷新时刻；
  最近刚投出的仍保持单飞，不会因 10 分钟扫描重复启动。

**2026-08-23 本轮新增整改**：
- `orchestrate` 从“定时只 dry-run”改为每 10 分钟真 `--apply`，最多八场。
- YouTube 源站错误与正常空结果分型；单场错误不阻塞其他比赛，整班仍告警。
- probe 生成的 WTA 官方封面随草稿提交，不再留下失效引用。
- 批量生产 render 默认 `push=true`；多场按 slug 并行，L2 质检落库后自动派
  push-only，全局只串行微信 POST 和发布账本。

**2026-08-24 10 分钟成片整改**：
- match-reel / interview-clip 共用 `received_at → production_sla` 计时合同；调度器
  传原始时刻，成片工具合并写入 `render.json`，超线出 warning、不阻断发布。
- 赛后开麦缓存第二份 ASR 模型和 Chromium，针对 10m09s 样本的 5m44s 最大项下刀，
  不改转写模型、不降画质。
- 草稿 matrix 完成后立即 dispatch `interview-auto-render`，取消 0~10 分钟空等；
  多个正式采访仍按 slug 并行 render。
- 场上采访来源从逐个串行改成 4 路有界并行；保留注册表顺序与 1..8 防限流上限。

**仍待修（按优先级）**：
1. **赛场之上草稿 → 正式 spec 的语义闭环**：probe 会自动产出 pending 草稿，
   但草稿的比分/赢家/顶栏/结构化资料来源/冷开场兑现仍不足以安全通过 L1。
   不能把“模型写出 JSON”直接当终审；需要像 interview 的 promote 工具一样，
   从赛果和来源证据机械补齐，再用视觉/比分板验证窗口，过 L1 才进入 render。
2. **下载后 L0 同场身份闸**：OCR/视觉读取片中双方和赛事，与候选签名核对；
   标题窄匹配仍不能百分之百防官方频道错挂/合集错段。
3. **render 失败自动重试的边界**：网络/Release 5xx 可有限重试；spec/画面质量失败
   必须保持红灯，不应盲重跑。
4. **ATP 当场高清封面自动源**：WTA 已能抓官方赛后稿头图，ATP 仍缺同强度通路。
