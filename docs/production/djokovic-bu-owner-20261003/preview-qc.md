# Djokovic–Bu 本地画面预览 QC

结论：18段共26张实际原生画面预览与封面已目检。英语字幕均可在1080×1440画布内完整显示；固定居中取景与比分回贴正确。原统计卡字幕遮挡问题已由主代理修改 `stat_card_full_canvas:true`，新版原生分支实际渲出并目检通过。未试听任何音频。

## 方法与范围

使用当前 worktree 原生 `parse_segments`、`cut_segment`、`cut_still_segment`、ATP逐帧蒙版、`write_subtitles`、`write_topbar_ass` 和 `topbar_scrim_source` 输出实际1080×1440画面；封面由 `render_cover_local.py` 渲出。每段选取代表位置，英语quote严格使用spec声明的cue起止与文本。中文旁白字幕为了画面布局预览按原生subtitle_cues在段长内分配，其采样时刻没有使用TTS边界，不作为最终语音同步证明。这里不是整片渲后QC，不覆盖溶解/混音。完整原始文件只读，spec未由本代理改写。

CLI核查：build_match_reel只有probe/render及dry-run/check-narration/cover-only；preview_segments_local只看源片缩略图，不包含字幕布局。因此本次直接调用上述真实生产函数。

## 目检结果

- 封面 `cover.jpg`：官方本场德约庆祝照，睁眼微笑、右拳高举、左手持拍；标题已为“首盘4比6落后 / 德约3盘逆转小布”。名字、三盘比分、抢七上标、2:52均清楚。高举拳头略接近上方品牌台头，是照片自然构图，不影响面部和胜利情绪。
- 固定居中：所有比赛段 `cx=0.5`、track=false，源810×1080居中窗口放大至1080×1440，无横摇、contain黑边或新增模糊背景。边线跑动时部分人物/球短暂出画属于锁定构图；未擅自改动。
- 比分回贴：代表帧板位于左下y≈1227，上方字幕底边约1203，至少24px间隔，名字与列没有字幕盖压。源转播撤板的近景预览中不贴假比分。比分画面对应源帧，晚段布0、德约3/AD与赛点布2、德约5/40正确；局分滞后不凭画面宣布布破发。
- 双语宽度：1-based第14段（0-based13，“How has he won that point?”）中英单行均在安全横向范围，英语没有截断，中文字幕完整。第12段长句“It’s a lightning quick start from Novak Djokovic.”同样完整。第6段超长英语被原生自动折成两行英语+一行中文，三行文本整体仍在板顶以上，没有横向溢出。第17段末句英语两行+中文一行，完整且不遮网前双方上半身。
- 统计值：左布、右德约，43%(13/30)对73%(27/37)，W/UE31/20对40/30；数字归属正确。旧 `segment-15-01.jpg`保留问题证据：普通旁白字幕横压二发英文标签/破发转化行，普通topbar重复卡头。父代理已修复为full_canvas。
- 新统计页 `segment-15-full-canvas.jpg`：重新读取修复后spec、原生materialize statcard、cut_still_segment，再通过真实 `full_canvas_filtergraph` 恢复原始卡画面。已确认统计页没有普通topbar与字幕层，二发中英文标签、43与73、分母和破发行清楚；音频由生产路径独立保留，本代理未听。证据 `stat-full-canvas-verified.json`。
- 章节卡：第2段“172分钟 才赢下的胜利”与第18段“胜负之外 每球必争”主文字、kicker、底部账号信息与旁白字幕位置相互让开。父代理后续若改文案，应在成片复核。

## 文件

- `frame-manifest.json`：26张代表帧的源时间、段内时间、实际字幕和比分是否存在。
- `segment-01-01.jpg`至`segment-18-01.jpg`：代表画面；部分段有02/03图。
- `contact-1.jpg`、`contact-2.jpg`、`contact-3.jpg`：26图联系表，含旧统计页仅供追溯。
- `cover.jpg`、`stat_card.jpg`、`title_card_02.jpg`、`title_card_18.jpg`：原生独立资产。
- `segment-15-full-canvas.jpg`：修复后的真实统计页预览，为本次通过的统计页版本。

当前画面预览无新增阻断问题。仍需生产成片检查实际TTS字幕同步、音频完整句、转场与最终编码。
