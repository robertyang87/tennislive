# 自动字幕的空档：zheng-charaeva-beijing-2026-interview

阈值 2 秒；空档 **7** 处。

第一份是 ASR（small），第二份 ASR 是 `medium`（多语模型）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 14.9–17.2 秒（片内，2.3 秒；源片 https://youtu.be/LGHCCL4VHCw?t=276）

- 键：`276.9-279.2`
- 第二份 ASR（medium）：**什么都没有** → 核对原声：环境声、未识别语音，还是时间边界漂移？
- 已销账：字幕时间轴自动销账：VAD 测到 0.056s 人声，第二份 ASR（medium）没听出词——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 20.3–24.5 秒（片内，4.1 秒；源片 https://youtu.be/LGHCCL4VHCw?t=282）

- 键：`282.3-286.5`
- 第二份 ASR（medium）：**什么都没有** → 核对原声：环境声、未识别语音，还是时间边界漂移？
- 已销账：VAD 自动销账：VAD 在核心区只测到 0.000s 人声（≤0.12s），第二份 ASR（medium）一个词都没听到——没人说话，自动销账（证据 gap_vad_attestation.json）

## 68.6–71.9 秒（片内，3.4 秒；源片 https://youtu.be/LGHCCL4VHCw?t=330）

- 键：`330.6-333.9`
- 第二份 ASR（medium）：`尤`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 0.000s 人声，第二份 ASR（medium）听到「尤」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 84.2–90.0 秒（片内，5.8 秒；源片 https://youtu.be/LGHCCL4VHCw?t=346）

- 键：`346.2-352.0`
- 第二份 ASR（medium）：`Okay.`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

## 114.7–117.8 秒（片内，3.1 秒；源片 https://youtu.be/LGHCCL4VHCw?t=376）

- 键：`376.7-379.8`
- 第二份 ASR（medium）：`Well,`　→ **第一份（ASR（small））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 0.002s 人声，第二份 ASR（medium）听到「Well,」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 130.5–132.7 秒（片内，2.2 秒；源片 https://youtu.be/LGHCCL4VHCw?t=392）

- 键：`392.5-394.7`
- 第二份 ASR（medium）：**什么都没有** → 核对原声：环境声、未识别语音，还是时间边界漂移？
- 已销账：**否**

## 177.4–180.3 秒（片内，2.9 秒；源片 https://youtu.be/LGHCCL4VHCw?t=439）

- 键：`439.4-442.3`
- 第二份 ASR（medium）：**什么都没有** → 核对原声：环境声、未识别语音，还是时间边界漂移？
- 已销账：字幕时间轴自动销账：VAD 测到 0.000s 人声，第二份 ASR（medium）没听出词——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

