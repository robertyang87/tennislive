# 转写交叉校验：cobolli-mensik-laver-cup-2026-doubles-interview

- 第一份：ASR（small.en） **360** 词
- 第二份：faster-whisper（medium.en）**361** 词
- **对不上 7.8%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `from winning the laver cup` → `you're just one match away`
- `to` → `you know it's`
- `laver cup and` → `third year that`
- `never won a match` → `came`
- `finish` → `speak`
- `—` → `yeah i don't know`
- `—` → `a`
- `specialist i mean i'm not double` → `—`
- `jakub` → `one of the best performances ever for me jacob`
- `mcenroe was up jakob patrick mcenroe` → `macramore`
- `—` → `a`
- `it` → `—`
