# 自动字幕的空档：rybakina-sabalenka-us-open-2026-final-ceremony

阈值 2 秒；空档 **2** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `small.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况分不出来，得人去听。

## 96.3–98.7 秒（片内，2.4 秒；源片 https://youtu.be/L7EtjUS4IwY?t=104）

- 键：`104.2-106.6`
- 第二份 ASR（small.en）：`Of`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：掌声和欢呼，不是漏词。判据是自动字幕自己给的：100.56 那条事件的文本就是「you guys. [applause and cheering]」，而它一直覆盖到下一条 106.56——也就是说 ASR 自己把这 6 秒标成了掌声和欢呼，空档（104.2~106.6）整段落在它里面；106.56 她**重新起头**说「Of course, I want to say thank you to the people without who I wouldn't be here」，这是掌声打断致辞再接上的标准形状（CLAUDE.md「颁奖致辞这类素材，被掌声打断是常态而不是异常」那一条记的两个判据：两头夹着噪声标记 ＋ 随后重新起头）。前一句是「It's an amazing memories for me. Thank you guys.」——她谢完观众，全场鼓掌，这个位置鼓掌完全合理。
⚠️ **这是推的，不是听的**：沙箱下不动这条源片的音视频流（只下得动字幕），所以我没有听过这 2.4 秒，也没有量过响度。`--stage verify` 在 runner 上跑第二份 ASR ＋ Silero VAD 之后要回来核一遍——那条路才有音轨。
⚠️ **这一栏的每个键都会被当成空档键去核**（`test_销掉的空档得真的是空档` 拿当前字幕重算一遍空档，销了而现在没有的键当场红）——所以说明只能写进值里，不能另起一个 `_why` 键。第一版就是这么写的，当场红在 `['_why']`。

## 125.1–128.4 秒（片内，3.3 秒；源片 https://youtu.be/L7EtjUS4IwY?t=133）

- 键：`133.0-136.3`
- 第二份 ASR（small.en）：`And`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：同上，掌声。131.00 那条事件的文本就是「[applause]」，空档（133.0~136.3）紧跟在它后面；136.32 她重新起头说「And last I want to say thank you to all people who made this tournament possible」。前一句是「And without you, it won't be possible.」——她谢完团队和家人，全场鼓掌。
⚠️ 同样是推的不是听的，等 `--stage verify` 的 VAD 结果核。

