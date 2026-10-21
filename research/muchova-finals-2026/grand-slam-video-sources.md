# 穆霍娃2026：四大满贯止步轮视频来源

更新：2026-10-21。用户要求四大满贯都配她止步当轮真实视频。主线程进一步明确：当轮赛后结果画面也能作为事实旁白配图，不额外要求必须取得完整主集锦。以下四站已有可用归档；精确剪点与现场原声仍应在正式选段时核。

| 时间／止步轮 | 可用官方视频 | 实际文件／归档ID | 核验范围 |
|---|---|---|---|
| 1月25日 澳网第四轮，负高芙1-6、6-3、3-6 | [Australian Open集锦](https://www.youtube.com/watch?v=ZCkYFYyJlK8) | `sources/videos/ZCkYFYyJlK8.mp4`；`source-ZCkYFYyJlK8` | 1080p，194.165秒。片尾球分、握手及第四轮赛果字样核对；穆霍娃橙色adidas裙，高芙白色NB。 |
| 5月29日 法网第三轮，负泰希曼1-6、5-7 | [Roland-Garros官方X](https://x.com/rolandgarros/status/2060369494891978888) | `sources/videos/2060367806730776578.mp4`；`source-2060367806730776578` | 1080×1920，41.123秒。该场泰希曼跪地庆祝与挥手，不能称为穆霍娃失误／反应。可用4–13秒左右当轮结果画面配TTS，正式锁剪前看连续段。 |
| 7月11日 温网决赛，负诺斯科娃2-6、7-5、3-6 | [Wimbledon决赛集锦](https://www.youtube.com/watch?v=XfE9M6__724) | `sources/videos/XfE9M6__724.mp4`；`source-XfE9M6__724` | 1080p，255.396秒。已核人物及末盘赛果；片尾冠军捧杯是诺斯科娃，勿标穆霍娃冠军。 |
| 9月4日 美网第三轮，负纳瓦罗3-6、5-7 | [US Open单打集锦](https://www.youtube.com/watch?v=EUk-bMVXRa4) | `sources/videos/EUk-bMVXRa4.mp4`；`source-EUk-bMVXRa4` | 1080p，209.862秒。真实单打、NAVARRO/MUCHOVA记分、赛点握手及第三轮结果页核对。 |

四条源的可重复下载地址都是：`https://github.com/robertyang87/tennislive/releases/download/source-<id>/<id>.mp4`。完整参数、字节数、SHA256、Actions run、抽帧路径在同目录 `grand-slam-video-candidates.json`。澳网、美网仅作有限片尾身份核验，不能据此声称每个高光回合都已逐帧审过。

## 法网官方X的当场身份链

[WTA官方5月29日报告](https://www.wtatennis.com/news/4511276/andreeva-reaches-roland-garros-fourth-round-with-tour-leading-32nd-win)在“Teichmann comeback gains momentum”段说明她逆转第二盘1-5，6-1、7-5击败穆霍娃，并直接嵌入上述Roland-Garros原帖。已实际下载HTML，确认含**同一status ID2060369494891978888**。主帖ID与下载的X媒体ID不同，不要混用。

证据：`evidence/rg-r32-wta-official-embedded-x.html`；抽帧 `contact-sheets/rg-r32-full.jpg`。2秒间隔通览：芥末色Nike裙白帽的泰希曼跪地、低头、起身和挥手；没有可据以叙述穆霍娃具体失误或本人情绪的画面。只叙述当轮结果。

## 法网主集锦补找记录

[FFT官方2026转播说明（5月12日）](https://www.rolandgarros.com/en-us/article/roland-garros-2026-tv-broadcasters-france-international)明确beIN Sports是东南亚／中东北非持权方、Eurosport覆盖欧洲50余地区，TNT/HBO Max美国、Sony印度；证据本地 `evidence/rg-2026-official-broadcasters.html`。此证据用于确认原始广播官方身份与地域范围，不等同我们发布成片的授权。

- beIN SPORTS Asia认证频道 [EaI5nviJFvU](https://www.youtube.com/watch?v=EaI5nviJFvU)，网页题名和2026-05-29日期正确；常规归档run39634416455返回Video unavailable，没有可视听文件。
- beIN SPORTS Indonesia认证频道 [kpkpGUcJB8k](https://www.youtube.com/watch?v=kpkpGUcJB8k)，同题同日；run39634799959也返回Video unavailable。
- [TNT Sports当轮3分33秒集锦](https://www.tntsports.co.uk/tennis/roland-garros/2026/tennis-roland-garros-highlights-jil-teichmann-karolina-muchova_vid60078107/video.shtml)，run39634952083常规HTTP403；本地网页明确区域不可用。Eurosport多语种同片页面也显示区域不可用，未绕过。
- [SRF官方42秒结果视频](https://www.srf.ch/play/tv/sport-clip/video/teichmanns-maerchen-geht-auch-gegen-muchova-weiter?urn=urn:srf:video:e7a0a1a0-4408-4e10-952c-00ec74f7ac71)，run39635174791不支持URL；官方公开composition API声明`GEOBLOCK`、`playableAbroad:false`，停止，不绕过。
- [FanCode当轮8分11秒](https://www.fancode.com/tennis/tour/roland-garros-2026-19620189/video-highlights/jil-teichmann-vs-karolina-muchova-round-3-221152)，页面直接提供正确题名和公开HLS；本地及run39635588111常规取HLS均403。2025[Dream Sports官网声明](https://www.dreamsports.group/media-and-blog/roland-garros-2025-lands-on-fancode-with-every-match-every-stat-of-french-open)确认与SonyLIV合作，2026新闻也列其印度直播，但未取得2026第一方完整权利链，不作本轮选片。

已按主线程要求停止扩大不可取渠道，使用已自证同场的RG官方X结果画面，不把对手庆祝冒充Mu过程。

## WTA官方9分29赛季回顾

[稳定Brightcove播放器](https://players.brightcove.net/6041795521001/te01Hqw71_default/index.html?videoId=6407184037112)，WTA内容4596753，题名《Qualified! How Karolina Muchova made the 2026 WTA Finals Indian Wells》。本地 `sources/videos/wta-qualified-6407184037112.mp4`，568.405秒、1280×720/25fps；run39634851593成功归档 `source-6407184037112/6407184037112.mp4`。

每20秒全程抽样见 `contact-sheets/wta-qualified-overview.jpg`，可辨Brisbane、多哈、印第安韦尔斯、斯图加特、罗马、巴特洪堡、北京、武汉的巡回赛画面；抽样未见四GS或采访。不据此替代四GS，也不直接照搬其快剪结构；实际选镜头需逐场对比分与身份。未做全片转写。

## canonical字节一致性

重新实际下载长期Release中的BC三源，与此前本地ASR所用源逐个比对，**全部逐字节相同**，不需换源或重转写：

| source ID | 本地文件 | 尺寸／时长 | 字节／SHA256 |
|---|---|---|---|
| 6391563293112 | `miami-muchova-mboko.mp4` |1280×720/25fps，244.96秒|65,315,829；`b6117cb922680965f0eb5331d706396b2de4fe79ba8db7b8c8bcbf8c0d20327e`|
| 6399578560112 | `bad-homburg-champions.mp4` |1280×720/25fps，501.12秒|133,424,471；`b9d5d240edc28dbee579f57993faf0433adc2724d4f9d9c1973dc2759667cad3`|
| 6399808507112 | `bad-homburg-winners-feature.mp4` |1920×1080/25fps，165.28秒|76,219,109；`fbdf2f1c540d553b4c073e380ee3e0ce196573e7bd3bca22d43f87a2da6f4235`|

详见 `evidence/bc-canonical-comparison.json`，复下文件在 `sources/canonical-check/`。

## 排除错配

`tvYFq3pGI80`为穆霍娃／门西克vs纳瓦罗／保罗混双，不能代表美网女单第三轮。正确当轮单打使用`EUk-bMVXRa4`。

## 新补多哈捧杯替源

旧derived `doha_trophy.mp4`英语解说在源边界断句，主线程要求换源。现取得[WTA官方X原帖](https://x.com/WTA/status/2022719051408052453)的实际媒体`2022719030826504193`，常规run39636140047成功归档。11.400998秒、1280×720/25fps，本地 `sources/videos/2022719030826504193.mp4`。全片每秒抽帧及0.5秒实帧可见穆霍娃白外套橙裙站中央举金鹰杯，周围烟火；WTA多哈赛报实际HTML也包含exact原帖ID（`evidence/doha-report-trophy-x.html`）。现场音是否有完整英语句已交采访代理核，未沿用旧skip状态。

## 8月26日美网混双冠军视频

AO官方[9月3日文章](https://ausopen.com/articles/news/five-women-finding-form-us-open)的真实iframe指向[US Open官方YouTube og_Ex5oDa-4](https://www.youtube.com/watch?v=og_Ex5oDa-4)，题名《Cobolli/Bencic vs. Mensik/Muchova Extended Highlights | 2026 US Open Final》。run39636194284成功归档，实际文件`sources/videos/og_Ex5oDa-4.mp4`，727.666939秒、1920×1080/59.94fps、281,863,114字节，SHA256`e443434bb210837f021d4e0401081b3123265b06ea10c008eafa6571442b57e5`。USOpen官网另有23:30扩展版，不把两版时码混用。

尾段每5秒通览＋648–679秒逐秒抽帧：记分条BENCIC/COBOLLI与MUCHOVA/MENSIK、四人服装、冠军点与赛后拥抱、赢家页交叉核对。**最后冠军点约671–674秒，发球前抢十9–6，门西克发球；674秒穆霍娃张臂，677–679秒与搭档拥抱。** 可从670–681秒附近取完整最后发球至庆祝，正式成片仍逐帧锁边界并核原声。658–663秒是此前丢掉的冠军点，不要错当终局。抽帧`contact-sheets/usopen-mixed-championship-point.jpg`从648秒起、8列逐秒。片尾未见捧杯。

这项冠军属于混双，不给单打Race加分。日期采用比赛当地8月26日晚；8月27日是UTC报道日期。视频发布日期与比赛日期分开记录。
