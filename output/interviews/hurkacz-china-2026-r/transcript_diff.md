# 转写交叉校验：hurkacz-china-2026-r

- 第一份：ASR（small.en） **352** 词
- 第二份：faster-whisper（medium.en）**367** 词
- **对不上 6.0%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `hughie` → `you've a`
- `you know` → `no`
- `—` → `that was`
- `feel` → `fill`
- `you know` → `now`
- `well` → `we'll`
- `then` → `them`
- `shiel savara` → `shield sivara`
- `you know` → `no`
- `—` → `was cool it's`
- `i'm` → `then`
- `is` → `—`
- `wanna` → `want to`
- `—` → `so it's`
- `—` → `some`
- `tournaments` → `tournament`
- `wanna` → `want to`
- `—` → `is there`
- `no definitely you` → `i`
- `—` → `the female`
- `some` → `somewhere niggles`
- `—` → `it's but it's you know`
