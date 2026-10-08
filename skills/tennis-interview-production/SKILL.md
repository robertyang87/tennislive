---
name: tennis-interview-production
description: Produce and audit the Chinese tennis post-match video series “赛后开麦”: DeepSeek translates faithful bilingual subtitles, deterministic gates own cover and QC, and MiniMax runs only in the shadow benchmark. Use for on-court interviews, trophy-ceremony speeches, farewells and walk-ons, and for hand-written press conferences and broadcaster interviews, including source identity, subtitles, same-match lead-in, cover, takeaway, QC, PushPlus copy, and publication proof.
---

# 赛后开麦制作

把这套规则当作生产合同，不是写作风格建议。任何无法证明的项目都停在 waiting，
不得用模型自信、工作流绿灯或通用网球常识替代证据。

## 1. 先锁定产品与来源

- L0 认七种内容（`tools/interview_source_gate.py` 的 `REQUESTED_KINDS`）：赛后场上采访
  （`on_court`）、颁奖台致辞（`ceremony`）、告别仪式（`farewell`）、赛前出场秀
  （`walk_on`）——这四种自动链的来源验证认得出；赛后捧杯时刻（`trophy_moment`）
  是转播解说压在真实捧杯画面上，必须人工看过同场冠军和奖杯同框，不冒充球员致辞，
  自动链的标题发现认不出它，冷开场也不因此豁免；赛后新闻发布会（`press_conference`）和
  赛场里的转播商专访（`broadcaster_interview`）**只由人手写 spec 用**，自动链的来源验证
  永远判不出这两种。混采区、演播台对坐、远程连线、第三方台标的独家采访和来源不明的
  一律拒绝。
- 来源、比赛、轮次、受访者、赢家、对手必须指向同一场；认不准就停止。
- 优先使用官方单场集锦末尾自带的采访；若集锦没有采访，使用独立官方场上采访。
- 独立采访正文必须另配同一场官方集锦的获胜/赛点画面作开场；不能拿另一场凑。

## 2. DeepSeek 负责语言事实

读取 `references/deepseek.md`。英文原话与顺序是不可改写的证据层；中文、收尾和
推送文案只能建立在逐句转写、已核赛果与给定事实包上。模型不得补故事。

## 3. 视觉事实：生产链走确定性闸，MiniMax 只在影子基准里

2026-08-30 费德勒名人堂事故复盘之后，生产链的封面与画面判断不再交给外部模型：
封面走 `tools/audit_interview_cover.py`（`interview-clip.yml` 里跑）加人／会话终审。
`references/minimax.md` 只在影子基准 `tools/benchmark_interview_models.py` 里用——
标准照旧是那一份：模型必须对自己实际看到的帧给出人物、场景、同场、封面、裁切、
镜像与字幕可读性证据，看不清就是低置信度或 false。

## 4. 固定成片合同

- 画布为 1080×1440、3:4；保留英文原声，不用中文配音覆盖受访者。
- 正文英文与中文字幕逐条一一对应；不得合并、漏行或错位。
- 保留原视频的主要内容，不设时长上限、不挖金句（账号所有者 2026-08-08「要保证
  原始内容的完整性啊」）。
- 场上采访先用 10–20 秒同场冷开场交代比赛结束（赛点 → 庆祝 → 解说交代赛果），
  发布会和致辞不接冷开场；开场保留现场原声并提供英文/中文字幕。
- 封面必须是本场正确人物，优先正面、睁眼、清晰、有采访/奖杯/赛事语境的帧。
- 收尾是“本条最值得记住的一点 + 与本场有关的问题”，不得用万能套话；问题往积极的
  方向落——请读者期待他兑现，不请读者怀疑他。

## 5. 通过顺序

严格按 `references/quality-gates.md` 从 L0 到 L4 执行。只有正式 spec、render、
QC、PushPlus 发送和 `pushed.json` 五阶段都有可核验证据，才可称为链路跑通。

## 6. 账号所有者的口味

标题、收尾卡、封面帧的被否／被选对照写在 `references/deepseek.md` 和
`references/minimax.md` 各自的「账号所有者的口味」一节；全部口味规则在
`.claude/skills/tennis-owner-taste/SKILL.md`。

## 7. 影子晋级

先在已发布的 `gauff-pegula-cin2026-final` 上复做，不改原 spec、不 render、不
dispatch、不发布。DeepSeek 至少 85 分、MiniMax 至少 90 分，且候选通过机械硬闸，
才有资格进入正式生产。学习结构和判断标准，禁止复制样片措辞到别的比赛。
