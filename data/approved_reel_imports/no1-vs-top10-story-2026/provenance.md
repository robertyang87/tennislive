# 《世界第一的及格线？》自有制作线成品母带导入说明

- 栏目：网球有故事（story_kind=other，规则/机制题）。片名《世界第一的及格线？》，台头 topic「27 年里第一个对前十输多赢少的年终第一」。
- 母带在自有制作线完成（本地代码渲染，非 tennislive 原生渲染器）：分镜/图卡照 tennislive 仓库 design_tokens DARK 定版与 explainer 台头复刻（用户 2026-11-27 四轮返工后定版），旁白为本地 edge-tts 通道 zh-CN-XiaoxiaoNeural +0% 实际合成，原声两段为兹维列夫上海采访（源 KlSx2iN2c4I）逐字双语字幕。
- 事实口径：2000—2026 共 27 个年终第一对前十战绩（比赛当时排名、退赛计入、walkover 不计、拉沃尔杯除外），主源 Tennis-DB Research 2026-11-01 历年表并与 ATP Win/Loss Index 逐行互证；兹维列夫 2026 全季 7 胜 10 负（41.2%）为 27 年里唯一低于五成者（FACT-CHECK 已存档于制作工作区）。
- 本地已跑通管线同款检查：push_reel --stage check 通过（标题「11.27网球有故事|世界第一的及格线？」）；check_reel_landed 0 项不合格并签 qc_attestation；foreground_audio_gate 逐段审听证据（双路 ASR 交叉核对）已入 data/audio_reviews/no1-vs-top10-story-2026*；配音库存 voice_quality_inventory.json 已捕获（实际冻结 TTS 小包 33 条）。
- v3 修音（2026-11-27，所有者裁决 B 路）：v2 首推被自动听审闸拦下（PushPlus 未调用、账本 attempt 已按日志证据改判 not_sent）；判红 6 处（数字短语内停顿 5 处＋第 20/21 段整句被拆）经查均为词边界对齐漂移伪影，修法只动合成侧（同文本重合成、三段按句界拼合、第 20/21 段合并为一整句单次合成、两处朗读标点微调），display 锁稿一字未动，其余 28 段音频逐字节不变；v3 母带 252.80s / sha256 4607e9df…，本地全套自动听审预检五项全过，assemble 脚本 assemble_v3.py。
- v4 四处定规修改（2026-11-27，所有者看过 v3 已推版后下达并明确批准重推）：①旁白全片换云健 zh-CN-YunjianNeural +0% 重合成（v3 误用晓晓；原声两段不动；合成侧处置 2 条——6-06 数字短语内两处真停顿、2-04 头尾死静音，均只在波形上收窄异常静音，口播词句与锁稿逐词一致）；②右上字卡删来源注、只留章节标（来源只记制作文档/素材库）；③底部字幕带删分割线（像素核查 v3 同行签名 1.000 → v4 全片 max 0.154）；④全片去掉背景音乐，只留旁白＋原声＋现场声，响度以 loudnorm 两遍重新归一到与 v3 相同口径（成品实测 −19.7 LUFS / TP −6.0）。画面素材/窗口/切点/台头/封面与 v3 一致；v4 母带 252.33s / 112,716,323 B / sha256 3894ff0c…。账本里 v3 的 sent attempt（4607e9df…，PushPlus ade3160463a049dcbf9b2327ec2c3f67）为上一母带的历史投递记录，逐字保留；本次为第二次推送。
- 导入后由 import-approved-no1-top10 工作流重组母带验 sha、复跑原生 QC、建 Release 并过 auto_push_gate 后 dispatch match-reel push。
