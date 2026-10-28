# 转写交叉校验：eala-gibson-tokyo-2026-r16-interview

- 第一份：ASR（small） **115** 词
- 第二份：faster-whisper（medium.en）**155** 词
- **对不上 18.3%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small），右＝第二份）

- `—` → `absolutely everything it's real quality well you lost the first set but you came back strong what was the key to your victory tonight`
- `—` → `well i guess that's`
- `first` → `key to your victory tonight the second`
- `really` → `—`
- `and` → `—`
- `saw` → `were in the philippines for`
- `lot of your country's flags and also` → `long time how did you feel when you came back`
- `do` → `did`
- `very` → `so`
- `and see you in the quarters` → `for your support`
- `everyone` → `—`
- `congratulations` → `thank you thank you so much`
