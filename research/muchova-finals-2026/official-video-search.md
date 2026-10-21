# 穆霍娃2026晋级总决赛：官方视频补全

本文件只记录源片与有限抽样检查，不代表最终剪点、完整听核、双语字幕、配音或成片QC已通过。全部文件参数与SHA-256见 `official-video-candidates.json`。原始MP4保留本地，不提交进Git。

## 已实际取得

| 节点 | 官方来源 | 本地文件 | 检查结果 |
| --- | --- | --- | --- |
| 3月24日迈阿密1/4决赛 | [WTA集锦4475905](https://www.wtatennis.com/videos/4475905/muchova-edges-past-mboko-in-two-tight-sets-to-reach-first-miami-semifinal)，Brightcove6391563293112 | `sources/videos/miami-muchova-mboko.mp4` | 已下载官方MP4，1280×720；尾段记分条V.MBOKO/K.MUCHOVA、穆霍娃白色Adidas橙色发带与用户图片对应，赛点庆祝及握手已抽样核；无本人采访。 |
| 4月18日斯图加特半决赛 | [WTA官方YouTube](https://www.youtube.com/watch?v=2uXyDSE58NU) | `sources/videos/2uXyDSE58NU.mp4` | 1920×1080，310.03秒；画面记分条Svitolina/Muchova及终场6-4、2-6、6-4匹配；尾段无本人采访。 |
| 4月19日斯图加特决赛 | [WTA官方YouTube](https://www.youtube.com/watch?v=cu2BtcEjWww) | `sources/videos/cu2BtcEjWww.mp4` | 1920×1080，309.75秒；runner真实标题匹配，250秒起尾段记分条E.RYBAKINA/K.MUCHOVA、冠军点及终场7-5、6-1已抽样核。个别短反应/切场镜头出现浅蓝衣对手，与决赛主镜头不一致，不能盲剪整个尾段，逐帧核后择用。 |
| 6月27日巴特洪堡冠军回顾 | [WTA Champions Reel](https://www.wtatennis.com/videos/4527848/champions-reel_-how-karolina-muchova-won-bad-homburg-2026)，Brightcove6399578560112 | `sources/videos/bad-homburg-champions.mp4` | 1280×720，501.12秒；360秒起为决赛Muchova/Osaka，486秒后实际颁奖，494秒附近举起大象奖杯，498秒附近亲吻奖杯。候选486–500.5秒；最终剪点、原声待审。 |
| 7月9日温网半决赛 | [Wimbledon官方YouTube](https://www.youtube.com/watch?v=dHmXLHG5hQc) | `sources/videos/dHmXLHG5hQc.mp4` | 1920×1080，666.83秒；Muchova/Gauff记分条、赛点、双方拥抱匹配，末段没有本人说话采访。 |
| 7月11日温网决赛 | [Wimbledon官方YouTube](https://www.youtube.com/watch?v=XfE9M6__724) | `sources/videos/XfE9M6__724.mp4` | 1920×1080，255.40秒；Muchova/Noskova记分条匹配；尾段捧冠军盘的人是诺斯科娃，不能误标为穆霍娃冠军。无穆霍娃亚军发言。 |

多哈主线程已从本库既有Release取得 `DMpp-l1vBaA.mp4` 和 `doha_trophy.mp4`，以主线程记录为准。

## 赛后采访新增需求

- [WTA冠军本人回顾：This is how I won Bad Homburg](https://www.wtatennis.com/videos/4528760/this-is-how-i-won-bad-homburg-karolina-muchova-on-a-memorable-week)，Brightcove6399808507112。已实际下载 `sources/videos/bad-homburg-winners-feature.mp4`，1920×1080、165.28秒、有音轨。约90秒抽样可见本人白T坐在奖杯旁对镜说话，其他部分有比赛画面。属于夺冠后回顾，不冒充场上颁奖发言。引语、语境、准确窗口及字幕由采访代理继续核验，当前pending。
- [Tennis Channel官方X颁奖发言](https://twitter.com/TennisChannel/status/2070815009106460975)：6月29日HerSportsNation报道嵌入相同链接，称其为穆霍娃6月27日感谢现场高温下球迷的发言。目前只发现链接，未下载，不视为可剪素材；已转交采访代理。
- 温网本人亚军发言与多哈本人夺冠发言由 `interview_excerpts` 代理继续查独立官方视频；不能因为比赛集锦中没有，就写成官方未发采访。

## 错误候选已排除

Tennis Canada [3月24日Muchova-Mboko赛报](https://www.tenniscanada.com/news/pro-tennis/2026/mboko-troubled-by-muchova-again-in-miami-open-quarters)嵌入的 `m_tBjmZeVqs` **不是这场比赛**。实际归档标题是 Mirra Andreeva vs. Victoria Mboko / 2026 Miami Open Round of 16；抽帧记分条、球员也都是安德烈娃和姆博科。虽为WTA来源且已成功归档，明确排除，不进入穆霍娃影片素材。官方文章嵌入不能代替视频身份核验。

## 取得方法与可复现性

- 既有Release先查；缺片的四条YouTube通过库内 `download-video.yml` 归档，无渲染、无PushPlus。全部run成功，三条正确比赛的archive URL与run在JSON中。
- 本地YouTube请求被代理明确403，未绕过。WTA网页HTML解码后读取其公开mediaId，经同站官方Brightcove播放器policy和公开playback接口取普通MP4，实际ffprobe确认视频与音轨。
- 长期入口使用官方页面或 `https://players.brightcove.net/6041795521001/te01Hqw71_default/index.html?videoId=MEDIA_ID`。CDN带签名短效URL不作长期主源。
- `contact-sheets/` 中有限抽样墙可供复核，尤其 `bad-homburg-trophy-480.jpg` 从源片480秒起每秒一格；墙上时间码是相对480秒的局部时间，使用时须加480。

本次三条Brightcove本地MP4直接上传尝试均HTTP401，确认无附件后已删除只由本任务新建的空Release元数据。后续Brightcove归档run已按主线程要求取消。这里不把空Release算作归档成功；三条实际本地MP4仍完好。
