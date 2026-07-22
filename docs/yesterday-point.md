# 「这一分，值回放」自动项目

公开栏目名为「这一分，值回放」；内部任务名保留 `yesterday-point`。`tennislive point` 与日报、网球故事分开运行，输出到
`output/YYYY-MM-DD/yesterday-point/`。GitHub Action 在北京时间 09:23 执行，给赛事官方留出上传赛后视频的时间。

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

成片为 1080×1920。原始 16:9 主体使用 `contain` 完整置于画布中央，留白区域由同帧柔化背景填充。系统没有逐帧、全覆盖、高置信度追踪证据时，不启用动态裁切。

字幕包含对阵、赛事轮次和全场比分。成片和发布文案不展示来源署名，来源与“最佳回合”证据只保留在内部 `manifest.json`。配套小红书文案只有一个正文段落：一句钩子、2–3 句白话看点、一个评论问题，连同 3–6 个标签控制在手机一屏内。

## 运行

```bash
TENNISLIVE_YESTERDAY_POINT=on tennislive point --date today --outdir output
```

## Hot Shots 热度层

`Hot Shot` 不再因为没有写 `of the Day` 就自动丢弃。来自 Tennis TV / ATP Media 或巡回赛官方账号的单分短片，只要满足昨日日期、赛事与双方球员唯一关联、6–120 秒、至少 720p、完整保留源视频，就可作为“Hot Shots”发布。它的内部等级为 1，低于“当日最佳”(3) 和“全场最佳”(2)，公开文案不会把它误写成“公认最佳”。集锦、倒计时、Top 10、采访和多分拼接仍然跳过。

产物包括：

- `yesterday-point.mp4`
- `yesterday-point.zh-CN.srt`
- `xiaohongshu.txt`
- `copy.html`
- `push.html`
- `manifest.json`

没有满足全部门槛的视频时，任务会生成 `status=skipped` 的清单并正常结束；抓取、渲染或质量校验异常会生成 `status=failed` 并使 Action 失败。
