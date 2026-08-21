# 转写交叉校验：swiatek-rybakina-cincinnati-2026-qf

- 第一份：ASR（small.en） **430** 词
- 第二份：faster-whisper（medium.en）**427** 词
- **对不上 5.1%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `it's` → `—`
- `—` → `the`
- `going to` → `gonna`
- `—` → `you know`
- `—` → `you know`
- `going to` → `gonna`
- `going to` → `gonna`
- `and` → `—`
- `of` → `—`
- `a` → `that`
- `—` → `tennis`
- `and` → `—`
- `got to` → `gotta`
- `pegula` → `pagula`
- `setters` → `sellers`
- `going to` → `gonna`
- `going to` → `it's gonna`
- `semi` → `semis`
- `iga swiatek` → `igor siontek`
