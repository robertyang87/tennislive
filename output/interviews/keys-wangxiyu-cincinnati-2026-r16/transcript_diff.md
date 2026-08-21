# 转写交叉校验：keys-wangxiyu-cincinnati-2026-r16

- 第一份：YouTube 自动字幕 **469** 词
- 第二份：faster-whisper（medium.en）**470** 词
- **对不上 3.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝YouTube 自动字幕，右＝第二份）

- `xiu 7664` → `shiyu 7 6 6 4`
- `but` → `the`
- `either selk` → `maybe sara baedek`
- `arena sabalena` → `irina sabaleka`
- `maddie` → `—`
- `you` → `—`
- `to` → `a`
- `good` → `—`
- `like` → `—`
- `—` → `a`
- `o'clock` → `o 'clock`
- `going to` → `gonna`
- `8` → `eight`
- `9` → `nine`
