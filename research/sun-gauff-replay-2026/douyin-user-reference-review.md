# 用户补充抖音线索核查

输入：[认蒸你就熟了的分享短链](https://v.douyin.com/HV_ciaXMyAw/)。实际落地视频 id `7693204834988694441`。网页直接版触发 JS challenge；[抖音精选公开页](https://jingxuan.douyin.com/m/video/7693204834988694441)能够读取完整公开 metadata 和下载媒体。

## 身份及媒体

- 作者：认蒸你就熟了，公开作者 id `96789449890`，不是赛事/巡回赛/球员或转播官方账号。
- 发布：2026-10-05 15:23:54 UTC（北京 23:23:54）。
- 时长：33.6 秒。
- 已实际下载 768×576 H264 与 1440×1080 H265 两档，24fps；后者仅约 527kbps，是平台 rendition，不能据输出尺寸宣称原转播高清。
- 原片：`/workspace/scratch/sun-gauff-replay-2026/douyin-user-reference.mp4`、`douyin-user-reference-1080.mp4`。
- 完整 metadata 在 scratch `douyin-user-metadata.json`，仓库精简 provenance 在 `douyin-user-reference-provenance.json`。

## 已实际看的视觉内容

使用 ffmpeg 按每 2 秒抽整条原片并查看 contact sheet（`douyin-contact.jpg`），全部为孙心然坐在椅子上的连续近景：低头、擦脸、喝饮料、再看向场边。

这条 **没有** 以下画面：5-4/15-15 原分完整回合、LED闪动、向裁判申诉、裁判回看、宣布恢复比分、重打完整回合。不能由此补原分事故动作，也不能用作者标题代替本人心理解释。

标题中“高芙玩不起”“重打直接把节奏打没了”属于作者的观点和因果解释，不是经视频证明的事实。近景没有可读比分板，单靠它不能确定处于哪一局；第 11 局被破之后的坐标仍由其他原始媒体证据和孙本人解释支持。

ASR 试验：faster-whisper small.en 对 ffmpeg 解码的 16kHz 单声道浮点音频做英文/VAD 转写，结果空数组；这只是一次算法结果，**不是人工听审**，不能据此说原片没有声音或解说。没有从该算法提取可使用的裁判原话。

## 追到官方广播画面

新找到 [Sky Sport 本场官方公开集锦](https://sport.sky.de/tennis/artikel/gauff-bezwingt-16-jaehriges-wunderkind-in-peking/13595497/37577)，自有 Sky Sport 网站、Brightcove 正式账号 `6058004230001`，媒体 reference id `8c31da6f-f3ee-47d1-8967-da31340f41f8`，metadata `AD_SUPPORTED`，2026-10-05 15:55:22 UTC 发布，时长 90.837 秒。

- Progressive MP4最高720，实际取HLS master最高 **1920×1080/50fps**，下载完整视频和外部音频后无重编码封装。
- 文件：`/workspace/scratch/sun-gauff-replay-2026/sky-highlight-1080.mp4`（H264视频 + AAC音频，已 ffprobe 确认）。
- 仓库 `sky-highlight-provenance.json`、`sky-master.m3u8` 保留官方来源及档位证据。
- 实看全源每 5 秒 contact、17–40 秒每 1 秒 contact：约 **34–38 秒**有孙坐椅低头、随后蓝毛巾擦脸的原始近景，人物、服饰、椅背、毛巾动作与用户抖音相符；这段可用来追原画面。
- Sky精剪没有完整LED申诉/回看序列。17–23秒是另一回合及高芙近景，24–30秒为高芙赢首盘的SET POINT回合；不能拿它们充当5-4的LED事故。
- 官方广播来源能否按本项目“官方素材”规则作为正式成片源，由主制作按当前授权/项目规则判定；非官方抖音不会自动替代官方来源。

## 给制作的结论

用户参考确实帮助追到了同一真实情绪近景的正式广播1080来源；没有帮助补齐原分事故。原分仍按已互证事实解释；泪水仍尊重孙本人“看到机会从眼前流失”的解释，不把作者的“委屈/玩不起”说成事实。


## 追加：新浪聚合不能当主办方回应；真正事故研究片

[中网 ChinaOpen 新浪聚合](https://www.sina.cn/news/detail/5350809453724560.html)顶部是认证中国网球公开赛官方微博发布赛果，其后的多作者推荐卡片分别属于其他作者。检索片段把底部“回放下看看”与官方标题连在一起，不能认定其为官方回应。

[AXWrxZeC](https://t.cn/AXWrxZeC)最终指向 `1034:5350804031471716`。[公开 H5 页面](https://h5.video.weibo.com/show/1034:5350804031471716)及 API 核明真实作者 `Tennis欧阳文升`（UID `1727918390`，认证为体育博主/体育视频博主），正文 ID `5350805252604520`，时长 185.712 秒。下载 `/workspace/scratch/sun-gauff-replay-2026/weibo-ouyang-incident.mp4`；H264 1844×1080、AAC，源带微博作者水印。该视频只作研究参考，未找到官方发布者或正式广播台标公开溯源。

已视看每 5 秒 contact 与关键区每 1 秒 contact：

- 0–约 18 秒：高芙局分 4、孙心然 5，15-15 的原回合。
- 20–60 秒：高芙靠近主裁交谈。
- 65–70 秒：`VIDEO REVIEW IN PROGRESS`。
- 85–102 秒：原回合录像回放。
- 110–130 秒：主裁说明，孙心然来到裁判椅前交谈。
- 145 秒后：球员准备恢复，随后高芙和主裁再交谈；片内没有重打获胜分全回合。

另一 [AXWrIhDE](https://t.cn/AXWrIhDE)最终指向 `1034:5350801573609489`，作者 `毛毛还活着-TennisAlive`（体育博主/微博原创视频博主），时长 32.832 秒。下载 `/workspace/scratch/sun-gauff-replay-2026/weibo-tennisalive-slow.mp4`，1920×884 带作者水印，后段人为慢放/放大，不能认作原生完整 1080 官方广播。

**申诉时机必须保留边界：** TennisNow写丢分后成功申请复核；[Tennis365 当日报道](https://www.tennis365.com/tennis-news/coco-gauff-china-open-controversy-novak-djokovic-stupid-rule)描述回合末在孙即将得分之前停止。慢动作 28.4 秒静帧 `slow-end-08.jpg`可见孙远端追球、伸拍与球仍在拍前，高芙在网前已举左手朝裁判。此证据足以排除“输完整分后才首次举手”这种确定措辞，但没有人工聆听原声，不断言当时已口头叫停，举手与正式复核请求也需要区分。推荐成片事实表述：**回合末高芙举手示意，随后提出 LED 干扰审查，VAR 确认闪动后判重打。**

## 追加：Sky 来源归档和音轨

原 master 只有 `de (Main)`/`audio-0`，没有备用纯现场音轨。production_setup对完整音轨 tiny/base multilingual交叉识别为德语，擦脸34–38秒也有德语播报；因此不能剪去解说后称纯现场。原音直接使用或改用确实无解说的窗口须依项目音频规则审查。

原生1080混合源 SHA256 `1d2a70a9dc082b14ccf9c8f0149dd7163159e3c1c1dcffa89a301d68bcf88a68`。Sky 网页原 URL 被 yt-dlp generic extractor报 Unsupported URL；Brightcove数值 ID公开播放器 URL识别成功但缺网页Origin遭domain policy403。用 yt-dlp原生 `smuggle_url`携带 **公开 Sky网页 referrer** 后完整解析成功（只正常浏览器来源头，无token或认证），输入 URL存scratch `sky-ytdlp-referrer-url.txt`。正常 `download-video` workflow 已发，保留run `37367984697`；runner实际下载MP4必须重新测SHA并绑定，不能复用本地remux字节hash假定一致。所有签名metadata/m3u8已移入scratch；Git provenance只保留公开网页、account/id和实际字节hash。

Sky17–20秒比分已5-5、15-15；24–29秒高芙6/孙5、40-0 SET POINT。20–32秒不是事故5-4那分，更不能声称是该分重打。34–38秒擦脸属于第一盘失利后的剪辑情绪片，不能剪成事故即时反应。
