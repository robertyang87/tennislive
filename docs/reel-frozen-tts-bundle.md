# 赛场之上：预检配音直接用于正式渲染

2026-10-13。普通 TTS 缓存用于减少合成请求；它不保证另一台机器拿到同一份音频。郭涵煜一期的预检与正式渲染配音字节不同，导致最后再次审音。本次增加有限配音快照，直接保留本期实际调用产生的 MP3 和 WordBoundary，不扫描整个缓存、不打包源片或成片。

## 本地调用

先完成文案和声音参数，再导出预检中的真实配音：

```bash
PYTHONPATH=src python tools/build_match_reel.py render \
  --spec specs/reels/SLUG.json --outdir /tmp/reel-check \
  --check-narration --tts-bundle-out /tmp/SLUG-tts.zip
PYTHONPATH=src python tools/reel_tts_bundle.py /tmp/SLUG-tts.zip
```

ZIP 的 `manifest.json` 包含各请求的文字、音色、语速、音高、风格、起始停顿、后端，以及音频和词边界哈希。解开这个小包即可审听实际配音；快照本身不代表读音合格。完成读音复核后，正式渲染指定原包：

```bash
PYTHONPATH=src python tools/build_match_reel.py render \
  --spec specs/reels/SLUG.json --outdir /tmp/reel-final \
  --tts-bundle-in /tmp/SLUG-tts.zip --tts-bundle-out /tmp/SLUG-final-tts.zip
```

两步需使用相同 `--voice`、`--rate`、`--pitch` 和实际 TTS 后端；省略时沿用 CLI 默认值。导入绕过网络合成和可变缓存，输出保留原 ZIP 字节。旁白、声音参数、后端或合成实现变化会拒绝导入，不能静默重新合成。调整取景、字幕位置、源片地址和剪辑时间不会让声音失效，画面和时长仍须通过当前检查。需要改旁白时，重新预检导出并复核新配音。

## GitHub Actions

`match-reel.yml` 的 `mode=narration` 已完整生成配音后，把小包发布为 `reel-tts-<slug>-<hash前16位>` Release 的 `tts_bundle.zip`，完整哈希与下载地址记入 `data/narration_checks/<slug>.json`。即使只是旁白超出画面时窗，完整配音包仍可发布供延长画面后复用，原检查依旧失败退出，不宣称时长适配或审音通过。在分支上运行会将记录提交回分支；main 上不会自动提交记录，需把本次记录通过 PR 保存后才能供后续 render 自动恢复。

`mode=render` 自动恢复该记录中的小包；没有 narration 快照声明时，尝试使用同名已有 `render.json` 中的快照，先核 ZIP 完整性和当前请求，再下载源片；正式渲染完整核一次音频解码，然后严格复用。首次制作没有快照记录时正常合成并导出，下载链接记入 `render.json.tts_bundle`。已有快照的引用缺失、下载失败、字节篡改或声音不匹配会报错，修复引用或重新预检后再运行。不会下载含整部影片的大审音归档。

若首次渲染后只改画面，工作流可从既有 render 记录自动恢复。narration 记录优先；已有声明损坏时不会用旧 render 记录绕过失败。也可使用 `render.json.tts_bundle.url` 下载小包，通过上述本地 `--tts-bundle-in` 复用。完整 native archive 继续保留，供成片拼接与最终凭据验证使用。

音频解码和 WordBoundary 核验只查文件能否使用，未恢复响度、幅值、静音或增益检查。快照标记 `artifact_kind=native_tts_inputs`、`quality_approval=false`，不代替当前读音、画面、字幕、原声内容或发布审核。这里只验证复用机制；下一条新视频仍须从原始收件时间量到真实微信接口回执，不能据此宣布已达到20分钟。

## 本地有限输入实测

[原始实测记录](reel-tts-bundle-benchmark-2026-10-13.json)。8条实际本地缓存音频，3轮：小包404,155字节（约395KiB），捕获与解码核验中位1.196秒，下载前完整性/参数检查中位0.00243秒，完整导入核验与复用中位1.157秒；8个MP3恢复后的SHA逐项相同。这里只量小包机制，不含网络传输、Hosted启动、整片编码或微信推送，不能外推端到端节省。
