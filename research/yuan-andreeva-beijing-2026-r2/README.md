# 袁悦—安德烈耶娃，北京2026第二轮：重做事实与封面证据

正式稿：`specs/reels/yuan-andreeva-beijing-2026-r2.json`，由Codex全新重写。用户明确禁用DeepSeek；此目录旧草稿只供错误审计，不能进入自动候选或生产。

## 已核实比赛事实

2026年10月2日，中网WTA1000女单第二轮（64强），钻石球场室外硬地。袁悦以6-3、0-6、0-6不敌4号种子米拉·安德烈耶娃，官方比赛用时1:52:38。袁悦当前排名135、安德烈耶娃5；4号种子不能写成世界第4。来源在`facts.json`，全场官方发球统计原始数据在`raw-stats.json`。

官方stats接口未提供制胜分与非受迫失误。TNNS runner查询10/2取得246场但按两人姓名未匹配，本机浏览器又遇人机验证；这些结果不能证明本场统计不存在，也不能填零或猜测。

## 已纠正封面人物错误

中网本场赛报（`https://www.chinaopen.com/cn/contents/281/1624.html`）唯一正文图`827ac52c284cb630.jpg`确为本场实拍，但黑裙、绿色帽球员是**安德烈耶娃**，不是袁悦。此前“袁悦黑裙”的claim错误，已移除；赛事、日期与EXIF匹配只能证实场次，不能证实人物。袁悦本场穿薄荷绿裙。

错误生产asset `assets/reel/yuan-andreeva-beijing-2026-r2-chinaopen-official.jpg`经全部spec引用检查后删除。旧draft移至`discarded/yuan-andreeva-beijing-2026-r2.draft.json`，标明discarded并移除旧portrait生产引用；不再位于`specs/reels/pending/`。历史错误URL仅保留在rejected evidence，严禁复用。

## 曾采用的抽帧（已按用户高清要求替换）

`assets/reel/yuan-andreeva-beijing-2026-r2-yuan-frame-132.80.jpg`，WTA本场官方视频原生1920×1080的132.80秒帧，薄荷绿裙袁悦偏正面、双眼睁开。此帧记分条为Y.YUAN 5 Ad、M.ANDREEVA [4] 3、SET POINT #2，提供本场阶段证据；人物需结合脸、源片18–27秒与官方头像核对，不能仅凭绿帽认人。封面裁切需避开记分条，人物脸避开标题带，最终渲染由主agent检查。

依据`CLAUDE.md`2026-09-26 owner established授权：“如果没有高清大图可备选的话，抽帧也可以，但是要尽量清晰偏正面的图片”。正式spec记录了`_frame_why`、`_low_res_why`及原视频hash，完整照片与帧溯源在`cover-photo-evidence.json`。

WTA照片接口按袁悦id全48条最新仅9/30首轮；WTA photo-resources、赛后稿头图、AP成功检查后无本场袁悦匹配。中网文章唯一图是对手；WP接口404、中文微信正文403、北京当地报纸未配置属于受阻/未跑，结果未知，不能宣称全网不存在。此次采用抽帧是已检查源没有可用本场实拍的生产fallback。

本文件不声明最终视频已验证、已渲染或已发布；这些状态由主agent最终检查决定。

## 最终高清封面候选

用户10月2日追加要求“封面换高清大图”，故不用抽帧。采用WTA官方2026克卢日站袁悦动作资料照，3280×2183，photo id4443690，Petean Calin Florin/WTA；2月3日为API发布日期，实际拍摄时刻未知。并非本场摄影，正式文案如实说明为本赛季资料照。2026北京第二轮Getty确有袁悦6000×4000照片，但公开预览带水印，没有获取原图。高清检索范围和候选来源分别见hd-cover-search.json及hd-cover-candidates.json。
