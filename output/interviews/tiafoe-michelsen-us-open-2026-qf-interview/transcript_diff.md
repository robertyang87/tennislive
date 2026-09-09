# 转写交叉校验：tiafoe-michelsen-us-open-2026-qf-interview

- 第一份：ASR（small.en） **264** 词
- 第二份：faster-whisper（medium.en）**262** 词
- **对不上 10.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `frances` → `—`
- `of` → `—`
- `—` → `but`
- `to get` → `getting`
- `—` → `and`
- `—` → `and`
- `to` → `—`
- `michelsen` → `nicholson`
- `seven six` → `7 6`
- `sleeping` → `asleep in`
- `of` → `—`
- `—` → `i was`
- `y'all` → `y 'all`
- `two` → `to`
- `semifinals` → `semi finals`
- `shelton` → `chilton`
- `going to` → `gonna`
- `going to` → `gonna`
- `they've got to` → `they better`
- `—` → `played before`
- `played for four hours forty` → `was 40`
- `going to` → `gonna`
