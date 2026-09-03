# 转写交叉校验：bu-jodar-us-open-2026-r1-interview

- 第一份：ASR（small.en） **502** 词
- 第二份：faster-whisper（medium.en）**501** 词
- **对不上 8.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `rafael jodar` → `rafa hodor`
- `really` → `a very`
- `is` → `—`
- `is` → `was`
- `—` → `it`
- `rain` → `rained`
- `stop` → `stopped`
- `then make` → `it made`
- `save` → `saved`
- `anytime` → `any time`
- `then` → `—`
- `looks like` → `—`
- `in my` → `—`
- `is very` → `it's`
- `—` → `of`
- `qualies` → `quality`
- `day we` → `we're`
- `—` → `a`
- `—` → `a`
- `chill` → `cheer`
- `try to` → `—`
- `tell` → `told`
- `i was` → `—`
- `8 00 a m` → `to aem`
- `00` → `—`
- `ready to` → `right where i`
- `have i` → `—`
- `—` → `a`
- `00` → `—`
- `i` → `—`
- `—` → `not`
- `played` → `play`
- `lost qualies` → `lose in the quality`
- `—` → `and`
- `—` → `to`
- `—` → `in the`
- `us` → `u s`
- `bu` → `boo`
- `—` → `boo yinchakite`
