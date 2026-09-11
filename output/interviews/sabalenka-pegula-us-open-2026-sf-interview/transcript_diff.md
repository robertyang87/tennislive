# 转写交叉校验：sabalenka-pegula-us-open-2026-sf-interview

- 第一份：ASR（small.en） **335** 词
- 第二份：faster-whisper（medium.en）**347** 词
- **对不上 3.0%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `aryna` → `well arena`
- `match` → `much a place against`
- `—` → `it was`
- `—` → `thank you`
- `—` → `the`
- `—` → `i`
- `—` → `could i`
- `legends` → `—`
- `in` → `—`
- `else's night` → `else fights you`
- `nelly` → `nellie`
- `we'll` → `will`
- `—` → `well`
- `well` → `world`
- `aryna` → `arena`
