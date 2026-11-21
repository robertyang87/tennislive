# tennis-money-story-2026 落地包来源与状态

- 成片（v5）：final_tennis_money_story_v5.mp4（1080×1440，697.609s，220,212,799 B，
  sha256 a269948e3a1f1d21fb022e583aa835b249394b2a400e84d06166ec5b1afa708e）；
  封面 poster.jpg 为定版封面原件
  （sha256 a4a1378a7877250919ae0f49563b5882f1a9591ff8ab62069c6802d87eed38b4），
  成片第一页即该封面静帧 2.0 秒。
- v5 与 v4 的唯一差异：两段原声（第 34 段丹尼尔太郎播客 298.465–342.965、
  第 45 段乔娃林斯卡法网发布会 416.422–454.422）的烧录字幕由中文提要式（3＋4 条）
  改为逐句双语字幕（10 句，EN 原文＋ZH 译文，逐字取自审听包，字幕窗按句子
  毫秒级切分）。其余镜头画面与 v4 逐字节同源（非原声段抽帧与 v4 像素级一致），
  音轨与 v4 解码后逐字节一致（decoded audio SHA-256
  5ab1a2bfe451c42011911f73e6e96fe3b61f1aab5b5d0df1c669ae96edef71c2），
  总时长不变。v4 原文件保留未动。账号所有者 2026-11-21 批准出 v5 并推送。
- 制作：自有制作线（tennis-money-story-2026/build，build_v5.py＋assemble_v5.py），
  非原生渲染器；spec 按 laver-cup-history-2026 先例以母带自身为 source
  `approved_master` 建模，68 段为母带连续跨度；旁白 edge-tts
  zh-CN-XiaoxiaoNeural，锁稿见仓外 SCRIPT.md（65 行，逐行事实标注）。
- 人工 QC：真实做过——QC_RECORD.md 及 v2/v3/v4 逐项修正与抽帧记录在案
  （字幕断行锁定表、字形审计、左上标题块与封面逐像素对齐、封面页 60 帧整接等）；
  v5 双语字幕抽帧自检在仓外 frames_v5/（两段原声各帧双语完整可读、无溢出）。
- 审听：对母带本体执行（data/audio_reviews/tennis-money-story-2026*）：
  faster-whisper small 全片 zh 一遍＋F00/OA1/OA2 窗口 en 交叉核对，原始输出
  在 raw/。F00 冷开为现场人群声、无前景英文（VAD 交叉核对结论在案）。
  v5 音轨与 v4 逐字节一致，审听结论原样沿用；审听包 source_sha256 已换为
  v5 身份并注明复核依据，plan 经 foreground_audio_gate.rebind_plan 重绑定。
- subtitles.ass：由 v5 成片实际烧录字幕导出（锁稿文本＋v3 锁定 SUB_BREAKS
  断行＋原声段 10 条双语事件，格式照原生 write_subtitles 双语成例：
  EN 行 Inter 小字在上、ZH 主行在下、\an2 下锚）；全部事件时间已按所属段落
  窗口做厘秒级钳制，避免厘秒取整跨段（与成片烧录差 ≤0.01s，低于一帧）。
- 管线闸口（2026-11-21 本地实跑，全过）：
  - push_reel --stage check：通过（标题「11.20网球有故事|职业网球真的赚钱么」）。
  - foreground_audio_gate.require：恰好 10 条 required cues，全在第 34/45 段。
  - check_reel_landed：0 项不合格，qc_attestation.json 已签发
    （film a269948e3a1f…，render.json 已钉 attestation sha）。
  - auto_push_gate：本地因产物未入仓＋render.json 尚无 Release video_url
    按设计跳过（这两项由 CI 导入流程的 release/提交步补齐后在 CI 内判定，
    与 laver 先例同一顺序）。
- 导入：tools/import_approved_money.py＋.github/workflows/import-approved-money-story.yml
  （仿 import-approved-laver，钉版 v5 身份；required 文件含 render_inputs.json
  与 audio_review_binding.json，CI 内重跑 push_reel check 与 check_reel_landed）。
- 配音听审补件（2026-11-21 恢复趟）：首趟 match-reel 推送 run 44864938825 在
  push_reel 发送前被 voice_quality_gate 拦下（waiting_voice_quality_review：
  缺 voice_quality_inventory.json），作业日志确证 push() 未被调用、PushPlus
  未被联系、无回执生成；账本 attempt 因此记 uncertain 后经人工核实改记
  not_sent（核实依据即该 run 日志，见账本 resolution 字段）。
  本片旁白为自有制作线 edge-tts zh-CN-XiaoxiaoNeural 逐行合成（+0%/+0Hz，
  实际请求与实际音频字节冻结为 tts_bundle.zip，sha256
  98940060e8b9f04c631b163e19446758d9e5962fae7a46ad27cc192ac971afe4，65 条）；
  合成时未开启词边界流，词边界由实际音频的 faster-whisper 强制对齐实测补齐；
  53 条读稿取自制作记录 tts_full.py，12 条样片行读稿按全片读稿惯例由展示
  文本重构并经 ASR 逐字核对。voice_quality_inventory.json 已由
  voice_quality_gate.capture_inventory 生成并经 render_inputs 封存；
  五项自动听审由 CI 工作流 voice-review-money-story 在实际小包上执行，
  证据 voice_auto_review.json 与放行记录 voice_quality_review.json 随其
  提交落仓（method=automated_voice_suite，不冒充真人听审）。
- 听审 B 路修复（2026-11-21，账号所有者裁决走 B：修工具口径＋重建 marks）：
  首趟 CI 听审（run 44867051672）没过的真因不在配音本体：① 首版 marks 实为
  faster-whisper 自由转写 token（繁体字、阿拉伯数字形、误听），并非上文所记
  「强制对齐实测」——闸内 token 按原文 find 不到即跳过、zip 错位，语速/停顿/
  多音字定位全测歪（实测真实语速最高 4.68 字/秒，限值 6.3）；② 听审工具
  voice_auto_review 的完整性归一化有口径损耗（小数百分比丢「点」、区间丢
  「至」、并列百分比的「百分之」共享未建模、数字念法逐块贪心多塞音节），
  11 处「不完整」全是伪影。修复：(a) 工具归一化补齐上述口径并把念法挑选
  改成对参考的全局对齐（SUITE_VERSION 2，门槛常量未动），校准证据
  research/voice-auto-calib/normalization-20261121.json（原生包 andreeva-
  finals-2026 已过包 13/13 新旧同过；本集 65 条 small 转写旧口径 52 过→
  新口径 64 过，余 1 条为 ASR 漏听两个「第」、属 CI medium 复听范围；
  构造缺陷漏读/多读/换词仍全红、语速压缩样本仍判超标）；多音字参考字补
  第四档（GB2312 外单读音字，仅前三档为空时启用；qie1 的苆经晓晓实际
  合成＋ASR 验证读 qiē）。(b) 本集 marks 全部重建：对实际音频做
  faster-whisper small 词时间戳转写，按拼音单位全局对齐原文逐字切分实测
  边界；音频字节、请求文本、包成员顺序未动，新 bundle sha256
  6d79135fc2c1a91ae2b9c4c0c34b4164dcf3397fa36803df6458b0def5340153。
  render.json 的 tts_bundle 钉与 note 已同步更正（首版 note 的「强制对齐
  实测」表述不实，以本节为准），voice_quality_inventory 经 capture 重取、
  render_inputs 经 record 重封（新 sha 0d4e6fd738351b6c15dc260ac95c5a13283a1162f9e95ad855f3ab537cbbaa75）、
  qc_attestation 经 check_reel_landed 重签（0 项不合格）。
