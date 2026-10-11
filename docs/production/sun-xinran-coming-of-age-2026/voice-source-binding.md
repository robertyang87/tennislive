# 当前 v2 的真实语音组件绑定（未通过听核）

当前冻结 master：`861eae3d2cf1a8b4f6932b258e00d54308abec3eeafc7ada5599c0d829ce1272`，85,039,635 bytes，230.041333 秒，1080×1440。该记录不改变成片，也不宣告发布通过。

恢复两个历史 Actions artifact 的真实 MP3、word sidecar 和原始 manifest：基础 run 37388892198 / artifact 11379888992；修订 run 37390344049 / artifact 11380482910。S03、S04使用修订版，其余使用基础版。八章实际 narration 文本逐项等于当前 production spec；MP3 SHA、word sidecar SHA、原始 component manifest SHA 已核对。

| 章节 | source run / artifact | 当前片内起点 s | 原 MP3 时长 s | 全章 PCM 相关 | 实际 MP3 SHA256 |
| --- | --- | ---: | ---: | ---: | --- |
| S01 | 37388892198 / 11379888992 | 1.804333 | 22.032 | 0.993092 | `b603e4d7953bd78f13d4925653b25c352cb398a7d8b8f21164677fcc6fd9bebf` |
| S02 | 37388892198 / 11379888992 | 24.124333 | 23.448 | 0.993784 | `14af9fd623cffafadaa6d06c66995ae7a0f8a2aa0aaa081694107771f34fb27c` |
| S03 | 37390344049 / 11380482910 | 48.244333 | 27.120 | 0.991220 | `84a87237c8509b38e5e2b5c6224397d5d8c43f0f479dd789a352b49b63fc8b42` |
| S04 | 37390344049 / 11380482910 | 76.004333 | 27.624 | 0.925732 | `372c0030c36393992e7debbaec10104fa93e7ca4368ac61507bbb4e0fc457ead` |
| S05 | 37388892198 / 11379888992 | 104.284333 | 25.344 | 0.942359 | `104cec3e85742c2f04a2563aa9fc340356d64820ec94c04c4f506ef73302c597` |
| S06 | 37388892198 / 11379888992 | 130.284333 | 23.256 | 0.931204 | `3c69be8f086021686e1e4ec03fec3fec436b8da24dc596c8f02235098317d679` |
| S07 | 37388892198 / 11379888992 | 173.444333 | 26.904 | 0.993467 | `b0bdd154102af4a38b2d31f32ee46d6ce60749d5a8eb69664bd247c2fbbba339` |
| S08 | 37388892198 / 11379888992 | 201.004333 | 24.504 | 0.976243 | `8bb613c799b4c246b3b2dbd323ba7b8f71df8fd77d635946444eab0ce435ed8f` |

基础原始 manifest SHA：`a668d2e7a5130bb0e29d6e1b0e98b144c69b0d18295bb6d845ba6abec64ae767`；修订原始 manifest SHA：`549fb533c916007a9fc317ba3e3b0efef78da8269b0995d18c671c7bb7059f43`。voice=`zh-CN-YunjianNeural`，rate=`+22%`，pitch=`+0Hz`，backend=`edge`；这些为源文件实际记录，未新合成。

通过本地全文 8k PCM 相关定位实际组件，不使用 ASR 文字代替发音判断。当前 master 与源 master `509cca3263c96588d7726604e5b44b067d803a83867018fcc31dd85558a4bdd4` 的 10,728 个 AAC packet payload size/hash 全部一致；PTS 常量偏移约 1.199333 秒。末包 duration 元数据由 0.020667 秒变为 0.021333 秒，不改变 payload。

已执行仓库 `tools/package_sun_xinran_story.py` 的原生 `validate_audio_segments`，八章真实文件、原始 provenance manifest 和当前文本全部通过结构验证；`tools/adapt_sun_delivery_metadata.py` 的 `normalize_render` 对绑定当前 SHA/bytes 的 PENDING QA 正确拒绝：`Final QA must PASS and bind current actual film bytes/SHA`。仅执行这些真实函数，未伪造 QA PASS，也未执行发布 packager。

本地产物：`narration.bound.pending-review.json`、`render.bound.pending-review.json`、`qc.bound.pending-review.json`、`native-binding-validation.json`。native narration 中的 file/source_manifest_file 是真实本地绝对路径；跨机器使用须恢复实际组件 bytes 后重新定位路径，并重新运行相同校验。它们不是已发布 GitHub Release 资产。

仍待关闭：完整成片混音实际听核、八章发音/语调及嵌入源人声核验、当前 SHA 的原生 QA/CI 和发布包 attestation、对应当前 SHA 的实际 Release 资产 URL及发布去重记录。`human_listened=false`、`tone_pass=false`、`publishing_voice_pass=false`、`release_pass=false`。源身份/PCM相关不构成语音 pass，审片版仍未对外发布。
