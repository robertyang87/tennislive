# RNA 10 周年原声 ASR 核验

用 faster-whisper small 与 medium、CPU int8、beam 5、Silero VAD，对全部指定窗口交叉转写；没有声称人工听过原声。模型下载直接成功，没有绕过网络限制。

## 可用结论

- source 3 的 160–169 秒与 177–196 秒，两模型均未检出语句。完整窗口已交叉检查，可绑定相应源 SHA-256。
- source 1 的 121.27–121.99 秒，两模型均给出英语 “I've got it!”（候选中文：我来！），之后一句 small 为 “Change!”、medium 为重复 “I've got it!”；不可无条件认证整段。建议避开 121–123 秒。
- source 5 的 239–242 秒，两模型检测出西语候选，但内容有冲突，不能虚构双语字幕。
- 其余窗口有低置信或模板式 “Thank you” 输出，部分首词概率 < 0.04、no_speech > 0.7；保留原始输出并标 uncertain。
- 不可声称所有素材全是西语；不能把赛果 4 比 3 写成转播原话。

## 原始文件

`rna10-selected-small-asr.json`、`rna10-selected-medium-asr.json` 是完整选用窗口原始词时间码。`rna10-tails-small-asr.json` 是各源最后 25 秒探查；低置信尾片探查生成了不同语种的模板输出，不能当真实字幕。无 VAD 的 medium 给出了不存在于 VAD 结果的长颁奖词，因此放弃无 VAD 字幕。

`rna10-audio-review.json` 包含源 URL / SHA-256、范围、模型输出及明确 uncertain_spans，未绑定最终 spec，也没有编造 gate pass。

## 决胜窄窗口

source 1 的 132.4–145.7 秒 small 与 medium 独立 VAD 转写均为空；原始结果见 `rna10-decider-clean-asr.json`。该窗口可用真实 `asr_cross_checked` 无前景英语证据，JSON 的 `verified_alternative_windows` 已附可绑定证据。
