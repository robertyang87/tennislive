# 本片声学复核证据

实际声线：zh-CN-YunjianNeural；语速：+6%。完整段落音频 22 段，枚举并运行 121 个多音字位置。

结果：{'uncertain': 7, 'correct': 48, 'skipped': 46, 'unreliable': 20}。未出现明确 misread，但这不等于全部读对。uncertain、unreliable、skipped 全部待核，未作人工听审。

方法：现有 measure_polyphone 的 MFCC、DTW、F0 与参考字留一自测，输入完整的生产 speakable 段落。每位置对比一个常见异读，其余异读记录为未测；一、不常规变调以及数字、字母、专名的整体听辨没有借此声称通过。参考不足的轻声、罕见音仍为 skipped。

每个 target-NNN.json 有完整上下文、目标音、对照音、原始分数、自测、F0、音频路径。参考音频已复制到本目录 references/，整段原音与 WordBoundary 位于本目录。

封面替代表达已另生成实际音频：`cover-candidate/speech.mp3`。文本：险些无缘资格赛。他却拿走上海冠军。格 ge2 与冠 guan4 在3参考字对照中返回 correct；未人工听审，不作整句通过声明。

## 待核的非 skipped 位置

| 位置 | 上下文 | 目标音 | 结果 | 分数 |
|---|---|---|---|---|
| target-001 封面 | 差点没进资格赛 | cha4 | uncertain | 0.054 |
| target-011 第 3 段 | 十七，温网资格赛又摔伤退赛 | ge2 | unreliable | 0.547 |
| target-016 第 5 段 | 拿到位置，还要守住。资格赛 | yao4 | unreliable | 0.094 |
| target-017 第 5 段 | 还要守住。资格赛第一轮，先 | ge2 | uncertain | 0.176 |
| target-027 第 6 段 | 球，他打出对角制胜，再靠发 | jiao3 | uncertain | 0.071 |
| target-034 第 7 段 | 这一路反复遇见的关口。 | jian4 | unreliable | 1.000 |
| target-038 第 9 段 | 对格里克斯普尔， | ge2 | unreliable | 0.349 |
| target-046 第 10 段 | 最后一局，他还要救下两个破 | hai2 | unreliable | 0.768 |
| target-047 第 10 段 | 后一局，他还要救下两个破发 | yao4 | unreliable | 0.076 |
| target-062 第 15 段 | 克内希。他们曾是大学队友。 | ceng2 | unreliable | 0.240 |
| target-065 第 15 段 | 谁赢，这个家都会有一个大师 | dou1 | unreliable | 0.264 |
| target-066 第 15 段 | 赢，这个家都会有一个大师赛 | hui4 | unreliable | 0.452 |
| target-072 第 16 段 | 缩他的反应时间。四比六，又 | jian1 | unreliable | 0.483 |
| target-073 第 16 段 | 。四比六，又落后了。第二盘 | luo4 | uncertain | 0.016 |
| target-076 第 16 段 | 比三，瓦舍罗把表哥压在底线 | ba3 | unreliable | -0.034 |
| target-080 第 16 段 | 表哥发球局，把领先守到终点 | ba3 | unreliable | 0.573 |
| target-097 第 22 段 | 之后，他才在格施塔德复出。 | ge2 | unreliable | 0.163 |
| target-098 第 23 段 | 九月，成都头号种子，首 | du1 | unreliable | 0.552 |
| target-100 第 23 段 | 月，成都头号种子，首战就输 | zhong3 | uncertain | 0.097 |
| target-103 第 23 段 | 输给资格赛球员哈里斯。随后 | yuan2 | unreliable | 0.498 |
| target-109 第 24 段 | ，他以十七号种子的身份回到 | zhong3 | uncertain | 0.067 |
| target-111 第 24 段 | 置，比赛，仍要一场场打。 | yao4 | unreliable | 0.822 |
| target-112 第 24 段 | 比赛，仍要一场场打。 | chang3 | unreliable | -0.140 |
| target-113 第 24 段 | 赛，仍要一场场打。 | chang3 | unreliable | -0.038 |
| target-119 片尾 | 关注网球时差，时差归我， | cha1 | unreliable | 0.129 |
| target-120 片尾 | 网球时差，时差归我，好球归 | cha1 | unreliable | 0.551 |
| target-121 片尾 | ，时差归我，好球归你。 | hao3 | uncertain | 0.108 |

## 可考虑的文案改写

- 封面“差点没进资格赛”可改“险些无缘资格赛”；候选已实际合成，相关格/冠对照结果保存在 candidate.json。
- “拿到位置，还要守住。资格赛第一轮……”可改“第一轮，他先输抢七，随后连追两盘……”；减少还/要相邻的切词歧义，改后仍须重新合成核验。
- “对角制胜”可改“斜线制胜”；事实保持对角接发制胜，改后重测。
- “一场场打”可改“每场都从头打”；这是避开连续场字变调的备选，不代表原句错读，改后重测。
- 片尾品牌原文“关注网球时差，时差归我，好球归你。”未改变。2个差与好在本轮分别unreliable/unreliable/uncertain；应实际听辨完整音频与对照，不凭汉字ASR确认声调，也不为通过改固定品牌词。

## 最终文本绑定

截至写报告，发生 5 个段落文本变化。变化段落需要重新合成/复核，旧结果不能认领新句。

未填写任何 approved 或 pass。
