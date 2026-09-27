# 转写交叉校验：ruud-cerundolo-laver-cup-2026-presser

- 第一份：ASR（small.en） **1028** 词
- 第二份：faster-whisper（medium.en）**1038** 词
- **对不上 3.6%**（闸门 12%）

⚠️ 上面两个词数和分歧率都是**去掉 erm/uh/uhh/um/umm 这类填词之后**算的：这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把「说话人有多磕巴」量成「两份转写对不上」。

## 分歧逐处（左＝ASR（small.en），右＝第二份）

- `casper` → `kasper`
- `casper` → `kasper`
- `one set` → `once said`
- `tiebreak` → `tiebreaker`
- `—` → `it`
- `returns` → `return`
- `forehands` → `fours`
- `casper` → `gasper`
- `—` → `and`
- `it` → `—`
- `match` → `boys and the team and it's not just about me out there`
- `can` → `could`
- `—` → `yeah`
- `cerundolo's` → `sarundalo's`
- `it` → `but`
- `cerundolo` → `sarundalo`
- `10 point` → `—`
- `laver` → `labour`
- `yannick` → `janik`
- `yannick` → `janik`
- `yannick` → `janik`
- `contrast` → `contrasts`
- `strength` → `strengths`
- `—` → `kind of`
- `they're` → `they`
- `it` → `—`
- `—` → `little`
- `—` → `so`
- `yannick` → `janik`
- `—` → `obviously`
- `casper` → `kasper`
- `these players play there aren't too many` → `sort of`
- `—` → `and`
- `match ups` → `matchups`
- `casper` → `kasper`
- `cerundolo` → `serundolo`
