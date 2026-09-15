# 2026-09-15 第二批：已关 PR 的分支清理（**已执行**）

**327 → 5 条**（main ＋ 三个还开着的 PR ＋ 当时的工作分支）。

## ⭐ 最终的账：**main 自己只有 1.02 GiB**

一路量下来：

| 量的是什么 | 体积 |
|---|---|
| purge 之前的 `.git` | 3.0 GB |
| **只 clone main（全 history）** | **1.02 GiB** ← purge 真正的成绩 |
| 全量 clone（带上所有分支） | 3.05 GiB |

**purge 掉了三分之二。** 全量 clone 里多出来的那 2 GB，是剩下三条分支钉着的
——它们基于 purge 之前的 main，各自还带着已经从 main 全史抹掉的图：

    codex/production-review-20260909                      7631 张
    claude/grand-slam-qualifier-best-performance-z4ogyg   5151 张
    claude/tennis-news-video-ideas-ftpd2r                 5057 张

⚠️ **那三条不是残枝，是还开着的活**（#824 一份生产复盘、#674 一版等着看 spec 的
内容、#634 一条渲完没发的样板片 ＋ 一个 skill 目录）。它们合并、关闭或 rebase 到
重写后的 main，那 2 GB 才会跟着走——**那是内容决定，不是清理动作。**

⚠️ 而 **CI 走的从来不是全量 clone**：`--depth 1 --single-branch` 现在 20 秒 / 1.6G，
那一维早就不受这三条分支影响了。

上一批清掉 310 条残枝之后，全新 clone 只从 3.44 GiB 掉到 3.26 GiB——**剩下的体积
不是残枝，是 15 个还开着的 PR 的分支**，它们基于 purge 之前的 main，整份旧历史都在上面。

那 15 个逐个查过产物之后处置了 12 个（详见各 PR 里的说明）：

| 类别 | 数量 | 判据 |
|---|---|---|
| 片子**已经发出去了** | 4 | main 上 `pushed.json` ＋ `render.json` 都在 |
| 修复**已被 main 上更好的解法取代** | 2 | 如 `yt-dlp[default]` 取代逐条挂 CLI 参数 |
| 内容**过期**（按仓库时效性规矩不该再发） | 3 | 比赛日差了两周到一个月，且从没渲过 |
| 价值**已移植**到当前 main | 3 | #911（不能 merge，只能重新落一次改动）|

⚠️ **仍开着的 3 个 PR 的分支不在名单里**：`codex/production-review-20260909`（#824）、
`claude/grand-slam-qualifier-best-performance-z4ogyg`（#674）、
`claude/tennis-news-video-ideas-ftpd2r`（#634）——那三个装着还没落地的活，是内容决定。

⚠️ 每条都记着**末次提交 SHA**，删错了能按 SHA 重建成同名分支。

| 分支 | 末次提交 |
|---|---|
| `claude/codex-video-wechat-push-pa33ai` | `8d87b85dc483dbc121af782df3fa2397ecf5365f` |
| `claude/fils-tirante-2026-08-21` | `47474db99810b75aee37fb748555ed6c1975ed60` |
| `claude/shang-jun-cheng-sai-chang-a6k1vm` | `0b9008690abe6f57b6879937d5f73f3b24332912` |
| `claude/tiafoe-tien-2026-08-21` | `8e5a2dc827dbbf5b1c2f4895fe7130b1a6473e2b` |
| `claude/tirante-mensik-2026-08-20` | `71db45cf608babf10f5c2ee6d53142a4c901c80a` |
| `codex/ci-signed-url-scan-fast-20260821` | `06a8ca5332eed5223994f8d7212b5a106d8e07d4` |
| `codex/fils-tirante-final-20260821` | `cb813377fad3eb5591709b96b801b4b1eeebdae6` |
| `codex/fix-pipeline-health-cancelled-runs-2026-08-24` | `2b054de0387a77c207d00fa7f19700bdfe378394` |
| `codex/swiatek-rybakina-cincinnati-2026-qf-interview` | `4f442889b825a11792803ff6183188102561a3c9` |
| `feature/us-open-men-2026-preview` | `6d8cc740d6072ec072edb389fb45762530459cce` |
| `fix/interview-request-font-preflight` | `4da6e043ea45e24465ee44a1425ac6d8e48ea0a4` |
| `fix/interview-ytdlp-ejs` | `b2d57b436f4afe45ab57536d1482e6def0ec7728` |
