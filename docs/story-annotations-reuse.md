# 网球有故事：辅助贴纸模板

2026-09-08：用户要求精美、辅助理解、不挡主体，并作为通用模板。

复用 `render_story_info_band.py` 的品牌绿、暖白、得意黑标题、数字字体与软阴影，
不改封面与字幕。配置见 `requests/stories/zheng-usopen-icons.annotations.json`。

| role | 用途 | 限制 |
|---|---|---|
| context | 年份、赛事、典故解释 | 只在对应历史画面首次出现时展示 |
| number | 一个关键数字 | 写清首盘/决胜盘等范围，不做战力排行榜 |
| translation | 原文关键词翻译 | 与原帖分层，不能覆盖或改写截图原文 |

生成：

```sh
python tools/render_story_annotation_set.py requests/stories/zheng-usopen-icons.annotations.json --outdir assets/beatcards/zheng-usopen-icons
```

每张透明贴纸宽648px，高约184px（1080×1440成片）；显示3.8秒，轻微上浮淡入。
配置里的 `inset` 可直接复制到片段；`placement_verified` 是旁证，不能复制为渲染字段。

位置必须按镜头选择，禁止把默认右上角当成已审核。检查出现期间首、中、尾帧：
人脸、球拍触球处、篮球出手/球框、高尔夫推杆线路/洞杯、比分板都不能相交。
两侧都无留白就延后到死球或庆祝后的空镜，不靠缩小字硬塞。单屏最多一张，
遇原声关键球先退场。原帖整屏段以原文清晰为先；中文解释可放在独立字幕区。

生成贴纸不等于通过成片质检；必须在实际尺寸、实际画面与平台安全区内复核。
