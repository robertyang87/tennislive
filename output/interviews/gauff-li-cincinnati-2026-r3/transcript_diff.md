# 转写交叉校验：gauff-li-cincinnati-2026-r3

- 第一份：YouTube 自动字幕 **311** 词
- 第二份：faster-whisper（small.en）**311** 词
- **对不上 5.5%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝YouTube 自动字幕，右＝第二份）

- `she` → `—`
- `6 1 7 6 3` → `six one seven six set`
- `—` → `gough is on`
- `—` → `i'm`
- `to` → `—`
- `missed` → `miss`
- `this court` → `the score`
- `in` → `—`
- `tennis` → `centers`
- `staying` → `saying`
- `to` → `—`
- `tiebreaker i` → `tie breaker`
- `gauff` → `gough`
