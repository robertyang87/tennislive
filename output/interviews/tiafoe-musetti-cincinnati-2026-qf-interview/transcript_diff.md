# 转写交叉校验：tiafoe-musetti-cincinnati-2026-qf-interview

- 第一份：ASR（faster-whisper medium.en） **242** 词
- 第二份：faster-whisper（small.en）**242** 词
- **对不上 8.7%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（faster-whisper medium.en），右＝第二份）

- `managed` → `manage`
- `match` → `max`
- `missed the` → `mr`
- `pick up` → `pickup`
- `i` → `—`
- `—` → `it`
- `—` → `and`
- `did i` → `—`
- `did tonight` → `didn't know`
- `we're all just` → `rugs`
- `one percent` → `1`
- `—` → `he`
- `the` → `—`
- `—` → `i was`
- `—` → `yes sir`
- `match` → `max every max`
- `its` → `his`
- `its` → `his`
- `the` → `a`
