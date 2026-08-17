# 转写交叉校验：rybakina-townsend-cincinnati-2026-r2

- 第一份：YouTube 自动字幕 **364** 词
- 第二份：faster-whisper（medium.en）**358** 词
- **对不上 3.8%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝YouTube 自动字幕，右＝第二份）

- `eight 1000` → `one thousand`
- `is` → `—`
- `score line` → `scoreline`
- `well` → `—`
- `was` → `with`
- `the` → `—`
- `she is` → `she's a`
- `hardcourt` → `hardcore`
- `okay` → `—`
- `you've` → `you`
- `try` → `—`
