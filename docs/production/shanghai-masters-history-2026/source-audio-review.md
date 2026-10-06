# 本期比赛原声与双语字幕审查

当前状态：11 个选用或可选 source SHA 绑定的 wholewindow packet 已完成 asr_cross_checked 核验；其余候选继续 pending。所有记录 human_listened:false，不生成 data/audio_reviews。前面的采集记录用于保存失败／恢复证据，最终状态见末尾完成窗口与用途。

## 方法

1. 使用官方源下载结果的 SHA-256 绑定素材版本；引用绝对源秒数。
2. 对比 faster-whisper `small.en`、`medium.en` 的逐词时间和原始 provider `json3`，VAD 仅用于寻找遗漏前景语音。
3. 不确定人名、场上叫分或解说措辞不靠赛事事实补写原话；仍标 pending。
4. 同一完整英文句提供准确中文译文，且全句落在选用镜头内；窗口边缘截句则延长经视听核验的窗口或放弃整句。
5. 原声字幕仅说明实际所闻，不能将叙事旁白当作电视解说。
6. ASR 交叉核验不冒充真人听审；实际方法明确记录为 `asr_cross_checked`。

## 已发现的采集问题

- GitHub Actions run `37392696759`：六个 source cache 已成功恢复，采集步骤在第一次 ffprobe 调用失败，原因是 runner 未安装 ffmpeg/ffprobe。尚无可供审核的双 ASR 文件。最短修复是安装 ffmpeg 后重跑。
- `fedal2017` 原计划 `[290, 380]`，应扩展为 `[280, 380]`：拟选末球由 281 秒左右开始，旧 provider 的 293.06 秒字幕已是 “Masters champion for a second time” 句中，必须采集前文。

## 待审核候选（不是最终 EDL）

| 源 | 候选绝对秒 | 需解决的声音边界 |
| --- | --- | --- |
| cup2005 | 348–378 | 末球与胜者宣告；检查 378 秒边缘是否截句 |
| final2012 | 32.08–39.48 | 第一冠军点；源内具体叫分/解说全部核验 |
| final2012 | 76.44–85.64 | 第二盘盘点；不能截掉情绪解说后半句 |
| final2012 | 85.64–111.48 | 最后得分与握手；111.48 秒后片尾，若冠军点总结延长至片尾必须整句删去或换经审查窗口 |
| mayer2014 | 361.04–381.96 | 第四赛点；持续评论完整句 |
| mayer2014 | 388.04–407.88 | 第五赛点；译名与语句需双 ASR + provider 比对 |
| fedal2017 | 281–306 | 最后得分与夺冠宣告；需 280 秒起采集前文 |
| sinner2024 | 448–473 | 夺冠总结可能延至 478 秒；不得只截中间句 |
| vacherot2025 | 360–394 | 夺冠宣告、表兄弟拥抱；完整场上/解说语音，未听清仍 pending |

镜头完整性、固定中心满画布裁切及完整关键球，由独立视觉审查另行确认。本审查不能替代这些结论。

## 已取得的真实部分证据

GitHub MCP `fetch_workflow_job_logs` 获取 run `37393356416` attempt 1 的 job `112043397317`：采集已经产出全部 54 个文件，失败仅在 bot 推送冲突。日志包含两个模型的逐段文本和秒数，但未包含 source SHA、逐词时间、VAD 与原始 json3，故暂不封 `reviewed` EDL。attempt 2 已启动并等待原始文件正常保存。

### 逐句翻译准备（依据双 ASR 日志；边界待逐词证据，不是成片字幕）

- **2012，约37秒**：Nicely done.／处理得很漂亮。
- **2012，第二盘结束**：He's done it. What a fantastic effort by Novak Djokovic.／他做到了！诺瓦克·德约科维奇的表现太出色了。
- **2012，比赛结束**：He's done it! Victory for Djokovic, his first title here in Shanghai.／他做到了！德约科维奇获胜，这是他在上海的首冠。
- **2012，约99–106秒**：But of course back-to-back victories here in China, after proving unbeatable in Beijing last week.／他在中国连续两站夺冠，上周在北京也无人能挡。
- **2014，第4赛点前**：This is the moment of truth, surely. Three match points already. All of those have been on Federer's serve. Here's his first on his own deal.／这一刻，胜负就要见分晓了。此前已有三个赛点，都出现在费德勒发球时。这是梅耶尔第一次在自己发球时拿到赛点。
- **2014，第4赛点后**：This time, Federer makes no mistake with the backhand pass.／这一次，费德勒的反手穿越没有失手。
- **2014，第5赛点前**：Match point number five.／第五个赛点。
- **2014，第5赛点后**：That was so close to going over. That would have caused Federer all kinds of problems.／那一球差一点就过网了。如果过网，费德勒就麻烦了。
- **2014，约404–409秒**：Just get the feeling he just needs one match point, this Federer.／总觉得，费德勒只要一个赛点就够了。
- **2017，约290–296秒**：…is the Shanghai Rolex Masters champion for a second time.／……第二次成为上海大师赛冠军。开头完整名字的 dual ASR 并不一致（small误识别Peddler，medium遗漏），不能据赛事身份补写为已听清。
- **2017，约298–311秒**：For a fifth time in a row, he gets the better of his great rival, and wins title number 94 of his glorious career.／他连续第五次战胜这位伟大的对手，拿下辉煌职业生涯的第94冠。
- **2024，约462–473.2秒**：The world number one delivers an impressive display to claim a third Masters 1000 title of the year.／世界第一以令人印象深刻的表现，拿下本赛季第三座大师1000冠军。
- **2025，约368–372.4秒**：Game, set, match, Vacherot. Two sets to one.／比赛结束，瓦舍罗获胜，盘分2比1。
- **2025，约372.4–381.2秒**：Valentin Vacherot puts the icing on the cake to a fairy tale week in Shanghai.／瓦舍罗为上海这童话般的一周画上完美句号。

### 已确认的截句风险

- 2012：五冠军点总结整句至115.27秒，跨111.48秒源片尾；最终窗口应在上一句的106秒附近完整句尾截止，具体等逐词时间，不留截断英文。
- 2014第4赛点：361.04秒起点截掉355秒起的赛前解说，应向前扩；第5赛点407.88秒终点截掉至408.60秒的末句，应延长或整句前截断。
- 2017：306秒截断“辉煌生涯第94冠”句，完整至310.62秒。
- 2024：473秒仍可能截掉“of the year”的最后单词，实际双 ASR 最晚473.20秒，应保留安全余量。
- 2005新增326.8–343窗口：上一句“He will be serving for the title”到327.12秒，326.8秒起点截句。三重证据核验之后可考虑327.4秒起的纯动作候选，仍需完整关键球视觉审查。

## 已完成的窗口与用途（最终审查状态）

已完成的11个本期 wholewindow packet 均为 `asr_cross_checked`，绑定实际源 SHA 与双 ASR/provider/VAD 原始文件 SHA；`human_listened:false`。系统明确不支持 audio input，不能冒充真人或模型实际听觉审查。此方法属于仓库允许的 source evidence 方法，仍不替代最终混音检查。

- 2005 `328.0–343.0` 是说明旁白背景，发球在起点之前，**不能宣称完整关键球**。末球348–378及未知Vilas原词仍 pending。
- 2012 第一冠军点32.08–39.48、第二盘盘点76.44–85.64、末球与握手85.64–106.48保留各自完整可交叉核定的英语；106.48必须在下一“And”句之前结束，避免跨片尾。
- 2014 第4赛点354.88–381.96提供完整赛前与赛后英语。可选纯效果334.0–341.1、379.3–390.3供旁白背景；后者若接第4赛点，需避免379.3–381.96画面重复。
- 2017 proposed280.5–289.3仍 pending：VAD288.496–289.552压在最后0.8秒，冠军解说名字没有被双 ASR+provider清楚核定。保守空声窗280.5–288.4会失去关键球结局；建议真实2017官方照片配中文事实，删除未核原声。
- 2024 `462.0–473.4` 只保留**赛后夺冠解说与真实反应**，末球在462秒之前结束，不能当作完整末球。中文明确本赛季第三座大师1000冠军。原拟443–461.7仍有未解释VAD，保持 pending；可选更窄448.6–460.8尚需视觉连续性决定是否使用。
- 2025 raw360.0–381.9保留完整短评论、主裁宣告和童话周总结；381.9–393.3真实拥抱空声窗可以直接接中文旁白，所有源画面连续。若VO较短可从末端缩至390.x，不会触及英语，但root应把最终实际范围绑定到gate。

所有双语短cue 英文不超过50字符、中文不超过22字符，按实际 ASR逐词+provider合理分句，完整大句仍全部保留。只有选中窗口被审查；未使用的源范围不作完整听审声明。

## 2017安全替代与最终证据检查

已补 `fedal2017-preparation-effects`280.5–288.4 wholewindow packet，允许root取更窄280.5–284.0发球前准备子窗（视觉必须另确认）；可用原生0.65–0.75轻慢镜承载说明旁白，不循环、不声称完整最后一球。该范围内VAD没有speech、medium没有口语词，small的大写CHEERING AND APPLAUSE与provider整窗[Applause]对应，明确视为非语言事件标签。280.5–289.3仍然pending，因为越过288.496的下一语音VAD。

最终已实际验证11项EDL的source SHA、一切raw evidence SHA、packet SHA、整个选窗覆盖、cue在窗内、英文≤50字符、中文≤22字符。原先8个packet字节与SHA没有为了补用途而改动，root已绑定者不需刷新。用途只加在EDL和本审查记录：2005说明背景，2024赛后解说，两者都不能被误报为完整关键球。

## 原生字幕宽度修订

成片68px中文字的折算上限16。已用原生_quote_display、_sub_width、ass_row_size检验全部22个中文cue，折算宽度均≤14（最大14.0）。仅精炼3条译文：

- 2014：梅耶尔首次在发球时握有赛点。
- 2024：获本赛季第三座大师1000冠。
- 2025主裁宣告：瓦舍罗获胜，盘分2比1。

英文、绝对秒数、源SHA、原始ASR/provider/VAD证据全部未改。对应3个审查packet的中文及packet SHA已同步EDL；root须重封最终plan ledger，以新packet SHA绑定。此前“每cue中文≤22字”的准备约束已由本次实际原生宽度≤14验证收紧。
