# 《世界第一的及格线？》自有制作线成品母带导入说明

- 栏目：网球有故事（story_kind=other，规则/机制题）。片名《世界第一的及格线？》，台头 topic「27 年里第一个对前十输多赢少的年终第一」。
- 母带在自有制作线完成（本地代码渲染，非 tennislive 原生渲染器）：分镜/图卡照 tennislive 仓库 design_tokens DARK 定版与 explainer 台头复刻（用户 2026-11-27 四轮返工后定版），旁白为本地 edge-tts 通道 zh-CN-XiaoxiaoNeural +0% 实际合成，原声两段为兹维列夫上海采访（源 KlSx2iN2c4I）逐字双语字幕。
- 事实口径：2000—2026 共 27 个年终第一对前十战绩（比赛当时排名、退赛计入、walkover 不计、拉沃尔杯除外），主源 Tennis-DB Research 2026-11-01 历年表并与 ATP Win/Loss Index 逐行互证；兹维列夫 2026 全季 7 胜 10 负（41.2%）为 27 年里唯一低于五成者（FACT-CHECK 已存档于制作工作区）。
- 本地已跑通管线同款检查：push_reel --stage check 通过（标题「11.27网球有故事|世界第一的及格线？」）；check_reel_landed 0 项不合格并签 qc_attestation；foreground_audio_gate 逐段审听证据（双路 ASR 交叉核对）已入 data/audio_reviews/no1-vs-top10-story-2026*；配音库存 voice_quality_inventory.json 已捕获（实际冻结 TTS 小包 34 条）。
- 导入后由 import-approved-no1-top10 工作流重组母带验 sha、复跑原生 QC、建 Release 并过 auto_push_gate 后 dispatch match-reel push。
