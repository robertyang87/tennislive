# 谢尔顿 NCAA 一期交付记录

- 栏目：网球时差 · 网球有故事。
- 用户已确认最终修订版，并于 2026-09-14 授权资料归档、合入主线和沿用既有网页模板推送微信。
- 最终视频：1080 × 1440，329.761 秒，24 个叙事段落及品牌片尾。
- SHA-256：`6b72456490ef8210664938c10c24ddad8a1cdcceaf102982f98d30ed6cb8ad63`。
- 文件名：`explainer.mp4`，发布目标为 `explainer-shelton-ncaa-story` Release。
- 旁白与出处：`docs/shelton-ncaa-story-production.md`；素材来源与时间窗：`assets/explainer/shelton-ncaa/credits.json`、`media-sources.json`。
- 成片未放入 Git。当前待上传经用户确认的同一份视频至 Release；尚无微信发送回执，不得标记为已发送。

## 已修正的呈现问题

1. 两处 2022 年改用年份数字输入重新合成，避免旧读音缓存。
2. 字体缺少全角斜线，将其替换为“和”“及”“或”；图卡字符覆盖和文字边界检查通过。
3. 所有绿色标签去掉页码和章节数字，避免连续两组编号。
4. 上半图文区域加高约四分之一，说明文字同步放大。
5. 使用现有满版封面作为开场，保留原字体、品牌条和标题。
6. 照片动效只作用于图片区域；顶栏、字幕和讲解文字不可参与整页缩放。24 页共 72 个顶栏采样与原图比对通过。

## 网页模板与发送步骤

交付包复用 `knowledge_push_html_from_parts` 与 `to_copy_page`，包含封面、图卡、完整视频入口、可复制标题和正文。

上传 Release 后，校验视频 SHA-256 和下载链接；确认 main 上 copy.html 可达且为本期；再启用标准 explainer 发布流程。发送前预占账本，发送后保存 pushed.json 与回执。接口成功仅代表服务接收，不等于手机实际送达；状态不明时禁止盲目重推。

### ⚠️ 2026-09-14：那条一次性的 `shelton-ncaa-delivery.yml` 删掉了，发送走标准链路

上面这段「再启用标准 explainer 发布流程」落成了实际动作。原来那条专用工作流把
渲染 + 上传 Release + 发微信三件事自己又写了一遍，**而它违反七条既有判据**
（装 Chromium 没有超时／重试前不等 dpkg 锁、apt 那一步没有缓存也没有 ≥15 分钟的
预算、`git commit` 没有体积闸、提交者写着 Codex 而不是 Claude、发微信那一步的 step
`env` 里拿不到 token 所以 `trigger_pages_build` 会直接跳过）。

⚠️ **而这七条红一次都没露过面**：那条 PR 的 head 是工作流自己用 `GITHUB_TOKEN`
推的提交，GitHub 防递归不给它创建 workflow run，`get_check_runs` 返回
`total_count: 0`——**和「CI 还没起来」长得一模一样**。于是 PR 就那么开着，
`push-wechat` 那个 job 因为只在 `main` 上触发，一次都没跑过，**片子渲完、Release
传完、微信一个字没发**。这正是 CLAUDE.md「渲染那条提交是测试看得见的，而它永远
拿不到 CI」那条的实例。

现在的形状：

| | |
|---|---|
| 渲染 | `python tools/build_shelton_ncaa_story.py` → `python tools/check_shelton_release.py`（本地或手动 runner 跑，**没有专用工作流**） |
| 成片 | Release `explainer-shelton-ncaa-story` 的 `explainer.mp4`；`render.json` 的 `video_sha256` 就是判据，本地拉回来比过 |
| 发微信 | **`auto-push-explainer.yml`**——它盯的正是 `output/*/explainer/*/narration.json`，而本期交付包里就有这个文件，合进 main 即发 |
| 认领 | `src/tennislive/video/explainer.py` 的 `AUTO_PUSH_SLUGS` 加 `shelton-ncaa-story`（那儿写着验过什么） |

⚠️ **这条片子不是 `_SCRIPTS` 产的**（脚本在 `build_shelton_ncaa_story.py` 里），
而 `AUTO_PUSH_SLUGS` 只管「准不准自动发」，和谁渲的无关——两件事别混。
