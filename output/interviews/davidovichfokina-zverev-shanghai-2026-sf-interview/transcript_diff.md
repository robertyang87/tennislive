# 转写交叉校验：davidovichfokina-zverev-shanghai-2026-sf-interview

- 第一份：ASR（small.en） **301** 词
- 第二份：faster-whisper（medium.en）**282** 词
- **对不上 13.3%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `like` → `—`
- `no to to doesn't matter the result` → `you know that's a murder so`
- `if i` → `—`
- `i get` → `—`
- `the` → `—`
- `and` → `on the`
- `more` → `—`
- `no` → `—`
- `the` → `—`
- `know` → `—`
- `was` → `—`
- `i` → `—`
- `—` → `it`
- `the result no` → `there so now`
- `just` → `—`
- `no` → `now`
- `no` → `now`
- `no` → `now`
- `no` → `now`
- `you are` → `you're`
- `at the end` → `i think`
- `no to` → `not`
- `to` → `—`
- `fr` → `—`
- `know to` → `not`
- `to` → `—`
