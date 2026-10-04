# 转写交叉校验：djokovic-china-2026-r

- 第一份：ASR（small.en） **403** 词
- 第二份：faster-whisper（medium.en）**416** 词
- **对不上 2.2%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `—` → `i`
- `an` → `—`
- `—` → `the break`
- `—` → `and`
- `a` → `the`
- `a` → `get the`
- `they're` → `they are`
- `i` → `—`
- `—` → `yeah`
- `and` → `in`
- `—` → `and i`
- `—` → `that`
- `compete for` → `—`
- `—` → `it's`
- `—` → `these are`
- `—` → `it's been`
- `—` → `for`
- `—` → `to`
- `i` → `it`
