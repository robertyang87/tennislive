# 转写交叉校验：zverev-khachanov-us-open-2026-sf-presser

- 第一份：ASR（small.en） **1351** 词
- 第二份：faster-whisper（medium.en）**1365** 词
- **对不上 3.4%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `sasha` → `sascha`
- `at an` → `—`
- `it's a` → `—`
- `i` → `i've`
- `a` → `—`
- `final` → `finals`
- `—` → `matt`
- `—` → `just`
- `—` → `i just i`
- `—` → `like`
- `it` → `—`
- `seven` → `certain number`
- `—` → `i'm not like`
- `semifinal` → `semi finals`
- `—` → `like`
- `—` → `now`
- `i can start no clue` → `it gets over`
- `us` → `u s`
- `played` → `play`
- `—` → `you know`
- `did` → `—`
- `there` → `—`
- `you've` → `you`
- `—` → `really`
- `at ashe` → `ash`
- `frances` → `francis`
- `frances` → `francis`
- `a` → `the`
- `ground strokes` → `groundstrokes`
- `—` → `so`
- `—` → `a`
- `bercy` → `bersi`
- `fery` → `ferry`
- `—` → `i mean`
- `—` → `so for that`
- `in` → `on`
- `—` → `ibadu`
- `—` → `what`
- `really` → `—`
- `didn't it's very rare` → `mean`
- `the old spirit` → `they all`
- `jannik` → `janik`
- `—` → `winning`
- `and then` → `—`
- `—` → `or i thought`
- `is` → `it's`
- `think` → `mean`
- `jannik` → `janik`
- `with` → `which was`
- `—` → `go ahead`
