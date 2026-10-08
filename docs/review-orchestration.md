# 编排与派发审查（2026-10-04）

范围：`orchestrate.py`、显式 reel 队列、`reel-auto-ready`、采访草稿提升/自动渲染、三线自动发布入口。仅静态审查和本地假 API / 本地 Git 测试；没有向 GitHub 派发制作任务或发送消息。

## 已修复：ready 转正后丢失派发任务

旧 `reel-auto-ready.yml` 把草稿提升为正式 spec、删除草稿并提交到 main，再从 `/tmp/reel-ready` 派发 render。若此时网络失败或 runner 中断，下一班只扫描 `*.draft.json`，已转正的正式 spec 不再进队列。`auto-push-reel` 只观察成片 `render.json`，无法补回尚未渲染的任务。这不是慢一班，而是后续不会自动恢复。

现在转正时生成 `data/reel-dispatch-outbox/<内容hash>.json`，与 spec 一起提交后才派发；每班都排空此前的 pending intent，不依赖本班是否还有草稿。请求标识含 slug、spec/文案内容摘要；同一份转正输入不会因为重复 tick 再产生请求。记录里的 `dispatched` 只代表 GitHub API 已接受，绝不代表质检、渲染或推送已成功。

## 已修复：显式队列部分失败后重复重编码

旧 `dispatch_reel_queue.dispatch()` 顺序调用 `gh workflow run`，没有完成记录；第 N 个请求失败时，重新执行该 workflow 会再次派发已接受的前 N−1 条。按 slug 设置 concurrency 不能消除串行重复编码。

现在显式队列也使用同一个 outbox。请求标识由原事件 AFTER、队列路径与规范化请求内容摘要确定；新队列路径代表明确的新请求，允许有意重渲。同一请求的每条 API 接受后立即提交并持久保存 receipt，失败条目仍 pending，继续处理本批其他条目。显式队列通过重跑原触发 workflow 恢复；自动 ready 由定时 tick 恢复，两者不混淆。两条 workflow 都从最新 main 检出，避免 rerun 固定旧 event SHA 而看不到后续 receipt；原始队列事件的 BEFORE/AFTER 两个 SHA 都显式获取，仍按原事件范围验队列；原 AFTER 版本的队列、spec、文案逐字节与 main 对比，拒绝拿后续修改重建原始授权。

原显式队列的当日 `expected_date` 校验保持不变：跨日旧队列不会被当成今天的新发布授权自动放行。

## 不让旧意图消费新输入

请求保存 spec 与文案字节摘要。排空时若输入变化或缺失，标记 `invalidated` 并记录原因，绝不写入 `dispatched`；同批其他条目照常派发。自动 ready 请求保留最初 `_production.received_at`，复用 `PENDING_MAX_AGE` 新鲜窗；超期或时刻无效也进入独立 invalidated 状态，不能数天后补做过时比赛。后续 tick 不反复尝试已失效意图。需要提交新的经过审核的请求，不能用旧请求凭证为变更后的内容背书。

## 一致性边界与成本

- 每个请求各占一个文件，避免把所有 scheduler 都写到一个共享 JSON；复用现有 `push_with_rebase_retry` 处理不同文件的并发落库。
- 每个 API 接受后保存一次小型 Git 提交，最多 8 条/显式队列；代价是 Git push 次数，换取失败后不重复全部重编码。已有 receipt 不产生空提交或重复 API 请求。
- GitHub API 接受与 Git receipt 推送不能组成原子事务。如果 API 已接受、runner 随即消失，或 receipt 连续推送失败，下一趟仍可能重投。实现明确告警并停止进一步无账本派发，不声称 exactly-once，也不为消除该窗口新增外部服务。
- spec 摘要核对基于当前检出的 main；后续 GitHub 接受 `--ref main` 到实际 runner 检出之间，main 仍可能变化。现有制作/发布指纹与质检继续承担最终版本一致性，不以 dispatch receipt 代替它们。
- 本次修复恢复“派发前/派发失败”的 intent，不把“API 接受后制作失败”伪装成未派发；后者仍由现有制作失败修复/监控及显式重渲请求处理。

## 其余审查结论

- `orchestrate.py` 已逐条记录派发，工作流 `always()` 落库；各候选资源探测错误隔离，成功项保留。因此没有重复加一套相同功能。
- 采访已有按当前输入指纹挑选、70 分钟未落地重投、逐条派发成功后记账、共享 dispatch 状态三方合并，以及条件化预检缓存。未发现可以直接删除而不影响恢复/安全的明确冗余；未削弱这些机制。
- `orchestrate.dispatch_plan()` 按全库球员姓氏对永久拦截已有 spec，源码已承认缺比赛日期时“宁可漏点”；长期会漏掉同一对球员再次交手。建议后续把现有 spec 的赛事/年份/比赛日期规范化后再收窄去重，不在没有可靠匹配键的情况下直接移除防重。
- `reel-auto-ready` 当前即使无待处理草稿/intent，也会 setup-python 与 pip；这是可优化的空跑成本，但不能用“无 draft 即退出”重引入本次漏派。早退判据必须同时考虑未终结 intent，并保持轻量 nudge。

## 验证

新增回归覆盖部分 API 失败后继续 siblings、新 runner 恢复只重试失败项、同请求幂等、显式新请求允许重渲、无草稿时排空、输入变化失效且不连坐、Git 持久化失败不假报渲染成功，以及真实本地 bare remote 提交后 fresh clone 读取 receipt。没有使用真实 `gh workflow run`。
