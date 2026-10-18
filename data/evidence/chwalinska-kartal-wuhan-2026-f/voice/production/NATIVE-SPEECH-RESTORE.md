# 原生配音引用如何恢复

本目录JSON中的`native-speech/*.mp3`是本地展开路径，MP3不应提交到Git。完整原生配音和成对WordBoundary已在公开的内容哈希标记Release中：

https://github.com/robertyang87/tennislive/releases/download/reel-tts-chwalinska-kartal-wuhan-2026-f-2414de29cc3083bf/tts_bundle.zip

- ZIP SHA256：`2414de29cc3083bf79d08dc11e33ef22100671bd96605d8dd0fddc4ab34bf9d9`
- 大小：751095字节。
- 包内`manifest.json`保存9项完整request、request_id、MP3及raw marks哈希、实现哈希和时长。
- [native-speech-restore.json](native-speech-restore.json)逐项列出9个剪辑ID、完整request、ZIP成员名、本地MP3/marks路径及各自SHA256。音频与marks必须成对恢复。

执行：

```bash
python requests/reels/chwalinska-kartal-wuhan-2026-f/voice-review/restore_native_speech.py \
  --map data/evidence/chwalinska-kartal-wuhan-2026-f/voice/production/native-speech-restore.json \
  --outdir data/evidence/chwalinska-kartal-wuhan-2026-f/voice/production/native-speech
```

已有下载包可另加`--bundle /path/to/tts_bundle.zip`。工具先核整包SHA、完整request集合、实现、每个成员哈希，再写本地文件；现有文件不一致时拒绝覆盖。它只读取原字节，不调用TTS、不转码、不调声音，也不修改任何审核结论。公开下载验证已实际完成，恢复出的9个MP3及9个marks与所审核输入字节一致。GitHub下载时的临时签名跳转只在内存中跟随，不写入证据。

`reference-cache/`是声学对照参考音频及其配对边界，不在这份生产ZIP内。它们不提交Git；现有target JSON中的数值和参考哈希仍保留，但本说明不声称这些参考音频也可由生产ZIP恢复。若未来需保全这些对照音频，应另行存放带哈希的证据归档，不能靠重新网络合成冒充原参考字节。

当前新8段口播的120.504秒全旁白核听仍待用户答复；用户批准720p不属于配音答复。品牌仅复用上一片同完整原句、同request、同MP3/marks的真实owner确认。现有机器unknown与待核状态全部保持原样。
