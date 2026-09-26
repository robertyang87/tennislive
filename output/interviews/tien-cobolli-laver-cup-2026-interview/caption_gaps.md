# 自动字幕的空档：tien-cobolli-laver-cup-2026-interview

阈值 2 秒；空档 **3** 处。

第一份是 ASR（small.en），第二份 ASR 是 `medium.en`（英语专用）。**它什么都没听出来，不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况分不出来，得人去听。

## 4.2–9.8 秒（片内，5.6 秒；源片 https://youtu.be/NPJ0nTLVkbs?t=4）

- 键：`4.2-9.8`
- 第二份 ASR（medium.en）：`I`　→ **第一份（ASR（small.en））漏了英语，补进 `en_fixed`**
- 已销账：**否**

## 40.8–48.8 秒（片内，7.9 秒；源片 https://youtu.be/NPJ0nTLVkbs?t=40）

- 键：`40.8-48.8`
- 第二份 ASR（medium.en）：**什么都没有** → 人去听：没人说话，还是不是英语？
- 已销账：**否**

## 89.6–94.6 秒（片内，5.0 秒；源片 https://youtu.be/NPJ0nTLVkbs?t=89）

- 键：`89.6-94.6`
- 第二份 ASR（medium.en）：**什么都没有** → 人去听：没人说话，还是不是英语？
- 已销账：推的，没听音轨：主持人 88.9~89.2 问完「how much does it help you having the great Andre Agassi on your bench for your confidence?」，他 94.6 才开口答「It's amazing.」——一问一答之间的停顿。两份 ASR（small.en、medium.en）在这 5 秒里都没听出词，VAD 没能证明无人声，多半是主持人提到阿加西时的现场欢呼。问句和答句两头都完整，不是漏了谁的话。

