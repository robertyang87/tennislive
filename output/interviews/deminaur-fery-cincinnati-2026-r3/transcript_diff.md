# 转写交叉校验：deminaur-fery-cincinnati-2026-r3

- 第一份：ASR（small.en） **284** 词
- 第二份：faster-whisper（medium.en）**255** 词
- **对不上 13.0%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `—` → `be`
- `breakout` → `break out`
- `—` → `a`
- `1` → `'1`
- `it's` → `—`
- `but` → `—`
- `i mean` → `—`
- `it got` → `—`
- `but` → `—`
- `a` → `your`
- `i mean` → `—`
- `from` → `—`
- `i think you know` → `—`
- `kind of` → `—`
- `right and then` → `—`
- `kind of` → `—`
- `just` → `—`
- `by` → `—`
- `and` → `—`
- `kind of tiebreak` → `tie break`
- `so look` → `—`
- `and you know` → `—`
- `thank you` → `—`
