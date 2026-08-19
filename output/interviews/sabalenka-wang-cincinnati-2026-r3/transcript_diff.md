# 转写交叉校验：sabalenka-wang-cincinnati-2026-r3

- 第一份：YouTube 自动字幕 **307** 词
- 第二份：faster-whisper（small.en）**301** 词
- **对不上 4.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝YouTube 自动字幕，右＝第二份）

- `to 61 63` → `—`
- `sabalanka` → `sabalenka`
- `she is` → `she's`
- `61 63` → `six one six three`
- `it's` → `—`
- `the` → `—`
- `1 00` → `1000`
- `mason` → `—`
- `sabalena` → `sabalenka`
