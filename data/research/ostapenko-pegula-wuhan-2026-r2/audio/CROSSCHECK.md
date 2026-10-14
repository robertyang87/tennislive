# 当前官方源音频转写交叉核验

两个独立本地英文模型已完整转写0–303秒。真实模型为base.en/small.en，CPU int8各3线程；language=en、beam_size=8、vad_filter=False、word_timestamps=True、无prompt。原始识别未改写，全文和词时间分别保存在base.json/small.json。

源SHA256：`301dd05c374b11e55f35b09da4ba8066cbb14546c1242a1975331a105931c847`。实际解码时长309.5684375秒。未声称人工听审；现有captions也是自动字幕，不视为人工真值。

姓名只按真实双方身份规范为Jelena Ostapenko / Jess Pegula。第一盘6–2在佩古拉视角；结尾2–6、7–6、6–3在奥斯塔彭科视角。第二盘三个赛点错失者是佩古拉。抢七小分(7)不由此ASR确认。

| 保守源区间（秒） | 完整英文／忠实中文 | 核验覆盖 |
|---|---|---|
| 39.36–45.28 | A bit of punch and a bit of finesse from Ostapenko.<br>奥斯塔彭科既有力量，也有细腻的处理。 | small+captions; base phrase partial |
| 47.12–48.48 | First serve, set point.<br>一发，盘点。 | small+captions; base omitted |
| 52.52–56.08 | Set point gobbled up by Jess Pegula.<br>杰斯·佩古拉轻松拿下盘点。 | small+captions; base omitted |
| 56.14–61.98 | Frustration for Jelena Ostapenko, who hasn't quite hit the heights in the opening set here.<br>奥斯塔彭科很懊恼，她在首盘还没打出应有的水准。 | small+captions; base only tail fragment |
| 62.50–68.68 | Seamless from the American, the world number four in business here, six-two in just over half an hour.<br>美国选手打得行云流水，世界第四此刻掌控局面，半小时出头就以六比二拿下首盘。 | base+small+captions |
| 69.76–72.62 | So it's a big task facing Ostapenko here.<br>所以，奥斯塔彭科此刻面临着艰巨的任务。 | base+small+captions |
| 80.68–82.96 | There's another example, though, of her firepower.<br>不过，这又一次展示了她的火力。 | base+small+captions |
| 92.78–96.76 | Pegula did well to jam the return back, but she was always on the back foot.<br>佩古拉已经很好地把接发球挡了回去，但她始终处在被动之中。 | base+small+captions |
| 105.70–109.12 | Found the gap. Good pass from Ostapenko.<br>找到空当了，奥斯塔彭科打出漂亮的穿越。 | base+small+captions |
| 123.70–125.44 | Is there going to be another twist?<br>还会再有转折吗？ | base+small+captions |
| 125.44–129.48 | That's bone-rattling pace from Ostapenko.<br>奥斯塔彭科这一拍快得震人。 | small+captions; base omitted |
| 164.40–168.58 | Well, what can you do when Ostapenko plays like that?<br>奥斯塔彭科打成这样，你还能有什么办法？ | base+small+captions |
| 185.22–187.58 | That is unreal.<br>太不可思议了。 | base+small+captions |
| 200.18–204.56 | Oh, this is thunderous tennis.<br>这网球打得震天响。 | base+small+captions |
| 211.90–217.24 | Incredible. Absolutely incredible. And on we go in Wuhan.<br>不可思议。实在不可思议。武汉这场比赛还在继续。 | base+small+captions |
| 264.84–267.98 | Ostapenko packs a power punch in Wuhan.<br>奥斯塔彭科在武汉打出强劲一击。 | small+captions; base omitted |
| 268.78–275.58 | A dazzling attacking performance from one of the biggest hitters in the game, as she picks Pegula apart.<br>网坛火力最强的球员之一，打出耀眼的进攻表现，一点点拆解佩古拉。 | small+captions; base omitted |
| 277.04–278.38 | The second seed is stunned.<br>二号种子被打懵了。 | small+captions; base omitted |
| 279.22–284.00 | She missed three match points in the second set, and they proved so costly.<br>她在第二盘错失了三个赛点，而这让她付出了沉重代价。 | small+captions; base agrees only final they proved so costly |
| 285.40–290.52 | Ostapenko: too powerful, too potent, too good.<br>奥斯塔彭科：力量太强，威力太猛，打得太好了。 | small+captions; base omitted |
| 291.16–297.84 | And into the round of 16 from a set down: two-six, seven-six, six-three.<br>先丢一盘后逆转晋级十六强：二比六、七比六、六比三。 | small+captions; base omitted |
| 297.84–298.96 | What a performance.<br>多么精彩的表现！ | small+captions; base omitted |

上述时间是保守ASR词边界，不等于已听核的精准声学起止；crowd/静音间隔可能被分给句首词。That185.22–186.62、Oh200.18–201.58、初始A39.36–40.10等都有宽边界，剪辑前按视频片段实际完整性检查。

## 不确定或排除

- [15.12, 26.64]：backhand commentary name/word corruption and long interval bridging between two rallies。Can normalize player name to Ostapenko from identity, but do not treat merged15–26 interval as one continuous complete utterance. Backhand lexical restoration is plausible/caption-supported but ASR phoneme spelling weak.
- [146.12, 153.1]：First-serve-percentage subject conflicts。Do not claim subject verified: both ASR models name Pegula in the statistic sentence while captions attach Ostapenko. Neither identity nor statistic ownership can be silently corrected from task facts. Exclude exact quotation until resolved by additional evidence.
- [220.84, 223.02]：has/was lit a fire auxiliary and subject conflict。Likely intended Jelena Ostapenko has lit a fire, but exact auxiliary not independently agreed; avoid verbatim assertion. Name identity correction only, no automatic replacement of base subject.
- [239.38, 245.5]：Nice cushion volley ... previously is retrospective/deictic, word timing extends。Do not assert commentary describes the currently shown contact without visual matching. Conservative ASR window includes substantial gap, not precise acoustic offset.
- [252.08, 256.88]：play/plate and trailing boundary unreliable。play is base+caption-supported lexical correction. Small assigns of253.50–256.80 and plate256.80–256.88; exact end unsafe. Prefer other clean complete sentences for source-backed clips.

base共17段，small共32段。base在264–299秒大量漏识，结尾主要依据small＋captions，未冒称两个模型完整一致。每条原文、词时间、概率、具体分歧及来源hash见crosscheck.json。
