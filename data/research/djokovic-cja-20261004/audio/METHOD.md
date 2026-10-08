# 原声核验方法与当前状态

本期输入：https://www.youtube.com/watch?v=cjaHThpISKk 。证据与候选字幕只保存在本目录，不修改正式 spec。

## 约束

- 只转录实际源音轨；draft 文案、ATP 新闻文字和画面推断不充当实听。
- 原声字幕一条英语原文、一条中文语义翻译，源绝对时码另存；交给 spec 时 `at/end` 必须减去该段 `start`。
- 完整核对保留窗口内全部可辨识前景英语，连同句头、句尾；未查清的语句不签 `complete`。
- 原声段不叠自配旁白；安静回合可给旁白，须核没有英语尾音被覆盖。
- 两种实际 ASR 输出逐句交叉比对；有分歧时扩大/错开窗口重新核验；无法解除分歧则排除或明确待审。
- ASR 交叉核验不是人工实听。本代理没有人工耳听，不声称人工实听；最终条目须写 `method=asr_cross_checked` 与 `actual_listening_performed=false`。
- 精彩转播解说归 `broadcast`；采访不进赛场之上。
- 未提供任何凭空英语台词。没有字幕轨不等于没有解说，ASR没有结果也不等于没有人声。

## 首批优先级

1. 开局被破发与首盘救盘点/救破发点；
2. 次盘接发破发、扳盘；
3. 决胜盘最后两赛点与庆祝（采访排除）；
4. 声调与评价有感染力的完整关键回合。

## 源状态（2026-10-04）

既有 probe run37208304068 已 success。artifact caption_debug 明确 YouTube 多 client 字幕获取失败（429），因此不可引用不存在的 captions.txt。probe 时长319.181497s，313.05–319.18s记录数字静音；50fps官方源由素材代理恢复精确缓存字节，本地尚未落地。恢复后绑定源 SHA256，再开始ASR。


源已恢复：`/workspace/djokovic-cja-research/source/cjaHThpISKk.mp4`，122255880 bytes，SHA256 `2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2`。H264 1920×1080 50fps，AAC 44.1kHz stereo；通过旧 runner cache 精确恢复，未重下不同版本。

## 第三模型结果

`large-v3-turbo` 权重1617884929 bytes，SHA256与HuggingFace LFS身份一致；完整出处和初次配置错误/修正记录在 `raw/turbo-model-integrity.json`。它只跑目标窗，没有冒充全源第三份。

- 开局 `Out it goes`、稀疏处 `Gets him`、`Perfect placements`、救BP后的 `Oh, he was stretching there, Zverev`，经第三模型两次上下文/短窗及另两种英语模型解除。
- 266.44–268.56仍无法解除：同一真实音频首词在How/And/Out之间，第三模型首词概率极低。不要把它写成确定英语，不要签整段complete。后一完整句269.0–271.86是 `I don't think anybody breathing`；不添加识别中未出现的is。
- 第一赛点长回合229.2–266.4的观众声会令模型产生标准幻觉：base两次“I'm going to take a nap”、small.en“Thank you”、turbo宽窗“Oh my God/Thank you”，错开短窗又变成非词性“Ah ah”或“Let's go”；两英语模型248–256目标窗均无台词。没有稳定可辨识的转播英语句子，因此不把噪声假写成精彩原声字幕；这种结论依据ASR反证，不能描述为人工听过或没有任何人声。
- 末尾turbo宽窗305.1后出现Thank you，短窗302–307只剩Breathe it in，另外small/medium也没有Thank you，故不印幻觉。
- 313.05起的数字静音用probe实测证明；有模型在该段幻想You/Thank you，证明原始ASR不能不经核验照单全收。

## 处理唯一未知短句

首个赛点完整画面保留。可由root独立制作短叙述窗口，仅对266.44–268.56原声做确定的局部静音，再保留后一完整英语句；原生mute=true只压到-26dB，不是真静音。现有reviewed_effects只授权RNA10固定slug，不可复用；原声变换需绑定新源SHA、可审计变换及新窗口证据，不能把本期整个声轨切换到获准给别条视频的narratedmode。
