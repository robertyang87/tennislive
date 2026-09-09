# 转写交叉校验：zheng-rybakina-us-open-2026-qf-presser

- 第一份：ASR（small.en） **832** 词
- 第二份：faster-whisper（medium.en）**842** 词
- **对不上 3.8%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `cole` → `cool`
- `—` → `now`
- `quarter final` → `quarterfinal`
- `bit` → `—`
- `—` → `of you`
- `you` → `—`
- `—` → `just`
- `it` → `that`
- `bit` → `big`
- `missed` → `miss`
- `it's` → `is`
- `a` → `the`
- `—` → `okay abel`
- `qinwen` → `chinwen`
- `—` → `or`
- `to` → `you'll`
- `in` → `—`
- `there are` → `there's`
- `a` → `—`
- `eva's` → `ava's`
- `down sets` → `downsets`
- `things` → `thing`
- `things` → `thing`
- `like` → `—`
- `much` → `match`
- `you know` → `—`
- `it` → `—`
- `—` → `the`
- `like` → `—`
- `—` → `all right shimon`
- `—` → `and`
- `—` → `and`
- `—` → `i`
- `qualifying` → `calling`
- `out` → `on`
- `want` → `wants`
- `—` → `you know`
- `—` → `you know`
- `too much` → `to match`
- `—` → `question that was my`
