# 转写核对表：swiatek-rybakina-tor2026-final

源片 https://www.youtube.com/watch?v=bDttZof7qXI　采访段 373.8–415.0 秒（共 14 行）

| # | 片内 | 跳到源片 | 英文 | 中文 | 判据 |
|--:|:--|:--|:--|:--|:--|
| 1 | 0:00.5 | [▶](https://youtu.be/bDttZof7qXI?t=374) | sorry that I had to win the first title with you | 抱歉 拿下这第一冠时 你不在场 |  |
| 2 | 0:04.3 | [▶](https://youtu.be/bDttZof7qXI?t=378) | when you weren't here. | 你没能在现场 |  |
| 3 | 0:06.2 | [▶](https://youtu.be/bDttZof7qXI?t=380) | Um, and yeah, as I said, | 就像我刚才说的那样 |  |
| 4 | 0:08.1 | [▶](https://youtu.be/bDttZof7qXI?t=381) | I want to dedicate this title to everyone | 我想把这个冠军献给 |  |
| 5 | 0:10.8 | [▶](https://youtu.be/bDttZof7qXI?t=384) | who is dealing uh with unfair judgment | 每一个正在承受不公评判 |  |
| 6 | 0:13.6 | [▶](https://youtu.be/bDttZof7qXI?t=387) | and hate. | 和恶意的人 |  |
| 7 | 0:14.5 | [▶](https://youtu.be/bDttZof7qXI?t=388) | Um, just keep pushing, keep growing, | 继续努力 继续成长 |  |
| 8 | 0:17.3 | [▶](https://youtu.be/bDttZof7qXI?t=391) | keep focusing on yourself | 专注在自己身上 |  |
| 9 | 0:18.6 | [▶](https://youtu.be/bDttZof7qXI?t=392) | because you know what's the best | 因为你知道什么 |  |
| 10 | 0:19.8 | [▶](https://youtu.be/bDttZof7qXI?t=393) | for you and always | 才是对你最好 |  |
| 11 | 0:29.9 | [▶](https://youtu.be/bDttZof7qXI?t=403) | and always remember what's ahead | 永远记得前面 |  |
| 12 | 0:31.8 | [▶](https://youtu.be/bDttZof7qXI?t=405) | and um what's might be possible. | 还有什么是可能的 |  |
| 13 | 0:34.3 | [▶](https://youtu.be/bDttZof7qXI?t=408) | Um so yeah, here we are. | 好了 我们走到了这里 |  |
| 14 | 0:38.4 | [▶](https://youtu.be/bDttZof7qXI?t=412) | Thank you. | 谢谢 |  |

## 还欠着的

（无）

听完之后：改对的写进 `en_fixed`；听下来本来就对的写进 `suspect_ok`（值写一句为什么），别默默留着——**一个常年挂着的待办和没有待办长得一模一样**。

## 自动字幕的空档（≥2 秒连一个事件都没有）

- **27.2–29.9 秒**（片内，2.8 秒空白，[跳过去](https://youtu.be/bDttZof7qXI?t=400)）　不是漏词。查了本地raw caption（cap_bDttZof7qXI.en.json3）：393.99秒她说到『and always』，紧接394.96秒出现[cheering]、398.89秒[applause]（观众为『不公评判和恶意』那句鼓掌），下一条字幕事件403.68秒『and always remember what's ahead and um what's might be possible』完整衔接——第二份ASR听到的『remember』就是这条事件提前几百毫秒的边界效应，YouTube原字幕在gap结束的同一时刻已经把这句话完整接上了，zh第52-53行『永远记得前面 还有什么是可能的』覆盖的正是这句，不缺内容

打开源片听这几秒：**有人说话就是漏了**，掌声／欢呼就不是。结论写进 spec 的 `caption_gaps_ok`（键 `起-止`，秒，一位小数）。
