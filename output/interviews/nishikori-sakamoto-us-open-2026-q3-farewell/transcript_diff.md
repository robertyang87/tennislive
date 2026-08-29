# 转写交叉校验：nishikori-sakamoto-us-open-2026-q3-farewell

- 第一份：ASR（small.en） **524** 词
- 第二份：faster-whisper（medium.en）**510** 词
- **对不上 7.3%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `he went` → `and`
- `—` → `his talent`
- `i'm` → `—`
- `i mean` → `—`
- `rei` → `lei`
- `great` → `—`
- `was` → `—`
- `enjoying` → `enjoyed`
- `in` → `with`
- `pros` → `close`
- `final` → `time finals`
- `and` → `—`
- `—` → `this week i'm`
- `—` → `so`
- `this` → `in`
- `moment` → `moments`
- `one` → `a whole`
- `speaking in japanese kei thanks the fans for their support okay thank you so much once again but` → `sure`
- `butorac` → `buterac`
- `kei` → `kay`
- `we've worked` → `we get to work`
