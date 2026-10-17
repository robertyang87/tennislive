# 转写交叉校验：jodar-medvedev-shanghai-2026-sf-interview

- 第一份：ASR（small.en） **195** 词
- 第二份：faster-whisper（medium.en）**196** 词
- **对不上 5.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `daniil` → `daniel`
- `—` → `a`
- `hard court` → `hardcore`
- `break points` → `breakpoints`
- `break points` → `breakpoints`
- `returned` → `return`
- `served` → `then serve`
- `daniil's` → `daniel is`
- `—` → `very`
- `give` → `be`
