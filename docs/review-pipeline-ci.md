# 三条视频流水线 Actions 实跑审查（2026-10-04）

本轮最值得处理的是重复返工、素材检出以及采访转写长尾。主线渲染并非普遍超过十分钟；清理误删证据和缓存缺口则有明确代码证据，已在本轮修复。以下运行数据均来自修改上线前的历史运行，不能作为本轮优化后的收益。

## 数据范围与限制

- 采集时间：2026-10-04T23:04:13+00:00。仓库 `robertyang87/tennislive`。
- 对三条主线分别请求最近 30 次运行；对 8 条定时工作流分别请求最近 20 次运行。仅取单页，没有遍历全历史。
- 读取三条主线全部 90 次运行的 job/step 元数据；另读每条定时工作流最新 3 次，共 114 次运行的步骤信息。没有下载日志、没有读取密钥、没有触发工作流。
- “运行墙钟”是 `updated_at - created_at`，含队列、准备和收尾；不是 GitHub 计费分钟。步骤耗时取 `completed_at - started_at`，API 精度为秒；0 秒不代表没有执行。
- failure 只表示运行失败，可能是质量闸正确拒绝，不等于代码缺陷；cancelled 单列。成功成片必须同时满足运行 success 且真正渲染步骤 success，不能把 probe/subs/push 的绿灯当出片成功。
- 三个 30 次样本的时间窗口差异很大，不能据此直接比较栏目稳定性。采访旧标题无 mode，失败若发生在渲染前无法可靠区分 render/cover，故不编造整窗 render 失败率。

## 运行结果

| 栏目 | UTC 样本窗口 | 成功 / 失败 / 取消 | 失败占全部运行 | 成功成片数 | 成功成片墙钟中位数 |
|---|---|---:|---:|---:|---:|
| 赛场之上 | 2026-10-03T20:19:49Z 至 2026-10-04T21:33:22Z | 21 / 7 / 2 | 23.3% | 5 | 7.18 分钟 |
| 赛后开麦 | 2026-09-27T01:45:10Z 至 2026-10-04T18:43:30Z | 15 / 13 / 2 | 43.3% | 9 | 6.82 分钟 |
| 网球有故事 | 2026-09-03T09:39:17Z 至 2026-10-01T04:51:26Z | 28 / 0 / 2 | 0.0% | 28 | 4.67 分钟 |

赛场之上样本中，标题明确为 render 的 12 趟：5 成功、6 失败、1 取消。失败占全部 render 为 50.0%，排除取消后为 54.5%；样本集中在少数同一 slug 的反复调试，不能外推长期失败率。赛后开麦只有最新 2 趟标题明确为 render（1 成功、1 失败），其余旧标题不能可靠归类。

## 最大耗时步骤

只统计上表成功成片。不同步骤的中位数来自不同运行，不能相加当整趟中位数。

| 栏目 | 步骤 | 中位秒数 | 最大秒数 | 样本数 |
|---|---|---:|---:|---:|
| 赛场之上 | render — 出成片 | 254 | 378 | 5 |
| 赛场之上 | Run actions/checkout@v4 | 69 | 74 | 5 |
| 赛场之上 | 装依赖 | 29 | 30 | 5 |
| 赛场之上 | 起 PO token provider | 11 | 16 | 5 |
| 赛后开麦 | 剪 + 烧字幕 | 158 | 259 | 9 |
| 赛后开麦 | 转写交叉校验 | 100 | 621 | 9 |
| 赛后开麦 | Run actions/checkout@v4 | 35 | 71 | 9 |
| 赛后开麦 | 装依赖 | 17 | 34 | 9 |
| 网球有故事 | 生成解说视频 | 152.5 | 239 | 28 |
| 网球有故事 | 安装 ffmpeg | 29 | 33 | 28 |
| 网球有故事 | Run actions/checkout@v4 | 27 | 57 | 28 |
| 网球有故事 | 安装 Chromium | 17 | 20 | 28 |

网球有故事样本跨近一个月，`安装 ffmpeg` 的历史中位 29 秒包含旧实现，不能解释为当前每次仍付同样成本。三线最新成功成片如下：

| 栏目 | 运行 | 总墙钟 | 最慢 3 步 |
|---|---|---:|---|
| 赛场之上 | [37213753618](https://github.com/robertyang87/tennislive/actions/runs/37213753618) | 9.13 分钟 | render — 出成片 378s；Run actions/checkout@v4 69s；装依赖 27s |
| 赛后开麦 | [37225530876](https://github.com/robertyang87/tennislive/actions/runs/37225530876) | 6.37 分钟 | 剪 + 烧字幕 123s；Run actions/checkout@v4 71s；转写交叉校验 66s |
| 网球有故事 | [36817051948](https://github.com/robertyang87/tennislive/actions/runs/36817051948) | 3.47 分钟 | 生成解说视频 107s；Run actions/checkout@v4 41s；安装中文字体（幻灯需要） 14s |

采访 [36338290942](https://github.com/robertyang87/tennislive/actions/runs/36338290942) 的转写交叉校验为 621 秒，整趟 1019 秒。它是真正的长尾样本，优化应优先复用有效的转写判定、已验证素材及模型缓存，不能通过删除交叉校验降低质量。

## 失败落点

以下只统计 conclusion=failure 的步骤名称；不读取日志就无法进一步认定具体错误或质量问题。

| 栏目 | 失败步骤 | 次数 |
|---|---|---:|
| 赛场之上 | render — 出成片 | 3 |
| 赛场之上 | 查成片本身合不合格 | 2 |
| 赛场之上 | 发布文案前置检查 | 1 |
| 赛场之上 | narration — 只查旁白装不装得下 | 1 |
| 赛后开麦 | 转写交叉校验 | 6 |
| 赛后开麦 | 验封面视觉（完全本地，生产硬闸） | 3 |
| 赛后开麦 | 出封面并验视觉（完全本地，排在转写和编码之前） | 2 |
| 赛后开麦 | 剪 + 烧字幕 | 1 |
| 赛后开麦 | 取字幕切行 | 1 |

赛后开麦的 13 次失败中，6 次落在转写交叉校验、5 次落在封面视觉闸；这支持“把可本地判定的错误尽早挡住、有效证据可复用”，不支持取消这些闸。赛场之上另有 2 次落在成片质检，不能当作可删除的冗余。

## 定时调度观察

工作流文件共 60 份，8 份含启用的 schedule。配置理论频次合计 772 次/天；实际 GitHub schedule 有延迟/丢弃，且工作流互相唤醒，下面的近 20 次混合了 schedule、workflow_dispatch 与 push，不能把配置次数乘中位墙钟当成实付成本。

| 工作流 | 配置次/天 | 近20次成功/失败/取消 | schedule / dispatch / 其它 | 墙钟中位数 | UTC窗口 |
|---|---:|---:|---:|---:|---|
| official-social-images | 144 | 20/0/0 | 20/0/0 | 82s | 2026-10-01T05:39:02Z 至 2026-10-04T21:50:31Z |
| interview-auto-render | 144 | 20/0/0 | 4/13/3 | 84.5s | 2026-10-04T07:26:11Z 至 2026-10-04T22:16:32Z |
| source-health | 4 | 20/0/0 | 20/0/0 | 44s | 2026-09-28T23:19:37Z 至 2026-10-04T21:33:18Z |
| oncourt-interviews | 96 | 17/3/0 | 20/0/0 | 389s | 2026-10-01T05:41:16Z 至 2026-10-04T21:40:28Z |
| reel-auto-ready | 144 | 20/0/0 | 3/17/0 | 113s | 2026-10-04T08:52:12Z 至 2026-10-04T22:16:26Z |
| pipeline-health | 24 | 20/0/0 | 8/12/0 | 38.5s | 2026-10-03T16:46:48Z 至 2026-10-04T22:32:40Z |
| reel-cover-upgrade | 72 | 20/0/0 | 6/14/0 | 22s | 2026-10-03T22:14:12Z 至 2026-10-04T22:16:30Z |
| orchestrate | 144 | 20/0/0 | 5/15/0 | 53s | 2026-10-04T05:44:09Z 至 2026-10-04T22:15:43Z |

最近步骤证据：

- [official-social-images 37237698757](https://github.com/robertyang87/tennislive/actions/runs/37237698757)：checkout 67 秒，扫描步骤 0 秒、落库步骤 0 秒。另按该 run 的确切 revision `4adb2769d4a2b41b6cc18994c0b0513d8dee618a` 读取 watch 配置：唯一任务截至 `2026-08-28T23:59:59Z`，按 `_active` 在这趟 10 月 4 日运行中必定跳过。因此这一趟有明确空轮询证据；不外推全部 20 趟。
- [reel-auto-ready 37239383734](https://github.com/robertyang87/tennislive/actions/runs/37239383734)：checkout 88 秒，重试封面/证据/提升 22 秒。应优先减小轮询检出范围，不能只削业务检查。
- [reel-cover-upgrade 37239387705](https://github.com/robertyang87/tennislive/actions/runs/37239387705)：checkout 11 秒，找目标 0 秒，后续依赖/识别步骤跳过，已有早退生效。
- [interview-auto-render 37239389401](https://github.com/robertyang87/tennislive/actions/runs/37239389401)：早退探针执行 19 秒后仍进入依赖和 provider 步骤。仅凭 step 元数据无法断定这是无效空转，需以后记录候选数、实际派发数、阻塞原因和内容指纹。

建议顺序：

1. 官方图片轮询的检出收窄已实施，详见下节。reel-auto-ready 仍应先量候选/变化/派发数量，再逐一对照封面识别的文件依赖收窄资源检出，确保素材、字体和证据仍可用。
2. 用主事件唤醒＋低频兜底替代重复短周期扫描需要先量 source 发布时间和最大可接受发现延迟，同时保留 schedule 丢失后的恢复机制。当前样本不足以定一个新的安全 cron，故本轮没有改频率。
3. 健康检查安静就是正常，不能按“没有视频产出”认定其冗余。手动历史工作流不增加 schedule 成本，删除前应证明无入口/无恢复用途。

## 本轮已经落实的局部改进

- 两条此前未持久化共享 TTS 的工作流接入缓存：采访只在 render 恢复；解说片按 slug、语音参数和代码输入分隔。相同输入稳定主键避免每趟重复存一份。TTS 实现变化隔离旧缓存。
- 三线 artifact 使用 `compression-level: 0`。本地 3,567,085 字节 H264 样片，zlib level 6 用 0.1507 秒仅省 0.004%，level 0 用 0.0063 秒；这是样片实验，不是生产加速承诺。
- match 清理改为 source 前缀＋媒体扩展名，避免裸 `source*` 误删已入库的来源证据；失败 artifact 同步保留 JSON/TXT 证据。
- 官方图轮询改用 non-cone 稀疏检出，只取根安装文件、data/specs/src/tools、官方图专属目录及 `output/**/render.json`。调用链为 `collect_official_social_images.py → official_social_images`：不读取其它 assets；`monitor_trigger_ready` 却需要 render 清单。旧配置整个排除 output，会让新启用的 watch 错报尚未成片；本轮同时补齐这份轻量输入。
- 对 revision `4adb2769d4a2b41b6cc18994c0b0513d8dee618a` 的 Git Trees API blob-size 元数据逐路径求和，原检出 4,581 文件 / **1,258,504,003 字节（1200.20 MiB）**；新检出 3,287 文件 / **55,528,654 字节（52.96 MiB）**，内容体积约减少 **95.59%**。根树的递归响应过大，改对所需子树分别读取并确认 `truncated=false`；未下载媒体文件。这里是 HEAD 未压缩 blob 的工作区检出体积估算，既不是 Git pack 网络字节，也不是已实测 Actions 耗时改进。
- 新增真实临时 Git 仓库的稀疏检出行为测试：根 pyproject/README 与源码保留、媒体排除、官方 watch 的 spec/render 输入保留、实际 `monitor_trigger_ready` 通过、新官方图和结果能正常进 git 索引。
- 更新后共 35 项定向测试通过；此前三线 91 个 shell 块通过 `bash -n`，新测试包含真实执行清理脚本。未降低质量闸，也未触发发布。

## 复查方式

```bash
gh api "repos/robertyang87/tennislive/actions/workflows/match-reel.yml/runs?per_page=30"
gh api "repos/robertyang87/tennislive/actions/runs/37213753618/jobs?per_page=100"
```

替换 workflow 文件名或运行 ID 即可。以下逐条索引保留当时的样本；后续“近30次”会随新运行移动。

### 赛场之上：30次运行索引

| 运行 | 创建时间 UTC | 标题 | 结论 | 墙钟秒 | 失败步骤 |
|---|---|---|---|---:|---|
| [37236570182](https://github.com/robertyang87/tennislive/actions/runs/37236570182) | 2026-10-04T21:33:22Z | match-reel · cookies · eala-zheng | success | 128 | — |
| [37215542135](https://github.com/robertyang87/tennislive/actions/runs/37215542135) | 2026-10-04T16:06:31Z | match-reel · push · zverev-djokovic | success | 138 | — |
| [37213753618](https://github.com/robertyang87/tennislive/actions/runs/37213753618) | 2026-10-04T15:38:23Z | match-reel · render · zverev-djokovic | success | 548 | — |
| [37208304068](https://github.com/robertyang87/tennislive/actions/runs/37208304068) | 2026-10-04T14:10:52Z | match-reel · probe · zverev-djokovic | success | 497 | — |
| [37202182946](https://github.com/robertyang87/tennislive/actions/runs/37202182946) | 2026-10-04T12:27:45Z | match-reel · cookies · eala-zheng | success | 119 | — |
| [37198396596](https://github.com/robertyang87/tennislive/actions/runs/37198396596) | 2026-10-04T11:20:21Z | match-reel · probe · medvedev-cerundolo | success | 332 | — |
| [37194752841](https://github.com/robertyang87/tennislive/actions/runs/37194752841) | 2026-10-04T10:15:01Z | match-reel · probe · de-rublev | success | 375 | — |
| [37194751234](https://github.com/robertyang87/tennislive/actions/runs/37194751234) | 2026-10-04T10:15:00Z | match-reel · probe · vacherot-fils | success | 290 | — |
| [37194749785](https://github.com/robertyang87/tennislive/actions/runs/37194749785) | 2026-10-04T10:14:58Z | match-reel · probe · minaur-rublev | success | 335 | — |
| [37191024903](https://github.com/robertyang87/tennislive/actions/runs/37191024903) | 2026-10-04T09:05:27Z | match-reel · probe · yastremska-chwalinska-ci-scorebox | success | 297 | — |
| [37185767230](https://github.com/robertyang87/tennislive/actions/runs/37185767230) | 2026-10-04T07:26:05Z | match-reel · probe · alcaraz-shapovalov | success | 350 | — |
| [37185400772](https://github.com/robertyang87/tennislive/actions/runs/37185400772) | 2026-10-04T07:18:51Z | match-reel · render · sabalenka-bartunkova-beijing-2026-r3 | success | 386 | — |
| [37184849680](https://github.com/robertyang87/tennislive/actions/runs/37184849680) | 2026-10-04T07:07:41Z | match-reel · render · sabalenka-bartunkova-beijing-2026-r3 | failure | 397 | 查成片本身合不合格 |
| [37184253645](https://github.com/robertyang87/tennislive/actions/runs/37184253645) | 2026-10-04T06:55:54Z | match-reel · render · sabalenka-bartunkova-beijing-2026-r3 | failure | 174 | render — 出成片 |
| [37184135694](https://github.com/robertyang87/tennislive/actions/runs/37184135694) | 2026-10-04T06:53:35Z | match-reel · narration · sabalenka-bartunkova-beijing-2026-r3 | cancelled | 16 | — |
| [37182857136](https://github.com/robertyang87/tennislive/actions/runs/37182857136) | 2026-10-04T06:27:29Z | match-reel · probe · sabalenka-exit-s3mqDeV5E_w | success | 287 | — |
| [37181476427](https://github.com/robertyang87/tennislive/actions/runs/37181476427) | 2026-10-04T05:59:45Z | match-reel · cookies · eala-zheng | success | 119 | — |
| [37171069726](https://github.com/robertyang87/tennislive/actions/runs/37171069726) | 2026-10-04T02:26:41Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | success | 431 | — |
| [37169969418](https://github.com/robertyang87/tennislive/actions/runs/37169969418) | 2026-10-04T02:05:09Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | success | 450 | — |
| [37169633135](https://github.com/robertyang87/tennislive/actions/runs/37169633135) | 2026-10-04T01:58:53Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | failure | 253 | render — 出成片 |
| [37156362096](https://github.com/robertyang87/tennislive/actions/runs/37156362096) | 2026-10-03T21:49:10Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | success | 391 | — |
| [37155634536](https://github.com/robertyang87/tennislive/actions/runs/37155634536) | 2026-10-03T21:35:27Z | match-reel · push · nadal-academy-10th-2026 | success | 156 | — |
| [37154869497](https://github.com/robertyang87/tennislive/actions/runs/37154869497) | 2026-10-03T21:22:21Z | match-reel · cookies · eala-zheng | success | 127 | — |
| [37154023283](https://github.com/robertyang87/tennislive/actions/runs/37154023283) | 2026-10-03T21:08:01Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | failure | 420 | 查成片本身合不合格 |
| [37153808249](https://github.com/robertyang87/tennislive/actions/runs/37153808249) | 2026-10-03T21:04:23Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | failure | 111 | 发布文案前置检查 |
| [37153781338](https://github.com/robertyang87/tennislive/actions/runs/37153781338) | 2026-10-03T21:03:57Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | cancelled | 24 | — |
| [37153090726](https://github.com/robertyang87/tennislive/actions/runs/37153090726) | 2026-10-03T20:52:23Z | match-reel · render · zheng-kalinskaya-beijing-2026-r2 | failure | 186 | render — 出成片 |
| [37152637527](https://github.com/robertyang87/tennislive/actions/runs/37152637527) | 2026-10-03T20:44:45Z | match-reel · narration · zheng-kalinskaya-beijing-2026-r2 | failure | 116 | narration — 只查旁白装不装得下 |
| [37151147690](https://github.com/robertyang87/tennislive/actions/runs/37151147690) | 2026-10-03T20:19:51Z | match-reel · probe · rna10-source-7 | success | 333 | — |
| [37151145784](https://github.com/robertyang87/tennislive/actions/runs/37151145784) | 2026-10-03T20:19:49Z | match-reel · probe · rna10-source-6 | success | 383 | — |

### 赛后开麦：30次运行索引

| 运行 | 创建时间 UTC | 标题 | 结论 | 墙钟秒 | 失败步骤 |
|---|---|---|---|---:|---|
| [37225530876](https://github.com/robertyang87/tennislive/actions/runs/37225530876) | 2026-10-04T18:43:30Z | interview-clip · render · djokovic-china-2026-r | success | 382 | — |
| [37225174671](https://github.com/robertyang87/tennislive/actions/runs/37225174671) | 2026-10-04T18:37:57Z | interview-clip · render · djokovic-china-2026-r | failure | 246 | 剪 + 烧字幕 |
| [37224838410](https://github.com/robertyang87/tennislive/actions/runs/37224838410) | 2026-10-04T18:32:35Z | interview-clip · subs · medvedev-china-2026-r | success | 240 | — |
| [37224837036](https://github.com/robertyang87/tennislive/actions/runs/37224837036) | 2026-10-04T18:32:33Z | interview-clip · subs · djokovic-china-2026-r | success | 246 | — |
| [37210156189](https://github.com/robertyang87/tennislive/actions/runs/37210156189) | 2026-10-04T14:40:52Z | interview-clip · subs · hurkacz-china-2026-r | success | 234 | — |
| [37168560409](https://github.com/robertyang87/tennislive/actions/runs/37168560409) | 2026-10-04T01:37:12Z | interview-clip · push · nadal-academy-10th-2026-championship-speech | success | 132 | — |
| [36338290942](https://github.com/robertyang87/tennislive/actions/runs/36338290942) | 2026-09-27T17:48:13Z | interview-clip | success | 1019 | — |
| [36337385713](https://github.com/robertyang87/tennislive/actions/runs/36337385713) | 2026-09-27T17:33:30Z | interview-clip | failure | 147 | 转写交叉校验 |
| [36336313197](https://github.com/robertyang87/tennislive/actions/runs/36336313197) | 2026-09-27T17:16:21Z | interview-clip | success | 406 | — |
| [36335539520](https://github.com/robertyang87/tennislive/actions/runs/36335539520) | 2026-09-27T17:04:00Z | interview-clip | success | 417 | — |
| [36334379967](https://github.com/robertyang87/tennislive/actions/runs/36334379967) | 2026-09-27T16:44:59Z | interview-clip | failure | 126 | 转写交叉校验 |
| [36333590996](https://github.com/robertyang87/tennislive/actions/runs/36333590996) | 2026-09-27T16:32:00Z | interview-clip | success | 409 | — |
| [36333320670](https://github.com/robertyang87/tennislive/actions/runs/36333320670) | 2026-09-27T16:27:38Z | interview-clip | failure | 164 | 出封面并验视觉（完全本地，排在转写和编码之前） |
| [36332654741](https://github.com/robertyang87/tennislive/actions/runs/36332654741) | 2026-09-27T16:16:55Z | interview-clip | failure | 137 | 转写交叉校验 |
| [36330845471](https://github.com/robertyang87/tennislive/actions/runs/36330845471) | 2026-09-27T15:47:29Z | interview-clip | failure | 154 | 出封面并验视觉（完全本地，排在转写和编码之前） |
| [36318179820](https://github.com/robertyang87/tennislive/actions/runs/36318179820) | 2026-09-27T12:11:48Z | interview-clip | success | 351 | — |
| [36317724291](https://github.com/robertyang87/tennislive/actions/runs/36317724291) | 2026-09-27T12:03:24Z | interview-clip | success | 197 | — |
| [36317566907](https://github.com/robertyang87/tennislive/actions/runs/36317566907) | 2026-09-27T12:00:39Z | interview-clip | failure | 82 | 取字幕切行 |
| [36291512052](https://github.com/robertyang87/tennislive/actions/runs/36291512052) | 2026-09-27T03:28:38Z | interview-clip | success | 572 | — |
| [36290473318](https://github.com/robertyang87/tennislive/actions/runs/36290473318) | 2026-09-27T03:07:00Z | interview-clip | success | 584 | — |
| [36289872829](https://github.com/robertyang87/tennislive/actions/runs/36289872829) | 2026-09-27T02:54:38Z | interview-clip | failure | 228 | 转写交叉校验 |
| [36289566943](https://github.com/robertyang87/tennislive/actions/runs/36289566943) | 2026-09-27T02:48:14Z | interview-clip | success | 143 | — |
| [36289125019](https://github.com/robertyang87/tennislive/actions/runs/36289125019) | 2026-09-27T02:39:03Z | interview-clip | failure | 162 | 验封面视觉（完全本地，生产硬闸） |
| [36288574575](https://github.com/robertyang87/tennislive/actions/runs/36288574575) | 2026-09-27T02:27:40Z | interview-clip | failure | 563 | 验封面视觉（完全本地，生产硬闸） |
| [36287539860](https://github.com/robertyang87/tennislive/actions/runs/36287539860) | 2026-09-27T02:06:29Z | interview-clip | success | 299 | — |
| [36287538482](https://github.com/robertyang87/tennislive/actions/runs/36287538482) | 2026-09-27T02:06:27Z | interview-clip | failure | 318 | 转写交叉校验 |
| [36286576284](https://github.com/robertyang87/tennislive/actions/runs/36286576284) | 2026-09-27T01:47:01Z | interview-clip | failure | 356 | 验封面视觉（完全本地，生产硬闸） |
| [36286574939](https://github.com/robertyang87/tennislive/actions/runs/36286574939) | 2026-09-27T01:46:59Z | interview-clip | failure | 390 | 转写交叉校验 |
| [36286483990](https://github.com/robertyang87/tennislive/actions/runs/36286483990) | 2026-09-27T01:45:11Z | interview-clip | cancelled | 170 | — |
| [36286482488](https://github.com/robertyang87/tennislive/actions/runs/36286482488) | 2026-09-27T01:45:10Z | interview-clip | cancelled | 166 | — |

### 网球有故事：30次运行索引

| 运行 | 创建时间 UTC | 标题 | 结论 | 墙钟秒 | 失败步骤 |
|---|---|---|---|---:|---|
| [36817051948](https://github.com/robertyang87/tennislive/actions/runs/36817051948) | 2026-10-01T04:51:26Z | explainer-video · atp250-medvedev-hangzhou-2026 | success | 208 | — |
| [36811524280](https://github.com/robertyang87/tennislive/actions/runs/36811524280) | 2026-10-01T03:39:34Z | explainer-video · atp250-medvedev-hangzhou-2026 | success | 245 | — |
| [36808709110](https://github.com/robertyang87/tennislive/actions/runs/36808709110) | 2026-10-01T03:03:11Z | explainer-video · atp250-medvedev-hangzhou-2026 | success | 242 | — |
| [36251845082](https://github.com/robertyang87/tennislive/actions/runs/36251845082) | 2026-09-26T15:24:49Z | explainer-video | success | 290 | — |
| [36251443527](https://github.com/robertyang87/tennislive/actions/runs/36251443527) | 2026-09-26T15:17:55Z | explainer-video | success | 293 | — |
| [36250119375](https://github.com/robertyang87/tennislive/actions/runs/36250119375) | 2026-09-26T14:54:53Z | explainer-video | success | 263 | — |
| [36249638228](https://github.com/robertyang87/tennislive/actions/runs/36249638228) | 2026-09-26T14:46:23Z | explainer-video | success | 283 | — |
| [35612160319](https://github.com/robertyang87/tennislive/actions/runs/35612160319) | 2026-09-21T14:26:20Z | explainer-video | success | 340 | — |
| [35610848970](https://github.com/robertyang87/tennislive/actions/runs/35610848970) | 2026-09-21T14:14:46Z | explainer-video | success | 290 | — |
| [35523769564](https://github.com/robertyang87/tennislive/actions/runs/35523769564) | 2026-09-20T16:46:40Z | explainer-video | success | 247 | — |
| [35508110551](https://github.com/robertyang87/tennislive/actions/runs/35508110551) | 2026-09-20T11:32:12Z | explainer-video | success | 332 | — |
| [35507491281](https://github.com/robertyang87/tennislive/actions/runs/35507491281) | 2026-09-20T11:19:08Z | explainer-video | success | 359 | — |
| [35506213465](https://github.com/robertyang87/tennislive/actions/runs/35506213465) | 2026-09-20T10:51:12Z | explainer-video | cancelled | 161 | — |
| [35505831188](https://github.com/robertyang87/tennislive/actions/runs/35505831188) | 2026-09-20T10:42:44Z | explainer-video | cancelled | 137 | — |
| [35453091042](https://github.com/robertyang87/tennislive/actions/runs/35453091042) | 2026-09-19T15:51:06Z | explainer-video | success | 252 | — |
| [35441881952](https://github.com/robertyang87/tennislive/actions/runs/35441881952) | 2026-09-19T12:05:31Z | explainer-video | success | 273 | — |
| [35132768293](https://github.com/robertyang87/tennislive/actions/runs/35132768293) | 2026-09-16T18:10:46Z | explainer-video | success | 278 | — |
| [35131919600](https://github.com/robertyang87/tennislive/actions/runs/35131919600) | 2026-09-16T18:02:40Z | explainer-video | success | 292 | — |
| [35128704061](https://github.com/robertyang87/tennislive/actions/runs/35128704061) | 2026-09-16T17:31:21Z | explainer-video | success | 328 | — |
| [35126806203](https://github.com/robertyang87/tennislive/actions/runs/35126806203) | 2026-09-16T17:13:11Z | explainer-video | success | 285 | — |
| [35125575502](https://github.com/robertyang87/tennislive/actions/runs/35125575502) | 2026-09-16T17:01:25Z | explainer-video | success | 224 | — |
| [35123457589](https://github.com/robertyang87/tennislive/actions/runs/35123457589) | 2026-09-16T16:41:11Z | explainer-video | success | 290 | — |
| [35121173001](https://github.com/robertyang87/tennislive/actions/runs/35121173001) | 2026-09-16T16:19:40Z | explainer-video | success | 300 | — |
| [35063801507](https://github.com/robertyang87/tennislive/actions/runs/35063801507) | 2026-09-16T06:27:36Z | explainer-video | success | 303 | — |
| [35062135492](https://github.com/robertyang87/tennislive/actions/runs/35062135492) | 2026-09-16T06:04:58Z | explainer-video | success | 266 | — |
| [34935776241](https://github.com/robertyang87/tennislive/actions/runs/34935776241) | 2026-09-15T06:10:25Z | explainer-video | success | 227 | — |
| [34933148370](https://github.com/robertyang87/tennislive/actions/runs/34933148370) | 2026-09-15T05:32:24Z | explainer-video | success | 190 | — |
| [34924032694](https://github.com/robertyang87/tennislive/actions/runs/34924032694) | 2026-09-15T03:11:25Z | explainer-video | success | 325 | — |
| [34918822026](https://github.com/robertyang87/tennislive/actions/runs/34918822026) | 2026-09-15T01:50:10Z | explainer-video | success | 262 | — |
| [33740037850](https://github.com/robertyang87/tennislive/actions/runs/33740037850) | 2026-09-03T09:39:17Z | explainer-video | success | 262 | — |
