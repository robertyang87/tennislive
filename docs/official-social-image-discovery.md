# 官方比赛高清图片监测

这条链路专门解决“视频已经做好，只缺最终高清封面”的问题。定时任务本身每
10 分钟醒一次，但**平时不抓任何账号**；只有 watch 同时满足“成片
`render.json` 已存在”和“封面仍有 `frame_at`、`_low_res_why` 或明确 pending
标记”才会针对这场比赛监测。顺序为：官方微博/Sina 公共镜像、官方 X、官方
Instagram、US Open CMS/CDN。

## 判定规则

- **爆冷比赛先找明星输家的情绪。** 世界前 20 球员被排名低至少 30 位的
  对手淘汰时，封面第一候选是明星球员在本场失利后的失落、落寞或难以置信的
  高清近景；只有找不到合格当场图时，才降级为爆冷赢家庆祝照，并在 provenance
  里写明降级原因。这个优先级只改变“选哪位球员”，不放宽下面的本场与清晰度闸。

- 微博图片统一请求公开的 `/large/` rendition；X 图片统一请求 `name=orig`；
  Instagram 从公开页面元数据选择可见的最大 rendition。
- 相同照片用 SHA-256 和感知哈希合并。保留像素更高的文件，但把官网的图片 ID、
  摄影师署名和每一个落地页一起写入 `provenance`。
- 当前默认长边至少 1600px，而且必须有“本场比赛”证据。没有合格图时状态保持
  `pending-high-resolution-current-match-image`，不会用模糊抽帧冒充高清封面。
- `public-access-rights-unverified` 只表示公开页面可读取，不表示获得转载授权；
  发布前仍要按平台规则确认使用权并保留署名。
- 找到合格原图后，会把原图和结果清单落入仓库；结果文件就是停止标记，下一轮
  会自动跳过，不会继续无意义扫描。同时更新该片 spec 的 `cover.portrait.image`，
  清除抽帧/低清豁免，并触发 `match-reel` 的 `cover` 专用渲染，不重做整条视频。

## 增加后续比赛

在 `data/official_social_image_watch.json` 增加一个 watch，填写球员、赛事、监测
起止时间、对应 spec、成片 `render.json` 和来源。已经人工确认属于本场的具体帖子可设置
`verified_for_match: true`；账号主页只能设置 `discover_posts: true`，发现的帖子
必须由公开 caption 分别命中 `evidence_groups` 的每一组（通常一组对应一位球员），
不能因为只出现一位球员就把整页放行。

本地运行：

```bash
python tools/collect_official_social_images.py \
  --watch-file data/official_social_image_watch.json \
  --output artifacts/official-social-images
```

结果位于每场比赛的 `manifest.json`。`selected` 是可交给现有封面质检器的第一
候选；`source_status` 会区分正常无图和登录限制。X/Instagram 被限制时不会绕过
登录或中断整轮采集，微博与 US Open CMS 仍会继续运行。
