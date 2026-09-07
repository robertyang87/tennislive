# 自动字幕的空档：zheng-swiatek-us-open-2026-r4-interview

阈值 2 秒；空档 **3** 处。

第一份是 YouTube 自动字幕，第二份 ASR 是 `medium.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况分不出来，得人去听。

## 10.5–13.1 秒（片内，2.6 秒；源片 https://youtu.be/VFHIp4MEEOs?t=10）

- 键：`10.5-13.1`
- 第二份 ASR（medium.en）：**什么都没有** → 人去听：没人说话，还是不是英语？
- 已销账：掌声打断。源片自动字幕在 **8.52 和 13.10 各有一个 `[cheering]` 标记**，这 2.6 秒正夹在两个欢呼之间——主持人开口第一问（「Qinwen, congratulations. What an unbelievable performance that was. But I have to ask」）被全场欢呼打断，13.10 之后他接着说 `in the previous round against Madison Keys`，是同一句话的后半截。⚠️ **判据是字幕自己的噪声标记，我没有听音轨**（沙箱下不动这条源片的媒体流）。

## 71.6–75.4 秒（片内，3.9 秒；源片 https://youtu.be/VFHIp4MEEOs?t=71）

- 键：`71.6-75.4`
- 第二份 ASR（medium.en）：`It's`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：掌声。这一段**没有噪声标记**，所以拿画面自证：她在 71.6 说完第一个长回答的最后一句（「That's all I can say.」），而 `frame-grab`（run 34152151794）抽到的 **72s 和 74s 两张真帧都切到了看台**——举着「QUEEN IS BACK」牌子的球迷特写；70s 那张也是观众席。**受访者答完一段、转播切观众席**是标准做法，那几秒是掌声不是漏词。75.44 主持人开口问第二个问题。⚠️ **判据是画面加转播惯例，不是听出来的**——沙箱听不了音轨，这一条比另外两条软一档。

## 134.3–136.7 秒（片内，2.4 秒；源片 https://youtu.be/VFHIp4MEEOs?t=134）

- 键：`134.3-136.7`
- 第二份 ASR（medium.en）：`Can`　→ **第一份（YouTube 自动字幕）漏了英语，补进 `en_fixed`**
- 已销账：掌声。源片自动字幕 **132.31 有 `[cheering and applause]`**，就在她说完「That's why I'm here.」（谢团队）之后；136.72 主持人开口问第三个问题（`Qinwen, you were out with injury...`）。⚠️ **判据是字幕自己的噪声标记，我没有听音轨。**

