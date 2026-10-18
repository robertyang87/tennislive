# 武汉决赛制作续接

当前分支：codex/wuhan-2026-final-reel，根目录 /workspace/tennislive。准备内容尚未提交；没有正式渲染、合并或推送，不可称成片已完成。

## 用户最终内容要求

- 用户视频 https://www.youtube.com/watch?v=HIvIvgwXkqs ，武汉WTA1000女单决赛。
- 封面明确选择武网官方1725-02，并最新要求居中裁切铺满画布；已渲真实封面cover-review/cover-final.jpg，spec使用原始照片focus0.46/zoom1，用户选定亲杯侧脸闭眼照，不自行换图。原图1920x1281，按指定3:4需1.124倍，_low_res_why与credits已如实记录。
- 全部受众内容用赫瓦林斯卡，不再用月亮姐。内部owner原话历史字段可保留。
- 用户明确要求正文和TTS加入首个WTA巡回赛单打冠军就是1000赛冠军，不向观众补ITF/WTA125说明。
- WTA官方：2009赛制以来第4位；此前大坂直美2018印第安维尔斯、安德莱斯库2019印第安维尔斯、姆博科2025蒙特利尔。正文已列赛事；actual TTS已列前三人和第4位。

## 当前输入状态（原问题已异步发出）

1. 本期实际约120.504秒9段旁白核听；已完整发成可播放音频。请等待用户明确答复，不用重复问或宣称听过。音频 /workspace/scratch/wuhan-final-listening-review/actual-narration-review.mp3，SHA d672e04799696c73df5251fed08770e321db91721587bf74070ef1f8f5c94fec；其9段原输入映射见 voice/production/owner-listening-request-map.json。仅品牌复用上期用户核听证据；8段新口播未获得本期owner确认。机器已做完整双ASR/42声学尝试，0确认错读，19中高支持，32待核；不把unknown改pass。
2. 720p已经用户2026-10-18原话「可以用 720如果可以完整展示内容的话」明确批准。本条精确Release URL白名单和spec范围已记录；见source-quality-approval.json。此答复只关闭源清晰度问题，不代表核听通过。

## 已冻结且可直接复用

正式spec specs/reels/chwalinska-kartal-wuhan-2026-f.json；16段，按真实配音收紧卡片后约332.15秒（5:32）。正式narration文本已冻结，不为画面修改重合成。

主1080p官方短源：/workspace/scratch/HIvIvgwXkqs.mp4，305.295964秒，1920x1080/25fps，SHA f0a8d9d5262a63af26695207e345a2e62f32cc3604e05490d9208925c61af8c3。
https://github.com/robertyang87/tennislive/releases/download/source-HIvIvgwXkqs/HIvIvgwXkqs.mp4

补片720p官方长源：/workspace/scratch/wuhan-final-extended-release.mp4，467.68秒，1280x720/25fps，SHA b12a62ce71598faba8b69addc733e5b0682c8dc5f867935674c53b3418b165ad。
https://github.com/robertyang87/tennislive/releases/download/source-6407050487112/6407050487112.mp4
官方WTA video4593997/Brightcove6407050487112；已两次核全部formats最高720p。不得把conform放大说成原生1080p。

实际生产TTS9requests（8新口播+品牌），云健+6%/+0Hz，edge：
/workspace/scratch/wuhan-final-tts.zip ，751095B，SHA 2414de29cc3083bf79d08dc11e33ef22100671bd96605d8dd0fddc4ab34bf9d9。
https://github.com/robertyang87/tennislive/releases/download/reel-tts-chwalinska-kartal-wuhan-2026-f-2414de29cc3083bf/tts_bundle.zip
canonical data/narration_checks/<slug>.json已记录公开URL/hash，正式render可自动strict_import。native实际预检全装得下，最终旁白20.976秒包含新增事实/三个人名。保留同ZIP，避免云端重新合成。

本地uploads.github.com401，本期已用临时draft Release notes+隔离单runner桥传原ZIP，公开下载原SHA与原字节均复核；没有音频或base64进git、没有重合成、17个临时draft已删，临时worktree/branch也已清理。审计voice-review/frozen-tts-transfer.json，最终run39140882386；首失败39140782286缺不必要ffmpeg依赖，如实留记录，不声称首趟成功。

## 事实与画面

官方LS001赫瓦林斯卡2-6 6-4 6-2卡尔塔尔，02:43:05；正式10/12周榜赫22/卡170；二者POL/GBR，种子赫16/卡非种子。开球实际首分未获官方PBP（404），FS/ESPN约北京18:35–18:40，旁白只说北京时间10月18日晚上，别冒认metadata为首分。

FS完整182分重建与WTA总分91/91、BP16/13、比分一致。W/UE赫23/27，卡32/36，全部来源与hash已落fact-packet/point-by-point。新一周首进Top20有官方QF稿证据，不编精确新排名。

根与视觉代理均实际看全两源4秒墙；细查证据visual/visual-review.json、visual/targeted-boundary-review.json。
- 主32.44–61.2首盘1-4长点TTS；61.2–85.12完整首盘盘点纯原声。不能同段TTS+原声quote。
- 补222.08–265.12次盘3-3第4BP，赫兑现4-3。初看卡近景误判救回已撤回，正式按FS/WTA正确结果，不因近景/未翻牌判断胜负。
- 补265.12–296.28是4-4完整可用发球动作→点死球。不要用YT115.76（已在抛球），也不要以固定offset把补片剪到298.24（会截下一分活球）。补源省略了更早持球前摇，不能冒称完整等价YT全部准备。
- 主146.56–158.64完整第二盘盘点，整体舍弃158.76后未确证句头原声；不捏英语。
- 补324.16–330.48决胜2-2破发完整点和第一句And she gets some help。330.76后第二句整句不使用，不强改blanks为blinks。
- 补387.12–399.48末局第3BP完整发球与回合。small/base.en无英文，turbo低p模板Thank you已按三档上下文判作ASR artifact，留raw不造谢谢字幕，不切发球来避幻听。
- 主178.28–225.44完整第三赛点（含首发失误+重发）、倒地、握手；冷开195.84–201.4，只用赢后首句完整英语。
- 主227.04–246.64团队庆祝，score_inset=false，真实无原生板，不贴看台补丁。
- 0-2、前2BP/前2赛点两源无完整画面，仅内部说明、受众事实解释，不拿别点冒充。

10个原声窗口/27条双语cue及index已完成，reel_review_files --require-review --rebind-plan --stage通过11JSON；raw ASR和关联source-level reports也需最终提交，别只提交已stage的11文件。每个packet绑定原源SHA；不做响度/RMS/静音/原声增益检查，不假称听审。

主probe已按相同SHA真实5fps标定搜索框90,826,550,980；补probe在output/2026-10-18/reel/<slug>-extended/probe.json，用渲染相同conform1920x1080再扫描，全467.68s/2338帧。原始probe几何仍如实1280x720。自定义框calibration/production_preflight/开场北京时间坐标test/copy19字5tag全pass；静态polyphone零提示不是声音通过。实际声学证据voice/production保留，不改unknownpass。

## 后续执行与已闭合授权

- 若接受720p：在tools/build_match_reel.py的APPROVED_LOW_RES_SOURCES只加本片精确Release URL:720，spec.source_quality_exceptions按现有schema min_height720/approved_by user/reason真实用户原话；保留原生尺寸，不能全局放低清。只运行相关既有tests/test_reel_source_quality_exception.py及目标checks。若不接受720p，按既有HD源＋原生事实卡改方案，不能偷用这4窗。
- 若确认本期听过自然：写owner-listening-review.json绑定上面实际review audio/9inputs/bundle/raw reply，品牌沿用旧exact bytes。不要把机器unknown文件改成pass。若指出错读，限改相关原句并只重审新音频，其他exact inputs复用。
- 得到所需答复后，跑一次完整当前cheap preflight/taste/selected CI scope；预览真实ASS（含本期实际包），检查新冠17格子句的实际自然拆分，不因离线warning盲目重合成。所有视频固定cx0.5/trackfalse全屏3:4；封面按用户最新铺满，勿恢复canvas。
- 正式spec/所有证据/原图与copy提交新PR（目前没有本期PR），branch push，dispatch native match-reel render push=false，严格导入2414原包。完成实际film SHA/Release/QC全绑定、实际抽帧核验、当前HEAD CI绿后自己合并→自动PushPlus→真实pushed.json/ledger sent回执，完整流程不再问发布许可。
- 不stage voice-review/tts-seed-cache里的MP3/marks缓存，不把zip/mp4进git。所有源片/音频/成片走Release；本期tinyJSON/JPG证据按路径纳入。

## 本轮720p批准后的实际预览发现

- 已写精确URL的720p批准，13个既有源质量测试和production_preflight通过。
- 用冻结2414包严格复用9段音频，完成16帧自动+8帧手选原生ASS预览；首冠成就语义分句、人名不拆开、蓝卡与封面通过实际视觉检查。
- 正式render之前发现补源比分板回贴裁成左上半，真实原帧及预览manifest见caption-preflight。根因是WTA蒙版扫描未走conform，FFmpeg将超出native720高度的crop位置静默夹回。交source_audio修实现及缓存transform身份；修后必须重新实际预览补源四窗，不把首轮失败报告覆盖为通过。
- 本期编辑终审editorial-final-review.json无文稿阻塞；XHS列前三人具体赛事，TTS有三人姓名及第四位，用户并未要求将所有赛事年份也念入视频。

## 当前已提交与正式渲染

- PR https://github.com/robertyang87/tennislive/pull/1300 ，branch codex/wuhan-2026-final-reel，head cf92fb3a。已rebase当时main e6edee1c。
- WTA/cache/conform适配119测试通过；补齐CI所需历史output文本后完整test_match_reel395通过（首次稀疏检出不足15fail记录保留在scratch，不误称本期制作问题）。
- 修复后的12帧原生预览完成，root已看四窗完整两行名字与比分、点头提示条。fixed-root-review/manifest/sheet及独立代理报告留caption-preflight，首次失败原帧保留。
- 正式render已派39143852218、head cf92fb3a、push=false、冻结2414包。当前未完成，不合并或推送，尤其新旁白核听仍pending。
- 新增fixed预览/修复报告在本地未提交，等runner回写正式产物后一起提交最终审片证据，避免渲染中改变branch。

## 必须优先处理的新反证：盘点原窗截在活球

- 已取消正式run39143852218，GitHub确认completed/cancelled，仍在checkout阶段，未形成电影/发布。
- 独立原25fps反证：158.64仍在回合末球未落地，旧完整结论明确撤回。见caption-preflight/preview-review.json及boundary-correction原PNG。
- 最小画面方案保主1080p146.56–161.60，完整SP/死球/赢后反应与两句英语。long同点296.28–308.84可完整保动作，但同样有歧义解说，不能冒充无英文替代。
- main158.76首句各4档及同源long两档均有不确定句头。末次main154–162只给两人专名context，turbo只出Ska seals the deal. Why not?，不能据此写已核Chwalinska。有限ASR已停止，3新raw+second-set-point-boundary-correction留证。
- 已对话播放4秒原声157.60–161.60并异步询问用户句头，问题已发不要再问；实际clipSHA/源映射见source-english-listening-request.json。
- complete-point-pending-spec.json是具体新完整窗草案，尚未替换正式spec/packet/index，避免把未知声音错记pass。原正式spec现已明确被此反证阻止继续render/合并；绝不能派旧spec重渲。等用户核准句头后落准确两条双语cue、更新packet为新完整窗、rebind index，再原生预览和正式render，冻结TTS不变。
- 同时仍待120.504秒本期新旁白用户核听。两项都是真实发出的核听，不用720p回话代答。

- 最终已将正式spec和script的已知错误切点修正到161.60；second_set_point packet如实改为pending并记录uncertain_spans。旧index不冒认当前音频计划通过，原生gate将阻止渲染，直到用户核准句头并补两条完整双语cue后用工具rebind。complete-point-pending-spec与正式spec保持当前同字节，方便审查具体修改；上述“尚未替换”是此前步骤历史，已被此条取代。
