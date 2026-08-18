# 转写交叉校验：fils-lehecka-cincinnati-2026-r3

- 第一份：ASR（small.en） **290** 词
- 第二份：faster-whisper（medium.en）**293** 词
- **对不上 6.2%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `our tour` → `arturo`
- `match` → `matches`
- `play` → `played i'm`
- `we` → `—`
- `condition` → `conditions`
- `boys` → `ball is`
- `close` → `closed it`
- `to` → `—`
- `i'm missing` → `i miss in`
- `—` → `yeah`
- `let's` → `that`
- `—` → `a`
- `once at` → `one set`
- `this` → `the`
- `you` → `you've`
- `autograph` → `autographs`
- `yeah` → `—`
- `—` → `i've`
