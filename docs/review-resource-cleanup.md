# 资源清理审查（2026-10-04）

基线：`4adb2769d4a2b41b6cc18994c0b0513d8dee618a`。资源清理阶段按 Git 路径索引审查 25,576 个文件，仅读取相关源码及少量目标 blob，没有下载整库视频或改写历史。随后集成测试阶段另取完整 assets 验证依赖，未因此扩大删除范围。

## 已落实

| 项目 | 文件数 | HEAD blob 字节数 | 证据与处理 |
| --- | ---: | ---: | --- |
| `.gh-cache/gh/run-log-*.zip` | 16 | 450,172 | gh CLI 的本地 Actions 日志下载缓存，不是生产流水线输入；删去缓存副本，并忽略整个 `.gh-cache/`，避免每个新 run 再进库。业务诊断与发布账本保留。 |
| 根目录 `poster_local.jpg` | 1 | 454,786 | 实际查看为「张帅 · 第十五次」本地封面预览；内容对应 `specs/reels/zhang-shuai-story.json` 的 hook/topic，原始封面图仍在 `assets/reel/zhang-wimbledon-2015-qualifying.jpg`，正式封面仍在 `output/2026-09-18/reel/zhang-shuai-story/poster.jpg`。`tools/render_cover_local.py` 定义本地预览生成路径，既有 `tests/test_preview_segments.py` 已规定其不应进库。删除漏落根目录的预览，并补根目录忽略规则。 |
| 合计 | 17 | **904,958（约 0.86 MiB）** | 只减少后续 HEAD 检出/归档负担；不宣称 `.git` 历史体积同步缩小，也不把它计成视频编码提速。 |

历史缓存仍能从基线 commit 取回；GitHub 自身的旧运行日志可能到期，不能承诺重新下载总能恢复。本次没有删除 Git 历史。根目录预览原 blob 为 `d4a400c705ca6fd1c9cfbd70055caca27d02aca1`。

## 明确保留

- **764 个 `output/**/score_masks/*.mkv`**：这不是可以按扩展名扫掉的中间视频。`tools/check_reel_landed.py::scoreboard_geometry_problem` 对每一段 mask 验存在性和 SHA256；删掉会让逐帧比分板质量证据失效。
- **`cover_src/`**：`match-reel.yml` 明确保留用于封面本地返工，避免重新取源片和重复跑 runner。为省磁盘删除它反而降低制作效率。
- **正式封面、卡片、复制页、发布记录和审核 JSON**：历史消息可能直接引用仓库路径。没有做逐条 CDN/发布引用迁移，不按 `rg` 零命中删除。
- **`output/voice-samples/` 和 recovery 音频**：前者用于声音比较，后者涉及失败恢复；不是 `voice_NN.mp3` 那种已消费的合成中间物。
- **`output/interviews/*/_lead.ass`、`_trail.ass`**：工作流明确它们是逐 cue 质检和哈希所需证据，不能按 `_` 前缀一并忽略或删除。
- **`.omx/` 的历史会话和评审结果**：虽然包含本地 agent 状态，但也带过往视觉验收结论；没有把整个目录当临时缓存删除。
- **`data/research/**/*.log`**：它们属于已归档的研究/事实探测记录，不能因为 `.log` 后缀或既有忽略规则就删除 tracked 文件。
- **素材、字体及旧版图卡**：本次没有得到足够证据证明仅有一份副本之外都无用。模板、动态路径、独立生产脚本会读取资源；没有做全量素材下载，故不报告未经测量的可节省 GB 数。

## 防复发与验证

在真实 Git 忽略规则上验证 7 个正反例：CLI 新日志缓存、根目录及 output 本地预览会被忽略；正式封面、原始封面图、比分 mask 和采访 ASS 证据不会被新增规则忽略。核对 staged 删除仅含上述 17 个目标。

另发现 `match-reel.yml` 的 `source*` 清理模式能误中现有 `source_identity.json`、`source_photo.json` 和 `source_evidence.txt`；已交给工作流审查处理。这说明扩大删除通配符并不等于安全减负，必须区分下载媒体和事实来源凭证。
