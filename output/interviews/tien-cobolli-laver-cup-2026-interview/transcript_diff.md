# 转写交叉校验：tien-cobolli-laver-cup-2026-interview

- 第一份：ASR（small.en） **335** 词
- 第二份：faster-whisper（medium.en）**338** 词
- **对不上 3.9%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `learner tien` → `lerner t`
- `a` → `the`
- `6 2` → `six two`
- `a` → `the`
- `10` → `ten`
- `still has` → `sells`
- `—` → `was`
- `—` → `some`
- `—` → `is`
- `—` → `that`
- `but` → `—`
- `through` → `there`
- `—` → `was`
- `3 3` → `three three`
