# 转写交叉校验：zheng-liutova-us-open-2026-r1-interview

- 第一份：ASR（small.en） **465** 词
- 第二份：faster-whisper（medium.en）**459** 词
- **对不上 8.2%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `qinwen` → `—`
- `congratulation` → `congratulations`
- `play` → `played`
- `congratulation` → `congratulations`
- `and second i mean` → `—`
- `—` → `a`
- `consistent` → `consistency`
- `what` → `—`
- `what's happen` → `what happens`
- `cuz` → `because`
- `say` → `said`
- `—` → `actually`
- `was` → `—`
- `i` → `—`
- `can` → `could`
- `it's` → `—`
- `well` → `wow`
- `it` → `it's`
- `cuz` → `because`
- `quarterfinal is` → `quarterfinals`
- `us` → `the u s`
- `and` → `—`
- `play` → `playing`
- `—` → `i`
- `cuz really means` → `miss`
- `—` → `i mean`
- `qinwen` → `kin wen`
- `qualies` → `quality`
- `visit` → `visiting`
- `—` → `a`
- `really` → `—`
- `all the girl knows` → `other girls know`
- `—` → `a`
- `yeah` → `—`
