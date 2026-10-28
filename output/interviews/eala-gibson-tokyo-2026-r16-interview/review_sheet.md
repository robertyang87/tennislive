# 转写核对表：eala-gibson-tokyo-2026-r16-interview

源片 https://github.com/robertyang87/tennislive/releases/download/src-eala-tokyo-20261028/eala-tokyo-r16-interview-fbcopy.mp4　采访段 0.0–93.0 秒（共 21 行）

| # | 片内 | 跳到源片 | 英文 | 中文 | 判据 |
|--:|:--|:--|:--|:--|:--|
| 1 | 0:16.0 | 片内 16.0 秒 | I think really staying | 我觉得 |  |
| 2 | 0:21.4 | 片内 21.4 秒 | in the match never giving up. | 留在比赛里，永不放弃 |  |
| 3 | 0:23.6 | 片内 23.6 秒 | The first set was difficult | 第一盘确实很难 |  |
| 4 | 0:25.2 | 片内 25.2 秒 | and I had my chances so I knew | 但我也有过机会，所以我知道 |  |
| 5 | 0:27.8 | 片内 27.8 秒 | that if I kept my concentration I would have | 只要我保持专注 |  |
| 6 | 0:30.8 | 片内 30.8 秒 | more chances. | 机会还会再来 |  |
| 7 | 0:37.1 | 片内 37.1 秒 | The first set was really difficult | 第一盘真的很难打 |  |
| 8 | 0:39.3 | 片内 39.3 秒 | and I had my chances so I knew | 我也有过机会，我知道 |  |
| 9 | 0:42.2 | 片内 42.2 秒 | that if I kept my concentration I would have | 只要我保持专注 |  |
| 10 | 0:45.0 | 片内 45.0 秒 | more chances. | 机会还会再来 |  |
| 11 | 0:57.5 | 片内 57.5 秒 | And you saw a lot of your country's flags | 现场有很多你们的国旗 |  |
| 12 | 1:00.7 | 片内 60.7 秒 | and also the crowd was really rooting | 而且观众一直在为你 |  |
| 13 | 1:03.5 | 片内 63.5 秒 | for you. | 加油助威 |  |
| 14 | 1:04.3 | 片内 64.3 秒 | How do you like that? | 感觉怎么样？ |  |
| 15 | 1:05.5 | 片内 65.5 秒 | Thank you so much everybody. | 非常感谢大家 |  |
| 16 | 1:13.1 | 片内 73.1 秒 | Thank you very much and see you | 非常感谢 |  |
| 17 | 1:19.3 | 片内 79.3 秒 | in the quarters. | 四分之一决赛见 |  |
| 18 | 1:20.1 | 片内 80.1 秒 | Thank you very much everyone. | 非常感谢大家 |  |
| 19 | 1:24.7 | 片内 84.7 秒 | Best of luck on your next match too. | 也祝你下场好运 |  |
| 20 | 1:28.1 | 片内 88.1 秒 | Thank you so much. | 非常感谢 |  |
| 21 | 1:29.3 | 片内 89.3 秒 | Congratulations. | 恭喜你 |  |

## 还欠着的

（无）

听完之后：改对的写进 `en_fixed`；听下来本来就对的写进 `suspect_ok`（值写一句为什么），别默默留着——**一个常年挂着的待办和没有待办长得一模一样**。

## 自动字幕的空档（≥2 秒连一个事件都没有）

- **31.6–37.1 秒**（片内，5.5 秒空白，片内 31.6 秒）　已听核：此段为日语同传（第一答尾巴的日译）加掌声，英文模型误听为 “Well, I guess that's the key to your victory tonight.”；英文原答及其原样重复已由前后字幕行覆盖。所有者 2026-10-29 拍板日语段留空、不补字幕，故销账。
- **46.1–57.5 秒**（片内，11.4 秒空白，片内 46.1 秒）　已听核：此段为日语第二问的场馆 PA 同传（菲律宾国旗与声援内容，与其后 57.5s 起的英文第二问同内容），英文模型误听为菲律宾句；所有者 2026-10-29 拍板日语段留空、不补字幕，英文第二问与第二答已完整成行，故销账。
- **66.6–69.9 秒**（片内，3.3 秒空白，片内 66.6 秒）　字幕时间轴自动销账：VAD 测到 0.000s 人声，第二份 ASR（medium.en）没听出词——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

打开源片听这几秒：**有人说话就是漏了**，掌声／欢呼就不是。结论写进 spec 的 `caption_gaps_ok`（键 `起-止`，秒，一位小数）。
