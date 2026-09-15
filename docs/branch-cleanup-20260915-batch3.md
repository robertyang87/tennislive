# 2026-09-15 第三批：最后三条分支

15 个积压 PR 全部处置完之后，剩下这三条也腾出来了。

| PR | 为什么关 |
|---|---|
| #634 | 配乐那半**被账号所有者 2026-08-29 的「第二种方案」推翻**；快放放开的是它自己没用上的能力；社媒截图＋skill 是新增面不是修复。**唯一真没落地的「证据卡压字幕」那道闸已移植**，而且当场抓到两条存量 |
| #674 | 它要改的 `src/tennislive/render/qualifier_charts.py` **随 #905 瘦身删掉了**，在当前 main 上没有落脚点；内容本身也已发出去（`pushed.json` 在） |
| #824 | 只加一份文档，而 main 在这之后已走出 8 份；PR 自己写着「性能目标**尚待实施和实测**」，同期 `video-production-fast-path.md` 那条路已经真的在跑 |

⚠️ 三条都**不能 merge**：基于历史重写之前的 main，merge-base 已不存在，
合并会把整份旧历史重新挂回 main（那 2 GB 对象永久回来）。所以有价值的东西
走**移植**，不走合并。

⚠️ 每条都记着**末次提交 SHA**，要重做那几条内容时可以按 SHA 重建。

| 分支 | 末次提交 |
|---|---|
| `claude/grand-slam-qualifier-best-performance-z4ogyg` | `31e83bbb878c64986c616982644fe4e7ea3d6886` |
| `claude/tennis-news-video-ideas-ftpd2r` | `da16eca10ebab1a82b00b936db6a40f15cdac723` |
| `codex/production-review-20260909` | `9ae06e0dcdad204a070c1ee251a6c097879741cb` |
