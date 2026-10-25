# 转写交叉校验：rybakina-fernandez-ningbo-2026-f-speech

- 第一份：ASR（medium.en） **293** 词
- 第二份：faster-whisper（small.en）**192** 词
- **对不上 38.9%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（medium.en），右＝第二份）

- `twice` → `choice`
- `say thank you to my team most of them back home watching supporting` → `—`
- `guys and thank you to stas` → `—`
- `—` → `and`
- `—` → `a`
- `visios ballboys` → `physios ball boys`
- `so` → `very`
- `really appreciate the opportunity to be back in china and to be able to join the team i really appreciate the opportunity to be here today i` → `—`
- `also` → `—`
- `say` → `—`
- `you to` → `—`
- `i really appreciate the opportunity to meet people who are very important to us and who are very important to us we are very proud of` → `well thank`
- `i hope you will join us we hope that you will join us we hope that you will be able to join our team and i hope that you will join us and` → `so much`
- `ningguo` → `nying washeshi`
