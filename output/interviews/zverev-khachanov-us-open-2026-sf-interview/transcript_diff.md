# 转写交叉校验：zverev-khachanov-us-open-2026-sf-interview

- 第一份：ASR（small.en） **298** 词
- 第二份：faster-whisper（medium.en）**282** 词
- **对不上 7.0%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `at` → `—`
- `maybe` → `—`
- `has` → `—`
- `you know` → `—`
- `on your` → `when you're`
- `these` → `—`
- `i think` → `—`
- `incredible` → `—`
- `frances` → `francis`
- `the` → `—`
- `to` → `—`
- `semi final` → `semifinal`
- `to` → `—`
- `i cannot` → `not`
- `all right` → `—`
