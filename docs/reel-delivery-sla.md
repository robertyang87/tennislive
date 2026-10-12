# 赛场之上：从收到素材到微信回执的计时

`tools/reel_delivery_sla.py`记录用户端到端目标。它独立于`video_sla.py`原有“已批准制作链接→MP4就绪”指标，不重置或改变原渲染计时，也不发送微信、不预占发送、不修改任何QC、render、pushed或发布账本。

收到素材时保存一次明确的起表文件；不能到下载完或开始渲染时重填起点：

```json
{
  "started_at_utc": "2026-10-12T20:11:13Z",
  "target_push_deadline_utc": "2026-10-12T20:31:13Z",
  "target_seconds": 1200,
  "source_url": "https://www.youtube.com/watch?v=662TF-JlyZY"
}
```

在保存了原生发布证据的仓库版本上运行：

```bash
PYTHONPATH=src python tools/reel_delivery_sla.py \
  --repo "$PWD" \
  --slug paolini-bejlek-wuhan-2026-r1 \
  --outdir output/2026-10-13/reel/paolini-bejlek-wuhan-2026-r1 \
  --clock /tmp/reel-request-clock.json \
  --report /tmp/reel-delivery-report.json
```

工具先调用原生`validate_qc`验证同一成片、当前spec、烧片字幕、render及其输入清单。普通发布fingerprint应是该filmSHA；消息修订则必须通过原生`publication_revision.resolve(..., phase="finish")`，不能把合法修订误要求为直接filmSHA，也不能凭手写revision标签跳过父回执和资产核验。

完成必须同时具备已提交的`pushed.json`与同slug的sent账本，唯一对应本片或原生合法修订的fingerprint，回执、run、记录时间三项一致。无回执、sending、uncertain、旧影片、旧回执、两个重复身份、脏本地标记或不合法修订均返回`delivery_confirmed:false`、`met:false`，不生成完成耗时。

`receipt_recorded_at`取原生账本与marker一致的`at`，是接口回执写入证据的时间，**没有宣称知道provider响应的精确网络时刻或手机物理送达时间**。报告保留起表文件路径与SHA、成片SHA和实际publicationfingerprint。确认送达但超过1200秒时仍记录真实`elapsed_seconds`，`delivery_confirmed:true`、`met:false`；CLI成功退出只表示观察报告正常生成，不表示预算达标，也不改变质量门禁。

普通报告可放`/tmp`或独立证据位置，不允许覆盖原生output目录、发布账本或起表文件。此工具只读仓库证据，不访问外网；它不新增制作门禁或发送触发器。
