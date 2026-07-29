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
    ("athens-parthenon.jpg", "File:Parthenon Athens.jpg", None),
    # 埃斯托里尔原来是 File:Estoril - panoramio.jpg，一段海岸步道加铁轨，既不是
    # 地标也不是球场，整页铺开像个火车站。Commons 上也没有中央球场——卡西诺那张
    # 建筑只占中间一条，上下全是天空和草坪。改用赛事官方媒体，见 OFFICIAL_VENUES。
    ("estoril-centre-court.jpg", None, None),
    # 汉堡：原来是一片屋顶远景，既不是地标也不是球场。罗森布洛姆中央球场那几张
    # 都不能用——"Centre Court Am Rothenbaum"那张画面是场外纪念品帐篷，顶棚那张
    # 只见钢索不见球场，球场全景是 2200×590 的宽幅（cover 到 3:4 只剩中间 20%，
    # 页眉整个糊掉）。改用易北爱乐音乐厅这个地标；注意 File:Elbphilharmonie
    # Hamburg.jpg 拍于施工期、满屏塔吊，要的是建成后的这张。
    ("hamburg-skyline.jpg",
     "File:Elbphilharmonie with Kaiserkai promenade viewed from HafenCity.jpg", None),
    # 巴勒莫：原来用的是马西莫剧院这个地标。赛事官网是 WordPress，
    # wp-json 里搜意大利语 "campo centrale" 就出了 Campo-centrale-dallalto——
    # 自上而下拍的中心球场，红土上刷着 PALERMO，两侧看台都在竖切里。
    # 又一次印证「搜索词按赛事自己的语言写」。
    ("palermo-campo-centrale.jpg", None, None),
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
    ("verona-arena.jpg", "File:Verona Arena (Arena di Verona).jpg", None),
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
    # 辛辛那提：原来那张是侧面横拍，竖版裁完只剩中段。赛事官网是 WordPress，
    # wp-json/wp/v2/media?search=stadium 一查就是一堆 2560 宽的官方图；选的这张
    # 从底线后方顶层往下拍，近端看台 / 球场 / 远端看台整个碗都在竖切里。
    # 注意：这个站用浏览器 UA 请求 wp-json 会被 WAF 挡 403，用脚本自己的 UA 反而
    # 200——「取不到」和「0 命中」要分开，见 tools/probe_venue_photos.py 的 Blocked。
    ("cincinnati-center-court.jpg", None, None),
    # 美网：原来是按分类自动挑的，挑到一张从侧面看台横拍的——竖版裁完只剩
    # 中间一条。换成"从顶层沿球场长轴往下看"：整个碗竖着排在画面里，
    # 近端看台在下、球场在中、远端看台和天际线在上，竖切也切不掉。
    ("usopen-arthur-ashe-stadium.jpg",
     "File:View From the Top of the Arthur Ashe Stadium (9614299124).jpg", None),
    # 基茨比厄尔：原来用的是山景地标。球场照 Commons 上有——红土中心球场，
    # 看台后面就是阿尔卑斯，赛事身份和地点一张图说全了。
    ("kitzbuhel-tennis-stadium.jpg", "File:Tennisstadion Kitzbuehel, 2015.jpg", None),
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
    ("gstaad-panorama.jpg", "File:July in Gstaad.jpg", None),
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
    # 原来钉的是**全园航拍**，中心球场只是画面里的一块，当背景时看不出是哪儿。
    # 换成场内满场：草地、看台、顶棚桁架。
    ("wimbledon-centre-court.jpg", "File:Centre Court Wimbledon 2009.JPG", None),
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
    "palermo-campo-centrale.jpg": {
        "title": "Country Time Club 中心球场 · 自上而下"
                 "（场地前场刷着 PALERMO；赛事官网媒体库 Campo-centrale-dallalto）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Palermo Ladies Open",
        "page": "https://www.palermoladiesopen.it/wp-content/uploads/2021/09/"
                "Campo-centrale-dallalto.jpg",
    },
    "cincinnati-center-court.jpg": {
        "title": "Center Court · Lindner Family Tennis Center"
                 "（赛事官方媒体库 STADIUM-2021_WSOPEN_SOLOMON_001）",
        "license": "unverified · 赛事官方媒体",
        "artist": "Cincinnati Open（署名 Solomon）",
        "page": "https://cincinnatiopen.com/wp-content/uploads/2023/04/"
                "STADIUM-2021_WSOPEN_SOLOMON_001.jpg",
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


def main() -> int:
    failed = fetch_set(ROOT / "assets" / "venues", VENUES, min_width=1600)
    failed += backfill_credits(ROOT / "assets" / "venues", VENUES)
    failed += fetch_set(
        ROOT / "assets" / "players", PLAYERS, min_width=1000, prefer_portrait=True
    )
    failed += fetch_set(ROOT / "assets" / "trivia", TRIVIA, min_width=1000)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
