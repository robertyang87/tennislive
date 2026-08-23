# 无人值守流水线：耗时 / 并行 / 稳定性 / 自愈 现状盘点

2026-08-23 复盘并执行整改。目标（账号所有者）：自动化，多场并行，时效性高不能卡住，
稳定性高，能自我修复。

## 1. 一条片子的时间账（实测）

match-reel run 实测耗时（按 mode 分）：

| mode | 做什么 | 实测耗时 |
|---|---|---|
| push | 只发微信 | 41s |
| cookies | 只验 YouTube 能不能下 | 51s |
| narration | 只查旁白装不装得下 | ~110s |
| probe | 下源片 + 缩略图墙 + 切点 + 字幕 + 备料草稿 | 128~409s |
| render | 分段 + TTS + 混音 + 编码 | 271~831s（片长越长效） |

机器串行下限（单场、正常长度）：probe ~4 分 + render ~6 分 + 质检合并 ~1 分 ≈ 11 分。
符合 docs/thirty-minute-pipeline.md 的账。**长片（306s 源片）render 涨到 14~17 分**，
30 分钟目标对长片结构性达不到（已记在半小时协议里）。

## 2. 并行性：哪里并行、哪里串行

| 环节 | 并行/串行 | 证据 |
|---|---|---|
| probe/render 跑起来 | ✅ **天然并行** | `concurrency: group: match-reel-${{slug}}`，不同 slug 互不阻塞 |
| 不同栏目（reel/interview/explainer） | ✅ 并行 | 各是独立 workflow |
| 编排器「探测集锦」 | ✅ 已并行（2026-08-17 改） | ThreadPoolExecutor，N 场探测时间压成最慢那一场 |
| 编排器「dispatch run」 | ⚠️ 串行 | gh workflow run 每场 1~2s，N 场串行 ~N×2s，可接受 |
| 同一 slug 的 probe/render | ⚠️ 串行（设计如此） | concurrency cancel-in-progress，防互相覆盖 output |
| 赛后开麦候选转写 | ✅ 逐场 matrix | `oncourt-interviews` 一场一个 runner，`max-parallel: 4` |
| 赛后开麦冷开场搜索/翻译 | ✅ 并行 | `attach_interview_lead_in.py` ThreadPoolExecutor，默认 4 |
| 赛后开麦 render / publish | ✅ 按 slug 并行 | 两条 workflow 的 concurrency 都按 slug 分组 |

**关键结论**：多场并行的**瓶颈不在流水线**（probe/render 天然并行），而在
**编排器 dispatch 之前的那段探测**——已经并行化了。剩下的串行点都是「本来就该
串行」的（同 slug 不能并发、dispatch 要顺序写 state）。

## 3. 稳定性：哪些地方会静默失败

| 风险点 | 现状 | 会静默吗 |
|---|---|---|
| 集锦探测超时/没搜到 | `search()` 返回 []，`tennistv_fallback` 吞 SystemExit | 出声（日志） |
| 探测到**错的**集锦（别的站/别的场） | `pick_highlight` 判据「宁可窄」，但拿错仍可能 | ⚠️ 静默——流水线无一步拦，只有人看才发现 |
| probe 跑起来后失败（下载失败/无字幕） | 编排器已标记「已 dispatch」，不会重试 | ❌ 静默，且不重试 |
| cron 失败 / dispatch 0 条 | 无告警 | ❌ 静默——日志有，但没人被叫回来 |
| 封面抓不到官方实拍 | `fetch_cover` 返回非 0，草稿留空出声 | 出声，但 render 前闸会拦 |

## 4. 自愈：失败会不会自己重来

| 场景 | 会不会自愈 | 缺口 |
|---|---|---|
| 集锦还没上传（探测没搜到） | ✅ 会 | 探测失败**不记 state**，下次 cron 重探 |
| probe 失败（下到一半/无字幕） | ❌ 不会 | 编排器已记「已 dispatch」，永不重试 |
| render 失败 | ⚠️ 部分 | concurrency cancel 了旧 run 不重跑，要人手动 re-run |
| cron 本身失败 | ❌ 不会 | 无告警，要人去看 run 列表 |

## 5. 已修 / 待修清单

**已修（2026-08-17）**：
- 编排器探测集锦并行化（ThreadPoolExecutor）

**已修（2026-08-23，赛后开麦）**：
- 每 30 分钟扫描，候选同时写生产清单和来源待复核清单。
- L0 先证明“本场获胜后的场上话筒采访”；发布会、演播室、unknown 不制作。
- 多比赛逐场 matrix 并行转写；词级时间码与正式切行器同源后逐行翻译。
- 独立采访自动配同场官方集锦末段、原声解说和中英字幕，找不到不降级。
- L2 生成绑定 spec/source/正文 ASS/冷开场 ASS/film 的 QC attestation；正文和
  原解说都逐 cue 核对中英字幕，通过即自动推送。
- 同姓球员的赛果匹配同时核对名字首字母、赛事和轮次；仍有歧义就停产，不猜首条。
- 发送前独立 ledger 预占，成功/状态不明都有持久记录，重渲不能擦除。
- render dispatch 超过 3 小时仍无 `render.json` 会自动释放重投并刷新时刻；
  最近刚投出的仍保持单飞，不会因 10 分钟扫描重复启动。

**待修（按优先级）**：
1. **probe 失败自愈**：编排器 state 要区分「已 dispatch」和「dispatch 但失败了」。
   目前 `mark_dispatched` 只记成功，probe 失败后不会重试。改法：probe 工作流
   失败时把 slug 从 state 摘掉（或 state 记「最后一次 dispatch 的 run 状态」），
   下次 cron 就能重探重发。
2. **失败告警**：cron 失败 / dispatch 0 条 / probe 失败，推到微信或至少写进
   job summary 并标红（CLAUDE.md「出了问题当场解决，别等人来问」）。
3. **探测拿错的兜底**：pick_highlight 已经「宁可窄」，但「拿错」这最后一层没有
   闸。可考虑 probe 后校验源片记分条上的球员名，对不上就报废重探。
