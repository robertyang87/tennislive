# 自动字幕的空档：rybakina-fernandez-ningbo-2026-f-speech

阈值 2 秒；空档 **26** 处。

第一份是 ASR（medium），第二份 ASR 是 `small`（多语模型）。**它什么都没听出来，不等于这几秒没人说话**——ASR 空词不能证明静音：可能没人说话、不是英语或该语言识别失败，需结合语言窗、VAD 和原声核对。

## 0.0–2.5 秒（片内，2.5 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=5）

- 键：`5.6-8.1`
- 第二份 ASR（small）：`have your champion speech. Hello`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 1.350s 人声，第二份 ASR（small）听到「have your champion speech. Hello」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 4.4–8.7 秒（片内，4.3 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=9）

- 键：`10.0-14.3`
- 第二份 ASR（small）：`want to congratulate Layla with a great week, a`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 3.640s 人声，第二份 ASR（small）听到「want to congratulate Layla with a great week, a」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 8.7–11.6 秒（片内，2.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=14）

- 键：`14.3-17.2`
- 第二份 ASR（small）：`lot of tough matches, tough wins, congrats to you and`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 2.160s 人声，第二份 ASR（small）听到「lot of tough matches, tough wins, congrats to you and」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 11.6–14.5 秒（片内，2.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=17）

- 键：`17.2-20.1`
- 第二份 ASR（small）：`your team and good luck for the rest of the`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 2.240s 人声，第二份 ASR（small）听到「your team and good luck for the rest of the」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 15.2–22.0 秒（片内，6.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=20）

- 键：`20.8-27.6`
- 第二份 ASR（small）：`我要 祝 賀 我的 對 手 吳 沛 爾 蘭 德 斯 在 明 波 的 比 賽 當 中 你 打 的 很多 很 精 彩 也 很 艱 難 的 比 賽`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 6.180s 人声，第二份 ASR（small）听到「我要 祝 賀 我的 對 手 吳 沛 爾 蘭 德 斯 在 明 波 的 比 賽 當 中 你 打 的 很多 很 精 彩 也 很 艱 難 的 比 賽」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 22.0–28.7 秒（片内，6.7 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=27）

- 键：`27.6-34.3`
- 第二份 ASR（small）：`希望 你 跟 你的 團 隊 在 接下來 勝 於 不多 的 賽 季 繼續 有 出 色 的 發 揮 精 彩 的 表 現`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

## 28.7–32.3 秒（片内，3.5 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=34）

- 键：`34.3-37.9`
- 第二份 ASR（small）：`Then I would like to say`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 0.554s 人声，第二份 ASR（small）听到「Then I would like to say」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 34.2–37.3 秒（片内，3.1 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=39）

- 键：`39.8-42.9`
- 第二份 ASR（small）：`of them back home watching supporting Thank you so much`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 2.380s 人声，第二份 ASR（small）听到「of them back home watching supporting Thank you so much」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 37.3–40.7 秒（片内，3.4 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=42）

- 键：`42.9-46.3`
- 第二份 ASR（small）：`guys, and thank you to stars for staying with me`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 2.720s 人声，第二份 ASR（small）听到「guys, and thank you to stars for staying with me」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 40.7–44.3 秒（片内，3.6 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=46）

- 键：`46.3-49.9`
- 第二份 ASR（small）：`this week and Supporting each match and of`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 2.880s 人声，第二份 ASR（small）听到「this week and Supporting each match and of」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 46.9–50.2 秒（片内，3.3 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=52）

- 键：`52.5-55.8`
- 第二份 ASR（small）：`this tournament possible Laura`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 2.580s 人声，第二份 ASR（small）听到「this tournament possible Laura」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 50.2–53.8 秒（片内，3.6 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=55）

- 键：`55.8-59.4`
- 第二份 ASR（small）：`for always taking such a good care of us chair empires`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 2.880s 人声，第二份 ASR（small）听到「for always taking such a good care of us chair empires」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 56.9–59.0 秒（片内，2.1 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=62）

- 键：`62.5-64.6`
- 第二份 ASR（small）：`you so much guys 同`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

## 59.0–61.1 秒（片内，2.1 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=64）

- 键：`64.6-66.7`
- 第二份 ASR（small）：`时 我要 感 谢 我的 团 队 很多`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 1.360s 人声，第二份 ASR（small）听到「时 我要 感 谢 我的 团 队 很多」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 61.1–63.2 秒（片内，2.2 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=66）

- 键：`66.7-68.8`
- 第二份 ASR（small）：`的 成 员 其实 是 在 家 乡 正`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 1.460s 人声，第二份 ASR（small）听到「的 成 员 其实 是 在 家 乡 正」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 66.1–68.4 秒（片内，2.3 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=71）

- 键：`71.7-74.0`
- 第二份 ASR（small）：`还有 在 现 场 我们 团 队 的 成 员 我的`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 1.600s 人声，第二份 ASR（small）听到「还有 在 现 场 我们 团 队 的 成 员 我的」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 68.4–70.6 秒（片内，2.2 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=73）

- 键：`74.0-76.2`
- 第二份 ASR（small）：`教 练 对 于 我 这 一 周 的 信 任 我要`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 1.540s 人声，第二份 ASR（small）听到「教 练 对 于 我 这 一 周 的 信 任 我要」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 76.0–78.1 秒（片内，2.0 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=81）

- 键：`81.6-83.7`
- 第二份 ASR（small）：`彩 的 表 现 的 付 出 同`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：字幕时间轴自动销账：VAD 测到 1.340s 人声，第二份 ASR（small）听到「彩 的 表 现 的 付 出 同」——成品字幕相邻两行的时间轴已经盖住这段空档的核心区，按字幕时间轴销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 84.3–89.2 秒（片内，4.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=89）

- 键：`89.9-94.8`
- 第二份 ASR（small）：`次 感 谢 大家 Then`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：**否**

## 89.2–94.1 秒（片内，4.9 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=94）

- 键：`94.8-99.7`
- 第二份 ASR（small）：`of course, thank you to my family friends sponsors and`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 4.200s 人声，第二份 ASR（small）听到「of course, thank you to my family friends sponsors and」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 94.1–96.7 秒（片内，2.6 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=99）

- 键：`99.7-102.3`
- 第二份 ASR（small）：`all of you guys Thank you so much for an`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 1.920s 人声，第二份 ASR（small）听到「all of you guys Thank you so much for an」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 96.7–98.7 秒（片内，2.1 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=102）

- 键：`102.3-104.3`
- 第二份 ASR（small）：`amazing atmosphere every day.`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 1.360s 人声，第二份 ASR（small）听到「amazing atmosphere every day.」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 98.7–100.8 秒（片内，2.1 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=104）

- 键：`104.3-106.4`
- 第二份 ASR（small）：`It's It's`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 1.106s 人声，第二份 ASR（small）听到「It's It's」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 100.8–103.5 秒（片内，2.6 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=106）

- 键：`106.4-109.1`
- 第二份 ASR（small）：`it's amazing to play in front of you always gives a`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 1.940s 人声，第二份 ASR（small）听到「it's amazing to play in front of you always gives a」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 106.3–108.8 秒（片内，2.6 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=111）

- 键：`111.9-114.4`
- 第二份 ASR（small）：`keep on playing and it's already a second year here`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 1.880s 人声，第二份 ASR（small）听到「keep on playing and it's already a second year here」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

## 108.8–111.9 秒（片内，3.0 秒；源片 https://youtu.be/0XhJ4hqRRYA?t=114）

- 键：`114.4-117.5`
- 第二份 ASR（small）：`second win and it's such a special place for me`　→ **第一份（ASR（medium））可能漏了原文或发生时间边界漂移，核对 `en_fixed`**
- 已销账：双 ASR 自动销账：VAD 测到 2.340s 人声，第二份 ASR（small）听到「second win and it's such a special place for me」——这些词已按原顺序出现在前后 8 秒的成品字幕里，是两套时间码的边界漂移、不是漏了，按双 ASR 销账（不是 VAD 证明没人说话）（证据 gap_vad_attestation.json）

