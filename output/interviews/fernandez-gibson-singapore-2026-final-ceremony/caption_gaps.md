# 自动字幕的空档：fernandez-gibson-singapore-2026-final-ceremony

阈值 2 秒；空档 **3** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `small.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况分不出来，得人去听。

## 25.3–27.7 秒（片内，2.4 秒；源片 https://youtu.be/972H4pIo248?t=410）

- 键：`410.1-412.5`
- 第二份 ASR（small.en）：`I`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：字幕时间轴本来就盖着这一段（第 15 行 407.12–414.96），第二份 ASR 只听到一个 `I`。gap_vad_attestation（run 36317566907 之后那趟 subs）`speech_seconds: 0`。

## 54.8–59.4 秒（片内，4.7 秒；源片 https://youtu.be/972H4pIo248?t=439）

- 键：`439.6-444.2`
- 第二份 ASR（small.en）：**什么都没有** → 人去听：没人说话，还是不是英语？
- 已销账：她说完「pushing me forward」之后的掌声：frame-grab 434/436/438 三格是台下教练席的人在鼓掌，440 切回她、嘴没动。VAD `speech_seconds: 0`，第二份 ASR 什么都没听出来。⚠️ 没听音轨，判据是 VAD ＋ 画面。

## 93.9–98.2 秒（片内，4.2 秒；源片 https://youtu.be/972H4pIo248?t=478）

- 键：`478.7-483.0`
- 第二份 ASR（small.en）：`and`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：「for many years to come」之后的掌声：480 那一格是看台全景（球迷挥着荧光棒），482 远景她站在颁奖台上。VAD `speech_seconds: 0`，第二份 ASR 只有一个 `and`——就是 482.96「And then finally」的第一个词提前露头。⚠️ 没听音轨，判据是 VAD ＋ 画面。

