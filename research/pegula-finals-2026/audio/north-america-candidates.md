# 佩古拉2026北美赛季：官方素材与原声候选

本轮仅做素材/提纲研究，未正式render。8条实际源均为1920×1080，已下载并逐条ffprobe、SHA绑定；不是仅凭网页标签判断。现有spec只用作发现线索，下面原声来自本次真实字节的small.en/medium.en；必要处额外保留turbo诊断，未声称人工听审。

## 先给提纲可直接采用的两段本人话语

1. **辛辛那提亚军自嘲（冷开场优先）**：`pIRDCAcGpz0`，52.24–58.70，共6.46秒。完整三句：
   > “I’m a little upset. I have two of these now. I wanted the bigger one, but that’s okay. It’s still a pretty trophy.”
   > 我有点郁闷。这种奖杯我已有两座。我想要更大的，不过没关系。这个奖杯也很漂亮。

   本人持亚军奖杯、笑着说，完整句尾58.48；下一句59.66/59.70才开始，默认0.25秒尾巴不漏新词。9/9人脸样本通过，固定人物cx=.501。背景只能写**2024、2026两次亚军**，不用旧稿“两年两次”。

2. **美网八强后谈消极念头（结尾优先）**：`2FI5qs9EXNs`，57.40–74.72，共17.32秒。原话核心：
   > “I just have to tell all the negative me to shut up and just play tennis and compete and battle and think out there and try and problem-solve as best I can.”
   > 我得对那个消极的自己说：闭嘴，继续打网球，去竞争、战斗，动脑筋，尽全力解决问题。

   全窗还保留前面的short-term memory及末尾“that’s all I’m trying to do, really”。9/9人物样本通过，固定cx=.524。下一位主持人Well在75.12/75.14开始，74.72+.25=74.97不漏词。可压为62.84–74.72的完整核心句，但更短窗人物中心需制作时重测。**这是战胜纳瓦罗后的话，不冒充负萨巴之后或确认年终之后的话。**

## 六场比赛候选

| 本场 | 精确官方ID | 候选源时间 | 本轮状态 |
|---|---|---|---|
| dc-final | `OvjNXy1mQjY` | 234.72–260.50 | asr_cross_checked_candidate |
| toronto-r16 | `w29uIOOBVYM` | 261.90–277.52 | visual_complete_sentence_candidates_tail_boundary_needs_lock |
| cincy-sf | `C8_5ag2DYn0` | 262.72–275.40 | asr_cross_checked_candidate |
| cincy-final | `Z2_awLHqcww` | 236.60–260.50 | asr_cross_checked_candidate |
| us-qf | `beax9TP-Dlk` | 168.84–179.90 | visual_complete_umpire_words_unresolved_not_audio_approved |
| us-sf | `1WAjW7l89YQ` | 142.94–169.70 | visual_complete_background_umpire_unresolved_not_audio_approved |

- **华盛顿**：完整第二冠军点与伊埃拉跪地/网前反应。保留“magical moment…first ever tour title delivered in DC”到260.24；下一句261.86之后，尾巴安全。佩古拉本场6-4先赢一盘后4-6、0-6告负。
- **加拿大**：真实最后一分擦网球、施耐德举手致歉及网前握手；“Oh…Goodness me…Back-to-back good fortune”。277.52后马上接“A smile…”的新句，若保持此窗，正式制作必须处理**仅窗外0.25秒尾巴**或重新锁结束边界，不掐已选完整句。
- **辛辛那提半决赛**：262.72起真实赛点，267后佩古拉握拳。完整保留“She needs the first only”及“Jessica Pegula…for the second time…final here in Cincy”到275.28；275.40+.25在下一句Her275.72之前。254–261是另一分，不能拿来冒充赛点。
- **辛辛那提决赛**：完整末分、庆祝与网前拥抱。重要：旧spec声称解说255.28结束，**实际双ASR到258.10/258.20**，照抄会截句。第一词It被ASR沿前段无语音延长，句头显示点仍属候选，制作时细校；完整选窗保留句头。
- **美网八强**：真实第二赛点168.84起，**佩古拉远端发球**，纳瓦罗近端接发。旧spec把佩古拉写成接发者，实际169秒原图和发球标记可纠正。173.4–177.5裁判声仍未稳定核出，不能套“Game set and match”模板假装已核。本轮另有清楚的**190.70–203.20赛后反应窗**：“She got through it…She’s in the semis at her favorite tournament.”可供提纲采用。
- **美网半决赛**：142.94起完整末分与之后网前拥抱；150–155背景裁判声三模型仍不稳定，保留待核。163.16起主解说清楚：“Aryna Sabalenka is into another US Open championship match.”可单独用162.94–169.70的真实同场反应，不能称单独这个窗含完整回合。

## 证据与限制

- `north-america-source-manifest.json`：8源URL、Release、实际SHA、尺寸、时长、帧率；4源25fps、Cincy讲话29.97fps、美网两场与采访59.94fps。
- `north-america-download-dispatches.json`：7条缺源实际download-video研究存档run，均成功，绑定origin main；没有新建workflow、改代码、Git fetch/checkout或正式render。
- `*-small.en.json`、`*-medium.en.json`：本次源字节的实际逐词转写；`*-turbo-diagnostic.json`为明确标注的第三模型诊断。
- `visual/*-source-contact.jpg`及`*-court-center-contact.jpg`：本场原画面与固定3:4中裁诊断图。裁图是研究证据，未声称正式native字幕/成片通过。
- `speech-person-centers.json`：实际原生人物中心9点测量。
- 全部中文候选每行≤16字；精确cue与完整英文逐行在JSON。正式制作后仍须原生字幕帧及最终MP4检查。
- 部分击球可能离开固定球场中心裁框；不左移、不跟踪、不contain，不把“时间上完整回合”写成“每一拍动作全可见”。
- 本地不能播放听审；以上方法诚实记为source-bound机器交叉核验。未核裁判声保留uncertain，不编标准宣告。
