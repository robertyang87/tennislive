# 霍达尔—梅德韦杰夫：事实与故事包

**已核比赛：2026年10月17日晚，ATP1000上海半决赛。霍达尔6-3、6-4淘汰梅德韦杰夫，首次进入大师赛决赛。** 霍达尔20岁、世界13、第12种子；梅德韦杰夫30岁、世界6、第5种子。官方原生MS003已完赛，耗时01:44:06。

主线：前四轮都是先丢一盘后逆转的霍达尔，这次面对上海前冠军，两盘打进决赛；过程并不轻松，首盘第5个盘点才拿下，次盘领先被追回后重新起势，梅总连救3个赛点仍未翻盘。

## 可用钩子

- 连救3个赛点／梅总仍遭两盘淘汰
- 前四轮全靠逆转／这次两盘淘汰梅总
- 5个盘点才拿下／20岁新星淘汰梅总

前者更贴用户“梅总也输了”的角度。钩子是否取赛点/盘点取决于源片真实画面，不能用其他回合冒充。

## 每盘过程与关键点

**第一盘：霍达尔6比3。** 先从2-1破到3-1；接着梅总在霍达尔的发球局拿到4个破发点，最后回破3-2；霍达尔立刻再破到4-2，随后救一个破发点保到5-2；5-3发球胜盘局用了5个盘点才拿下。

**第二盘：霍达尔6比4。** 霍达尔开局破发并保发2-0；梅总连拿3局，追回并反超3-2；霍达尔再连拿3局至5-3。梅总3-5发球局救3个赛点后保到4-5，霍达尔随后love hold，以全场第4个赛点收下胜利。

注意逐分记录局分是**局结束后**的分数；如`5-4 梅总发球拿下`，事件开始前其实是霍达尔5-3领先。`points-parsed.json`保留原始局分并注明server/winner；需要源代理核对实际画面与取段时间，不由事实包猜时间码。

## 收尾与背景

- 决赛已经确定：10月18日霍达尔VS达维多维奇，西班牙内战；官方计划不早于北京时间16:30。
- 霍达尔是上海历史最年轻决赛选手，第一次进大师赛决赛。这是他本季第2场胜世界前10。
- 如果要讲都灵：官网写其即时冠军积分第9，夺冠可升第6并首次进入世界前10；这些是条件句，不能提前说已经夺冠/已锁定年终席位。

## 数据与旧草稿冲突

`spec-ready-stats-jodar-first.json`可直接取统计块：a霍达尔、b梅总，完整官方发球/总分整数，W/UE明确取Flashscore全场并核分盘。

| 项目 | 霍达尔 | 梅德韦杰夫 |
|---|---:|---:|
| ACE | 6 | 3 |
| 双误 | 2 | 4 |
| 一发进球 | 69%（58/84） | 56%（28/50） |
| 一发得分 | 66%（38/58） | 64%（18/28） |
| 二发得分 | 46%（12/26） | 41%（9/22） |
| 破发 | 4/7 | 2/6 |
| 总得分 | 73 | 61 |
| 制胜分 | 22 | 15 |
| 非受迫失误 | 22 | 21 |

- 旧草稿全场多数整数其实正确；耗时1:36错误，取官方1:44:06。
- 旧草稿把梅总第5种子写成世界第5，改世界第6。
- 旧草稿“梅总一发得分47%→85%”来自Flashscore不自洽分盘分母，官方对应58%（7/12）→69%（11/16），不采用该摆动钩子。
- 官方新闻写制胜分22比14，Flashscore全场22比15，且分盘15+7=22、9+6=15；UE13+9=22、11+10=21。数据卡统一采用有原始全场/分盘证据的Flashscore22/15，内部记录新闻冲突，不混填14。

## 素材身份边界

用户新URL `0gX2hUan9Vc`：主线程首次oEmbed请求代理403后停止，身份未核验；事实代理未再请求YouTube。旧草稿URL是`aE21b2-ef-Y`，两者不能自动认作同源。

现有原生probe39036715783及GH缓存绑定旧URL、134.164898秒、1920×1080、原文件d36a1ec214289256.mp4、58208673字节。但本地记录未存title/uploader/channel，这些记录不能代替官方频道验证。主线程恢复已有缓存并独立核画面。官网视频列表有本场官方Brightcove影片（video6407012514112/account6057277721001），只作为独立赛事身份对照，不声称与旧YouTube片字节相同。

## 来源

- [官方本场报道](https://en.rolexshanghaimasters.com/en/media/news/medvedev-jodar-shanghai-2026-saturday)
- [官方原生MS003统计](https://en.rolexshanghaimasters.com/-/tournaments/matchStatsApi/MatchStats?year=2026&eventId=5014&matchId=ms003)
- [霍达尔官方资料](https://en.rolexshanghaimasters.com/en/players/rafael-jodar/j0dz)
- [梅德韦杰夫官方资料](https://en.rolexshanghaimasters.com/en/players/daniil-medvedev/mm58)
- [官方决赛赛程](https://en.rolexshanghaimasters.com/en/scores/schedule)
- [同场官方视频列表](https://en.rolexshanghaimasters.com/en/media/videos)
- [Flashscore全场及分盘统计](https://local-global.flashscore.ninja/2/x/feed/df_st_1_nwiNy6gC)
- [Flashscore逐分](https://local-global.flashscore.ninja/2/x/feed/df_mh_1_nwiNy6gC)

`requests.json`为新取回记录；`copied-primary-provenance.json`保留上个已完成事实任务复用的官方原响应取回时间。未修改spec、未调配音、未派工作流或发布。

### 官方独立素材元数据已取回

Brightcove公开播放器config与Playback API均正常200。本场标题为“Highlights: Jodar defeats Medvedev to reach Shanghai 2026 final”，video6407012514112/account6057277721001；303.147秒，2026-10-17T13:24:46.566Z发布。HLS主清单实际最高1280×720，MP4亦720；不能冒称有1080。

`official-brightcove-source.json`含canonical player URL、可用媒体URL与清单分辨率，`official-brightcove-video-metadata.json`为原响应，`official-brightcove-requests.json`为取回记录。未下载完整影片。该官方5分钟版可供主线程与已恢复134秒1080缓存逐镜对照；不能仅因同场就声称二者字节一致或旧上传者已获官方认证。
