# 64–67.8 秒字幕空隙核验

真实 medium / tiny 自动语种短窗与宽窗、VAD 开关合计八次 ASR 已完成，原始输出保存并绑定 SHA。没有人工听审声明。

medium / tiny 窄窗出现模板式 Thank you（首词概率 0.010–0.047），medium VAD 则给出低置信 Mm-hmm。没有稳定可确认的新语句，不应烧录 Thank you。medium 宽窗保留前句 out today 的尾音直至64.92/65.18，并将下句当地语言 Com sabeu 错写成 Once/Kwan，从67.56/67.66起。

真实 AudioSet AST 对64–67.8给Speech=.491、Applause=.466；排除边界后的64.34–67.4给Speech=.5025、Applause=.4777。支持掌声存在，但没有证明无残留人声。65秒截图中观众拍手是场景辅证，不能冒充听审。

可以诚实描述“掌声/现场声，夹杂短暂未辨识人声”。不能认证静音、纯非语言声音或确定的Thank you，不能把事件标签当作自动销VAD字幕闸的完整语句证据。

完整模型输出及SHA见gap-final-review.json。
