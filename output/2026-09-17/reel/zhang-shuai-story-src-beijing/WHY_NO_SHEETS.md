# 这三份 probe 只留 `probe.json`，缩略图墙删掉了

`zhang-shuai-story-src-beijing` / `-navarro` / `-toronto` 这三条源**没有进片子**，
它们留在这儿是**一条结论的证据**，不是待挑的素材：

| slug | 源 | probe 量到 |
|---|---|---|
| `-beijing` | WTA 官方 2024 中网 Day 1 合集（张帅–凯斯勒在 360.5~539s） | **1280×720** |
| `-navarro` | WTA 官方 2024 中网第二轮 张帅–纳瓦罗 | **1280×720** |
| `-toronto` | WTA 官方 2026 多伦多第三轮 萨巴伦卡–张帅 | **1920×1080** |

前两条过不了 `--dry-run` 的 1080p 硬闸（「视频一定要选 1080p 及以上的清晰度」）。
第三条是**专门为了排除「是不是管线取不到 1080p」才跑的对照组**——同一条管线、同一个
频道、同一天，2026 年那条回的是 1080p，所以 720p 是 WTA 2024 年那两条上传自己的天花板，
不是我们没取对。

绕过那道闸要把 URL 写进 `tools/build_match_reel.py` 的 `APPROVED_LOW_RES_SOURCES`，
而那张表写着「仅限账号所有者按 URL 明确授权过的那几条」——所以这一版把 2024 年北京
那一段从画面改成了旁白（spec 第 18~19 段），账记在 `specs/reels/zhang-shuai-story.json`
的 `_sources_why` 里。

缩略图墙（`contact_*.jpg` / `score_*.jpg`，三份加起来 17 MB）删掉了：**结论在
`probe.json` 的 `width`/`height` 两个字段里**，那几十张 JPEG 只是挑段用的，而这三条
不挑段。要重新看画面，重跑一次 probe 就有。
