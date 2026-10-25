# 转写交叉校验：rybakina-fernandez-ningbo-2026-f-speech

- 原声语言窗口（仅转写，不翻译）： [{"start": 5.6, "end": 20.4, "language": "en"}, {"start": 20.4, "end": 33.5, "language": "zh"}, {"start": 33.5, "end": 63.9, "language": "en"}, {"start": 63.9, "end": 94.6, "language": "zh"}, {"start": 94.6, "end": 121.45, "language": "en"}]
- 第一份：ASR（medium） **391** 词
- 第二份：faster-whisper（small）**401** 词
- **对不上 10.5%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（medium），右＝第二份）

- `please` → `—`
- `leylah` → `leila`
- `贺` → `賀`
- `对` → `對`
- `费 尔 南` → `吳 沛 爾 蘭`
- `宁` → `明`
- `赛 当` → `賽 當`
- `了` → `的`
- `艰 难` → `艱 難`
- `赛` → `賽`
- `团 队` → `團 隊`
- `来 剩 余` → `來 勝 於 戶 多`
- `的 赛` → `賽`
- `继 续` → `繼 續`
- `发 挥` → `發 揮`
- `现` → `現 then i would like`
- `stas` → `stars`
- `—` → `and`
- `—` → `a`
- `umpires` → `and powers`
- `ball boys` → `ballboys`
- `的` → `们`
- `事 方` → `世 芳`
- `事` → `世`
- `事` → `世`
- `事` → `世`
- `—` → `的`
- `宁` → `临`
- `and` → `then`
- `—` → `it's it's`
- `ningbo xie xie` → `ninguo thank you`
