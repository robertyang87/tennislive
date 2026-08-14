# 自动字幕的空档：swiatek-rybakina-tor2026-final

阈值 2 秒；空档 **1** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `small.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况分不出来，得人去听。

## 27.2–29.9 秒（片内，2.8 秒；源片 https://youtu.be/bDttZof7qXI?t=400）

- 键：`400.9-403.7`
- 第二份 ASR（small.en）：`remember`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：不是漏词。查了本地raw caption（cap_bDttZof7qXI.en.json3）：393.99秒她说到『and always』，紧接394.96秒出现[cheering]、398.89秒[applause]（观众为『不公评判和恶意』那句鼓掌），下一条字幕事件403.68秒『and always remember what's ahead and um what's might be possible』完整衔接——第二份ASR听到的『remember』就是这条事件提前几百毫秒的边界效应，YouTube原字幕在gap结束的同一时刻已经把这句话完整接上了，zh第52-53行『永远记得前面 还有什么是可能的』覆盖的正是这句，不缺内容

