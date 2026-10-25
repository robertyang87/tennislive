# 自动字幕的空档：rybakina-fernandez-ningbo-2026-f-speech

阈值 2 秒；空档 **2** 处。

第一份是 ASR（medium），第二份 ASR 是 `small`（多语模型）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 29.0–32.3 秒（片内，3.3 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=34）

- 键：`34.6-37.9`
- 第二份 ASR（small）：`Then I would like to say`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 0.554s 人声，第二份 ASR（small）听到「Then I would like to say」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 85.3–89.2 秒（片内，3.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=90）

- 键：`90.9-94.8`
- 第二份 ASR（small）：`Then`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

