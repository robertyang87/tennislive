# 转写交叉校验：faria-shelton-cincinnati-2026-r2

- 第一份：ASR（small.en） **299** 词
- 第二份：faster-whisper（medium.en）**298** 词
- **对不上 7.7%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `jaime` → `shaim`
- `—` → `a`
- `—` → `it's`
- `ten` → `10`
- `you've got to` → `you gotta`
- `going to` → `gonna`
- `beat` → `—`
- `going to` → `gonna`
- `happens` → `happened so i'm`
- `in` → `and`
- `you've got to` → `you gotta`
- `because` → `—`
- `he` → `you`
- `break down` → `breakdown`
- `—` → `you know`
- `—` → `the on`
- `i made` → `make`
- `this` → `the`
- `a` → `—`
