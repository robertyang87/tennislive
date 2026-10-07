# 转写交叉校验：zheng-charaeva-beijing-2026-interview

- 原声语言窗口（仅转写，不翻译）： [{"start": 262.0, "end": 301.0, "language": "en"}, {"start": 301.0, "end": 352.0, "language": "zh"}, {"start": 352.0, "end": 392.5, "language": "en"}, {"start": 392.5, "end": 455.8, "language": "zh"}]
- 第一份：ASR（small） **586** 词
- 第二份：faster-whisper（medium）**592** 词
- **对不上 1.7%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small），右＝第二份）

- `eleven` → `11`
- `得` → `的`
- `—` → `了`
- `未 清` → `影 响`
- `—` → `in`
- `unclear` → `how the ground`
- `cheer` → `share`
- `unclear` → `battle`
- `钦` → `清`
- `钦` → `清`
- `—` → `然 后`
- `钦` → `清`
