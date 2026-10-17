# 自动字幕的空档：kartal-ostapenko-wuhan-2026-sf-interview

阈值 2 秒；空档 **1** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `small.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 33.2–44.4 秒（片内，11.2 秒；源片 https://youtu.be/abL2j0xldOc?t=330）

- 键：`330.2-341.4`
- 第二份 ASR（small.en）：`So,`　→ **第一份（YouTube 自动字幕）可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 10.116s 人声，第二份 ASR（small.en）听到「So,」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

