"""下载"一分钟"栏目用的场馆图与球员图（Wikimedia Commons，授权白名单）.

场馆图为人工挑选的固定文件；球员图从对应 Commons 分类里按许可白名单
自动挑选（优先横图、大图）。实际选中的文件、作者、许可写入各目录的
credits.json 供人工复核。upload.wikimedia.org 对云端 IP 限流较狠
（429），故下载带重试退避，缩略图被拒时回退原图并在本地用 Pillow
压到 1920px 以内。CI 运行（见 assets.yml）。
"""

from __future__ import annotations

import io
import json
import re
import time
import unicodedata
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "tennislive-asset-fetch/1.0 (github.com/robertyang87/tennislive)"}
OK_LICENSES = ("CC0", "CC BY", "Public domain", "PD")  # "CC BY" 亦匹配 CC BY-SA
MAX_EDGE = 1920

# (输出文件名, Commons 文件名或 None, 检索词/分类名)
VENUES = [
    # 城市地标（该站没有可用的球场照时用）
    # 雅典：帕特农地标 → Telekom Center Athens 改成网球场的实拍，见 OFFICIAL_VENUES。
    # 这一站是**唯一一个需要动像素**的：赛事在室内、晚场、看台不打灯，原图
    # 压完卡片遮罩后均值只有 21.6、中位 14，摆在格施塔德（54）和汉堡（67）
    # 旁边就是一块黑。
    #
    # 但它和「逆光剪影」那条不是一回事，别混：那张是**主体本身**没入暗部
    # （中位 0、95% 像素纯黑，怎么调都回不来）；这张的球场是打了灯的，
    # 暗的是四周。gamma 2.4 提亮之后压完是均值 55.6 / 中位 53，正好落在
    # 已用那几张的区间里，看台、横幅、记分牌全部可读。
    # **动了像素就要写明**——credits 里记着 gamma 值。
    # ⚠️ 雅典这一条**赛事本身搞错过一次**。manifest 里的 "athens open" 对应的是
    # **WTA 250 的 Athens Open**：2026 年 7 月 13–19 日、露天硬地、打在
    # Athens Olympic Tennis Centre（ΟΑΚΑ）。而我先后配过两张
    # Telekom Center Athens 的室内照——那是 **ATP 的 Hellenic Championship**，
    # 2025 年 11 月、室内、另一个场馆，2026 年 ATP 赛历上根本没有雅典站。
    # 同城不同赛事不同场地，和「ATV Bancomat 印成维罗纳」是同一类错：
    # **先确认这条 alias 对的是哪个赛事，再去找场地**。
    # 判据：WTA 官方页 /tournaments/1175/athens/，赛事官网 athens-open.com/venue。
    ("athens-olympic-tennis-centre.jpg", None, None),
    # 埃斯托里尔原来是 File:Estoril - panoramio.jpg，一段海岸步道加铁轨，既不是
    # 地标也不是球场，整页铺开像个火车站。Commons 上也没有中央球场——卡西诺那张
    # 建筑只占中间一条，上下全是天空和草坪。改用赛事官方媒体，见 OFFICIAL_VENUES。
    ("estoril-centre-court.jpg", None, None),
    # 汉堡：地标（易北爱乐）→ Am Rothenbaum 中心球场。这一站被判过两次"没有"，
    # 两次都是**查法不对**，不是真没有：
    #
    # 1. 第一次翻 Commons 关键词搜索，只翻出场外纪念品帐篷 / 只见钢索的顶棚 /
    #    2200×590 的宽幅。**改成按分类列**（`Category:Am Rothenbaum`，19 个文件）
    #    立刻看见 `Hamburg Rotherbaum DS148n..DS177n` 一整组球场内景——
    #    关键词搜索命中的是标题里带词的，这一组标题里一个词都没有
    # 2. 第二次翻官网的 wp-json `?search=`，德语 Rothenbaum / Center Court /
    #    Stadion / Anlage 全 0。**search 匹配的是标题/说明**，而赛事站的图叫
    #    `WIV_7686`、`20260726_1639255` 这种相机原始文件名，再准的词也搜不到。
    #    要按页把媒体库整个列下来再按尺寸筛（`--wp-list`）
    #
    # 选中 DS150n：从底线后方高处沿球场长轴拍，竖切之后近端看台/红土/远端看台
    # 与顶棚全在框内——正是「竖版卡里的全景取决于拍摄视角」那条要的角度。
    # 远处大屏写着 HAMBURG 2024，那是汉堡申办 2024 奥运的口号，不是赛事年份
    # （拍摄时间 2015-08，两者对得上，不矛盾）。
    ("hamburg-rothenbaum-centre-court.jpg", "File:Hamburg Rotherbaum DS150n.jpg", None),
    # 巴勒莫换过两次。第一次从马西莫剧院这个地标换成官网的
    # Campo-centrale-dallalto（wp-json 搜意大利语 campo centrale 命中的）。
    # 但那张**几乎是纯俯视**——竖切之后整屏只有红土，看不出是个碗，
    # 是 `preview_venue_crop.py --scrim` 那一版联系表把它暴露出来的。
    # 官网媒体库 430 张整个列过一遍（--wp-list），**没有第二张全景**：
    # 全是球员、颁奖、发布会。现在这张来自 LiveSicilia 的转载，黄昏、
    # 近端蓝色看台 + 红土 + 远端看台 + 巴勒莫的山，整个碗都在。
    # 官方来源优先，但**官方没有全景时，构图优先于出处**。
    ("palermo-country-time-centre-court.jpg", None, None),
    ("istanbul-historical-peninsula.jpg",
     "File:Historical peninsula and modern skyline of Istanbul.jpg", None),
    # 雅西：原来用的是文化宫地标。Baza Sportivă Ciric 的中心球场满场照在
    # 罗马尼亚新闻站上（红土、两侧蓝色看台、树林作背景），整个碗都在竖切里。
    # 顺带记一条，纠正 CLAUDE.md 里「ATP 总站封」那个说法：**403 是按文件来的，
    # 不是整站**。同一时刻 iasi-2023-venue.jpg 返回 200 + image/jpeg，
    # gstaad-2023-venue.jpg / hamburg-2023-venue.jpg 返回 403——Sitecore 对
    # 不存在的媒体就是回 403 而不是 404。所以：
    #   - `<slug>-<year>-venue.jpg` 这个命名**猜不出来**，七个站四个年份全军覆没
    #   - 但**拿到真实文件名就能直接取**，不需要绕镜像域名
    #   - 判据是拿一个已知存在的（iasi-2023-venue.jpg）当对照：它 200 而别的 403，
    #     说明是文件不在，不是我被挡了
    ("iasi-ciric-centre-court.jpg", None, None),
    # ⚠️ 这一站原来整条都是错的：slug 叫 verona、卡上印「维罗纳 · 意大利」、
    # 配图是维罗纳的圆形竞技场（一座歌剧院，跟网球没关系）。
    # **赛事名里的 ATV 是 Antico Tiro a Volo——罗马的一家俱乐部**，
    # 不是 Associazione Tennis Verona。判据是 WTA 自己的赛事页：
    # wtatennis.com/tournaments/1130/**rome**/ 的标题就是
    # 「ATV BANCOMAT TENNIS OPEN Overview」。
    # 别名里的 "verona" 也一并去掉——维罗纳另有一站 ATP Challenger
    # （Internazionali di Tennis Verona），留着会把那站也套上罗马的图。
    # 现在的图见 OFFICIAL_VENUES：挡板上写着 ATV / ROMA，自证。
    ("rome-atv-tennis-open-courts.jpg", None, None),
    # 北京：钻石球场满场。中网 ATP500 与 WTA1000 同场地，一条别名两边都命中。
    ("beijing-diamond-court.jpg", None, None),
    # 上海：旗忠中央球场。判据是顶棚那八瓣白玉兰——全世界只有这一个，认场地不用看文字。
    ("shanghai-qizhong-centre-court.jpg", None, None),
    # 武汉：光谷中央球场满场。挡板上的赛事名和年份自证，不靠看图推断。
    ("wuhan-optics-valley-centre-court.jpg", None, None),
    # 成都：ATP 官方图库的 stadium shot，文件名自证年份与场地。
    ("chengdu-centre-court.jpg", None, None),
    # 杭州：小莲花那圈花瓣状可开合顶棚是这个场馆独有的，认场地不用看文字。
    ("hangzhou-lotus-centre-court.jpg", None, None),
    # 宁波：赛事方通过 PR Newswire 发的官方图。
    ("ningbo-centre-court.jpg", None, None),
    # 广州：2025 收官报道的现场图。
    ("guangzhou-centre-court.jpg", None, None),
    # 温斯顿-塞勒姆：Wake Forest 中心球场黄昏满场。
    ("winston-salem-centre-court.jpg", None, None),
    # 蒙特雷：赛事官网自己的场馆图，场地刷着 MONTERREY，背景马德雷山，自证。
    ("monterrey-centre-court.jpg", None, None),
    # 辛辛那提：从空场换成满场。上一版构图没问题，问题是空。
    ("cincinnati-centre-court-full.jpg", None, None),
    # 瓜达拉哈拉：Complejo Panamericano 满场，场地刷着 GUADALAJARA。
    ("guadalajara-centre-court.jpg", None, None),
    # 圣保罗：2025 首届 SP Open，场地刷着 SÃO PAULO。
    ("sao-paulo-centre-court.jpg", None, None),
    # 首尔：奥林匹克公园网球中心。
    ("seoul-olympic-park-centre-court.jpg", None, None),
    # 东京：有明コロシアム，ATP500 与 WTA500 共用。注意大阪那站同名不同场地。
    ("tokyo-ariake-coliseum.jpg", None, None),
    # 新加坡：Kallang Tennis Hub，场地刷着 SINGAPORE 自证。空场且只有 680px，是这一批里最弱的一张，代价记在 credits。
    ("singapore-centre-court.jpg", None, None),
    # 巴塞尔：St. Jakobshalle 满场，场地刷着 BASEL 自证。
    ("basel-st-jakobshalle.jpg", None, None),
    # 维也纳：Wiener Stadthalle 满场。
    ("vienna-stadthalle-centre-court.jpg", None, None),
    # 大阪：靱テニスセンター。⚠️ 和东京有明是**同名不同场地**，见下面 tokyo 那条的别名注释。
    ("osaka-utsubo-centre-court.jpg", None, None),
    # 布鲁塞尔：欧洲公开赛 2025 年搬到 Brussels Expo Palais 12，别拿安特卫普时期的图
    ("brussels-centre-court.jpg", None, None),
    # 金奈：SDAT Nungambakkam，2026 年这站是 WTA250，场馆沿用旧 ATP 金奈赛的中心球场。
    # Commons 来的，钉住文件名让 fetch_set 能重取——**不进 OFFICIAL_VENUES**，
    # 那一档的含义是「不在 Commons、许可没核实」。
    ("chennai-centre-court.jpg",
     "File:Nungambakkam SDAT Tennis Stadium floodlit match panorama.jpg", None),
    # 斯德哥尔摩：皇家网球馆，官网（ATP Sitecore）只有合作方 logo 和球员头像，没有场馆图；
    # 这张出自 Commons，同上钉文件名
    ("stockholm-centre-court.jpg", "File:Kungliga Tennishallen.JPG", None),
    # 巴黎：2025 年起在 Paris La Défense Arena，别拿贝尔西的图
    ("paris-centre-court.jpg", None, None),
    # 香港：维多利亚公园中央球场，ATP／WTA 两站共用；协会站 tennishk.org 开着 wp-json，按 search=victoria 就能翻出整批
    ("hongkong-victoria-park.jpg", None, None),
    # 迪拜：赛事官网开着 wp-json，search=stadium 直接给出整组中心球场全景；WTA1000 与 ATP500 共用
    ("dubai-centre-court.jpg", None, None),
    # 迈阿密：赛事官网开着 wp-json；WTA1000 与 ATP1000 共用硬石球场
    ("miami-centre-court.jpg", None, None),
    # 马德里：赛事官网开着 wp-json，搜索词要用西语（pista/estadio）；WTA1000 与 ATP1000 共用
    ("madrid-centre-court.jpg", None, None),
    # 蒙特卡洛：官网 montecarlotennismasters.com 开着 wp-json（rolexmontecarlomasters.mc 那个域名本环境不通），搜索词用法语
    ("montecarlo-centre-court.jpg", None, None),
    # 斯海尔托亨博斯：libema-open.nl 开着 wp-json，搜索词用荷兰语；ATP250 与 WTA250 共用
    ("denbosch-centre-court.jpg", None, None),
    # 鹿特丹：官网非 WP，图在 /files/images/<年>/，渲染首页拿路径；DOM 尺寸是缩略的，原图更大
    ("rotterdam-centre-court.jpg", None, None),
    # 布里斯班：Tennis Australia 的 Adobe DM 图床（tennis.com.au/adobe/dynamicmedia/deliver/），width= 可调；源图 1200×800 封顶
    ("brisbane-centre-court.jpg", None, None),
    # 阿德莱德：同布里斯班，走 Tennis Australia 的 Adobe DM；WTA500 与 ATP250 共用
    ("adelaide-centre-court.jpg", None, None),
    # 奥克兰：asbclassic.co.nz 走 ATP Sitecore，/-/media/sites/tournaments/auckland/news/ 下有 finals-stadium-generic；ATP250 与 WTA250 共用
    ("auckland-centre-court.jpg", None, None),
    # 慕尼黑：bmwopen.de 开着 wp-json（747 项），搜 center court 直接中
    ("munich-centre-court.jpg", None, None),
    # 里约：rioopen.com 走 ATP Sitecore，vistageral.jpg 直接挂在 sites/tournaments/rio/ 根下
    ("rio-centre-court.jpg", None, None),
    # 蒙彼利埃：官网从 opensuddefrance.com 改名到 openoccitanie.com，wp-json 在新域名上
    ("montpellier-centre-court.jpg", None, None),
    # 巴塞罗那：curl 403 但 Playwright 渲染能过（按 UA 挡的）；ATP Sitecore
    ("barcelona-centre-court.jpg", None, None),
    # 多哈：赛事官网全部不通，走 WTA 赛事页 hero（photoresources.wtatennis.com）；WTA1000 与 ATP500 共用
    ("doha-centre-court.jpg", None, None),
    # 印第安维尔斯：官网是 DatoCMS、/media 页没有场馆图，走 WTA 赛事页 hero；Commons 那张是 Pacific Life Open 年代的，别用
    ("indianwells-centre-court.jpg", None, None),
    # charleston：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("charleston-centre-court.jpg", None, None),
    # bogota：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("bogota-centre-court.jpg", None, None),
    # ostrava：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("ostrava-centre-court.jpg", None, None),
    # linz：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("linz-centre-court.jpg", None, None),
    # rouen：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("rouen-centre-court.jpg", None, None),
    # strasbourg：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("strasbourg-centre-court.jpg", None, None),
    # nottingham：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("nottingham-centre-court.jpg", None, None),
    # badhomburg：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("badhomburg-centre-court.jpg", None, None),
    # hobart：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("hobart-centre-court.jpg", None, None),
    # abudhabi：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("abudhabi-centre-court.jpg", None, None),
    # cluj：WTA 赛事页 hero（数字 id 从 api.wtatennis.com 取）
    ("cluj-centre-court.jpg", None, None),
    # 女王俱乐部 ATP500：LTA 官网 /siteassets/events/hsbc/ 的 6000x4000 原图，底线后方沿长轴
    ("queens-club-centre-court-atp.jpg", None, None),
    # 女王俱乐部 WTA500：同一座中心球场，取 WTA 那一届的画面（围板 WTA 500）
    ("queens-club-centre-court-wta.jpg", None, None),
    # 伊斯本 ATP250 + WTA250：LTA 官网 /siteassets/events/eastbourne/，底线后方沿长轴，整个碗都在
    ("eastbourne-devonshire-park-centre-court.jpg", None, None),
    # 德雷海滩 ATP250：官网媒体库 2026-2027-press，夜场全景，近端远端看台都在
    ("delray-beach-stadium-centre-court.jpg", None, None),
    # 休斯顿 ATP250：ATP 赛事主视觉，红土 + 绿顶看台，focal 左移到 30% 让球场成为落点
    ("houston-river-oaks-centre-court.jpg", None, None),
    # 马略卡 ATP250：ATP 赛事主视觉，顶部收 160px 去掉空天
    ("mallorca-country-club-centre-court.jpg", None, None),
    # 达拉斯 ATP500：Ford Center 网球布置的实拍，底线后方沿长轴
    ("dallas-ford-center-centre-court.jpg", None, None),
    # 罗马 ATP1000 + WTA1000：ATP 赛事主视觉，Campo Centrale 满场
    ("rome-foro-italico-centre-court.jpg", None, None),
    # 哈雷 ATP500：ATP 赛事主视觉，OWL Arena 开顶满场
    ("halle-owl-arena-centre-court.jpg", None, None),
    # 斯图加特 ATP250：ATP 赛事主视觉，Weissenhof 草地；别名按赛事名写，别用城市名
    ("stuttgart-weissenhof-centre-court.jpg", None, None),
    # 布宜诺斯艾利斯 ATP250：ATP 赛事主视觉，Vilas 中央球场满场
    ("buenos-aires-vilas-centre-court.jpg", None, None),
    # 圣地亚哥 ATP250：ATP 赛事主视觉的 -sunset 变体，满场夜赛
    ("santiago-centre-court.jpg", None, None),
    # 斯图加特 WTA500：Porsche-Arena 室内红土；别名按赛事名写，别用城市名
    ("stuttgart-porsche-arena-centre-court.jpg", None, None),
    # 布加勒斯特 ATP250：赛事域名上的 stadium shot，红土满场
    ("bucharest-centre-court.jpg", None, None),
    # 主球场／主场馆（优先用这一类）
    # 华盛顿：File:FitzGerald Tennis Center.jpg 拍的确实是本站场馆，但构图不行
    # ——左上角一大块深色顶棚压掉小半屏，看台缩成一条，整页铺开看不出是球场。
    # 换成 2023 年 DC Open 的中央球场满场照：场地上印着 WASHINGTON D.C.，
    # 自己就把身份说清楚了。
    ("washington-fitzgerald-tennis-center.jpg",
     "File:Karatsev–Tiafoe in stadium at the 2023 DC Open 01.jpg", None),
    # 孟菲斯（2026 年新设的 WTA250，在 Leftwich Tennis Center）：球场本身在
    # Commons 上是真空——"Leftwich Tennis Center" 与 "Memphis Tennis Center"
    # 两条查询都是 0 命中，而同一批其他查询各返回 25 条，不是限流。最后是在
    # WTA 官方图库里找到的，见 OFFICIAL_VENUES。
    #
    # 中途走过两条弯路，都留在这儿免得再走一遍：城市夜景天际线（对题但不是
    # 球场）；赛事官网票务页那三张 Stadium 图**全是效果图不是实拍**——横幅上
    # 的字是糊的（TOPNO / MEMPH / TENOS GEHPLIS），观众是重复贴图。带假文字
    # 的渲染图比一张真实城市照更糟。
    # 后来换成主球场（全场航拍是对的，但那不是中心球场）。这一步差点栽进
    # **另一个坑，比效果图更隐蔽**：WTA 赛事页挂在这一站名下的 hero 图
    # （1167_Memphis-Hero-2）确实是**实拍**——放大看观众是一个个不同的人，
    # 场地上还刷着 MEMPHIS CLASSIC——但它**不是这个场地**。
    #
    # 判据是**场地自身的颜色**，不是文字：孟菲斯主球场是**灰色前场 + 蓝色
    # 场心 + 蓝白临时看台**，赞助带是深蓝的（Mercedes-Benz / TOPNOTCH /
    # crionet / Campbell Clinic）；那张 hero 是**绿色前场 + 紫黄赞助带 +
    # 绿色折叠椅**。两者对不上。它上传于 2026-06-25、早于首届 7/25 开赛，
    # 多半是别处拍的宣传图后期刷上了场地文字。
    #
    # 「官方图库把它挂在这一站名下」是**间接信号**，不是产物。真正能证伪的
    # 是把它跟同场地的另一份画面并排比颜色——见 CLAUDE.md。
    #
    # 现在用的是 Action News 5 (WMC-TV) 2026-07-26 赛事报道成片第 14.0 秒的
    # 截帧：临时看台坐着人、蓝色场地、赞助带清楚。代价如实记在 credits：
    # 1280×720 的源，裁掉下方台标条后放大了 2.78 倍，偏软。
    ("memphis-leftwich-stadium-court.jpg", None, None),
    # 洛斯卡沃斯 ATP250（Cabo Sports Complex 的 Estadio Alejandro Burillo）：
    # 球场在 Commons 上是真空——"Cabo Sports Complex" 只命中一张波兰滑水赛的
    # 照片，"Estadio Alejandro Burillo" 0 命中，全站与这个赛事沾边的只剩一个
    # logo PNG。原来退而用地标埃尔阿尔科海蚀拱，但那是海蚀拱不是球场。
    #
    # 球场照最后在赛事官网自己的媒体库里找到，见 OFFICIAL_VENUES。顺带三条
    # 探测经验：官网挂着三个域名，abiertoloscabos.com 是个裸的目录索引、
    # loscabosopen.com 是 Hostinger 的停放页，活的那个是 loscabostennisopen.com；
    # 它的 /en/photos 和 /en/gallery 都是 404，**别据此判定"没有图库"**——
    # 它是 WordPress，wp-json/wp/v2/media?search=… 一查就把原图连尺寸一起列出来。
    ("los-cabos-estadio-alejandro-burillo.jpg", None, None),
    # 加拿大站：原来钉的 File:RogersCup2011-2.jpg 名字里带赛事，画面却是场外
    # 的赞助商帐篷、排队人群和旗杆——不是球场也不是地标。整页拿它当底的时候
    # 一眼就看出来了。换成主球场（Sobeys Stadium / 旧称 Rexall Centre）的中央
    # 球场俯瞰，场地上就印着 TORONTO。
    # 再换一次：那张 Rexall Centre 俯瞰是侧面横拍且空场，竖版裁完只剩中段。
    # 现在是单打决赛满场的中心球场，整个碗都在竖切里，场地前场还刷着 TORONTO。
    # 官方渠道这站全空：nationalbankopen / tenniscanada / sobeysstadium 三个域名
    # 都不是 WordPress（wp-json 全 404），tenniscanada 的 assets CDN 要从页面读
    # 真实 URL、猜不出来；Commons 与 Openverse 都是 0。
    ("canada-sobeys-centre-court.jpg", None, None),
    # 加拿大站是**一个赛事名、同周在两座城市办**，而且男女每年互换主办城市
    # （2025 男子多伦多／女子蒙特利尔，2026 反过来）。只按赛事名匹配的话
    # 两条都命中，随便挑一条就有一半的概率在卡上印错城市。
    # manifest 里用 host_years 声明「哪一年办哪条巡回赛」，
    # venue_assets._hosts() 按 match.tour + 年份奇偶挑。
    # 蒙特利尔这张：场地前场刷着 MONTRÉAL，赞助带 Banque Nationale / ROGERS。
    ("canada-iga-stadium-centre-court.jpg", None, None),
    # 辛辛那提：原来那张是侧面横拍，竖版裁完只剩中段。赛事官网是 WordPress，
    # wp-json/wp/v2/media?search=stadium 一查就是一堆 2560 宽的官方图；选的这张
    # 从底线后方顶层往下拍，近端看台 / 球场 / 远端看台整个碗都在竖切里。
    # 注意：这个站用浏览器 UA 请求 wp-json 会被 WAF 挡 403，用脚本自己的 UA 反而
    # 200——「取不到」和「0 命中」要分开，见 tools/probe_venue_photos.py 的 Blocked。
    # 美网换过两次。第一次从侧面横拍换成 View From the Top of the Arthur Ashe
    # Stadium——角度对了，但那张拍于 2013 年，**画面里没有顶棚**：阿瑟阿什
    # 2016 年才装可开合顶棚，等于印了一个已经不存在的样子（画面上半屏是
    # 露天看台加曼哈顿天际线）。
    # 现在这张是 2024 女单四分之一决赛：顶棚桁架在画面上方，两层看台满场，
    # LED 带上写着 QINWEN ZHENG / ARYNA SABALENKA，包厢层写着
    # ARTHUR ASHE STADIUM——年份、场地、赛事全部自证。
    ("usopen-arthur-ashe-stadium.jpg",
     "File:Aryna Sabalenka vs. Qinwen Zheng in a quarterfinals of the 2024 US Open - 01.jpg", None),
    # 基茨比厄尔换过两次：山景地标 → Commons 的 Tennisstadion Kitzbuehel 2015
    # → 现在这张满场。第二版是**空场**，而且拍摄点在一端很高处，竖切之后
    # 球场被压在画面最底下，整屏是空看台和山坡；试过按 x 位移预裁 3:4 四档，
    # 四档都救不回来——**问题在拍摄点，不在裁法**。
    # Commons 这条线是真空：Category:Austrian Open (tennis) 连两个年份子分类
    # 一起列完，横图且 ≥1500px 的只有两张，其中一张就是上一版。
    # 官网 generaliopen.com 的图廊按 /img/<md5>.jpg 存（去掉 _soft 后缀就是原图），
    # 22 张里没有球场全景。现在这张来自 Kitzbüheler Anzeiger，
    # 远端雨棚上写着 KITZBÜHEL CHAMPIONSHIPS，自证。
    ("kitzbuhel-centre-court.jpg", None, None),
    # 布拉格：原来用的是城堡地标。Livesport Prague Open 打在 Štvanice，
    # 场地前场刷着 PRAGUE，赞助带是 crocodille / Quantcom——画面自己认领。
    ("prague-stvanice-central-court.jpg",
     "File:Central tennis court at Štvanice 02.jpg", None),
    # Gstaad：搜索里名字带赛事的那张（EFG Swiss Open Gstaad-ATP 250）其实是
    # 球员特写，中间还压着摄影师水印，既不是场馆也不能用——名字对题不等于
    # 内容对题。Commons 上也没有 Roy Emerson Arena 的照片，Category:Gstaad
    # 的 136 张几乎全是雪景（这里是滑雪胜地）。而瑞士公开赛是七月红土——
    # 拿雪景当七月比赛的背景，季节整个错了，和"温网草地配法网司线"是同一类错。
    # 所以取夏季的萨嫩兰谷地：季节对得上，chalet + 阿尔卑斯谷地也就是格施塔德
    # 本身的样子。
    # 格施塔德：山谷地标 → Roy Emerson Arena 中心球场，见 OFFICIAL_VENUES。
    # 这一站踩的是「图库路径 404 不等于没有图库」的变体：官网 wp-json 返回
    # 401（插件挡了），首页那张叫 Roy-Emerson-Arena.png 的打开是**谷歌地图
    # 截图**，于是"官网没有球场照"。
    # 真正的入口在 **sitemap** 里：`wp-sitemap-posts-page-1.xml` 一列就看见
    # `/media/photos/`（530 张）和 `/infos/le-village-le-stade/`。后者 12 张
    # 里就有整个球场。**wp-json 被挡时，sitemap 是另一条进得去的门。**
    # 另：站上挂的是 `-1024x683` 的缩略图，去掉这个后缀就是 6000×4000 原图。
    ("gstaad-roy-emerson-arena.jpg", None, None),
    ("bastad-tennis-stadium.jpg", "File:Båstad Tennis Stadium.jpg", None),
    # 下面这批原本只躺在 assets/ 与 credits.json 里、不在本列表中。fetch_set()
    # 会按本列表重建 credits.json，所以漏登记的条目每跑一次 CI 就被冲掉一次
    # ——umag 的图还在 manifest 里生效，credits 一丢它就整条消失。补登记。
    # 乌马格：Commons 那张是球场**外立面**，不是场内。赛事官网走的是 Sitecore，
    # 图廊路径 /-/media/sites/tournaments/umag/galerije/goran/goran-(N).png 顺着
    # N 探就能拿到场内图（1..3、6 存在，其余是 soft-404 的 text/html——**要看
    # Content-Type**）。最后选的是克罗地亚旅游局媒体库那张满场夜场：红土、蓝色
    # 看台、泛光灯，整个碗都在竖切里，比官方图廊里的空场版有气氛。
    ("umag-goran-ivanisevic-centre-court.jpg", None, None),
    ("ao-rod-laver-arena.jpg", "File:RodLaverArenanight2013.jpg", None),
    # 同一组照片里换了一张：first round 那张是从角上拍的，竖切之后球场歪在一边；
    # quarter final 这张是从底线后方看过去，近端看台 / 蓝色球场 / 远端看台加墨尔本
    # 天际线整个碗都在竖切里。
    ("ao-rod-laver-bowl.jpg",
     "File:Rod Laver Arena Melbourne Park Australian Open 2023 quarter final.jpg", None),
    # 法网：原来钉的 "vue extérieure" 那张，画面主体是场外一尊举拍的雕像，
    # 夏蒂埃球场只在背后露一角——当背景图时雕像成了焦点，不像主球场。
    # 换成球场内景：红土、看台，以及"LA VICTOIRE APPARTIENT AU PLUS OPINIÂTRE"。
    ("rg-philippe-chatrier.jpg", "File:Court Philippe Chatrier 2024.jpg", None),
    # 温网换过两次。第一次从**全园航拍**换成 Centre Court Wimbledon 2009——
    # 那张确实是场内，但**站在侧面看台横着拍**：竖切之后画面上半屏全是顶棚
    # 桁架，草地只剩底下一条。是 `--scrim` 那一版联系表把它暴露出来的
    # （之前只渲裁切不渲遮罩，压完更看不清）。
    # 现在这张是 2023 男单决赛，从底线后方看台高处沿长轴拍：近端观众、整片
    # 草地、远端满场看台、开着的屋顶，一个不少；记分牌上 Alcaraz / Djokovic
    # 可读，画面自己把是哪一场说死了。
    ("wimbledon-centre-court.jpg", "File:2023 Wimbledon Men's singles final (1).jpg", None),
    ("usopen-arthur-ashe-exterior.jpg", "File:Arthur Ashe Stadium, July 7, 2018.jpg", None),
]

# 赛事官方媒体来源的场馆图。有些站 Commons 上根本没有能用的主球场照片，官网
# 的媒体库里却有——埃斯托里尔就是这样。这类图不在 Commons，抓取脚本不去重取，
# 只负责**保住出处**：fetch_set() 会按 VENUES 重建 credits.json，不在这里登记
# 就每跑一次 CI 冲掉一次。
#
# 授权不做检索闸门（见 CLAUDE.md）：来源 URL 全程记录，许可名缺失就写
# unverified，发布前的权利判断由人工检验环节负责。
OFFICIAL_VENUES = {
    "bucharest-centre-court.jpg": {
        "title": "布加勒斯特中央球场满场，红土，远端看台顶上写着 ROMANIA，围板是 ȚIRIAC OPEN，球网上是 ATP TOUR",
        "license": "unverified · ATP 官方图，经赛事域名 tiriacopen.ro 取得",
        "artist": "ATP 官方图（摄影师未署名）",
        "page": "https://www.tiriacopen.ro/-/media/images/news/2024/04/21/12/16/bucharest-2024-stadium-shot-2.jpg",
    },
    "stuttgart-porsche-arena-centre-court.jpg": {
        "title": "斯图加特 Porsche-Arena 室内红土中心球场，场地前场刷着 STUTTGART，围板 porsche-tennis.com，大屏是 Świątek 对 Raducanu 与 WTA 500",
        "license": "unverified · 赛事主办方官方图，转载站未署名",
        "artist": "Porsche 赛事官方图（摄影师未署名，经 sport-s.de 转载）",
        "page": "https://sport-s.de/wp-content/uploads/2024/06/Porsche-Tennis-Totale.jpg",
    },
    "santiago-centre-court.jpg": {
        "title": "圣地亚哥中央球场夜场满场，红土，灯柱亮着，远处是安第斯山与圣地亚哥城区",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/santiago_tournimage_2020-sunset.jpg",
    },
    "buenos-aires-vilas-centre-court.jpg": {
        "title": "布宜诺斯艾利斯草地网球俱乐部 Guillermo Vilas 中央球场满场，红土，近端远端看台与灯柱都在画面里",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/buenosaires_tournimage_2019.jpg",
    },
    "stuttgart-weissenhof-centre-court.jpg": {
        "title": "斯图加特 TC Weissenhof 草地中心球场满场，挡板写着 BOSS，侧板写着 TC Weissenhof 与 Region Stuttgart",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/stuttgart_tournimage_2022.jpg",
    },
    "halle-owl-arena-centre-court.jpg": {
        "title": "哈雷 OWL Arena 中心球场满场，开顶状态，环形挡板写着 TERRA WORTMANN OPEN 与 owlarena-world.de",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/halle_tournimage_2023.jpg",
    },
    "rome-foro-italico-centre-court.jpg": {
        "title": "福罗意大利中央球场（Campo Centrale）满场，从底线后方沿长轴拍，记分牌写着 F. VERDASCO / R. NADAL，围板是 Internazionali 的赞助带",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/rome_tournimage_2019.jpg",
    },
    "dallas-ford-center-centre-court.jpg": {
        "title": "弗里斯科 Ford Center at The Star 主球场，从底线后方高处沿长轴拍，挡板写着 DALLAS OPEN 与 ATP 500，记分牌是 PAUL / OPELKA，场地前场刷着 DALLAS",
        "license": "unverified · 赛事官网媒体库 dallasopen.com",
        "artist": "赛事官方图（摄影师未署名）",
        "page": "https://www.dallasopen.com/-/media/images/news/2026/01/12/02/39/dallas-2026-prize-money-image.jpg",
    },
    "mallorca-country-club-centre-court.jpg": {
        "title": "圣蓬萨 Mallorca Country Club 中心球场满场，草地两端看台都在，围板写着 MALLORCA，背后是松林覆盖的山坡",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://mallorcachampionships.com/-/media/images/atp-tournaments/tournament-images/mallorca_tournimage_2022.jpg",
    },
    "houston-river-oaks-centre-court.jpg": {
        "title": "River Oaks 乡村俱乐部主球场满场，绿色顶棚看台与裁判塔，围板写着冠名商 FAYEZ SAROFIM & CO.，旗杆上是美国旗与得州旗",
        "license": "unverified · ATP 官方图，经赛事域名镜像取得",
        "artist": "ATP 官方赛事主视觉（摄影师未署名）",
        "page": "https://dallasopen.com/-/media/images/atp-tournaments/tournament-images/houston_tournimage_2019.jpg",
    },
    "delray-beach-stadium-centre-court.jpg": {
        "title": "德雷海滩网球中心主看台球场夜场满场，场地刷着 ATP TOUR，记分牌写着 PAUL / TIEN 与 ATP 250",
        "license": "unverified · 赛事官网媒体库 delraybeachopen.com",
        "artist": "赛事官方图（摄影师未署名）",
        "page": "https://www.delraybeachopen.com/",
    },
    "eastbourne-devonshire-park-centre-court.jpg": {
        "title": "德文郡公园中心球场满场，挡网写着 EASTBOURNE、围板写着 Rothesay INTERNATIONAL，背景是伊斯本的教堂尖顶与维多利亚式排屋",
        "license": "unverified · 赛事主办方 LTA 官网图库",
        "artist": "LTA 官方图（摄影师未署名）",
        "page": "https://www.lta.org.uk/fan-zone/international/hsbc-championships/",
    },
    "queens-club-centre-court-wta.jpg": {
        "title": "女王俱乐部中心球场满场，围板写着 HSBC CHAMPIONSHIPS 与 WTA 500，草地上刷着 LONDON",
        "license": "unverified · 赛事主办方 LTA 官网图库",
        "artist": "LTA 官方图（摄影师未署名）",
        "page": "https://www.lta.org.uk/fan-zone/international/hsbc-championships/",
    },
    "queens-club-centre-court-atp.jpg": {
        "title": "女王俱乐部中心球场（安迪·穆雷球场）满场，场地前场刷着 ATP TOUR，围板写着 HSBC CHAMPIONSHIPS，左侧为俱乐部红砖会所",
        "license": "unverified · 赛事主办方 LTA 官网图库",
        "artist": "LTA 官方图（摄影师未署名）",
        "page": "https://www.lta.org.uk/fan-zone/international/hsbc-championships/weather-forecast/",
    },
    "cluj-centre-court.jpg": {
        "title": "BT Arena 中心球场 · 室内紫色场地满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/04/28/cdcb778a-237c-4075-820e-f5e4762863e2/2050-Cluj.jpg",
    },
    "abudhabi-centre-court.jpg": {
        "title": "扎耶德体育城网球中心中心球场 · 满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/10/20/cbae0b62-ac90-4b4f-8c15-4acdb35ea037/2088-Abu-Dhabi.jpg",
    },
    "hobart-centre-court.jpg": {
        "title": "Domain 网球中心中心球场 · 满场，背景是霍巴特的山",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/04/28/d1ead324-0027-4f5b-a4d4-489b562639ea/1050-Hobart.jpg",
    },
    "badhomburg-centre-court.jpg": {
        "title": "Bad Homburg 中心球场 · 草地满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/04/28/5023f41c-baec-4531-b585-260d8d468f3f/2017-Bad-Homburg-Open-2.jpg",
    },
    "nottingham-centre-court.jpg": {
        "title": "诺丁汉网球中心中心球场 · 草地满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/10/16/0b899ba9-b477-48ea-9e9e-5cb6aeb30699/1080_bg_Nottingham-min.jpg",
    },
    "strasbourg-centre-court.jpg": {
        "title": "Tennis Club de Strasbourg 中心球场 · 红土满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/05/12/ffbc5331-cbef-4d6a-8f6d-3a0c93eefa0e/406-Strasbourg.jpg",
    },
    "rouen-centre-court.jpg": {
        "title": "Kindarena 中心球场 · 室内红土满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/05/02/45da6924-0e65-40ec-b971-04b2806da1f8/2066-Rouen.png",
    },
    "linz-centre-court.jpg": {
        "title": "TipsArena Linz 中心球场 · 室内紫色场地满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/04/28/5b8f9a8e-bc19-4019-8e7a-f8a5ccd60071/528-Linz.jpg",
    },
    "ostrava-centre-court.jpg": {
        "title": "Ostravar Aréna 中心球场 · 室内满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2026/05/29/1c78195c-5e01-4cfd-9c6b-c8b3fba080c4/1054-Ostrava-Background.jpg",
    },
    "bogota-centre-court.jpg": {
        "title": "Centro de Alto Rendimiento 中心球场 · 红土满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2026/06/03/55ee0af0-08ca-4764-96e3-21b366d4bfae/Tournament-background-894-Bogota-new.png",
    },
    "charleston-centre-court.jpg": {
        "title": "Credit One Stadium 中心球场 · 满场",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/04/28/1588de8d-8dcd-449f-99a9-e0e2eb688e40/804-Charleston.JPG",
    },
    "indianwells-centre-court.jpg": {
        "title": "印第安维尔斯网球花园 1 号球场 · 满场，场地前场刷着 INDIAN WELLS",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/04/28/d1b371b4-11cf-4c25-99dc-a3b8bcaa06e4/609-BNP-Paribas-Open.jpg",
    },
    "doha-centre-court.jpg": {
        "title": "哈利法国际网球场中心球场 · 夜场满场，背景是多哈天际线",
        "license": "unverified · WTA 官方媒体库",
        "artist": "photoresources.wtatennis.com 官方图库",
        "page": "https://photoresources.wtatennis.com/photo-resources/2025/10/16/31b8cefd-8f3d-4180-949d-be019385cdd6/1003_bg_Qatar_Doha-min.jpg",
    },
    "barcelona-centre-court.jpg": {
        "title": "皇家巴塞罗那网球俱乐部 拉法·纳达尔球场 · 红土满场",
        "license": "unverified · 赛事官方媒体库",
        "artist": "barcelonaopenbancsabadell.com 官方图库",
        "page": "https://www.barcelonaopenbancsabadell.com/-/media/images/news/2026/04/13/19/29/barcelona-2026-results.jpg",
    },
    "montpellier-centre-court.jpg": {
        "title": "Sud de France Arena 中心球场 · 满场（粉蓝双色场地）",
        "license": "unverified · 赛事官方媒体库",
        "artist": "openoccitanie.com 官方图库",
        "page": "https://www.openoccitanie.com/wp-content/uploads/2025/01/sdf-arena-pleine-scaled.jpg",
    },
    "rio-centre-court.jpg": {
        "title": "瓜加·库尔滕球场（Jockey Club）· 红土满场，背景是里约的山",
        "license": "unverified · 赛事官方媒体库",
        "artist": "rioopen.com 官方图库",
        "page": "https://www.rioopen.com/-/media/sites/tournaments/rio/vistageral.jpg",
    },
    "munich-centre-court.jpg": {
        "title": "MTTC Iphitos 中心球场 · 红土满场（BMW Open）",
        "license": "unverified · 赛事官方媒体库",
        "artist": "bmwopen.de 官方图库",
        "page": "https://www.bmwopen.de/wp-content/uploads/2025/04/Center-Court.jpg",
    },
    "auckland-centre-court.jpg": {
        "title": "ASB 网球中心中心球场 · 满场，场地上写着 AUCKLAND / TĀMAKI MAKAURAU",
        "license": "unverified · 赛事官方媒体库",
        "artist": "asbclassic.co.nz 官方图库",
        "page": "https://www.asbclassic.co.nz/-/media/sites/tournaments/auckland/news/finals-stadium-generic.jpg",
    },
    "adelaide-centre-court.jpg": {
        "title": "纪念大道公园中心球场 · 满场，场地前场刷着 ADELAIDE",
        "license": "unverified · 赛事官方媒体库",
        "artist": "Tennis Australia 官方图库",
        "page": "https://www.tennis.com.au/adobe/dynamicmedia/deliver/dm-aid--c42ebf2c-6c1d-4667-aba1-21221d7a24b4/adelaide-summer-of-tennis-court.jpg",
    },
    "brisbane-centre-court.jpg": {
        "title": "帕特·拉夫特球场（昆士兰网球中心）· 满场",
        "license": "unverified · 赛事官方媒体库",
        "artist": "Tennis Australia 官方图库",
        "page": "https://www.tennis.com.au/adobe/dynamicmedia/deliver/dm-aid--29ecf2d2-3d24-4378-a734-13a92a329a35/brisbane-international-pat-rafter-arena.jpg",
    },
    "rotterdam-centre-court.jpg": {
        "title": "鹿特丹 Ahoy 中心球场 · 满场，从高处俯瞰整个碗",
        "license": "unverified · 赛事官方媒体库",
        "artist": "Alyssa van Heyst / abnamro-open.nl 官方图库",
        "page": "https://www.abnamro-open.nl/files/images/2027/AAO_260215_Alyssa%20van%20Heyst_3545.jpg",
    },
    "denbosch-centre-court.jpg": {
        "title": "Autotron 中心球场 · 草地，满场（利贝马公开赛）",
        "license": "unverified · 赛事官方媒体库",
        "artist": "libema-open.nl 官方图库",
        "page": "https://libema-open.nl/wp-content/uploads/2025/06/Libema_250612_2862-scaled.jpg",
    },
    "montecarlo-centre-court.jpg": {
        "title": "蒙特卡洛乡村俱乐部雷尼尔三世球场 · 满场，背景是地中海",
        "license": "unverified · 赛事官方媒体库",
        "artist": "montecarlotennismasters.com 官方图库",
        "page": "https://montecarlotennismasters.com/wp-content/uploads/2020/04/vue.jpg",
    },
    "madrid-centre-court.jpg": {
        "title": "魔盒（Caja Mágica）曼诺洛·桑塔纳球场 · 满场，红土",
        "license": "unverified · 赛事官方媒体库",
        "artist": "mutuamadridopen.com 官方图库",
        "page": "https://mutuamadridopen.com/wp-content/uploads/2025/04/wta.jpg",
    },
    "miami-centre-court.jpg": {
        "title": "硬石球场中心球场 · 2026 年迈阿密公开赛，满场",
        "license": "unverified · 赛事官方媒体库",
        "artist": "miamiopen.com 官方图库",
        "page": "https://www.miamiopen.com/wp-content/uploads/2026/07/260328_MO_TDS6543-scaled.jpg",
    },
    "dubai-centre-court.jpg": {
        "title": "迪拜网球场中心球场 · 黄昏满场，场地前场刷着 DUBAI",
        "license": "unverified · 赛事官方媒体库",
        "artist": "dubaidutyfreetennischampionships.com 官方图库",
        "page": "https://dubaidutyfreetennischampionships.com/wp-content/uploads/2026/02/Dubai-Duty-Free-Championships-Stadium_005.jpg",
    },
    "hongkong-victoria-park.jpg": {
        "title": "维多利亚公园中央球场 · 2024 年香港网球公开赛，满场（袁悦 vs 布尔特）",
        "license": "unverified · 协会官方媒体库",
        "artist": "香港网球总会（tennishk.org）官方图库",
        "page": "https://www.tennishk.org/wp-content/uploads/2024/12/241102_CCM1_Katie-Boulter_PHKTO250_HN109223-scaled.jpg",
    },
    "paris-centre-court.jpg": {
        "title": "Paris La Défense Arena 中心球场 · 2025 年巴黎大师赛，满场",
        "license": "unverified · 赛事官方媒体库",
        "artist": "André Ferreira / FFT · rolexparismasters.com 官方图",
        "page": "https://images.prismic.io/rpm-site/ajvcN1bRV8_Qf0Qh_RolexParisMasters2025-Andr%C3%A9FerreiraFFT.jpg",
    },
    "brussels-centre-court.jpg": {
        "title": "Palais 12（Brussels Expo）中心球场 · 2025 年首届布鲁塞尔站，科梅萨纳 vs 戈芬",
        "license": "unverified · 赛事官方媒体库",
        "artist": "Belga / europeanopen.be 官方图库",
        "page": "https://europeanopen.be/wp-content/uploads/2025/10/Belgaimage-136797717.jpg",
    },
    "osaka-utsubo-centre-court.jpg": {
        "title": "靱テニスセンター（Utsubo Tennis Center）中央球场 · 从底线后方看，远端与两侧绿色看台都在框内",
        "license": "unverified · 转载，作者未署名",
        "artist": "unknown（モリタテニス靱 转载）",
        "page": "http://mtp-tennis.com/utsubo/images/senter.jpg",
    },
    "vienna-stadthalle-centre-court.jpg": {
        "title": "Wiener Stadthalle 中心球场 · 满场（2025 Erste Bank Open）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（Kronen Zeitung 转载）",
        "page": "https://imgl.krone.at/scaled/3913474/v9f6623/full.jpg",
    },
    "basel-st-jakobshalle.jpg": {
        "title": "St. Jakobshalle 中心球场 · 满场（场地前场刷着 BASEL）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（unitycms 转载）",
        "page": "https://cdn.unitycms.io/images/7usBtfvqq_sAboyyMyFIom.jpg",
    },
    "singapore-centre-court.jpg": {
        "title": "Kallang Tennis Hub 中心球场（场地前场刷着 SINGAPORE，室内，两侧蓝色看台与顶棚桁架都在竖切里）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（TennisTalker 转载）",
        "page": "https://media.tennistalker.it/2025/01/Singapore-Open-campo.jpeg",
    },
    "tokyo-ariake-coliseum.jpg": {
        "title": "有明コロシアム（Ariake Coliseum）中心球场 · 场地前场刷着 TOKYO",
        "license": "unverified · 转载，作者未署名",
        "artist": "unknown（个人博客转载）",
        "page": "https://cdn-ak.f.st-hatena.com/images/fotolife/e/epokopoko/20200405/20200405173255.jpg",
    },
    "seoul-olympic-park-centre-court.jpg": {
        "title": "首尔奥林匹克公园网球中心中心球场（Korea Open）",
        "license": "unverified · 转载，作者未署名",
        "artist": "unknown（Trip.com 转载）",
        "page": "https://ak-d.tripcdn.com/images/0103912000ew95azuF824.jpg",
    },
    "sao-paulo-centre-court.jpg": {
        "title": "SP Open 中心球场（场地前场刷着 SÃO PAULO，2025 首届）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（Guia do Tenista 转载）",
        "page": "https://guiadotenista.com.br/wp-content/uploads/2025/09/IMG_8074-scaled.jpg",
    },
    "guadalajara-centre-court.jpg": {
        "title": "Complejo Panamericano de Tenis 中心球场 · 满场夜场（场地前场刷着 GUADALAJARA，赞助带 AKRON）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（Guadalajara Secreta 转载）",
        "page": "https://offloadmedia.feverup.com/guadalajarasecreta.com/wp-content/uploads/2024/05/08095411/1-2.jpg",
    },
    "cincinnati-centre-court-full.jpg": {
        "title": "Center Court · Lindner Family Tennis Center 满场（2025 赛事官方图 AW5_0234）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Cincinnati Open",
        "page": "https://cincinnatiopen.com/wp-content/uploads/2025/10/AW5_0234.jpg",
    },
    "monterrey-centre-court.jpg": {
        "title": "Estadio GNP Seguros 中心球场 · 满场（场地前场刷着 MONTERREY，看台顶写着 GNP Estadio，背景是马德雷山）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Abierto GNP Seguros",
        "page": "https://abiertognpseguros.com/media/pages/guia-del-torneo/visit-monterrey/b9f38a59c0-1715623630/estadio-gnp-seguros-1920x.jpg",
    },
    "winston-salem-centre-court.jpg": {
        "title": "Wake Forest Tennis Complex 中心球场 · 黄昏满场",
        "license": "unverified · 新闻站转载",
        "artist": "Camera Work USA（Triad Business Journal 转载）",
        "page": "https://media.bizj.us/view/img/12022122/winston-salem-open-stadium-photo-by-camera-work-usa.jpg",
    },
    "guangzhou-centre-court.jpg": {
        "title": "广州网球公开赛中央球场 · 满场（2025 赛事收官报道）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（南方 + 转载）",
        "page": "https://media.nfnews.com/media-nfh/image/202510/27/7dda1595028b42189b7a215a0541e62a.jpg",
    },
    "ningbo-centre-court.jpg": {
        "title": "宁波网球中心中央球场 · 满场（2024 宁波公开赛开赛，PR Newswire 发布的赛事官方图）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Ningbo Open（PR Newswire 发布）",
        "page": "https://mma.prnewswire.com/media/2532199/Ningbo_International.jpg",
    },
    "hangzhou-lotus-centre-court.jpg": {
        "title": "杭州奥体中心网球中心「小莲花」中央球场 · 满场（2025 领克杭州网球公开赛）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（普利吉体育 转载）",
        "page": "https://img03.71360.com/w3/0qn2g4/20250924/66d99a1c5687521d16f8c59b2adf26de.jpg",
    },
    "chengdu-centre-court.jpg": {
        "title": "四川川投国际网球中心中央球场 · 满场（ATP 官方图库 chengdu-2025-stadium-shot）",
        "license": "unverified · 赛事官方媒体",
        "artist": "ATP Tour",
        "page": "https://www.atptour.com/-/media/images/news/2025/08/13/13/44/chengdu-2025-stadium-shot.jpg",
    },
    "wuhan-optics-valley-centre-court.jpg": {
        "title": "光谷国际网球中心中央球场 · 满场（挡板上写着「东风岚图·武汉网球公开赛 DONGFENG VOYAH · WUHAN OPEN」与「2024东风岚图·武汉网球公开赛」）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（大武汉 转载）",
        "page": "https://www.app.dawuhanapp.com/c/10001/202410/d45fc4e1868afc8ae97999dffa39df03.jpeg",
    },
    "shanghai-qizhong-centre-court.jpg": {
        "title": "旗忠网球中心中央球场 · 顶棚八瓣白玉兰可开合（上海劳力士大师赛）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（赛倍明照明 转载）",
        "page": "https://www.sportsbeams.cn/web/uploads/image/20250516/7KQ41674TPF5pOWqJj2Dfvx20909D21F.jpg",
    },
    "beijing-diamond-court.jpg": {
        "title": "国家网球中心钻石球场 · 满场（场地前场刷着「北京中网」，2023 中网男单决赛）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（新浪体育转载）",
        "page": "https://n.sinaimg.cn/spider20231005/214/w2048h1366/20231005/0a57-133e0b7b85e05c9a50f65167521a5b79.jpg",
    },
    "memphis-leftwich-stadium-court.jpg": {
        "title": "Memphis Classic 主球场（Action News 5 2026-07-26 赛事报道，"
                 "成片第 14.0 秒；临时看台、Mercedes-Benz / TOPNOTCH / crionet "
                 "赞助带、Campbell Clinic 挡布；裁掉了下方的台标条，"
                 "1280×720 源放大 2.78 倍）",
        "license": "unverified · 电视台新闻画面截帧",
        "artist": "Action News 5 / WMC-TV",
        "page": "https://www.actionnews5.com/2026/07/26/"
                "memphis-classic-tournament-full-swing-pro-tennis-returns-leftwich/",
    },
    # 画面自己把身份说死了：右侧赞助带印着 LOS CABOS（带市徽）和 Mifel，场地
    # 前场地面上也刷着 LOS CABOS。放大看这些字都是清楚的——不是效果图那种
    # "像英文的形状"（孟菲斯那三张栽在这儿，见上面 VENUES 的注释）。
    # 媒体库里这就是原图，1200×800，没有更大的 size。
    "los-cabos-estadio-alejandro-burillo.jpg": {
        "title": "Estadio Alejandro Burillo · Cabo Sports Complex（赛事官方媒体库 Main stadium 09）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Mifel Tennis Open by Telcel Oppo",
        "page": "https://loscabostennisopen.com/wp-content/uploads/"
                "2025/07/Main-stadium-09.jpg",
    },
    "athens-olympic-tennis-centre.jpg": {
        "title": "Athens Olympic Tennis Centre（ΟΑΚΑ）中心球场 · "
                 "2026 首届 Athens Open 开幕式，满场",
        "license": "unverified · 赛事官方媒体",
        "artist": "Vanda Pharmaceuticals Athens Open",
        "page": "https://athens-open.com/venue",
    },
    "rome-atv-tennis-open-courts.jpg": {
        "title": "Circolo Antico Tiro a Volo（罗马）红土场 · 挡板上写着 "
                 "ATV · ANTICO TIRO A VOLO TENNIS OPEN 与 ROMA，背景是罗马城郊",
        "license": "unverified · 新闻站转载",
        "artist": "Il Mondo del Tennis",
        "page": "https://ilmondodeltennis.com/2022/07/"
                "torneo-internazionale-al-circolo-antico-tiro-a-volo/",
    },
    "gstaad-roy-emerson-arena.jpg": {
        "title": "Roy Emerson Arena 中心球场 · 满场（红土上刷着 GSTAAD，赞助带 "
                 "EFG Private Banking，记分牌显示比赛进行中；背景是木屋群与阿尔卑斯山）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Fabian Meierhans / EFG Swiss Open Gstaad",
        "page": "https://swissopengstaad.ch/wp-content/uploads/2024/05/"
                "EFG-SOG23-3-%C2%A9FabianMeierhans.jpg",
    },
    "canada-iga-stadium-centre-court.jpg": {
        "title": "Stade IGA 中心球场 · 满场（场地前场刷着 MONTRÉAL，赞助带 "
                 "Banque Nationale / ROGERS；近端看台、蓝绿场地、远端满场看台"
                 "与雷暴天空全在竖切里）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（Radio-Canada 转载）",
        "page": "https://images.radio-canada.ca/q_auto,w_2400/v1/ici-info/sports/"
                "16x9/stade-iga-montreal-tennis-omnium-banque-nationale.jpg",
    },
    "canada-sobeys-centre-court.jpg": {
        "title": "Sobeys Stadium 中心球场 · 单打决赛满场（场地前场刷着 TORONTO）",
        "license": "unverified · 转载，作者未署名",
        "artist": "unknown（View the VIBE 转载）",
        "page": "https://viewthevibe.com/wp-content/uploads/2022/08/"
                "Aviva-Centre-during-the-singles-final-3-Res.jpeg",
    },
    "umag-goran-ivanisevic-centre-court.jpg": {
        "title": "Stadion Goran Ivanišević 中心球场 · 满场夜场（红土、蓝色看台、泛光灯）",
        "license": "unverified · 旅游局官方媒体",
        "artist": "Croatian National Tourist Board（croatia.hr 媒体库）",
        "page": "https://cdn.croatia.hr/mediagallery-dxp-production/"
                "_ATP_Stadion_Gorana_Ivanisevica_Colours_of_Istria.jpg",
    },
    "iasi-ciric-centre-court.jpg": {
        "title": "Baza Sportivă Ciric 中心球场 · 满场（红土、两侧蓝色看台）",
        "license": "unverified · 转载，作者未署名",
        "artist": "unknown（ProSport.ro 转载）",
        "page": "https://www.prosport.ro/wp-content/uploads/2022/12/iasi-open-scaled.jpg",
    },
    "kitzbuhel-centre-court.jpg": {
        "title": "Generali Open 中心球场 · 满场（远端看台雨棚上写着 KITZBÜHEL "
                 "CHAMPIONSHIPS，赞助带 Stanglwirt / ALPQUELL；近端看台的观众、"
                 "红土、远端看台与阿尔卑斯山全在竖切里）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（Kitzbüheler Anzeiger 转载）",
        "page": "https://www.kitzanzeiger.at/media/system/singleimage/"
                "center-court-kitzbuehel.webp",
    },
    "palermo-country-time-centre-court.jpg": {
        "title": "Country Time Club 中心球场 · 黄昏（挡板上 Veneta Cucine / PEUGEOT / "
                 "WTATENNIS.COM，背景是巴勒莫的山；近端蓝色看台、红土、远端看台"
                 "全在竖切里）",
        "license": "unverified · 新闻站转载，作者未署名",
        "artist": "unknown（LiveSicilia 转载）",
        "page": "https://livesicilia.it/wp-content/uploads/2021/07/"
                "Campo-centrale-Country-Time-Club-scaled.jpg",
    },
    "estoril-centre-court.jpg": {
        "title": "Millennium Estoril Open · estadio2",
        "license": "unverified · 赛事官方媒体",
        "artist": "Millennium Estoril Open",
        "page": "https://estoril-open-media.s3.amazonaws.com/images/"
                "605e1eb638ec06001c0f674b-estadio2.jpeg",
    },
}

# 球员图：按 Commons 人物分类自动挑选（分类内都是本人照片，比全文检索准）
PLAYERS = [
    ("zheng-qinwen.jpg", None, "Category:Zheng Qinwen"),
    ("jannik-sinner.jpg", None, "Category:Jannik Sinner"),
    ("carlos-alcaraz.jpg", None, "Category:Carlos Alcaraz"),
    ("aryna-sabalenka.jpg", None, "Category:Aryna Sabalenka"),
    ("iga-swiatek.jpg", None, "Category:Iga Świątek"),
    ("coco-gauff.jpg", None, "Category:Coco Gauff"),
    ("novak-djokovic.jpg", None, "Category:Novak Djokovic"),
    ("stefanos-tsitsipas.jpg", None, "Category:Stefanos Tsitsipas"),
]

# 冷知识配图：与故事主题对应（文件名 = trivia-<slug>.jpg）
TRIVIA = [
    ("trivia-scoring-history.jpg", None, "real tennis court jeu de paume"),
    ("trivia-yellow-ball.jpg", None, "tennis ball close-up"),
    ("trivia-longest-match.jpg", None, "Isner Mahut"),
    ("trivia-hawkeye.jpg", None, "Category:Hawk-Eye"),
    ("trivia-golden-slam.jpg", None, "Steffi Graf 1988"),
    ("trivia-surfaces.jpg", None, "Roland Garros clay court"),
    ("trivia-big-three.jpg", None, "Federer Nadal"),
    ("trivia-china-tennis.jpg", None, "Category:Li Na (tennis player)"),
    # 历史上的今天：抓当年事件现场照，无合规候选时回退对应场馆图
    ("trivia-otd-0725.jpg", None, "Carlos Alcaraz 2021 Umag"),
    ("trivia-otd-0803.jpg", None, "Zheng Qinwen 2024 Olympics Paris"),
    ("trivia-otd-0820.jpg", None, "Djokovic Alcaraz Cincinnati 2023"),
    ("trivia-otd-0909.jpg", None, "Coco Gauff 2023 US Open"),
]


def api(params: dict) -> dict:
    params = {"format": "json", **params}
    for attempt in range(4):
        r = requests.get(API, params=params, headers=UA, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After") or 0) or 15 * (attempt + 1)
            time.sleep(min(wait, 90))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Commons API 429 rate limited after retries")


def imageinfo(titles: list[str]) -> list[dict]:
    data = api({
        "action": "query", "prop": "imageinfo", "titles": "|".join(titles),
        "iiprop": "url|extmetadata|size", "iiurlwidth": MAX_EDGE,
    })
    out = []
    for p in (data.get("query", {}).get("pages") or {}).values():
        for ii in p.get("imageinfo") or []:
            md = ii.get("extmetadata") or {}
            out.append({
                "title": p.get("title"),
                "license": (md.get("LicenseShortName") or {}).get("value", "?"),
                "artist": re.sub(r"<[^>]+>", "", (md.get("Artist") or {}).get("value", "?")).strip()[:60],
                "width": ii.get("width", 0),
                "height": ii.get("height", 0),
                "thumb": ii.get("thumburl"),
                "url": ii.get("url"),
                "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote((p.get('title') or '').replace(' ', '_'))}",
            })
    return out


# 非比赛照片的杂项文件（签名、画像、红毯、渲染图等）不作候选
BAD_TITLE_WORDS = (
    "signature", "autograph", "caricature", "drawing", "stamp", "logo",
    "red carpet", "laureus", "award", "gala", "premiere", "3d", "render",
)

# 人工目检不合格的具体文件（远景/合影/渲染图），永不再选
REJECTED_TITLES = {
    "File:Lttc4284 28.jpg",
    "File:Świątek Yuan AO26 R1.jpg",
    "File:Aryna Sabalenka vs. Qinwen Zheng in a quarterfinals of the 2024 US Open - 01.jpg",
    "File:3D Tennis Ball.jpg",
    "File:Opdenhövel und Graf.jpg",
    "File:25th Laureus World Sports Awards - Red Carpet - Novak Djokovic - 240422 193213-2.jpg",
    "File:Aktion Tennisball auf dem Bumke-Gelaende 3.jpg",
}

# 文件名里带这些词的多为球场内照片，优先于活动照/生活照
TENNIS_CONTEXT_WORDS = (
    "open", "wimbledon", "roland", "garros", "wta", "atp", "tennis", "court",
    "cup", "masters", "final", "match", "serving", "serve", "practice", "trophy",
)


def _usable(title: str) -> bool:
    low = title.lower()
    return (
        low.endswith((".jpg", ".jpeg"))
        and title not in REJECTED_TITLES
        and not any(w in low for w in BAD_TITLE_WORDS)
    )


def _tennis_context(title: str) -> bool:
    low = title.lower()
    return any(w in low for w in TENNIS_CONTEXT_WORDS)


def _category_files(cat: str, depth: int = 2) -> list[str]:
    """分类下的图片文件；名人分类常见两层结构：'X by year' -> 'X in 2024'."""
    data = api({
        "action": "query", "list": "categorymembers", "cmtitle": cat,
        "cmtype": "file|subcat", "cmlimit": 100,
    })
    files, subcats = [], []
    for m in data.get("query", {}).get("categorymembers", []):
        title = m["title"]
        if title.startswith("Category:"):
            subcats.append(title)
        elif _usable(title):
            files.append(title)
    if depth > 0 and len(files) < 60:
        # 年份子分类新到旧优先，再钻 "by year" 中间层
        drill = sorted(
            (c for c in subcats if re.search(r"\b20\d\d$", c)), reverse=True
        )
        drill += [c for c in subcats if c.lower().endswith("by year")]
        for sub in drill[:5]:
            time.sleep(0.5)
            files += _category_files(sub, depth - 1)
            if len(files) >= 60:
                break
    return files


def _search_files(query: str) -> list[str]:
    data = api({
        "action": "query", "list": "search", "srsearch": query,
        "srnamespace": 6, "srlimit": 10,
    })
    hits = data.get("query", {}).get("search", [])
    return [h["title"] for h in hits if _usable(h["title"])]


def _candidate_titles(term: str) -> list[str]:
    if term.startswith("Category:"):
        return _category_files(term) or _search_files(term.removeprefix("Category:"))
    return _search_files(term)


def _subject_tokens(term: str) -> list[str]:
    """人物分类名 -> 匹配用词（'Category:Iga Świątek' -> ['iga', 'swiatek']）."""
    name = re.sub(r"\(.*?\)", "", term.removeprefix("Category:")).strip()
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return [w.lower() for w in folded.split() if w]


def _title_matches_subject(title: str, tokens: list[str]) -> bool:
    folded = unicodedata.normalize("NFKD", title)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
    for tok in tokens:
        if len(tok) >= 4 and tok in folded:
            return True
        if len(tok) < 4 and re.search(rf"\b{re.escape(tok)}\b", folded):
            return True
    return False


def pick_by_search(
    term: str, min_width: int = 1600, prefer_portrait: bool = False
) -> dict | None:
    titles = _candidate_titles(term)
    # 人物分类里常混着场馆/合影杂图：文件名必须含本人姓名，
    # 且排除 "X vs. Y" 式对阵照（多为看台全景，人物只是小点）
    if term.startswith("Category:"):
        tokens = _subject_tokens(term)
        if tokens:
            titles = [
                t for t in titles
                if _title_matches_subject(t, tokens) and " vs" not in t.lower()
            ]
    time.sleep(1)
    ok = []
    for batch_start in range(0, min(len(titles), 24), 8):
        for cand in imageinfo(titles[batch_start:batch_start + 8]):
            if any(s in cand["license"] for s in OK_LICENSES) and cand["width"] >= min_width:
                ok.append(cand)
        if ok:
            break
        time.sleep(1)
    if not ok:
        return None
    # 场馆/主题图横幅位用横图；球员图优先竖版（竖版多为特写，横版常是全场远景）
    def _orient(c: dict) -> bool:
        return c["height"] >= c["width"] if prefer_portrait else c["width"] > c["height"]

    ok.sort(
        key=lambda c: (_tennis_context(c["title"]), _orient(c), c["width"]),
        reverse=True,
    )
    return ok[0]


def download(cand: dict) -> bytes:
    """缩略图优先（体积小），429 退避重试；缩略图始终被拒时回退原图."""
    last: Exception | None = None
    for url in filter(None, (cand.get("thumb"), cand.get("url"))):
        for attempt in range(5):
            try:
                r = requests.get(url, headers=UA, timeout=90)
                if r.status_code == 429:
                    last = RuntimeError(f"429 Too Many Requests: {url}")
                    wait = int(r.headers.get("Retry-After") or 0) or 20 * (attempt + 1)
                    time.sleep(min(wait, 120))
                    continue
                r.raise_for_status()
                return r.content
            except requests.RequestException as e:  # noqa: PERF203
                last = e
                time.sleep(5)
    raise RuntimeError(f"下载失败: {last}")


def shrink(data: bytes) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, progressive=True)
    return buf.getvalue()


def fetch_set(
    out_dir: Path, wanted: list, min_width: int, prefer_portrait: bool = False
) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    credits_path = out_dir / "credits.json"
    try:
        old_credits = json.loads(credits_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old_credits = {}
    credits = {}
    failed = []
    for out_name, pinned_title, term in wanted:
        dest = out_dir / out_name
        # 已入库的图不再重选：避免署名与图片错位，也少打 API（限流敏感）
        if dest.exists():
            # 官方媒体来源的出处以 OFFICIAL_VENUES 为准，不看盘上那份旧的
            credit = OFFICIAL_VENUES.get(out_name) or old_credits.get(out_name)
            if credit:
                credits[out_name] = credit
            print(f"KEEP {out_name}")
            continue
        if out_name in OFFICIAL_VENUES:
            # 官方媒体不是 Commons，这里没有可自动重取的路径；说清楚再往下走，
            # 别让它掉进 pick_by_search(None) 报一个看不懂的错。
            failed.append(
                f"{out_name}: 官方媒体来源的图不在盘上，需要人工从 "
                f"{OFFICIAL_VENUES[out_name]['page']} 重新取"
            )
            print(f"MISS {out_name}: 官方媒体来源，脚本不自动重取")
            continue
        try:
            if pinned_title:
                cand = next(iter(imageinfo([pinned_title])), None)
            else:
                cand = pick_by_search(
                    term, min_width=min_width, prefer_portrait=prefer_portrait
                )
            if not cand:
                raise RuntimeError("无符合授权/画质的候选")
            dest.write_bytes(shrink(download(cand)))
            credits[out_name] = {k: cand[k] for k in ("title", "license", "artist", "page")}
            print(f"OK {out_name} <- {cand['title']} [{cand['license']}] by {cand['artist']}")
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{out_name}: {e}")
            print(f"FAIL {out_name}: {e}")
            time.sleep(3)
    credits_path.write_text(
        json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return failed


def _norm_title(title: str) -> str:
    """Commons 文件名比较：下划线/空格等价，首字母大小写不敏感。"""
    return " ".join(str(title).replace("_", " ").split()).casefold()


def backfill_credits(out_dir: Path, wanted: list) -> list[str]:
    """给"图已在盘上、credits 却缺失"的条目补出处。

    fetch_set() 只在自己下载成功的那一刻写 credits；图片 CDN 限流严重
    （429），实际操作里常常出现"手动/分批把图弄下来了，但 credits 没跟上"。
    credits 缺字段的条目会被 load_venue_assets() **静默丢弃**，图明明在却
    不生效，很难发现。这里只查 API（不碰限流严重的图片 CDN），把缺的补齐。

    换图时同样要管：把某一站换成另一张 Commons 文件后，旧的 credits 仍然
    齐全，只是**指向上一张图**——署名和许可全错，而且不像"缺失"那样会被
    丢弃，它会照常生效并印错出处。缺出处只是不显示，错出处是把别人的作品
    记到另一个人名下。所以记录的 title 和 VENUES 里钉的文件名对不上时，
    按钉的那个重取。

    图被删掉时也要管：换站名（estoril-coast → estoril-centre-court）之后旧条目
    还留在 credits.json 里，指着一个盘上已经没有的文件。它不会印错什么，但
    "每个 credits 条目都在 VENUES 里登记"这条不变量会被它破坏，于是下次真的
    有图漏登记时反而看不出来。一并清掉。
    """
    credits_path = out_dir / "credits.json"
    try:
        credits = json.loads(credits_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        credits = {}
    required = ("title", "license", "artist", "page")
    failed = []
    for gone in [name for name in credits if not (out_dir / name).exists()]:
        print(f"DROP   {gone}: 图已不在盘上，清掉它的 credits")
        credits.pop(gone)
    for out_name, pinned_title, _term in wanted:
        if not (out_dir / out_name).exists():
            continue
        if out_name in OFFICIAL_VENUES:
            # 官方媒体：出处就写在 OFFICIAL_VENUES 里，不查 API
            if credits.get(out_name) != OFFICIAL_VENUES[out_name]:
                credits[out_name] = dict(OFFICIAL_VENUES[out_name])
                print(f"CREDIT {out_name} <- 赛事官方媒体（{OFFICIAL_VENUES[out_name]['artist']}）")
            continue
        recorded = credits.get(out_name) or {}
        complete = all(recorded.get(k) for k in required)
        stale = bool(
            pinned_title
            and recorded.get("title")
            and _norm_title(recorded["title"]) != _norm_title(pinned_title)
        )
        if complete and not stale:
            continue
        if not pinned_title:
            failed.append(f"{out_name}: 图在但没有 credits，且没有固定的 Commons 文件名")
            continue
        if stale:
            print(f"STALE  {out_name}: credits 记的还是 {recorded['title']}，按 {pinned_title} 重取")
        try:
            cand = next(iter(imageinfo([pinned_title])), None)
            if not cand:
                raise RuntimeError(f"Commons 查不到 {pinned_title}")
            credits[out_name] = {k: cand[k] for k in required}
            print(f"CREDIT {out_name} <- {cand['title']} [{cand['license']}] by {cand['artist']}")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{out_name}: 补出处失败: {exc}")
    credits_path.write_text(
        json.dumps(credits, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return failed


ATTRIBUTION_HEADER = """# Venue image attribution

<!-- 这个文件由 tools/fetch_venues.py 的 render_attribution() 生成，别手改。 -->
<!-- 判据：test_attribution_md_is_generated_from_credits。 -->

The machine-readable author, license, and source records live in `credits.json`.
Event-specific schedule backgrounds are cropped and darkened by the renderer;
the photographs are not otherwise altered.
"""


def render_attribution(credits: dict, on_disk: set[str]) -> str:
    """按 credits.json 生成署名页——**手写的那一版一定会过期**。

    换图时 credits.json 有测试盯着，这个 .md 没有，于是它悄悄留下了三条指向
    早就删掉的文件的记录（kitzbuhel-panorama / prague-castle-panorama /
    estoril-coast）。跟「换文件名要 grep 整个仓库包括 .md」是同一件事，只是
    靠人记住的方式挡不住第四次——所以改成生成的。
    """
    lines = [ATTRIBUTION_HEADER]
    for name in sorted(n for n in credits if n in on_disk):
        entry = credits[name]
        lines.append(f"## `{name}`\n")
        lines.append(f"- Title: {entry.get('title', '')}")
        lines.append(f"- Author: {entry.get('artist', 'unknown')}")
        lines.append(f"- Source: {entry.get('page', '')}")
        lines.append(f"- License: {entry.get('license', 'unverified')}")
        if entry.get("note"):
            lines.append(f"- Note: {entry['note']}")
        lines.append("- Changes: resized and cropped by the card renderer;"
                     " no semantic alteration\n")
    return "\n".join(lines)


def write_attribution(out_dir: Path) -> None:
    credits = json.loads((out_dir / "credits.json").read_text(encoding="utf-8"))
    on_disk = {p.name for p in out_dir.glob("*.jpg")} | {p.name for p in out_dir.glob("*.png")}
    (out_dir / "ATTRIBUTION.md").write_text(
        render_attribution(credits, on_disk), encoding="utf-8")


def main() -> int:
    failed = fetch_set(ROOT / "assets" / "venues", VENUES, min_width=1600)
    failed += backfill_credits(ROOT / "assets" / "venues", VENUES)
    write_attribution(ROOT / "assets" / "venues")
    failed += fetch_set(
        ROOT / "assets" / "players", PLAYERS, min_width=1000, prefer_portrait=True
    )
    failed += fetch_set(ROOT / "assets" / "trivia", TRIVIA, min_width=1000)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
