# 「这一分，值回放」自动项目

公开栏目名为「这一分，值回放」；内部任务名保留 `yesterday-point`。`tennislive point` 与日报、网球故事分开运行，输出到
`output/YYYY-MM-DD/yesterday-point/`。

ATP、WTA 各自独立选片、独立发布：互不挤占对方的名额，也不会因为另一方有更强的候选就被跳过。当天只有一方有满足硬门槛的视频时，只发布这一方；两边都有时各自成片、各自推送，分别位于 `yesterday-point/atp/` 与 `yesterday-point/wta/` 子目录，各自的 `manifest.json`、质量门禁与 PushPlus 推送完全独立。

### 独立重试：谁先有素材先推谁

两个巡回赛官方视频的上架时间并不同步，因此 GitHub Action 北京时间一天跑四班（09:23／12:23／15:23／19:23），给还没上架素材的一方持续重试的机会：

- 每一班次先检查 `atp/`、`wta/` 各自现有的 `manifest.json`；已经是 `status=pass` 的巡回赛本班次直接跳过——不重新抓取、不重新渲染、更不会重新推送同一条内容。
- 只有仍缺素材（`skipped`）的巡回赛会在本班次继续查询官方源；一旦找到合格视频就立即生成并推送，不等另一方。
- 顶层 `manifest.json` 的 `fresh_tours` 字段记录本班次真正新完成的巡回赛，PushPlus 只推送这个列表——这是避免同一条内容被重复推送到微信的关键。
- 到 19:23 末班仍未凑齐的一方，当天维持 `skipped`，不会无限重试下去。

## 选片硬门槛

- 比赛必须能由开赛时间证明属于北京时间昨日，且是已完赛单打。
- 页面域名必须属于巡回赛或大满贯官方来源。
- 标题或说明必须明确写出 `Point/Play/Shot/Rally of the Day` 或 `Point/Play/Shot/Rally of the Match`。普通 `Hot Shot`、`Best Point`、`Incredible Point` 即使是单回合也不够；集锦、采访、训练、Top 10 和夺冠之路同样会被拒绝。
- 只有 `...of the Day` 可以进入正式发布。`...of the Match` 只能留作候选：赛事新闻、人物热度、搜索趋势和播放量都不能证明“这个回合”是当天公认最佳，因此不能充当第二佐证。
- 同日出现多个官方日最佳候选且共识分并列时不猜测，整期跳过。官方标签、链接和共识分只写入内部 `manifest.json`。
- 视频必须与昨日比赛中的球员和赛事唯一对应，发布时间为昨日或今日，时长 6–120 秒，源清晰度至少 1280×720。
- 整个官方单回合源视频从 0 秒保留到结尾，不拼接、不抽取中间片段。

当前自动发现器并行使用 WTA 官方视频页、ATP Tour 官方 YouTube 频道，以及澳网、法网、温网和美网的官方 YouTube uploads feed；某一路失效时，其他来源仍可独立运行。大满贯的历史视频必须同时证明当前届年份、赛事与具体比赛，上传日期不能冒充比赛日期。

## 竖屏与文字

成片为 1080×1440（3:4），与本项目卡片图同一画布比例，方便和图文卡混排发布。原始 16:9 主体使用 `contain` 完整置于画布中央，留白区域由同帧柔化背景填充。系统没有逐帧、全覆盖、高置信度追踪证据时，不启用动态裁切——静态裁切可能把回合发生的那一刻直接裁出画面，比例再合适也不做。

字幕包含对阵、赛事轮次（中文轮次名）和全场比分，烧录时使用显式 PlayRes 的 `.ass` 字幕（而非交给 ffmpeg 猜测未声明分辨率的纯 SRT），避免字号被隐式放大、错位或异常换行。成片和发布文案不展示来源署名，来源与“最佳回合”证据只保留在内部 `manifest.json`；Hot Shots 层级的公开文案统一使用中文「神仙球」，不直接暴露 Tennis TV / ATP Media 等信源名称。配套小红书文案只有一个正文段落：一句钩子、2–3 句白话看点、一个评论问题，连同 3–5 个标签控制在手机一屏内。

## 运行

```bash
TENNISLIVE_YESTERDAY_POINT=on tennislive point --date today --outdir output
```

## Hot Shots 热度层

`Hot Shot` 不再因为没有写 `of the Day` 就自动丢弃。来自 Tennis TV / ATP Media 或巡回赛官方账号的单分短片，只要满足昨日日期、赛事与双方球员唯一关联、6–120 秒、至少 720p、完整保留源视频，就可作为“Hot Shots”发布。它的内部等级为 1，低于“当日最佳”(3) 和“全场最佳”(2)，公开文案不会把它误写成“公认最佳”。集锦、倒计时、Top 10、采访和多分拼接仍然跳过。

顶层 `output/YYYY-MM-DD/yesterday-point/manifest.json` 汇总当天两个巡回赛的状态（`{"ATP": "pass"|"skipped", "WTA": "pass"|"skipped"}`）。每个通过门槛的巡回赛在自己的子目录（`atp/` 或 `wta/`）下各自产出：

- `yesterday-point.mp4`
- `yesterday-point.zh-CN.srt`
- `yesterday-point.ass`（烧录用字幕，含显式 PlayRes）
- `xiaohongshu.txt`
- `copy.html`
- `push.html`
- `manifest.json`

某巡回赛当天没有满足全部门槛的视频时，只有该巡回赛的清单是 `status=skipped`，不影响另一方；两边都没有时顶层清单也是 `status=skipped`。抓取、渲染或质量校验异常会生成顶层 `status=failed` 并使 Action 失败。
