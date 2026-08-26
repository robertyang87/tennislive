# 赛后开麦质量门禁

## L0 来源与比赛身份

- `requested_content_type` 只能是 `on_court` 或 `ceremony`，检测类型必须一致。
- 官方来源、match.id、比赛、轮次、受访者和赢家全部一致；独立正文的 lead-in 必须同场。
- 任一项缺证据即 waiting，不生成正式 spec。

## L1 语言与结构

- 双 ASR 或等价交叉验证完成；所有红旗都被逐项解决或显式保守保留。
- 英中字幕行数和顺序严格一致，英语原话未被改写，主持人与球员不混淆。
- takeaway 与 PushPlus 文案只用已核事实，具体且非模板化。

## L2 视觉与成片

- MiniMax 视觉证据置信度至少 0.85，人物、场景、同场、非镜像、封面和字幕可读性通过。
- 成片为 1080×1440；保留英文原声；正文与同场开场均有双语字幕。
- QC attestation 为 `pass`，音画差、静音、字幕数量和文件哈希均满足机械门禁。

## L3 发布资格

- spec 明确认领自动发布；海报、复制页、成片 URL 和 QC 证明齐全。
- PushPlus 只在 L0–L2 全过后发送；发送失败不得伪装为成功。

## L4 发布证明

- 独立发布账本与 `pushed.json` 记录同一 slug、成片哈希、run 和发送成功状态。
- 没有 PushPlus 成功回执与 `pushed.json` 写入，不能称为完整链路跑通。

## 影子阈值

- DeepSeek ≥85/100；MiniMax ≥90/100；候选机械校验必须 pass。
- 影子只写报告目录；禁止修改 spec、render、workflow dispatch、PushPlus 或发布账本。
