# 少一次全尺寸拼接编码，减少重复安装

2026-10-13 继续按实际耗时优化。真实帧字幕预览和逐帧比分板蒙版缓存已合入 [#1233](https://github.com/robertyang87/tennislive/pull/1233)，交付前并行探活及图片去重已合入 [#1234](https://github.com/robertyang87/tennislive/pull/1234)。本次处理拼接与烧字幕，以及工作流的重复 editable 安装。

## 正式渲染默认使用新路径

入口与 spec 不变：

```bash
PYTHONPATH=src python tools/build_match_reel.py render \
  --spec specs/reels/<slug>.json --outdir /tmp/reel-render
```

分段、封面和片尾仍由各自的原生方法编码。已识别的原生溶解图，把每一路画面缩成 2×2，生成极小的中间视频作为音频处理的帧时钟；实际比赛画面仍从原来全尺寸分段输入最终编码。溶解与最终字幕、顶栏、脚注、角标和整屏恢复连接在同一图内，省掉原先全尺寸 `ultrafast/crf12` 拼接视频这一代压缩。2×2 视频是会删除的中间件，不进入成片或发布归档。

保留小视频时钟，是为了让原来的 `video copy / -shortest` 混音截止、真实片长上的音乐淡出与音频封存继续使用同一套命令。不能直接用名义段长之和替代真实视频结束时刻：非整帧样本名义 19.017 秒，实际为 19.04 秒。音频仍走原 AAC160k 拼接、原混音与 AAC192k、最终复制链；本次没有调整现场声、旁白或音乐增益，也没有新增归一化。

`tools/reel_join_fusion.py` 只识别现有原生溶解结构，无法识别时在编码前明确选择旧完整中间视频路径。已经开始执行的失败直接报错，不通过重试旧路径掩盖失败。保留原短片段／溶解尾料和拼接总长门禁。新成片再与实际小视频时钟逐包核对显示 PTS、帧数、帧率；比较按显示顺序排列，最终 medium 的 B 帧解码顺序差异不当作错误，不额外解码一次整片。

全尺寸输入在移除的编码边界做真正的 `yuv420p/limited range` 转换，保持原生色彩协商。最终仍是 `medium/crf18`、原兼容参数和音频复制；正式 ASS、逐帧比分板与提示条、原生全片 QC 和发布版本绑定照常执行。验证环境为 FFmpeg 7.1.5 和 hosted CI 同系列 BtbN N-127388。

## 实际媒体验证与计时

源为已核帕奥利尼对贝莱克视频，SHA `2fd4166d…`。使用原生分段与动态蒙版、真实封面、原生片尾和全屏统计图，以及实际已缓存配音。实验的字幕示意文本和缩短片段不是待发布电影。

| 样本／计时范围 | 原路径 | 新路径 |
|---|---:|---:|
| 19 秒样本，五个原生分段；拼接＋真实旁白混音＋最终字幕，三组交替中位数 | 11.923 秒 | 10.587 秒 |
| 非整帧封面，实际 19.04 秒；同链带循环测试输入，单次 | 11.664 秒 | 11.109 秒 |
| 暖缓存多音字安装调用，三组交替中位数 | 3.268 秒 | 0.764 秒 |

第一行约快 11.2%，新路径包含新增帧时钟核验的开销；各组均检查全部音频包，包含 PTS、时长、内容哈希和 side data，及最终显示帧时钟。计时使用相同已编码分段与输入，两边滤镜图都使用一个线程；不含源下载、分段编码、最终 QC 或上传。不能直接按比例外推整片，更不能与其他阶段或测试节省相加。见[正式实现三组计时和逐阶段命令](../data/evidence/reel-encode-startup-2026-10-13/production-bridge-benchmark.json)。

第二行的 476 帧、160k 拼接音轨与 894 个最终混音 AAC 包均一致。循环输入使用真实配音 MP3 作为压力测试输入，验证音乐处理链，未生成待发布音乐内容。见[非整帧与循环输入](../data/evidence/reel-encode-startup-2026-10-13/nonintegral-looped-audio-clock.json)、[最终成片包与时钟对比](../data/evidence/reel-encode-startup-2026-10-13/nonintegral-final-media.json)。

独立无损参照先拼接为 FFV1，再执行原生最终滤镜。普通场景 297 帧、带封面／统计整屏／真实配音的 475 帧，与融合图的全帧 MD5 完全一致。这里比较的是移除中间 H.264 压缩后的滤镜输出，不声称最终 H.264 文件字节一致。11.88 秒样本对同一无压缩滤镜参照的平均 PSNR 为原路径 47.758dB、新路径 48.094dB，未见该样本画质降低；不是所有素材的保证。见[原生扩展样本](../data/evidence/reel-encode-startup-2026-10-13/experimental-extended.json)、[独立质量比较](../data/evidence/reel-encode-startup-2026-10-13/reference-quality.json)。

封面、真实 MATCH POINT #2 提示条、整屏统计图和片尾四个样帧均独立查看，整屏及相应场景正常。示意字幕不作为当期内容合格凭证。见[样帧与实看记录](../data/evidence/reel-encode-startup-2026-10-13/visual-review.json)。早期纯视频／audio-only 实验保留在同一证据目录，其较大的百分比没有记成最终生产收益。

复现正式实现的计时需要上述真实原生分段、实际配音及 ASS；仓库只保存命令和校验和，不提交这些媒体。准备原实验输入目录后运行：

```bash
PYTHONPATH=src python data/evidence/reel-encode-startup-2026-10-13/benchmark_production_bridge.py \
  --inputs /path/to/verified/extended --outdir /tmp/fusion-benchmark
```

命令记录含原实验路径，其他机器须将所需配音／ASS／字体路径对应到同一已核输入。执行前逐个核对原生分段 SHA；脚本不合成配音、不写发布目录、不发消息。普通制作不需要这条 benchmark 命令。

## 避免重复构建项目

`match-reel.yml` 的多音字静态依赖步骤直接从本次检出的 `pyproject.toml` 读取 `pronunciation` extra，调用同一 Python 的 pip 安装该非空 `list[str]`。主依赖仍在后面按 mode 正常安装一次。字典 smoke 检查、失败退出、版本约束及现有缓存保留；缺失、空 extra 或错误类型在 pip 前失败。

暖缓存实测第三行，两边均在同一临时 venv 中，丢弃一次预热后交替三组。旧为 editable 安装进程，新包括 TOML 读取和 pip 调用；都不含独立字典导入检查，不称为整个冷启动用时。实测原命令在增加类型校验之前，原脚本与记录保留，不重新标为修订后测量。见[安装原始计时](../data/evidence/reel-encode-startup-2026-10-13/installation-results.json)、[计时边界与来源](../data/evidence/reel-encode-startup-2026-10-13/installation-provenance.json)。

两次真实 runner 的 checkout 为 51／55 秒、主要依赖为 27／25 秒；FFmpeg、字体和 Chromium 缓存已有效。素材目录约 1.28GiB，未验证依赖完整性就删检出范围会导致返工，这轮保留现有规则。原始步骤时间在本证据目录中，数据来自 Actions API，而不是完整日志。

本次没有生成、重发用户电影或推微信。下一期仍要从最初收到素材记录到真实微信回执，才能验证端到端 20 分钟；最终 head 按当前改动范围跑一次 CI，普通单片继续按产线选择回归。

首次 CI 为 6076 项通过、208 项跳过、3 项失败：原导出测试只抽取 `render()` 的最终调用，却未给测试上下文提供新增的 `final_inputs/final_audio_input`。三种帧率均在调用 FFmpeg 前报 `NameError`。修正夹具后，原 SPS、编码资源、CFR 与帧数要求保留，并让这三种帧率实际走融合图和真实帧时钟比较；BtbN 同款的 20 项相关检查通过。生产渲染代码与原始性能／媒体证据没有变化。见[失败与修订记录](../data/evidence/reel-encode-startup-2026-10-13/ci-export-fixture-correction.json)。
