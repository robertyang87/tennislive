# Venue image attribution

<!-- 这个文件由 tools/fetch_venues.py 的 render_attribution() 生成，别手改。 -->
<!-- 判据：test_attribution_md_is_generated_from_credits。 -->

The machine-readable author, license, and source records live in `credits.json`.
Event-specific schedule backgrounds are cropped and darkened by the renderer;
the photographs are not otherwise altered.

## `abudhabi-centre-court.jpg`

- Title: 扎耶德体育城网球中心中心球场 · 满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/10/20/cbae0b62-ac90-4b4f-8c15-4acdb35ea037/2088-Abu-Dhabi.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：围板一圈是 Mubadala Abu Dhabi Open 的赞助带。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `adelaide-centre-court.jpg`

- Title: 纪念大道公园中心球场 · 满场，场地前场刷着 ADELAIDE
- Author: Tennis Australia 官方图库
- Source: https://www.tennis.com.au/adobe/dynamicmedia/deliver/dm-aid--c42ebf2c-6c1d-4667-aba1-21221d7a24b4/adelaide-summer-of-tennis-court.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：场地前场刷着 ADELAIDE，围板一圈是本站赞助带。一张管两站——1 月的 WTA500 与 ATP250 同场地。⚠️ 同布里斯班：源图 1200×800 封顶，竖版卡 1.8× 放大。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `ao-rod-laver-arena.jpg`

- Title: File:RodLaverArenanight2013.jpg
- Author: Jono52795
- Source: https://commons.wikimedia.org/wiki/File:RodLaverArenanight2013.jpg
- License: CC0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `ao-rod-laver-bowl.jpg`

- Title: File:Rod Laver Arena Melbourne Park Australian Open 2023 quarter final.jpg
- Author: Gracchus250
- Source: https://commons.wikimedia.org/wiki/File:Rod_Laver_Arena_Melbourne_Park_Australian_Open_2023_quarter_final.jpg
- License: CC BY-SA 4.0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `athens-olympic-tennis-centre.jpg`

- Title: Athens Olympic Tennis Centre（ΟΑΚΑ）中心球场 · 2026 首届 Athens Open 开幕式，满场
- Author: Vanda Pharmaceuticals Athens Open
- Source: https://athens-open.com/venue
- License: unverified · 赛事官方媒体
- Note: ⚠️ 换掉了一张**赛事本身就搞错了**的图。上一版用的是 Telekom Center Athens 的室内蓝场——那是 ATP 的 Hellenic Championship（2025 年 11 月，室内），而 manifest 这一条对应的是 **WTA 250 的 Athens Open**：2026 年 7 月 13–19 日、露天硬地、打在 Athens Olympic Tennis Centre（WTA 官方页 /tournaments/1175/athens/，赛事官网 athens-open.com/venue 也写着 OAKA）。同城不同赛事不同场地，和「ATV Bancomat 印成维罗纳」是同一类错
- Changes: resized and cropped by the card renderer; no semantic alteration

## `auckland-centre-court.jpg`

- Title: ASB 网球中心中心球场 · 满场，场地上写着 AUCKLAND / TĀMAKI MAKAURAU
- Author: asbclassic.co.nz 官方图库
- Source: https://www.asbclassic.co.nz/-/media/sites/tournaments/auckland/news/finals-stadium-generic.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：场地上刷着 AUCKLAND 和毛利语地名 TĀMAKI MAKAURAU，看台横幅 ASB CLASSIC，背景是奥克兰天际线。3600×2400，是这一批里最大的一张。一张管两站——1 月的 ATP250 与 WTA250 同场地。官网走 ATP 的 Sitecore（/-/media/sites/tournaments/auckland/），和斯德哥尔摩同一套；**斯德哥尔摩那站这条路只有合作方 logo 和球员头像，奥克兰这站却有场馆图**——同一个 CMS 不等于同样的内容，要一站一站看。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `badhomburg-centre-court.jpg`

- Title: Bad Homburg 中心球场 · 草地满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/04/28/5023f41c-baec-4531-b585-260d8d468f3f/2017-Bad-Homburg-Open-2.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：围板 SOLARWATT / Bäderland 是本站赞助带。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `barcelona-centre-court.jpg`

- Title: 皇家巴塞罗那网球俱乐部 拉法·纳达尔球场 · 红土满场
- Author: barcelonaopenbancsabadell.com 官方图库
- Source: https://www.barcelonaopenbancsabadell.com/-/media/images/news/2026/04/13/19/29/barcelona-2026-results.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：围板一圈 Sabadell / Occident / LA VANGUARDIA 是这项赛事的赞助带，背景是俱乐部所在的 Pedralbes 一带山形。⚠️ 这个站 curl 拿浏览器 UA 返回 403，**Playwright 渲染却正常**——和 ATP 图床那条「403 是按文件来的」不同，这里是按 UA 来的：403 不等于取不到，换条路再试。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `basel-st-jakobshalle.jpg`

- Title: St. Jakobshalle 中心球场 · 满场（场地前场刷着 BASEL）
- Author: unknown（unitycms 转载）
- Source: https://cdn.unitycms.io/images/7usBtfvqq_sAboyyMyFIom.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `bastad-tennis-stadium.jpg`

- Title: File:Båstad Tennis Stadium.jpg
- Author: PROGuillaume Baviere
- Source: https://commons.wikimedia.org/wiki/File%3AB%C3%A5stad_Tennis_Stadium.jpg
- License: CC BY-SA 2.0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `beijing-diamond-court.jpg`

- Title: 国家网球中心钻石球场 · 满场（场地前场刷着「北京中网」，2023 中网男单决赛）
- Author: unknown（新浪体育转载）
- Source: https://n.sinaimg.cn/spider20231005/214/w2048h1366/20231005/0a57-133e0b7b85e05c9a50f65167521a5b79.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `bogota-centre-court.jpg`

- Title: Centro de Alto Rendimiento 中心球场 · 红土满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2026/06/03/55ee0af0-08ca-4764-96e3-21b366d4bfae/Tournament-background-894-Bogota-new.png
- License: unverified · WTA 官方媒体库
- Note: 自证：那道拱形钢架看台顶棚是这个场地独有的。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `brisbane-centre-court.jpg`

- Title: 帕特·拉夫特球场（昆士兰网球中心）· 满场
- Author: Tennis Australia 官方图库
- Source: https://www.tennis.com.au/adobe/dynamicmedia/deliver/dm-aid--29ecf2d2-3d24-4378-a734-13a92a329a35/brisbane-international-pat-rafter-arena.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：文件名由赛事方自己写着 brisbane-international-pat-rafter-arena，围板 ANZ / Queensland Australia。一张管两站——1 月的 WTA500 与 ATP250 同场地。⚠️ 代价：源图上限就是 1200×800（ 也只给 1200），竖版卡要 1.8× 放大，比同批其他站软。Tennis Australia 三站（布里斯班/阿德莱德/霍巴特）共用 tennis.com.au 的 Adobe Dynamic Media，URL 上的  可调但不会超过源图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `brussels-centre-court.jpg`

- Title: Palais 12（Brussels Expo）中心球场 · 2025 年首届布鲁塞尔站，科梅萨纳 vs 戈芬
- Author: Belga / europeanopen.be 官方图库
- Source: https://europeanopen.be/wp-content/uploads/2025/10/Belgaimage-136797717.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：顶上记分屏印着 CENTRE COURT 与两位球员名，横幅是这项赛事 2016–2024 的历届冠军，场边围板写着 BNP PARIBAS FORTIS / BXL。**赛事 2025 年从安特卫普 Lotto Arena 搬到布鲁塞尔 Brussels Expo Palais 12**，官方图库里 2024 及以前的照片全是旧场馆，不能用。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `canada-iga-stadium-centre-court.jpg`

- Title: Stade IGA 中心球场 · 满场（场地前场刷着 MONTRÉAL，赞助带 Banque Nationale / ROGERS；近端看台、蓝绿场地、远端满场看台与雷暴天空全在竖切里）
- Author: unknown（Radio-Canada 转载）
- Source: https://images.radio-canada.ca/q_auto,w_2400/v1/ici-info/sports/16x9/stade-iga-montreal-tennis-omnium-banque-nationale.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `canada-sobeys-centre-court.jpg`

- Title: Sobeys Stadium 中心球场 · 单打决赛满场（场地前场刷着 TORONTO）
- Author: unknown（View the VIBE 转载）
- Source: https://viewthevibe.com/wp-content/uploads/2022/08/Aviva-Centre-during-the-singles-final-3-Res.jpeg
- License: unverified · 转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `charleston-centre-court.jpg`

- Title: Credit One Stadium 中心球场 · 满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/04/28/1588de8d-8dcd-449f-99a9-e0e2eb688e40/804-Charleston.JPG
- License: unverified · WTA 官方媒体库
- Note: 自证：围板 Credit One / Prudential 是本站赞助带。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `chengdu-centre-court.jpg`

- Title: 四川川投国际网球中心中央球场 · 满场（ATP 官方图库 chengdu-2025-stadium-shot）
- Author: ATP Tour
- Source: https://www.atptour.com/-/media/images/news/2025/08/13/13/44/chengdu-2025-stadium-shot.jpg
- License: unverified · 赛事官方媒体
- Note: ⚠️ atptour.com 这个图床**用浏览器 UA 请求会被 WAF 挡 403，用脚本自己的 UA 反而 200**——取不到时先换 UA 再下结论
- Changes: resized and cropped by the card renderer; no semantic alteration

## `chennai-centre-court.jpg`

- Title: File:Nungambakkam SDAT Tennis Stadium floodlit match panorama.jpg
- Author: PlaneMad / Wikimedia
- Source: https://commons.wikimedia.org/wiki/File%3ANungambakkam_SDAT_Tennis_Stadium_floodlit_match_panorama.jpg
- License: CC BY-SA 3.0
- Note: SDAT 网球场（Nungambakkam）中心球场 · 夜场灯光下的整碗全景。自证：场边围板印着 CHENNAI OPEN，球网上是 ATP 标，看台上方写着 SPORTS DEVELOPMENT AUTHORITY OF TAMILNADU。⚠️ 拍的是旧的 ATP 金奈公开赛（2017 年停办），2026 年新办的是 WTA250，**同一座 SDAT 球场**——场馆没变、赛事换了。照片偏旧，是这一站唯一一张比赛中的整碗全景。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `cincinnati-centre-court-full.jpg`

- Title: Center Court · Lindner Family Tennis Center 满场（2025 赛事官方图 AW5_0234）
- Author: Cincinnati Open
- Source: https://cincinnatiopen.com/wp-content/uploads/2025/10/AW5_0234.jpg
- License: unverified · 赛事官方媒体
- Note: 换掉了上一版 STADIUM-2021_WSOPEN_SOLOMON_001：那张角度对、是官方图，但**空场加阴天**，压完卡片遮罩后整屏是灰蓝色的空座位。这张同一个场地、同样从底线后方，但满场
- Changes: resized and cropped by the card renderer; no semantic alteration

## `cluj-centre-court.jpg`

- Title: BT Arena 中心球场 · 室内紫色场地满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/04/28/cdcb778a-237c-4075-820e-f5e4762863e2/2050-Cluj.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：场地前场刷着 CLUJ-NAPOCA，围板 TeraPlast。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `dallas-ford-center-centre-court.jpg`

- Title: 弗里斯科 Ford Center at The Star 主球场，从底线后方高处沿长轴拍，挡板写着 DALLAS OPEN 与 ATP 500，记分牌是 PAUL / OPELKA，场地前场刷着 DALLAS
- Author: 赛事官方图（摄影师未署名）
- Source: https://www.dallasopen.com/-/media/images/news/2026/01/12/02/39/dallas-2026-prize-money-image.jpg
- License: unverified · 赛事官网媒体库 dallasopen.com
- Note: 这一站三张搜到的「大图」全是 3D 效果图（WFAA 那张迁址报道、官网 Premium Seating 那张、2023-11-27 的公告图 web20231127v1standsupdate）——CG 观众、平涂看台，一眼可辨。新场馆首届前后最容易混进渲染图
- Changes: resized and cropped by the card renderer; no semantic alteration

## `delray-beach-stadium-centre-court.jpg`

- Title: 德雷海滩网球中心主看台球场夜场满场，场地刷着 ATP TOUR，记分牌写着 PAUL / TIEN 与 ATP 250
- Author: 赛事官方图（摄影师未署名）
- Source: https://www.delraybeachopen.com/
- License: unverified · 赛事官网媒体库 delraybeachopen.com
- Note: 同目录邻号 dbo-feb-21st-general-night-095..110 逐个探过，只有 100 这一张是真图，其余全是 200 + text/html 的 soft-404
- Changes: resized and cropped by the card renderer; no semantic alteration

## `denbosch-centre-court.jpg`

- Title: Autotron 中心球场 · 草地，满场（利贝马公开赛）
- Author: libema-open.nl 官方图库
- Source: https://libema-open.nl/wp-content/uploads/2025/06/Libema_250612_2862-scaled.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：围板一圈 Libéma / KNLTB（荷兰网协）/ DEN BOSCH，草地上印着 ATP TOUR，右侧记分屏是 MEDVEDEV–MANNARINO。一张管两站——6 月的 ATP250 与 WTA250 同场地。官网 wp-json 4812 项，荷兰语词 baan / overzicht 比英语管用。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `doha-centre-court.jpg`

- Title: 哈利法国际网球场中心球场 · 夜场满场，背景是多哈天际线
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/10/16/31b8cefd-8f3d-4180-949d-be019385cdd6/1003_bg_Qatar_Doha-min.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：围板一圈 Qatar TotalEnergies Open / ooredoo，远处那座扭转塔楼是多哈天际线。一张管两站——2 月的 WTA1000（Qatar TotalEnergies Open）与 ATP500（Qatar ExxonMobil Open）同场地。⚠️ 这站的赛事官网五个域名全试过都连不上（qatartennis.org 根路径是 Page not found），最后是从 **WTA 赛事页的 hero 图**拿到的。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `dubai-centre-court.jpg`

- Title: 迪拜网球场中心球场 · 黄昏满场，场地前场刷着 DUBAI
- Author: dubaidutyfreetennischampionships.com 官方图库
- Source: https://dubaidutyfreetennischampionships.com/wp-content/uploads/2026/02/Dubai-Duty-Free-Championships-Stadium_005.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：场地前场刷着 DUBAI，围板一圈是这项赛事的赞助带，那顶帐篷状看台顶棚是这个场馆独有的。一张管两站——2 月的 WTA1000 和 ATP500 同场地，别名同为 dubai。官方媒体库（wp-json，12628 项）按 search=stadium 一次翻出十三张同角度的，挑的是顶棚居中、近端球员在击球的这一张。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `eastbourne-devonshire-park-centre-court.jpg`

- Title: 德文郡公园中心球场满场，挡网写着 EASTBOURNE、围板写着 Rothesay INTERNATIONAL，背景是伊斯本的教堂尖顶与维多利亚式排屋
- Author: LTA 官方图（摄影师未署名）
- Source: https://www.lta.org.uk/fan-zone/international/hsbc-championships/
- License: unverified · 赛事主办方 LTA 官网图库
- Changes: resized and cropped by the card renderer; no semantic alteration

## `estoril-centre-court.jpg`

- Title: Millennium Estoril Open · estadio2
- Author: Millennium Estoril Open
- Source: https://estoril-open-media.s3.amazonaws.com/images/605e1eb638ec06001c0f674b-estadio2.jpeg
- License: unverified · 赛事官方媒体
- Changes: resized and cropped by the card renderer; no semantic alteration

## `gstaad-roy-emerson-arena.jpg`

- Title: Roy Emerson Arena 中心球场 · 满场（红土上刷着 GSTAAD，赞助带 EFG Private Banking，记分牌显示比赛进行中；背景是木屋群与阿尔卑斯山）
- Author: Fabian Meierhans / EFG Swiss Open Gstaad
- Source: https://swissopengstaad.ch/wp-content/uploads/2024/05/EFG-SOG23-3-%C2%A9FabianMeierhans.jpg
- License: unverified · 赛事官方媒体
- Changes: resized and cropped by the card renderer; no semantic alteration

## `guadalajara-centre-court.jpg`

- Title: Complejo Panamericano de Tenis 中心球场 · 满场夜场（场地前场刷着 GUADALAJARA，赞助带 AKRON）
- Author: unknown（Guadalajara Secreta 转载）
- Source: https://offloadmedia.feverup.com/guadalajarasecreta.com/wp-content/uploads/2024/05/08095411/1-2.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `guangzhou-centre-court.jpg`

- Title: 广州网球公开赛中央球场 · 满场（2025 赛事收官报道）
- Author: unknown（南方 + 转载）
- Source: https://media.nfnews.com/media-nfh/image/202510/27/7dda1595028b42189b7a215a0541e62a.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `hamburg-rothenbaum-centre-court.jpg`

- Title: File:Hamburg Rotherbaum DS150n.jpg
- Author: AltSylt
- Source: https://commons.wikimedia.org/wiki/File:Hamburg_Rotherbaum_DS150n.jpg
- License: CC BY-SA 4.0
- Note: Am Rothenbaum 中心球场 · 从底线后方高处沿长轴拍，近端看台/红土/远端看台与顶棚全在竖切里；2015-08 拍摄，远处大屏是汉堡申办 2024 奥运的口号「HAMBURG 2024 – Das gibt's nur einmal!」，不是赛事年份
- Changes: resized and cropped by the card renderer; no semantic alteration

## `hangzhou-lotus-centre-court.jpg`

- Title: 杭州奥体中心网球中心「小莲花」中央球场 · 满场（2025 领克杭州网球公开赛）
- Author: unknown（普利吉体育 转载）
- Source: https://img03.71360.com/w3/0qn2g4/20250924/66d99a1c5687521d16f8c59b2adf26de.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `hobart-centre-court.jpg`

- Title: Domain 网球中心中心球场 · 满场，背景是霍巴特的山
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/04/28/d1ead324-0027-4f5b-a4d4-489b562639ea/1050-Hobart.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：官网被 Cloudflare 挡着（CNAME Cross-User Banned），这张来自 WTA 赛事页。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `hongkong-victoria-park.jpg`

- Title: 维多利亚公园中央球场 · 2024 年香港网球公开赛，满场（袁悦 vs 布尔特）
- Author: 香港网球总会（tennishk.org）官方图库
- Source: https://www.tennishk.org/wp-content/uploads/2024/12/241102_CCM1_Katie-Boulter_PHKTO250_HN109223-scaled.jpg
- License: unverified · 协会官方媒体库
- Note: 自证：场地前场刷着 HONG KONG，大屏写着 CENTRE COURT / YUAN · BOULTER，围板是 PRUDENTIAL 保誠香港網球公開賽，背景是铜锣湾天际线。一张图管两站——1 月的 ATP250 和 11 月的 WTA250 都在维园中央球场，别名同为 hong kong。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `houston-river-oaks-centre-court.jpg`

- Title: River Oaks 乡村俱乐部主球场满场，绿色顶棚看台与裁判塔，围板写着冠名商 FAYEZ SAROFIM & CO.，旗杆上是美国旗与得州旗
- Author: ATP 官方赛事主视觉（摄影师未署名）
- Source: https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/houston_tournimage_2019.jpg
- License: unverified · ATP 官方图，经赛事域名镜像取得
- Note: atptour.com 本环境全站 403，但 /-/media/images/atp-tournaments/tournament-images/ 是全站共享路径，任一 ATP 赛事域名都能代取
- Changes: resized and cropped by the card renderer; no semantic alteration

## `iasi-ciric-centre-court.jpg`

- Title: Baza Sportivă Ciric 中心球场 · 满场（红土、两侧蓝色看台）
- Author: unknown（ProSport.ro 转载）
- Source: https://www.prosport.ro/wp-content/uploads/2022/12/iasi-open-scaled.jpg
- License: unverified · 转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `indianwells-centre-court.jpg`

- Title: 印第安维尔斯网球花园 1 号球场 · 满场，场地前场刷着 INDIAN WELLS
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/04/28/d1b371b4-11cf-4c25-99dc-a3b8bcaa06e4/609-BNP-Paribas-Open.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：场地前场刷着 INDIAN WELLS，那圈绿色外场配紫色内场是这个场馆独有的。一张管两站——3 月的 WTA1000 与 ATP1000 同场地。⚠️ 上一轮从 Commons 找到的 Stadium 1 全景（4554×2000）构图更好，但记分牌上写着 PACIFIC LIFE OPEN——那是 2002–2008 的冠名，2009 年起就是 BNP Paribas Open 了，和「美网那张没有顶棚」同一类，弃用。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `istanbul-historical-peninsula.jpg`

- Title: File:Historical peninsula and modern skyline of Istanbul.jpg
- Author: Hunanuk
- Source: https://commons.wikimedia.org/wiki/File%3AHistorical_peninsula_and_modern_skyline_of_Istanbul.jpg
- License: CC0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `kitzbuhel-centre-court.jpg`

- Title: Generali Open 中心球场 · 满场（远端看台雨棚上写着 KITZBÜHEL CHAMPIONSHIPS，赞助带 Stanglwirt / ALPQUELL；近端看台的观众、红土、远端看台与阿尔卑斯山全在竖切里）
- Author: unknown（Kitzbüheler Anzeiger 转载）
- Source: https://www.kitzanzeiger.at/media/system/singleimage/center-court-kitzbuehel.webp
- License: unverified · 新闻站转载，作者未署名
- Note: 源只有 1496×997，竖切要放大 1.44 倍，偏软；但上一版（Commons 的 Tennisstadion Kitzbuehel 2015）是空场且球场被压在画面最底下，竖切之后整屏是空看台和山坡，构图差得多——精准与构图优先于清晰度
- Changes: resized and cropped by the card renderer; no semantic alteration

## `linz-centre-court.jpg`

- Title: TipsArena Linz 中心球场 · 室内紫色场地满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/04/28/5b8f9a8e-bc19-4019-8e7a-f8a5ccd60071/528-Linz.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：场地前场刷着 LINZ，围板 LINZ AG。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `los-cabos-estadio-alejandro-burillo.jpg`

- Title: Estadio Alejandro Burillo · Cabo Sports Complex（赛事官方媒体库 Main stadium 09）
- Author: Mifel Tennis Open by Telcel Oppo
- Source: https://loscabostennisopen.com/wp-content/uploads/2025/07/Main-stadium-09.jpg
- License: unverified · 赛事官方媒体
- Changes: resized and cropped by the card renderer; no semantic alteration

## `madrid-centre-court.jpg`

- Title: 魔盒（Caja Mágica）曼诺洛·桑塔纳球场 · 满场，红土
- Author: mutuamadridopen.com 官方图库
- Source: https://mutuamadridopen.com/wp-content/uploads/2025/04/wta.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：红土两侧写着 MADRID，围板一圈 MUTUA MADRILEÑA / ESTRELLA DAMM / PIF 是这项赛事的赞助带。一张管两站——4 月的 WTA1000 与 ATP1000 同场地。官网开着 wp-json（5978 项），西语词 pista / estadio 比英语词管用。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `mallorca-country-club-centre-court.jpg`

- Title: 圣蓬萨 Mallorca Country Club 中心球场满场，草地两端看台都在，围板写着 MALLORCA，背后是松林覆盖的山坡
- Author: ATP 官方赛事主视觉（摄影师未署名）
- Source: https://mallorcachampionships.com/-/media/images/atp-tournaments/tournament-images/mallorca_tournimage_2022.jpg
- License: unverified · ATP 官方图，经赛事域名镜像取得
- Note: 原图 1920x1080 上半是空天，按卡片裁法一半被遮罩压掉；顶部收 160px 后碗充满画面（放大 1.57x）。另有一张 emotiongroup 的鱼眼全景更漂亮，但记分牌是 KERBER / SHARAPOVA、围板写 Mallorca Open——那是已停办的 WTA 赛事，不是这一站，弃用
- Changes: resized and cropped by the card renderer; no semantic alteration

## `memphis-leftwich-stadium-court.jpg`

- Title: Memphis Classic 主球场（Action News 5 2026-07-26 赛事报道，成片第 14.0 秒；临时看台、Mercedes-Benz / TOPNOTCH / crionet 赞助带、Campbell Clinic 挡布；裁掉了下方的台标条，1280×720 源放大 2.78 倍）
- Author: Action News 5 / WMC-TV
- Source: https://www.actionnews5.com/2026/07/26/memphis-classic-tournament-full-swing-pro-tennis-returns-leftwich/
- License: unverified · 电视台新闻画面截帧
- Note: 2026-07-29 又整轮翻过一次，结论是**这张已经是能拿到的最好的实拍**，别再重跑：官网（Squarespace）只有 WebHero 和赞助 logo；WTA 赛事页只剩那张已被证伪的 1167_Memphis-Hero-2；StyleBlueprint 那张 StadiumView 是**效果图**（同一批搜索结果里就写着 releases stadium renderings）；Action News 5 另一条 7/23 的片子是场馆改建纪录片，没有赛事看台画面。⚠️ **新闻成片里会混进资料画面**：同一条 7/26 报道的 25–27 秒是室内蓝场、场地上印着 MEMPHIS OPEN / ATP WORLD TOUR——那是十年前停办的旧 ATP 赛事，**不是这个场地**。抽帧时要看场地上写的是什么，别只看片子讲的是哪一站
- Changes: resized and cropped by the card renderer; no semantic alteration

## `miami-centre-court.jpg`

- Title: 硬石球场中心球场 · 2026 年迈阿密公开赛，满场
- Author: miamiopen.com 官方图库
- Source: https://www.miamiopen.com/wp-content/uploads/2026/07/260328_MO_TDS6543-scaled.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：球网上是 WTA TOUR，围板一圈 itaú / PIF / betway / LACOSTE 是这项赛事的赞助带，看台那种蓝绿配色是硬石球场（Hard Rock Stadium）的。一张管两站——3 月的 WTA1000 与 ATP1000 同场地。官网开着 wp-json（4485 项），按 search=stadium/court/aerial 筛大横图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `montecarlo-centre-court.jpg`

- Title: 蒙特卡洛乡村俱乐部雷尼尔三世球场 · 满场，背景是地中海
- Author: montecarlotennismasters.com 官方图库
- Source: https://montecarlotennismasters.com/wp-content/uploads/2020/04/vue.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：红土两侧写着 MONTE CARLO，围板 BNP PARIBAS / ROLEX / FEDCOM（FEDCOM 是摩纳哥雇主联合会，本站赞助商，不是 Fed Cup），两块 ATP 记分屏上是迪米特洛夫对纳达尔。官网开着 wp-json（5580 项），法语词 vue / stade 命中率比英语高。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `monterrey-centre-court.jpg`

- Title: Estadio GNP Seguros 中心球场 · 满场（场地前场刷着 MONTERREY，看台顶写着 GNP Estadio，背景是马德雷山）
- Author: Abierto GNP Seguros
- Source: https://abiertognpseguros.com/media/pages/guia-del-torneo/visit-monterrey/b9f38a59c0-1715623630/estadio-gnp-seguros-1920x.jpg
- License: unverified · 赛事官方媒体
- Changes: resized and cropped by the card renderer; no semantic alteration

## `montpellier-centre-court.jpg`

- Title: Sud de France Arena 中心球场 · 满场（粉蓝双色场地）
- Author: openoccitanie.com 官方图库
- Source: https://www.openoccitanie.com/wp-content/uploads/2025/01/sdf-arena-pleine-scaled.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：文件名 sdf-arena-pleine（Sud de France Arena「满场」）由赛事方自己写着；那块粉红内场配蓝色外场是这个赛事独有的配色，大屏上是奥克西塔尼大区的徽记。⚠️ 赛事官网域名换过：opensuddefrance.com 会跳到 openoccitanie.com，wp-json 在后者上（517 项）——**按旧名找会以为这站没有 CMS**。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `munich-centre-court.jpg`

- Title: MTTC Iphitos 中心球场 · 红土满场（BMW Open）
- Author: bmwopen.de 官方图库
- Source: https://www.bmwopen.de/wp-content/uploads/2025/04/Center-Court.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：红土上刷着 MUNICH，球网上是 ATP TOUR，看台横幅 BMW Open by bitpanda，记分屏是 ALEXANDER ZVEREV 对 DANIEL ALTMAIER。原图 8192×5464，入库按 max-edge 缩到 4200。德语搜索词 center court / centercourt 直接命中（stadion / anlage 都是 0）。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `ningbo-centre-court.jpg`

- Title: 宁波网球中心中央球场 · 满场（2024 宁波公开赛开赛，PR Newswire 发布的赛事官方图）
- Author: Ningbo Open（PR Newswire 发布）
- Source: https://mma.prnewswire.com/media/2532199/Ningbo_International.jpg
- License: unverified · 赛事官方媒体
- Changes: resized and cropped by the card renderer; no semantic alteration

## `nottingham-centre-court.jpg`

- Title: 诺丁汉网球中心中心球场 · 草地满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/10/16/0b899ba9-b477-48ea-9e9e-5cb6aeb30699/1080_bg_Nottingham-min.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：围板一圈是本站赞助带。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `osaka-utsubo-centre-court.jpg`

- Title: 靱テニスセンター（Utsubo Tennis Center）中央球场 · 从底线后方看，远端与两侧绿色看台都在框内
- Author: unknown（モリタテニス靱 转载）
- Source: http://mtp-tennis.com/utsubo/images/senter.jpg
- License: unverified · 转载，作者未署名
- Note: 空场、源 1280×720（竖切放大 2.0 倍），偏软。留着是因为**不留会更糟**：这一站原来被东京有明那张图套走了，卡上会印「东京 · 日本」——同名不同城。等 WTA250 赛期的现场大图再换
- Changes: resized and cropped by the card renderer; no semantic alteration

## `ostrava-centre-court.jpg`

- Title: Ostravar Aréna 中心球场 · 室内满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2026/05/29/1c78195c-5e01-4cfd-9c6b-c8b3fba080c4/1054-Ostrava-Background.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：大屏上写着 OSTRAVA 与 WTA 250。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `palermo-country-time-centre-court.jpg`

- Title: Country Time Club 中心球场 · 黄昏（挡板上 Veneta Cucine / PEUGEOT / WTATENNIS.COM，背景是巴勒莫的山；近端蓝色看台、红土、远端看台全在竖切里）
- Author: unknown（LiveSicilia 转载）
- Source: https://livesicilia.it/wp-content/uploads/2021/07/Campo-centrale-Country-Time-Club-scaled.jpg
- License: unverified · 新闻站转载，作者未署名
- Note: 上一版是赛事官网的 Campo-centrale-dallalto，几乎纯俯视——竖切之后整屏只有球场，看不出是个碗。官网媒体库 430 张里翻过，没有第二张全景（全是球员、颁奖、发布会）
- Changes: resized and cropped by the card renderer; no semantic alteration

## `paris-centre-court.jpg`

- Title: Paris La Défense Arena 中心球场 · 2025 年巴黎大师赛，满场
- Author: André Ferreira / FFT · rolexparismasters.com 官方图
- Source: https://images.prismic.io/rpm-site/ajvcN1bRV8_Qf0Qh_RolexParisMasters2025-Andr%C3%A9FerreiraFFT.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：二层 LED 环带整圈滚着 PARIS LA DEFENSE ARENA，场边 LED 打着冠军 FELIX AUGER-ALIASSIME，文件名由 FFT 自己写着 RolexParisMasters2025。⚠️ **这项赛事 2025 年已从贝尔西（Accor Arena）搬到 Paris La Défense Arena**，贝尔西的照片是旧场馆。原图 3000×2000 顶上大半是灯梁，按 (0,700,1900,1980) 收成 1900×1280 再入库——竖版只取中间一条，不收边的话碗全被挤出画面（三档裁法渲出来比过）。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `prague-stvanice-central-court.jpg`

- Title: File:Central tennis court at Štvanice 02.jpg
- Author: Dobroš
- Source: https://commons.wikimedia.org/wiki/File:Central_tennis_court_at_%C5%A0tvanice_02.jpg
- License: CC BY-SA 4.0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `queens-club-centre-court-atp.jpg`

- Title: 女王俱乐部中心球场（安迪·穆雷球场）满场，场地前场刷着 ATP TOUR，围板写着 HSBC CHAMPIONSHIPS，左侧为俱乐部红砖会所
- Author: LTA 官方图（摄影师未署名）
- Source: https://www.lta.org.uk/fan-zone/international/hsbc-championships/weather-forecast/
- License: unverified · 赛事主办方 LTA 官网图库
- Changes: resized and cropped by the card renderer; no semantic alteration

## `queens-club-centre-court-wta.jpg`

- Title: 女王俱乐部中心球场满场，围板写着 HSBC CHAMPIONSHIPS 与 WTA 500，草地上刷着 LONDON
- Author: LTA 官方图（摄影师未署名）
- Source: https://www.lta.org.uk/fan-zone/international/hsbc-championships/
- License: unverified · 赛事主办方 LTA 官网图库
- Changes: resized and cropped by the card renderer; no semantic alteration

## `rg-philippe-chatrier.jpg`

- Title: File:Court Philippe Chatrier 2024.jpg
- Author: MFonzatti
- Source: https://commons.wikimedia.org/wiki/File%3ACourt_Philippe_Chatrier_2024.jpg
- License: CC BY-SA 4.0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `rio-centre-court.jpg`

- Title: 瓜加·库尔滕球场（Jockey Club）· 红土满场，背景是里约的山
- Author: rioopen.com 官方图库
- Source: https://www.rioopen.com/-/media/sites/tournaments/rio/vistageral.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：文件名 vistageral（葡语「全景」）由赛事方自己写着，画面是里约赛马会那片红土加科尔科瓦多一侧的山形，黄昏满场。同一个目录下还有一张纯俯视航拍（250226_geral），竖切之后只剩一块红土、看不出是个碗，按巴勒莫那条弃用。官网走 ATP 的 Sitecore，图直接挂在 /-/media/sites/tournaments/rio/ 根下。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `rome-atv-tennis-open-courts.jpg`

- Title: Circolo Antico Tiro a Volo（罗马）红土场 · 挡板上写着 ATV · ANTICO TIRO A VOLO TENNIS OPEN 与 ROMA，背景是罗马城郊
- Author: Il Mondo del Tennis
- Source: https://ilmondodeltennis.com/2022/07/torneo-internazionale-al-circolo-antico-tiro-a-volo/
- License: unverified · 新闻站转载
- Note: 这一站原来被标成「维罗纳 · 意大利」并配了维罗纳圆形竞技场——赛事名里的 ATV 是 Antico Tiro a Volo（罗马的俱乐部），不是 Associazione Tennis Verona。WTA 自己的赛事页就是 /tournaments/1130/rome/
- Changes: resized and cropped by the card renderer; no semantic alteration

## `rotterdam-centre-court.jpg`

- Title: 鹿特丹 Ahoy 中心球场 · 满场，从高处俯瞰整个碗
- Author: Alyssa van Heyst / abnamro-open.nl 官方图库
- Source: https://www.abnamro-open.nl/files/images/2027/AAO_260215_Alyssa%20van%20Heyst_3545.jpg
- License: unverified · 赛事官方媒体库
- Note: 自证：环场 LED 带上是 ABN AMRO OPEN，以及这项赛事的历届冠军名录（'05 FEDERER / '06 STEPANEK / '07 YOUZHNY / '08 LLODRA / '16 MURRAY…），场边围板 ABN·AMRO / LEXUS。室内夜场，均值 29、中位 19——和已入库的巴塞尔（30 / 7）同一档，球场本身打了灯，压完遮罩整个碗仍然读得出来。官网不是 WordPress，图在 /files/images/<年>/ 下，靠 Playwright 渲染首页拿到路径；DOM 里显示的是 1600×640，**直接取那个 URL 才是 2400×1600 的原图**。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `rouen-centre-court.jpg`

- Title: Kindarena 中心球场 · 室内红土满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/05/02/45da6924-0e65-40ec-b971-04b2806da1f8/2066-Rouen.png
- License: unverified · WTA 官方媒体库
- Note: 自证：围板一圈是本站赞助带；官网 wp-json 里 central 指的是球场名，不是全景。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `sao-paulo-centre-court.jpg`

- Title: SP Open 中心球场（场地前场刷着 SÃO PAULO，2025 首届）
- Author: unknown（Guia do Tenista 转载）
- Source: https://guiadotenista.com.br/wp-content/uploads/2025/09/IMG_8074-scaled.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `seoul-olympic-park-centre-court.jpg`

- Title: 首尔奥林匹克公园网球中心中心球场（Korea Open）
- Author: unknown（Trip.com 转载）
- Source: https://ak-d.tripcdn.com/images/0103912000ew95azuF824.jpg
- License: unverified · 转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `shanghai-qizhong-centre-court.jpg`

- Title: 旗忠网球中心中央球场 · 顶棚八瓣白玉兰可开合（上海劳力士大师赛）
- Author: unknown（赛倍明照明 转载）
- Source: https://www.sportsbeams.cn/web/uploads/image/20250516/7KQ41674TPF5pOWqJj2Dfvx20909D21F.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `singapore-centre-court.jpg`

- Title: Kallang Tennis Hub 中心球场（场地前场刷着 SINGAPORE，室内，两侧蓝色看台与顶棚桁架都在竖切里）
- Author: unknown（TennisTalker 转载）
- Source: https://media.tennistalker.it/2025/01/Singapore-Open-campo.jpeg
- License: unverified · 新闻站转载，作者未署名
- Note: ⚠️ 三条闸门都过了（场内 / 中心球场 / 看得见看台），**只差在清晰度和空场**：源仅 680×454，竖切要放大 1.59 倍；而且是赛前空场。翻过：赛事官网、Kallang 官方 heretoplay 站（TROPHY-5 那张取不到）、Sport Singapore、WTA photoresources、DDG 四组查询——满场的现场大图没找到，剩下的要么是带烧录文字的宣传图（prnewswire 那张 Key_Visual 是球员抠图拼的），要么是乒乓球的 OCBC Arena。要换就等 2026 赛期的现场图
- Changes: resized and cropped by the card renderer; no semantic alteration

## `stockholm-centre-court.jpg`

- Title: File:Kungliga Tennishallen.JPG
- Author: Kjetil Eggen
- Source: https://commons.wikimedia.org/wiki/File%3AKungliga_Tennishallen.JPG
- License: CC BY-SA 4.0
- Note: 皇家网球馆（Kungliga tennishallen）中心球场 · 满场，斯德哥尔摩公开赛比赛中。自证：围板印着 If STOCKHOLM OPEN，看台横幅 #ifsthlmopen，右侧挂 ATP 250 标；二层那条历届冠军名录（帕纳塔、麦肯罗、博格、维兰德、费德勒、蒙菲尔斯、伯蒂奇、迪米特洛夫）是这项赛事自己的荣誉墙。2014-10-19 拍摄。赛事官网走 ATP 的 Sitecore，/-/media 下只有合作方 logo 和球员头像，没有场馆图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `strasbourg-centre-court.jpg`

- Title: Tennis Club de Strasbourg 中心球场 · 红土满场
- Author: photoresources.wtatennis.com 官方图库
- Source: https://photoresources.wtatennis.com/photo-resources/2025/05/12/ffbc5331-cbef-4d6a-8f6d-3a0c93eefa0e/406-Strasbourg.jpg
- License: unverified · WTA 官方媒体库
- Note: 自证：看台横幅写着 Strasbourg / Grand Est。这一批十一站都是从 **WTA 赛事页的 hero** 拿的（photoresources.wtatennis.com），赛事页要用数字 id 访问，id 从 api.wtatennis.com 的 tournaments 接口按 from/to 取 2026 年那批。URL 上的 height 是裁切参数，只给 width 才是完整图。
- Changes: resized and cropped by the card renderer; no semantic alteration

## `tokyo-ariake-coliseum.jpg`

- Title: 有明コロシアム（Ariake Coliseum）中心球场 · 场地前场刷着 TOKYO
- Author: unknown（个人博客转载）
- Source: https://cdn-ak.f.st-hatena.com/images/fotolife/e/epokopoko/20200405/20200405173255.jpg
- License: unverified · 转载，作者未署名
- Note: ⚠️ 东京有两站共用有明：9 月的 ATP500 木下集团日本公开赛，和 10 月的 WTA500 东丽泛太平洋公开赛。别名两边都收。10 月大阪那站是另一个场馆（靱公园），不要被「Kinoshita Group Japan Open」这个同名冠名骗过去
- Changes: resized and cropped by the card renderer; no semantic alteration

## `umag-goran-ivanisevic-centre-court.jpg`

- Title: Stadion Goran Ivanišević 中心球场 · 满场夜场（红土、蓝色看台、泛光灯）
- Author: Croatian National Tourist Board（croatia.hr 媒体库）
- Source: https://cdn.croatia.hr/mediagallery-dxp-production/_ATP_Stadion_Gorana_Ivanisevica_Colours_of_Istria.jpg
- License: unverified · 旅游局官方媒体
- Changes: resized and cropped by the card renderer; no semantic alteration

## `usopen-arthur-ashe-exterior.jpg`

- Title: File:Arthur Ashe Stadium, July 7, 2018.jpg
- Author: D. Benjamin Miller
- Source: https://commons.wikimedia.org/wiki/File:Arthur_Ashe_Stadium,_July_7,_2018.jpg
- License: CC0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `usopen-arthur-ashe-stadium.jpg`

- Title: File:Aryna Sabalenka vs. Qinwen Zheng in a quarterfinals of the 2024 US Open - 01.jpg
- Author: Oleg Yunakov
- Source: https://commons.wikimedia.org/wiki/File:Aryna_Sabalenka_vs._Qinwen_Zheng_in_a_quarterfinals_of_the_2024_US_Open_-_01.jpg
- License: CC BY-SA 4.0
- Note: 阿瑟阿什球场 · 2024 美网女单四分之一决赛（LED 带上写着 QINWEN ZHENG / ARYNA SABALENKA，包厢层写着 ARTHUR ASHE STADIUM）。**上一版是 2013 年的，画面里没有顶棚**——阿瑟阿什 2016 年才装可开合顶棚，那张等于印了一个已经不存在的样子
- Changes: resized and cropped by the card renderer; no semantic alteration

## `vienna-stadthalle-centre-court.jpg`

- Title: Wiener Stadthalle 中心球场 · 满场（2025 Erste Bank Open）
- Author: unknown（Kronen Zeitung 转载）
- Source: https://imgl.krone.at/scaled/3913474/v9f6623/full.jpg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration

## `washington-fitzgerald-tennis-center.jpg`

- Title: File:Karatsev–Tiafoe in stadium at the 2023 DC Open 01.jpg
- Author: Hameltion
- Source: https://commons.wikimedia.org/wiki/File%3AKaratsev%E2%80%93Tiafoe_in_stadium_at_the_2023_DC_Open_01.jpg
- License: CC BY-SA 4.0
- Changes: resized and cropped by the card renderer; no semantic alteration

## `wimbledon-centre-court.jpg`

- Title: File:2023 Wimbledon Men's singles final (1).jpg
- Author: Daniel Cooper
- Source: https://commons.wikimedia.org/wiki/File:2023_Wimbledon_Men%27s_singles_final_(1).jpg
- License: CC BY-SA 2.0
- Note: 中央球场满场 · 2023 男单决赛（阿尔卡拉斯对德约科维奇，记分牌可读）；从底线后方看台高处拍，近端观众/草地/远端满场看台/开着的屋顶全在竖切里
- Changes: resized and cropped by the card renderer; no semantic alteration

## `winston-salem-centre-court.jpg`

- Title: Wake Forest Tennis Complex 中心球场 · 黄昏满场
- Author: Camera Work USA（Triad Business Journal 转载）
- Source: https://media.bizj.us/view/img/12022122/winston-salem-open-stadium-photo-by-camera-work-usa.jpg
- License: unverified · 新闻站转载
- Changes: resized and cropped by the card renderer; no semantic alteration

## `wuhan-optics-valley-centre-court.jpg`

- Title: 光谷国际网球中心中央球场 · 满场（挡板上写着「东风岚图·武汉网球公开赛 DONGFENG VOYAH · WUHAN OPEN」与「2024东风岚图·武汉网球公开赛」）
- Author: unknown（大武汉 转载）
- Source: https://www.app.dawuhanapp.com/c/10001/202410/d45fc4e1868afc8ae97999dffa39df03.jpeg
- License: unverified · 新闻站转载，作者未署名
- Changes: resized and cropped by the card renderer; no semantic alteration
