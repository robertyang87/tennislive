# 转写交叉校验：rybakina-frech-cincinnati-2026-r3

- 第一份：YouTube 自动字幕 **320** 词
- 第二份：faster-whisper（medium.en）**326** 词
- **对不上 5.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝YouTube 自动字幕，右＝第二份）

- `rybakina` → `we're back in her`
- `rybakina` → `rebacking it`
- `rybakina` → `rebacking`
- `from` → `for`
- `64 76` → `six four seven six`
- `rybakina` → `rebacking it`
- `you know` → `now`
- `—` → `and`
- `clouded` → `cloud it's`
- `it` → `—`
- `then` → `and`
- `it` → `—`
- `you're` → `you`
- `in` → `thing`
- `tie break` → `tiebreak`
- `serve` → `surf`
- `—` → `okay`
