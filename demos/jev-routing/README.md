# 网球时差 × Jev 栏目分流 Demo

独立演示程序，不修改现有生产路由、视频 QC、日期/双打规则或推送状态。

输入取自 `data/oncourt_interviews.json`：4 条明确场上采访、4 条带片尾采访标记的集锦、
4 条模糊赛后采访标题。另有 6 条明确标注的模拟边界样本，覆盖故事、前瞻、非网球、
发布会、信息不足和提示注入。样本来源版本记录在 samples.json。

已有库存 `kind`、`tail_interview` 和模拟标签仅用于展示，不发给模型，避免标签泄漏。
模型只读取 title/description/transcript/source。标题能支持类型判断，但不能证明画面事实。
原库存经过采访预筛，且演示样本为定向选择，因此不能用本 demo 估计整体准确率。

## 运行（Python 标准库，无额外依赖）

```bash
python demos/jev-routing/demo.py --out /tmp/jev-offline
# 在运行环境 Secrets 中配置 TYPESAFE_API_KEY 后：
python demos/jev-routing/demo.py --out /tmp/jev-live --live
python -m unittest discover -s demos/jev-routing -p 'test_*.py'
```

输出目录必须不存在。最多 30 条；每条请求一次、不自动重试；单次网络超时 15 秒。
401/402/403/429 立即停止后续调用，部分结果持续写入 receipts.jsonl。
默认离线，不调用 API；--live 才实际调用。JEV_MODEL 可固定版本，默认 jev-latest。
响应记录实际模型名、token 用量、端到端耗时、分类和概率；异常不记录密钥或响应正文。
暂定置信度 0.9 仅用于提示复核，未经校准，不自动派发。

## 查看

打开 `live-run/Jev_Tennis_Demo.html`，可筛选栏目、搜索标题、展开输入与概率、查看原素材。
页面展示已经完成的调用结果，筛选不产生 API 请求。重新调用使用上面的 CLI。
`live-run/results.json` 和 `receipts.jsonl` 保留真实结果。

费用按 $0.042 / 百万输入 token 折算，输出按公布免费价格；不是实际账单扣款。
没有验证账户赠送额度、有效期或免费额度是否用完。
公开接口参考：https://docs.typesafe.ai/introduction/quickstart

本地测试只验证输入隔离、离线不联网、响应结构和 HTML 转义；未做全量仓库回归。
该 demo 尚未进入生产流程；完整生产评估需要独立的人工标注集与现有方法对照。

## 2026-09-21 实测结果

18/18 次调用成功，模型 jev-1.13.0；输入 11,611 token，输出 1,785 token。
标价折算约 $0.000487662，不等于实际扣款。端到端 P50 6,929.5 ms，P95 13,185.2 ms
（nearest-rank，18 个小样本），含当前执行环境的网络开销，不能归因于模型推理本身。
11 条触发暂定复核提示。模糊采访标题仍可能被选成 interview；阈值尚未校准。
因此本轮不能证明能提速，不能自动替代现有制作或视觉判据。

模拟样本 5/6 与预设标签一致。足球采访错误分为 interview，置信度 0.41，被复核阈值标记。该错误必须保留为后续非网球规则检查的反例。

## 增量控制与净收益验证

参见 [production-value.md](production-value.md)。新增选择性调用、24 小时缓存、调用预算、熔断及独立手动审计工作流；尚未接管生产路由。

### 已完成真实缓存验证

经用户授权，所选真实素材冷调用 13.28 秒、跨数据库重开后的缓存读取 4.23 ms，
热运行无网络调用。分类为 uncertain（0.39），仍需原流程处理。8 秒调用先超时，
随后 30 秒隔离诊断成功；候选流程仍保留 8 秒超时。详见 production-value.md 和
cache-verification-diagnostic/summary.json。
