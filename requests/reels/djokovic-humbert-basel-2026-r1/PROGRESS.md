# 德约对安贝尔，巴塞尔2026首轮 · 赛场之上

用户指定：https://www.youtube.com/watch?v=MwcZYYG4hvE 。追加：内容丰富一点，字卡的时间少一点。正式slug `djokovic-humbert-basel-2026-r1`，分支 `codex/djokovic-MwcZYYG4hvE-reel`。

官方签表4-6 6-3 6-4；逐分188分与总分99/89一致，逐盘44/50/55分钟，全场2:29。首盘先丢发球局，次盘首局救2BP后破发，决胜盘2-2破发并守住领先。现原生spec约4分钟：多个完整关键分、准确双语原声，独立统计卡6.8秒，封面1.2秒，无长章节字卡；末尾6.8秒本场高清实拍配下一轮具体问题。

源片50fps 1080p，原生生产入口按现有规则整除到25fps，非伪称源生25fps；SHA83bd85e40b84f88ef603d25e298fd89c924011db66efd325a39479c7ab96b1ce。原始probe/存档/ASR run均在request.json。正式probe使用同一Release字节和实测定制比分搜索框98,920,488,1030，5fps全片量板1257帧。

封面本场官方ATP Media照片接口/Getty#4600358，IPTC和EXIF/比赛时段核对。证据evidence/cover-preview.jpg已实际看过：双眼正脸清晰，文字不遮脸，比分方向正确。完整原声核对方法asr_cross_checked，实际人工听审false，所有引用绑定原始small.en/medium.en的源SHA；原生foreground gate已过，不冒充人工听审。

本地Edge云健+6%实际旁白全部装得下，13请求快照SHA60c6f9e7d0dd6dce17a951d6983979ded2d93357d046d78beb57194255f752f9。此后删除1个普通回合旁白，现请求子集；最终由原生narration job重新捕获并发布最终快照，再严格导入render，不把本地未上传ZIP当已发布。uploads.github.com当前401；不导出凭据、不关闭TLS，走原生runner。空的reel-tts-djokovic-humbert-basel-2026-r1 Release为本次创建、待清理。

W/UE为Flashscore Match原行19/39及24/39，双方完整证据与列序已入spec。发球分母合计190与逐分188不同，保留供应商原行，不用这些分母推总分。另一个自动pending/djokovic-humbert.draft.json是同场TennisTV短源未完成草稿；本期已接手用户指定YouTube源，正式片不可再同栏目重复生产。

剩余：原生narration快照、真实voice auto suite、正式render、成片/QC/字幕抽帧、当前HEAD选择范围CI、合并、PushPlus及pushed.json；没有这些不称成片完成或发布。
