# 转写交叉校验：nadal-academy-10th-2026-championship-speech

- 原声语言窗口（仅转写，不翻译）： [{"start": 0.0, "end": 51.0, "language": "en"}, {"start": 51.0, "end": 61.0, "language": "ca"}, {"start": 61.0, "end": 67.0, "language": "en"}, {"start": 67.0, "end": 120.0, "language": "ca"}, {"start": 120.0, "end": 132.5, "language": "en"}, {"start": 132.5, "end": 172.6, "language": "es"}, {"start": 172.6, "end": 177.145034, "language": "en"}]
- 第一份：ASR（small） **428** 词
- 第二份：faster-whisper（large-v3-turbo）**447** 词
- **对不上 5.1%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small），右＝第二份）

- `well` → `andy`
- `a` → `—`
- `—` → `there`
- `slam` → `of islam`
- `—` → `let's`
- `—` → `but`
- `—` → `in in in`
- `of` → `—`
- `—` → `to`
- `—` → `with`
- `vull donar ses` → `volem ser`
- `unclear` → `me 'ls`
- `d'avui` → `d 'avui`
- `unclear` → `l 'apolla`
- `manacor` → `manacó`
- `això` → `a jo`
- `d'aquest` → `d 'aquest`
- `—` → `a`
- `l'ajuda` → `l 'ajuda`
- `l'altre` → `l 'altre`
- `s'està` → `s 'està`
- `d'aquest` → `d 'aquest`
- `—` → `així que`
- `tot` → `—`
- `suport` → `aport`
- `and` → `in`
- `—` → `bueno`
- `bonito` → `bueno o`
- `—` → `que`
- `y` → `—`
