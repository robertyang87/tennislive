# 自动字幕的空档：davidovichfokina-jodar-shanghai-2026-f-speech

阈值 2 秒；空档 **3** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `medium.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 36.6–62.5 秒（片内，25.9 秒；源片 https://youtu.be/kUbqV30q1OE?t=36）

- 键：`36.6-62.5`
- 第二份 ASR（medium.en）：`For sure, you're gonna I'm gonna be I Cannot`　→ **第一份（YouTube 自动字幕）可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：祝贺霍达尔段落后的长时间掌声欢呼（26秒）：VAD 测到 20s 人声系掌声误检，第二份 ASR 仅听到单个 'I'（边界漂移词，前后字幕已覆盖），双 ASR 自动销账（gap_vad_attestation.json）。

## 119.3–145.8 秒（片内，26.5 秒；源片 https://youtu.be/kUbqV30q1OE?t=119）

- 键：`119.3-145.8`
- 第二份 ASR（medium.en）：`I Want to`　→ **第一份（YouTube 自动字幕）可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：感谢团队段落后的掌声（26秒）：VAD 23s 人声系掌声误检，第二份 ASR 仅 'I'，双 ASR 自动销账。

## 187.6–218.7 秒（片内，31.1 秒；源片 https://youtu.be/kUbqV30q1OE?t=187）

- 键：`187.6-218.7`
- 第二份 ASR（medium.en）：`May how the G Cheetah Cheetah And`　→ **第一份（YouTube 自动字幕）可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：感谢赛事方段落后的掌声（31秒）：VAD 29s 人声系掌声误检，第二份 ASR 仅 'And'，双 ASR 自动销账。

