# 转写交叉校验：jodar-tabilo-cincinnati-2026-r3

- 第一份：ASR（small.en） **410** 词
- 第二份：faster-whisper（medium.en）**372** 词
- **对不上 13.7%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `rafa` → `—`
- `denis` → `dennis`
- `you know` → `—`
- `push you know` → `pushed`
- `you know` → `—`
- `yeah` → `—`
- `you know so` → `—`
- `you know seems` → `seemed`
- `more` → `—`
- `you know` → `—`
- `be` → `give`
- `be` → `give`
- `you know and` → `—`
- `favor` → `favour`
- `analyzing` → `analysing`
- `you know` → `—`
- `in` → `on`
- `you know so` → `—`
- `you know` → `—`
- `—` → `of`
- `gonna` → `going to`
- `you know` → `—`
- `you know` → `—`
- `in` → `than`
- `this type` → `these types`
- `you know` → `—`
- `you know` → `—`
- `center court` → `centre course`
- `yeah` → `yes`
- `you know` → `—`
- `you know` → `—`
- `and` → `—`
- `you know` → `—`
- `—` → `that`
