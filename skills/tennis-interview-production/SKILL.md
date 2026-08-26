---
name: tennis-interview-production
description: Produce and audit the Chinese tennis post-match video series “赛后开麦” with DeepSeek for faithful bilingual copy and MiniMax for visual evidence. Use for on-court interviews and trophy-ceremony speeches, including source identity, subtitles, same-match lead-in, cover, takeaway, QC, PushPlus copy, and publication proof.
---

# 赛后开麦制作

把这套规则当作生产合同，不是写作风格建议。任何无法证明的项目都停在 waiting，
不得用模型自信、工作流绿灯或通用网球常识替代证据。

## 1. 先锁定产品与来源

- 正文只接受比赛结束后球场内的即时采访（`on_court`）或颁奖台致辞
  （`ceremony`）。新闻发布会、混采区、演播室、远程连线和来源不明均拒绝。
- 来源、比赛、轮次、受访者、赢家、对手必须指向同一场；认不准就停止。
- 优先使用官方单场集锦末尾自带的采访；若集锦没有采访，使用独立官方场上采访。
- 独立采访正文必须另配同一场官方集锦的获胜/赛点画面作开场；不能拿另一场凑。

## 2. DeepSeek 负责语言事实

读取 `references/deepseek.md`。英文原话与顺序是不可改写的证据层；中文、收尾和
推送文案只能建立在逐句转写、已核赛果与给定事实包上。模型不得补故事。

## 3. MiniMax 负责视觉事实

读取 `references/minimax.md`。模型必须对自己实际看到的帧给出人物、场景、同场、
封面、裁切、镜像与字幕可读性证据。看不清就是低置信度或 false。

## 4. 固定成片合同

- 画布为 1080×1440、3:4；保留英文原声，不用中文配音覆盖受访者。
- 正文英文与中文字幕逐条一一对应；不得合并、漏行或错位。
- 开场若来自同场集锦，保留现场原声并提供英文/中文字幕。
- 封面必须是本场正确人物，优先正面、睁眼、清晰、有采访/奖杯/赛事语境的帧。
- 收尾是“本条最值得记住的一点 + 与本场有关的问题”，不得用万能套话。

## 5. 通过顺序

严格按 `references/quality-gates.md` 从 L0 到 L4 执行。只有正式 spec、render、
QC、PushPlus 发送和 `pushed.json` 五阶段都有可核验证据，才可称为链路跑通。

## 6. 影子晋级

先在已发布的 `gauff-pegula-cin2026-final` 上复做，不改原 spec、不 render、不
dispatch、不发布。DeepSeek 至少 85 分、MiniMax 至少 90 分，且候选通过机械硬闸，
才有资格进入正式生产。学习结构和判断标准，禁止复制样片措辞到别的比赛。
