# 自动字幕的空档：pegula-gauff-cin2026-final-runnerup

阈值 2 秒；空档 **3** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `small.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况分不出来，得人去听。

## 49.8–52.6 秒（片内，2.8 秒；源片 https://youtu.be/pIRDCAcGpz0?t=49）

- 键：`49.8-52.6`
- 第二份 ASR（small.en）：`I'm`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：自动字幕在这一段没有事件，raw json3 里前面紧接着一条 `[applause]`（47.815 秒起，覆盖到这段空档），后一句「I'm a little upset I have two of these now」在 52.64 秒重新起头——两头夹着掌声标记，是主持人／观众鼓掌打断，不是漏词。⚠️ 只核对了原始字幕的括号标记，没有实际听音轨（沙箱下不动这条视频的完整音视频流）。

## 99.2–101.5 秒（片内，2.4 秒；源片 https://youtu.be/pIRDCAcGpz0?t=99）

- 键：`99.2-101.5`
- 第二份 ASR（small.en）：**什么都没有** → 人去听：没人说话，还是不是英语？
- 已销账：同上，raw json3 在 101.526 秒有一条 `[applause]`，紧接着 101.5 秒后正文继续「And next I want to thank」——两头夹着掌声标记。⚠️ 同样只核对了字幕括号标记，没有实际听音轨。

## 153.3–156.0 秒（片内，2.7 秒；源片 https://youtu.be/pIRDCAcGpz0?t=153）

- 键：`153.3-156.0`
- 第二份 ASR（small.en）：**什么都没有** → 人去听：没人说话，还是不是英语？
- 已销账：同上，raw json3 在 151.306 秒有一条 `[cheering and applause]`，覆盖到这段空档，之后 156.04 秒正文继续「And yeah, it makes it so much fun to」——两头夹着欢呼／掌声标记。⚠️ 同样只核对了字幕括号标记，没有实际听音轨。

