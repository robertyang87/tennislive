# 转写交叉校验：zverev-tien-laver-cup-2026-interview

- 第一份：ASR（small.en） **330** 词
- 第二份：faster-whisper（medium.en）**353** 词
- **对不上 3.3%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `5 1` → `five and one`
- `laver` → `labour`
- `—` → `i think`
- `—` → `to`
- `—` → `for it`
- `it` → `you`
- `out` → `up`
- `—` → `and`
- `it` → `—`
- `learner` → `lerner`
- `—` → `so`
- `favourite` → `favorite`
- `laver` → `labor`
- `—` → `there's`
- `—` → `in`
- `—` → `you know`
- `week and` → `weekend`
- `—` → `with`
- `—` → `and`
- `—` → `i mean`
- `—` → `tim tim has to`
- `—` → `but you know i think`
