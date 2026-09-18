# 作品研究如何进入制作

`tools/reel_skill.py` 和 `tools/interview_skill.py` 在实际模型提示入口调用
`reference_learning.model_learning_instructions`，读取各自制作 skill 下的
`references/learned-rules.json`。默认登记表为空；缺失、格式错误或没有合格规则时，
原提示保持不变。此接入不触发渲染或发布。

研究候选继续留在 `agent/douyin-learning` 的 `research/douyin-learning/state.json`。
只有经过真实试验、QC与自有效果复核的规则，才通过代码审查复制进默认分支登记表。
登记表的布尔字段是审核记录，不代替读取回执原件，也不能从公开点赞自动计算。

每条记录包含：

- `id`、`version`、`status`（仅 `validated` 被采用）；同一 ID 仅保留一个当前版本。
- `roles`：`deepseek` 和/或 `minimax`，对应文案与视觉处理。
- `instruction`、`applicability`、`rollback`：具体规则、适用条件、撤回方式。
- `evidence`：非空的原始证据定位列表。
- `validation`：`qc_passed: true`、`outcome_passed: true`，以及非空的
  `qc_receipt`、`outcome_receipt`、`primary_metric`、`observation_window`、`reviewed_at`。

模型输入会带规则ID与版本，要求在制作审计中记录采用或跳过；加载日志只证明提示
读取成功，不能证明成片真正执行了规则。后续仍要核对真实spec、成片和QC回执。
一次只试一个主要变量，保留原有硬约束；未获验证的候选不进入默认生产提示。

撤回时将当前记录改为 `revoked`；下一次读取立刻恢复原提示，不缓存规则。
重复 ID 全部忽略，避免旧 validated 版本覆盖新撤回记录。版本历史由提交保留。

当前没有规则获增长验证。赛场之上和赛后开麦已提供读取入口；网球有故事需要在其
实际制作入口另行接入，不能仅靠同一份研究台账宣称三个栏目都已接通。
