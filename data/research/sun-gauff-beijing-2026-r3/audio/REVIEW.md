# 原声证据

方法为 `asr_cross_checked`，没有声称人工听审。

源片 SHA256：`79951bd5316ac8910ce6fc1200260c62492d1f791ed3690729dadeb7a6296b90`。源长425.482449秒。tiny.en和base.en两独立模型完成全源ASR；small.en、medium.en、large-v3-turbo和large-v3针对所选英文窗口复核。全源small.en只保留原始部分日志，未当作完整证据。

7个所选源窗，35条中英原声字幕（原19句按真实词边界拆成短cue）。231.28–243.20为空英文窗口，由两份全源独立ASR及前后句边界核验，不是仅凭单窗空结果。

已在正式spec写入quote，`data/audio_reviews/sun-gauff-beijing-2026-r3.json`绑定当前实际计划；源字节绑定校验通过。后续变更会使plan hash变化，需重绑。

分歧与取舍完整保留在 `commentary-inventory.json` 和各模型原始JSON/日志。215–217秒BillieJean句存在句头分歧，所选剪辑不含此窗口，没有将该处标完整。此前1分句尾tiny全源VAD串接伸展到81.46，clean base和small独立短窗止于79.94/80.32；所选81.04起没有此前英文话尾。131秒Oh/Well/Wow低置信且互相矛盾，tiny全源、small128窗、turbo128窗一致从She开句，排除不稳定插词。136–140秒孙心然姓名按本场官方身份还原，链接词And采用base和medium的一致结果，large-v3单窗But分歧保留在原始证据。最终总结in/and采用large-v3与base一致的in the second set。

模型权重在 `/workspace/scratch/sun-gauff/asr-models`，不进入仓库证据目录。

2026-10-05 更新：中文字幕最长13字；`quote_overflow_rows=[]`。完整原句保留在`sentence_groups`，拆后英文规范化合并与原句逐组一致。当前源字节绑定require与`validate_spec`通过。dry-run字幕/形状通过，完整退出被未绑定probe与发布标签数量拦住，已报告root处理。
