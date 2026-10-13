# 微信交付前的并行探活

2026-10-13 继续优化制作耗时。这次减少发布前的串行网络等待和重复 GET，默认随现有入口生效，无需修改 spec 或工作流参数。

`tools/push_reel.py` 先检查本地复制页、必要统计图和发布文案，再用固定两个 worker 同时等待复制页与视频。Pages 的触发、看门狗、当前标题比对、视频 Range 请求及各自重试次数、间隔和超时仍走原函数。两者都成功才继续发送；任一失败都收束 worker 并阻断，两者同时失败仍优先报告复制页原因。没有并行提交、部署或发送不同影片。

共享 `tennislive.publish.pushplus.wait_for_images` 对一条消息中的图片与视频地址去重，每轮最多四个 GET 同时执行。同地址同时作为 `<img>` 和“原图”链接时，保留更严格的 `image/*` 检查，HTTP 200 的 HTML 错误页不能绕过。下一轮只重试失败地址，响应始终关闭；等待全部成功后仍执行原有传播等待、长度检查和唯一消息 POST。探活结果不跨调用缓存。比赛、采访、故事及日报的共享图片检查均受益。

原有 `TENNISLIVE_COPYPAGE_ATTEMPTS`、`TENNISLIVE_COPYPAGE_RETRY_SECONDS`、`TENNISLIVE_PUSHPLUS_IMAGE_ATTEMPTS`、`TENNISLIVE_PUSHPLUS_IMAGE_RETRY_SECONDS` 和 `TENNISLIVE_PUSHPLUS_IMAGE_SETTLE_SECONDS` 继续使用，不增加新的调参项。现场原声音量、字幕与动态比分板、编码画质、影片 QC、消息修订重查和唯一发送账本沿用原规则。

## 可控 HTTP 实测

对同一基线 `7a1dbdb4` 与最终实现各执行三次，表中为中位数。真实本地 HTTP 服务提供固定响应延迟，模拟尚未上线、旧标题及错误图片类型；Pages 部署触发与看门狗在实验中打桩，没有向外网发请求或推送微信。这些数验证请求重叠与去重，不是线上 CDN 提速保证。

| 复制页与视频；每响应 200ms | 串行 | 并行 |
|---|---:|---:|
| 均已就绪 | 0.405 秒 | 0.204 秒 |
| 同在请求开始后 0.45 秒上线 | 0.659 秒 | 0.458 秒 |
| 两者各前两次未就绪 | 1.416 秒 | 0.711 秒 |
| 视频一直 404，最终阻断 | 1.416 秒 | 0.711 秒 |

同绝对时刻上线的场景，并行会更早探测第二项，HTTP 总次数可能增加；不承诺这一路减少请求数。实验使用两边相同的三次尝试、50ms 重试间隔，提交的生产函数仍保留原预算。证据：[每次请求与响应、峰值并发和阻断结果](../data/evidence/reel-delivery-readiness-2026-10-13/delivery-readiness-benchmark.json)。

| 图片与回退链接；每响应 80ms | 原请求数 → 优化后 | 串行 → 优化后 |
|---|---:|---:|
| 两张图及各自原图链接，加一个视频 | 5 → 3 | 0.411 → 0.085 秒 |
| 十二张图及各自原图链接 | 24 → 12 | 1.974 → 0.256 秒 |
| 两张图加视频，首张先返回 HTML、后正确 | 6 → 4 | 0.525 → 0.198 秒 |

十二张图实际峰值从 1 路变为 4 路。错误图片类型场景仍需重试，保留严格门禁。证据：[逐次计时及响应](../data/evidence/reel-delivery-readiness-2026-10-13/asset-readiness-benchmark.json)。

在包含基线 Git 历史的仓库中复现，输出独立文件，不覆盖已保存证据：

```bash
PYTHONPATH=src python data/evidence/reel-delivery-readiness-2026-10-13/benchmark_delivery.py \
  --out /tmp/delivery-readiness.json
PYTHONPATH=src python data/evidence/reel-delivery-readiness-2026-10-13/benchmark_assets.py \
  --out /tmp/asset-readiness.json
```

## 验证与取舍

新增检查覆盖真实 HTTP 同步读取、当前转义标题和 Range、任一失败禁止 POST、worker 收束、本地产物缺失与正文超限提前失败、标题前缀及唯一发送时序。共享探活检查覆盖四路上限、关闭所有响应、同地址严格图片类型及仅重试失败项。旧有发送前探活合同跟随新的调用边界保留。

真实帕奥利尼两次 runner 的 TTS 阶段为 9.538 秒、7.477 秒；本地九段实际缓存命中，日志显示 0.00 秒，显示精度不能作为精确零。仅看阶段计时无法判定全冷缓存。Azure 当前全局限流状态不适合直接加线程，因此这轮保留配音串行及缓存配对。见[实际 run、文件 SHA 与计时口径](../data/evidence/reel-delivery-readiness-2026-10-13/tts-performance-inspection.json)。

本次是公共发布代码与测试变更，按现有测试分层规则执行最终 head 的一次完整 CI；日常单片制作继续按各自产线选回归。没有生成或重发影片，尚未验证下一期从收到素材到真实微信回执的 20 分钟目标。
