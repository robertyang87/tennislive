# 视频制作效率与质量优化（2026-10-13）

这次优化减少重复计算和可提前发现的返工，不删除有效质量判据，也不调整现场原声大小。基线是 `6402c4ae`；实测在同一工作区、同一素材和字体环境进行。没有新出片或发送微信，不能把这些局部结果当成已经达到「收到素材到微信回执 20 分钟」。

## 实际改动和实测

| 环节 | 原耗时 | 优化后 | 验证 |
|---|---:|---:|---|
| 全库旁白与 spec 检查（同一条原测试，带 cProfile） | 44.49 秒 | 22.10 秒 | 原断言全部保留、两次均通过 |
| 369 份 spec 的图片检查，首次扫描 | 13.58 秒 | 11.75 秒 | 完整问题列表 SHA 相同，仍检出 3 个问题 |
| 上述同进程第二次扫描 | 13.52 秒 | 0.64 秒 | 完整问题列表 SHA 相同 |
| 112 份采访、194 次实际字幕重切 | 24.72 秒 | 23.64 秒 | 全部行、时间与错误输出共 1,324,356 字节完全相同 |

以上是本地单次对比，不是多轮中位数或云端总耗时；各行存在重叠，不能相加。采访只提升约 4.4%，不是把剖析中的全部字宽耗时消掉。

图片检查只缓存同进程内成功完整解码后的尺寸、EXIF 方向和结果，不保存像素、不缓存失败。每次查缓存仍读取整个文件并算 SHA；文件身份、内容或 Pillow 解码策略改变就重新解码。损坏 PNG、截断 JPEG、缺失图片、换根路径和放大裁切错误仍会失败。封面尺寸读取直接使用原始尺寸与 EXIF 方向，不再为了得到宽高复制整张大图。缓存上限 1024 条。

采访字宽缓存限于一次 `segment()` 调用和同一把字体尺子，上限 4096 条；下一条稿或显式传入的测宽函数不会继承结果。实际全量重切输出 SHA 是 `dd206c6665f21e175fc65bb04ffb99678482215439f95859306dfe7622f250c2`。

## 把字幕错误拦在编码之前

原生渲染现在拿到实际 TTS 时长后就构建最终 ASS，先于比分板扫描、封面编码和分段视频编码。跨字幕位置窗口、quote 末端越界等错误立即失败，不再白编整条片。使用的仍是原生字幕规则和实际词边界，不另造一个简化校验器。

已发布帕奥利尼对贝莱克视频的 17 段、9 份实际 WordBoundary、60 条字幕重放后，ASS 与发布版逐字节一致，SHA 为 `e627f621c032d1a3703c5733e4a40264b8a19e13f30f598599f89f8a2155cd89`。这只证明字幕调度等价；实际画面、全片原生 QC 和发布回执仍须各自核验。

## 保留原生输入，减少修订时重做

每次 render 通过实际 QC 后、上传 Release 和清理之前，保存独立的 `native-input-<slug>-<run_number>` Actions artifact。只保留已核电影、实际配音与词边界、原生元数据和比分遮罩；不复制媒体、不保存源片、cookies 或中间编码。归档与 run、head、spec 和每个文件的 SHA 绑定；归档失败阻断后续发布。

修订时优先取对应 run 的不可变输入，存在但过期或损坏的归档会失败，不能转而拿已经被覆盖的 Release 掩盖问题。后续组合仍必须通过新的原生全片 QC。详见[原生输入归档与重试审计](native-reel-retry-audit-2026-10-13.md)。

这多一次电影大小的上传，首轮净耗时尚未在 hosted runner 测量。收益是避免原配音被清理、旧电影被同名 Release 覆盖后无法严格复用；此前实际编码约 432 秒，不能直接把它记成归档净节省。

## 下一期按这个顺序执行

1. 官方源片、事实与剧情、官方睁眼大图并行准备；统一关键比分与时间线后冻结文案。使用 OpenAI、人工核验和本地工具，不使用 DeepSeek 或 MiniMax。
2. 先跑当期单片检查，沿用原生入口：

   ```bash
   python tools/production_preflight.py --spec specs/reels/<slug>.json --column 赛场之上
   python tools/build_match_reel.py render --spec specs/reels/<slug>.json --outdir /tmp/reel-check --dry-run
   ```

   从输出中处理红项；没有 probe 或原帧的项目不冒充已核。真实 TTS 与 ASS 检查通过之后再编码。
3. 有实际未变配音和源片时复用精确输入；旁白、参数或素材改变就核验受影响部分。原声响度、固定铺满竖屏、贴比分板字幕、完整关键回合与球员反应遵守原规则。
4. 用当前电影 SHA 和原帧证据审片，完成一次必要修订。先跑改动相关的目标与负向测试；公共代码改动再对最终 head 跑一次完整 CI，不靠逐次全库测试准备文案。
5. 全片 QC → 保留原生输入 → Release 字节核验 → 合并与复制页部署 → 微信推送 → 实际 provider 回执和单次发送账本。到回执才算完成。

这次没有增加重复的早检 CLI，也没有改 CI 测试选择或删除测试。已有单片 dry-run 负责制作前检查；这轮修改公共代码，所以最终提交仍走完整 CI。下一条真正的新片需重新计时，包括新增归档上传成本，才能判断 20 分钟目标与剩余瓶颈。

证据：[热点实测](../data/evidence/video-efficiency-2026-10-13/hot-checks-benchmark.json)、[真实字幕重放](../data/evidence/video-efficiency-2026-10-13/caption-equivalence.json)。

同条件复测脚本已保存；需要包含基线提交 `6402c4ae` 的 Git 历史和相同字体、素材。采访脚本依赖真实已发布字幕缓存，CI 的精简检出不能代替这份语料。在仓库根目录分别运行新进程：

```bash
python data/evidence/video-efficiency-2026-10-13/benchmark_image_gates.py baseline
python data/evidence/video-efficiency-2026-10-13/benchmark_image_gates.py optimized
python data/evidence/video-efficiency-2026-10-13/benchmark_interview_rulers.py baseline
python data/evidence/video-efficiency-2026-10-13/benchmark_interview_rulers.py optimized
```
