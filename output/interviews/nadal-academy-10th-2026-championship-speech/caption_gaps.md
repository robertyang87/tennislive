# 自动字幕的空档：nadal-academy-10th-2026-championship-speech

阈值 2 秒；空档 **3** 处。

第一份是 ASR（small），第二份 ASR 是 `large-v3-turbo`（多语模型）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音，需结合语言窗、VAD 和原声核对。

## 42.9–52.7 秒（片内，9.8 秒；源片 https://youtu.be/N5OzUjDXdOs?t=42）

- 键：`42.9-52.7`
- 第二份 ASR（large-v3-turbo）：`Bueno,`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 0.354s 人声，第二份 ASR（large-v3-turbo）听到「Bueno,」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 64.0–67.8 秒（片内，3.8 秒；源片 https://youtu.be/N5OzUjDXdOs?t=63）

- 键：`64.0-67.8`
- 第二份 ASR（large-v3-turbo）：`Com`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：保守声音事件标注：原声完整保留，字幕明确掌声夹杂未辨识人声；未认证静音、说话人或台词，也没有人工听审认领。VAD实测人声0.552s；证据data/transcript_reviews/nadal-academy-10th-2026-championship-speech/gap-final-review.json。（证据 gap_vad_attestation.json）

## 154.9–158.2 秒（片内，3.3 秒；源片 https://youtu.be/N5OzUjDXdOs?t=154）

- 键：`154.9-158.2`
- 第二份 ASR（large-v3-turbo）：`Hace que`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 2.640s 人声，第二份 ASR（large-v3-turbo）听到「Hace que」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

