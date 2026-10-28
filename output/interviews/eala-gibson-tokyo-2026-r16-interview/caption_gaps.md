# 自动字幕的空档：eala-gibson-tokyo-2026-r16-interview

阈值 2 秒；空档 **3** 处。

第一份是 ASR（small），第二份 ASR 是 `medium.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 31.6–37.1 秒（片内，5.5 秒；源片 https://github.com/robertyang87/tennislive/releases/download/src-eala-tokyo-20261028/eala-tokyo-r16-interview-fbcopy.mp4（片内 31.6 秒））

- 键：`31.6-37.1`
- 第二份 ASR（medium.en）：`Well, I guess that's the key to your victory tonight.`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

## 46.1–57.5 秒（片内，11.4 秒；源片 https://github.com/robertyang87/tennislive/releases/download/src-eala-tokyo-20261028/eala-tokyo-r16-interview-fbcopy.mp4（片内 46.1 秒））

- 键：`46.1-57.5`
- 第二份 ASR（medium.en）：`You were in the Philippines for a long time. How did you feel when you came back?`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

## 66.6–69.9 秒（片内，3.3 秒；源片 https://github.com/robertyang87/tennislive/releases/download/src-eala-tokyo-20261028/eala-tokyo-r16-interview-fbcopy.mp4（片内 66.6 秒））

- 键：`66.6-69.9`
- 第二份 ASR（medium.en）：**什么都没有** → 核对原声：环境声、未识别语音，还是时间边界漂移？
- 已销账：字幕时间轴自动销账：VAD 测到 0.000s 人声，第二份 ASR（medium.en）没听出词——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

