#!/usr/bin/env python3
"""封面官方实拍：把**所有查得通的渠道**扫一遍，并把「这张图是哪一场」查实。

CLAUDE.md「封面大图一律用官方高清实拍」那条的配套工具。以前只有两条路
（WTA 的 `photo-resources` ＋ 赛事官网的图库页），2026-08-16 又量出三条，
外加一批**实测走不通、别再试**的。全写在这儿，别每次现搓。

    python3 tools/find_cover_photo.py --player Tjen --event Cincinnati --day 6
    python3 tools/find_cover_photo.py --player Sabalenka --site cincinnatiopen.com --date 2026-08-16
    python3 tools/find_cover_photo.py --getty 2288964672      # 只查一个 Getty 编号是哪一场
    python3 tools/find_cover_photo.py --discover <新赛事域名>   # 换一站先跑这条

## ⭐⭐ 哪几条**跨得过赛事**——2026-08-17 量的，账很难看

账号所有者：「**多找几个渠道，不然下一个赛事就不一定有了啊**」。去量了一遍，
他说的这个风险不是隐忧，是**现状**：

| 渠道 | 跨赛事吗 | 分辨率 | 判据 |
|---|---|---|---|
| ⭐⭐ **AP 通讯社** | ✅ **通讯社，每站都派人** | **4700~8600px** | 说明里四要素 ＋ 署名全齐，原图挂在 `?url=` 上 |
| **WTA `photo-resources`** | ✅ **巡回赛级** | 4000px | 每站都在同一个 CDN 上，不用换域名 |
| **当地报纸每日图集** | ⚠️ **按城市换域名** | 4813px | 六份报纸里**五份**认同一个 `/picture-gallery/` ＋ `/gcdn/` 形状 |
| **赛事官网 WP 媒体库** | ❌ **基本是特例** | 5541px | 扫了 **11 个赛事官网，只有辛辛那提一个**开着 WP REST |

⚠️ **原来分辨率最高的两条（赛事图库、当地报纸）恰好都跨不过赛事**：一条只在
辛辛那提有，一条得先知道当地哪份报纸。**AP 那条是 2026-08-17 补上的，
它同时占住「最高」和「跨得过」两头**——这条渠道就是为账号所有者那句话找的。
换一站之前照旧先跑 `--discover`，别假设上一站那套还在。

⚠️ **这条渠道原来把 `cincinnati.com` 写死在代码里**——也就是说「当地报纸」
这一档在别的站上**根本不会跑**，而它跳过的样子和查空一模一样。现在按城市查
`_LOCAL_PAPERS`，查不到就明说没跑。

## ⭐⭐ 美网要「稳定」拿到高清图，走这一条：**USA TODAY 的每日图集**

账号所有者 2026-08-25：「**那你帮我稳定找到美网的高清图片**」。四条渠道逐条
量下来，美网这一站能当主路的只有一条，而它一开始**整个扫不到**（正则和
`_LOCAL_PAPERS` 两处各错一半，见下面那两个常量的注释）：

| 这一档 | 美网有没有 | 实测尺寸 | 铺 1080×1440 |
|---|---|---|---|
| ⭐⭐ **USA TODAY 每日图集** | ✅ **决赛周两辑都有** | **2187 ~ 6283px** | **1.01 ~ 2.91×** |
| 美网官方图片接口 | ✅ **每场都有（保底）** | 1280×720 **封顶** | 0.50×，要写 `_low_res_why` |
| AP 通讯社 | ⚠️ **正赛开打前是零** | —— | 见下 |
| WTA `photo-resources` | ❌ 大满贯不进 WTA 图库 | —— | —— |

    python3 tools/find_cover_photo.py --player Alcaraz --event "US Open" --date 2025-09-07

⚠️ **「AP 对美网是零」是一个真的零，别读成 bug**：2026-08-25 量过，AP 的美网
前瞻稿**配的全是别站的资料图**（温网、蒙特利尔、印第安维尔斯），一张美网都没有
——正赛开打之后它才会有本场图。

⚠️ **官方接口那一档是保底不是主路**：它每场都有、每个球员都有（阿尔卡拉斯
1523 条、萨巴伦卡 2110 条），但 `f_` 前缀就是顶，1280×720。**先走 USA TODAY，
它没有这一场再退回官方接口并写 `_low_res_why`。**

## 查得通的渠道（都实测过）

1. **WTA `photo-resources`**——文件名自带四要素
   （`Iga_Swiatek_-_Cincinnati_Open_2026_-_Day_6-DSC_2955.jpg`：球员、赛事、
   年份、第几个比赛日）。`?width=4000` 拿原图。
   ⚠️ **不带 `width` 参数是 400 不是 404**，按状态码判会以为图不存在。

   要扫的页面不止列表页：**单条视频页 `/videos/<id>/<slug>` 比列表页多带图**
   （谭雅妮那条集锦的页面上还挂着一张萨巴伦卡的 Getty）。所以列表页、单条页、
   `/news`、球员页、赛事页都要扫。

2. ⭐⭐ **`GettyImages-<id>.jpg` 现在可以用了。** 以前当成「文件名没有四要素、
   不能用」，其实两头都通：
   - WTA 的 CDN 存的是**无水印原图**，`?width=4000` 实测拿到 4000×2666
   - **Getty 自己的 `/detail/<id>` 页给出完整说明**——球员、赛事、轮次、场馆、
     日期，四要素一次全齐

   ⚠️ **看见 `GettyImages-*` 一律先查说明**，别因为它挂在这场的页面上就当成本场：
   实测 `2288964672` 挂在辛辛那提那条集锦的页面上，说明写的却是
   「**National Bank Open, August 08, 2026, Sobeys Stadium in Toronto**」——
   又一张资料图。同一批里 `2290118693`（Tauson–Stearns，辛辛那提 Day 5）和
   `2290359738`（Parry，辛辛那提 8/13）才是真的本站图。

3. ⭐ **赛事官网的 WordPress REST 媒体库**——比翻图库页早，而且能按日期过滤、
   直接给原图尺寸：

       /wp-json/wp/v2/media?per_page=100&orderby=date&order=desc
       /wp-json/wp/v2/media?after=2026-08-16T00:00:00
       /wp-json/wp/v2/posts?per_page=100&orderby=date&order=desc

   ⚠️⚠️ **必须带浏览器 UA**：拿 `tennislive/0.1` 这类 UA 请求是 **403**，
   看起来像「这个站没开 REST 接口」。这一条骗过我一次。
   ⚠️ 另一条等价入口是 `/?rest_route=/wp/v2/media`。
   ⚠️ 赛事图库的文件名**没有球员名**（`081526_DAY-EIGHT_MIKE-BAKER-112-of-229.jpg`）。

   ⚠️⚠️ **但「所以 `?search=<姓>` 在这儿是空的」这句话是错的，2026-08-17 量翻了。**
   WordPress 的 `search` 搜的**不只是文件名，还有 `title` / `alt_text` / `caption`
   这几个元数据字段**——而赛事方是给图填了 title 的：

       ?search=Fonseca  → CincyOpen8.16.26BJ_289.jpg（2000×1334，title="Fonseca"）
                          CincyOpen8.13.26BJ_66.jpg （2000×1333，title="Fonseca"）
       ?search=Shelton  → Ben-Shelton_20260815_000010.jpg（这一批**文件名就带名字**）

   **三个文件名都不含 `Fonseca`，可它们全被 search 搜出来了。** 那句错注释的来路
   很典型：只看了文件名，就替 `search` 下了结论——「我没查过的」被写成了「查过没有」。

   所以这一档**要按两条各扫一遍**：`?search=<姓>` 拿命名和元数据两种，
   `?after=/&before=` 拿当天全量。⚠️ 仍然要打开看：`search` 命中的可能是**场外**照
   （丰塞卡那三张里两张是签名和拿相机），过不了第 2 道闸门。

   ⚠️ **这条渠道也可能只有头像**：搜 `Shnaider` / `Chwalinska` 各只回一张
   492×656 的官方头像（`330482__Diana-Shnaider.jpg`），那不是比赛照。
   **「search 有命中」不等于「有能用的图」**，还是要看尺寸和内容。

4. ⭐ **图库什么时候上线是可以量的，别在当天下午反复扫。** 拿
   `posts?orderby=date` 读 `day-N-best-of-photos` 的 `date_gmt`，实测：

       day-1  2026-08-12T00:00Z      day-4  2026-08-15T00:48Z
       day-3  2026-08-14T01:56Z      day-5  2026-08-16T02:57Z

   也就是**当天那一辑在次日 UTC 00:00–03:00 之间上线**（当地 20:00–23:00）。

5. ⭐⭐⭐ **当地报纸的每日图集**（2026-08-17 挖出来的；⚠️ 它一度是分辨率最高的
   一条，同一天下午被下面第 6 条的 AP 超过了——**引用之前先看那张跨赛事的表**）。
   辛辛那提这一站是 **The Enquirer**（USA Today／Gannett 网络）派自己的摄影师拍，
   每个比赛日出一辑：

       索引  https://www.cincinnati.com/sitemap/2026/august/<DD>/
             （或 /search/?q=photos%20cincinnati%20open）
       一辑  /picture-gallery/sports/2026/08/<DD>/photos-cincinnati-open-<slug>/<id>/
       图    那一页的 `<script type=application/ld+json>` 里是一串 ImageObject，
             每条带 `url` ＋ **完整四要素说明** ＋ `copyrightHolder`

   ⚠️⚠️ **原图要换域名**：说明里给的是 `https://www.cincinnati.com/gcdn/authoring/…`，
   而那个地址**恒 406**（`www.usatoday.com/gcdn/…` 也是）。把
   `https://www.cincinnati.com/gcdn/` 换成 **`https://www.gannett-cdn.com/`**
   就是无水印原图——实测 **4813×3209**，铺 1080×1440 只要 **0.45×**，
   连 `_low_res_why` 都不用写。⚠️ 请求要带 `Accept: image/*`，不然还是 406。

   ⚠️ **它的说明比赛事图库的文件名还硬**：
   「Alex de Minaur, of Australia, returns to Quentin Halys, of France, at the
   Cincinnati Open at the Lindner Family Tennis Center in Mason, Ohio, on
   Saturday, August 15, 2026」——球员、对手、赛事、场馆、日期一句话全齐，
   四道闸门第一道直接过。
   ⚠️ 版权是报社的（`Albert Cesare/The Enquirer`），属于四类源里的第 ③ 档
   「新闻站／图片社转载」——授权照实记进 credits，发布前人工判断。
   ⚠️ **覆盖面和赛事图库一样偏主球场**：8/14 那辑 54 张、8/15 那辑 95 张，
   两辑里含 `Wang` 的都是 0 张。**有这条渠道不等于有这个人**。

6. ⭐⭐ **AP 通讯社**（2026-08-17 挖的，**唯一一条又高清又跨得过赛事的**）：

       搜索  https://apnews.com/search?q=<球员>%20tennis   ＋ /hub/tennis
       文章  <img src="https://dims.apnews.com/dims4/…?url=<原图>" alt="<说明>">
       原图  把 `?url=` 解出来 → assets.apnews.com/…   实测 **8212×5576 / 6226×4796**

   说明自带四要素 ＋ 署名：「Ben Shelton of the United States hoists the trophy
   following his win over compatriot Brandon Nakashima during final tennis action
   at the National Bank Open in Montreal on Thursday, Aug. 13, 2026.
   (Christinne Muschi/The Canadian Press via AP)」

   ⚠️ **别直接用 `dims.apnews.com` 那个地址**——它是按版面缩好的（980×653 /
   767×511），铺封面连一半都不到，而且**不报错**。
   ⚠️ **搜索结果里混着一批固定的边栏稿**：三个完全无关的词各回 69~70 篇，
   **三者交集 40 篇**。所以筛靠的是**说明里有没有这个人**，不是搜索结果本身。
   ⚠️⚠️ **光按人筛会拿回资料图。** 实测 `--player Svitolina` 不筛赛事时头三张
   是意大利公开赛捧杯 ＋ 多伦多半决赛两张——**每张都是她，没一张是这一场**。
   所以 `--event` 也要参与筛（同一份代码 `Shelton`＋`Montreal` 拿回 2 张全对）。
   ⚠️ 版权是 AP 的（第 ③ 档「新闻站／图片社转载」），署名照实记进 credits。

## 实测走不通的，别再试

| 路 | 结果 |
|---|---|
| Getty 自己的 comp 图 `media.gettyimages.com/id/…` | 脱离页面上下文一律 **400**（签名参数绑上下文）；而且 `w=gi` 是**带水印**的 |
| Getty API `api.gettyimages.com` | **401**，要 key |
| Getty 搜索页 `gettyimages.com/search/2/image` | 沙箱里 curl 拿到的是 **JS 壳**（0 个 asset）；**上 runner 开真 Chromium 也不行——直接弹 reCAPTCHA**（run 31983856305 抓到 `recaptcha/api2/anchor`）。这条 2026-08-17 探到底了 |
| 沙箱里开 Chromium 走代理 | `--proxy-server` 和 playwright 的 `proxy=` 都试过，一律 `ERR_CONNECTION_RESET`，连自家能 curl 通的站都打不开。**要真浏览器只能上 runner**（`probe-blocked.yml` 的 `mode=browser`） |
| `atptour.com` | 换浏览器 UA 之后仍是 **403**（沙箱和 runner 都是），这条老结论不变 |
| `photos.` / `media.` `.cincinnatiopen.com` 子域 | 403，换 UA 无效 |
| 网易／新浪等中文门户配的图 | 是**资料图**：实测 163 那两篇写这场球的稿子配的是她别站的旧照（960×640、1280×832），四道闸门第一道就过不了 |
| Reuters 图片站 | **401** |
| `api.wtatennis.com` 的 `media` / `photos` / `content` / `players/<id>/media` | 全 **404** |
| `wtatennis.com/galleries` | 404。`/photos` 有，但那是专题图集，不是当日比赛图 |
| tennis.com 的比赛页 | 只有国旗和头像，没有比赛图 |
| Flickr / Alamy / Imago / Zimbio | JS 渲染或带水印，取不到可用原图 |
| **WTA 单场比分页 `/scores/<MatchID>`** | **每一场给的是同一批 7 张**（实测 `LS063` 和 `LS039` 两场的清单一字不差，里面还混着 2023/2024 的旧图）——那是版面的边栏，**不是这一场的图**。看着最像「每场一张头图」，其实不是 |
| WTA 扫更多入口（`/scores`、`/tournament/<id>/…/scores`、`/photos`） | 相比现有三个入口只多出 **2 张，而且都不对题**（一张 2025 年的、一张别站的）。`/photos` 和 `/news` **返回的是同一份**（字节数一样） |
| 赛事 WP 媒体库的 `alt_text` / `caption` | 当天批量上传的那些**全是空的**，`?search=<姓>` 只匹配得上文件名（头像、少数精选图）。**这条路认不出照片里是谁**，是硬限制不是没调对 |
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html as html_mod
import json
import re
import sys
import time
import urllib.parse

import requests

# 浏览器 UA 不是洁癖：赛事官网的 WP REST 对非浏览器 UA 直接 403（见模块 docstring）。
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_PHOTO_RE = re.compile(
    r"photo-resources/\d{4}/\d{2}/\d{2}/[a-f0-9-]+/[^\"'\\\s]+?\.(?:jpg|jpeg|png)",
    re.I,
)
_CDN = "https://photoresources.wtatennis.com/"

# 扫 WTA 那一头要走的入口。**单条视频页比列表页多带图**，所以列表页只是起点。
# ⭐⭐ **大满贯那一档：美网有自己的图片接口。**
#
# WTA / ATP 那两条路对大满贯**都不成立**——`photoresources.wtatennis.com`
# 不收大满贯（8 月下旬只有辛辛那提），赛事官网的 WordPress 图库是巡回赛
# 站点才有的东西（`discover` 敲过 11 个官网，只有辛辛那提开着 WP REST）。
#
# ⚠️ **`usopen.org` 的每一个路径都返回同一份 4084 字节的 JS 壳**——
# `images.usopen.org`、`photo-assets.usopen.org` 的目录也一样。只看页面
# 必然得出「这站没有图库」，而**那个错结论和「真的没有」长得一模一样**。
# 答案在 `/en_US/json/gen/config_web.json` 的接口表里。
#
# ⚠️ **1280×720 是这个赛事的出版上限，不是「没找够」。** 试过十二个前缀
# （`a_ d_ e_ g_ h_ i_ o_ s_ x_ l_ m_ n_`）、六个目录（`xlarge/ orig/
# original/ full/ raw/ huge/`）、三种参数（`?width=4000` / `?w=4000` /
# `?resize=4000`）——前两组全 404，第三组**返回 200 但尺寸一个像素没变**
# （只换了一次 JPEG 编码，字节数会变大，**别被那个数骗成「拿到大图了」**）。
# 新闻条目和照片条目是同一套四档，也证实了这一点。
# 所以大满贯封面**默认就要写 `_low_res_why`**。
_USO = "https://www.usopen.org"
_USO_REST = _USO + "/relatedcontent/rest/v2/uso_v1/en"
_USO_PLAYERS = _USO + "/en_US/scores/feeds/{year}/players/players.json"

# ⚠️ 这个接口**间歇 403**（实测 6 次里 3 次），不是恒 403。取数失败一旦被吞成
# 空列表，调用方就会报「players.json 里没有叫 X 的人」——**取不到和查无此人
# 在产物上长得一模一样**，而后者会把人推去改查询词，改半天也改不出来。
_USO_PLAYERS_TRIES = 4


class UsoPlayersUnavailable(RuntimeError):
    """players.json 取不到（间歇 403）——**不是「没有这个人」**。

    分开报是有代价的（调用方要多一个分支），换来的是「这一档没跑」不会被读成
    「这一档查空了」。CLAUDE.md「空结果先自证是真空」那条说的就是这件事。
    """
_USO_PREFIX = {"small": "t_", "medium": "b_", "large": "c_", "xlarge": "f_"}

_WTA_PAGES = (
    "https://www.wtatennis.com/videos/highlights",
    "https://www.wtatennis.com/videos",
    "https://www.wtatennis.com/news",
)


def _get(url: str, timeout: int = 30) -> str:
    """⚠️⚠️ **必须走 `requests`，不能走 `urllib`。**

    2026-08-17 在 `cincinnati.com` 上量出来的：同一个 URL、同一个 UA、同一份
    `Accept`，**urllib 恒 403、requests 恒 200**。差别不在头的内容，在**头的
    大小写**——`urllib.request.Request` 会把头名规范成 `User-agent`（小写 a），
    而浏览器和 requests 发的是 `User-Agent`；Gannett 那道 WAF 按这个指纹判机器人。

    ⚠️ 这一条骗过我一次：换 Mac/Windows UA、换 Accept、加 Accept-Language 全试过，
    五种组合**全是 403**，看起来就像「这个站不让爬」——而真因是发请求的库。
    「这条路不通」和「我敲门的姿势不对」长得一模一样，**判空之前先换一个 HTTP 客户端**。
    """
    resp = requests.get(url, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def getty_caption(gid: str) -> str | None:
    """一个 Getty 编号是哪一场——球员、赛事、场馆、日期都在这一句里。

    ⚠️ 这是 `GettyImages-*.jpg` 唯一的四要素来源。文件名什么都不说，而它挂在
    哪个页面上**不能**当成它拍的是哪一场（模块 docstring 里那个反例）。
    """
    try:
        html = _get(f"https://www.gettyimages.com/detail/{gid}", timeout=25)
    except Exception as exc:                                    # noqa: BLE001
        return f"（查不到：{exc}）"
    m = re.search(r'<meta name="description" content="([^"]+)"', html)
    if not m:
        return None
    text = m.group(1)
    # 说明后面跟着一段固定的推销词，切掉
    return re.split(r"\s*Get premium, high resolution", text)[0].strip()


def sweep_wta(player: str | None, event: str | None, day: str | None) -> list[dict]:
    """扫 WTA 的所有入口，返回每张图的路径 ＋（Getty 的话）说明。"""
    pages = list(_WTA_PAGES)
    try:
        idx = _get(_WTA_PAGES[0])
        for vid, slug in sorted(set(re.findall(r"/videos/(\d+)/([a-z0-9-]+)", idx))):
            pages.append(f"https://www.wtatennis.com/videos/{vid}/{slug}")
    except Exception:                                           # noqa: BLE001
        pass

    found: dict[str, set[str]] = {}
    for url in pages:
        try:
            html = _get(url)
        except Exception:                                       # noqa: BLE001
            continue
        for path in set(_PHOTO_RE.findall(html)):
            found.setdefault(path, set()).add(url.rsplit("/", 1)[-1])

    out: list[dict] = []
    for path in sorted(found):
        name = path.rsplit("/", 1)[-1]
        # 站点自己的素材（赞助商 logo、栏目瓷砖、分享图）也住在同一个 CDN 上，
        # 不过滤的话不带条件跑一次会吐一屏 `Corpay_400x160.png` 这种。
        # 判据是**实拍图自己的命名**：`<球员>_-_<赛事>_-_Day_N-DSC_1234.jpg`
        # 或者 `GettyImages-<id>.jpg`，两种之外的一律不是比赛图。
        if not (re.search(r"-DSC_\d", name) or name.startswith("GettyImages-")):
            continue
        gid = re.match(r"GettyImages-(\d+)\.", name)
        row = {
            "name": name,
            "url": f"{_CDN}{path}?width=4000",
            "seen_on": sorted(found[path])[:2],
            "caption": getty_caption(gid.group(1)) if gid else None,
        }
        # 过滤：文件名带四要素的按文件名判，Getty 的按说明判
        hay = f"{name} {row['caption'] or ''}"
        if player and player.lower() not in hay.lower():
            continue
        if event and event.lower() not in hay.lower():
            continue
        if day and f"day {day}".lower() not in hay.lower() and f"Day_{day}" not in name:
            continue
        out.append(row)
    return out


_GANNETT_CDN = "https://www.gannett-cdn.com/"

#: ⚠️⚠️ **这个正则一度写死成 `sports/<年>/`，于是整类图集被漏掉。**
#: 2026-08-25 查美网时撞上的：Gannett 的图集路径在赛事名那一段是**可有可无的**，
#: 实测同时存在三种形状——
#:
#:     /picture-gallery/sports/2026/08/17/photos-cincinnati-open-round-3/<id>/
#:     /picture-gallery/sports/**tennis**/2025/09/07/carlos-alcaraz-.../<id>/
#:     /picture-gallery/sports/**tennis/open**/2025/09/06/aryna-sabalenka-.../<id>/
#:
#: 老正则只认第一种，于是**美网那一整类一条都扫不到**，而它报出来的样子
#: 和「这一天没有图集」一模一样（CLAUDE.md「扫得太窄和真的没有长得一模一样」）。
#: 中间那几段允许 0~3 层，日期那一段仍然锚死——不锚的话 `/picture-gallery/` 底下
#: 任何一条链接都会被收进来。判据 `test_图集正则要认得出赛事名那几段`。
_GALLERY_RE = re.compile(
    r"/picture-gallery/sports/(?:[a-z0-9-]+/){0,3}\d{4}/\d{2}/\d{2}/[a-z0-9-]+/\d+/")

#: ⭐ **办赛城市 → 当地那份 Gannett／USA TODAY 网络的报纸。**
#:
#: 这条渠道原来把 `cincinnati.com` **写死**在代码里，也就是说它只对辛辛那提
#: 一站有效——账号所有者 2026-08-17 那句「多找几个渠道，**不然下一个赛事就
#: 不一定有了啊**」点的正是这个。
#:
#: 2026-08-17 实测：同一个 `/picture-gallery/…/<id>/` 形状 ＋ 同一个 `/gcdn/`
#: 原图 CDN，**六份报纸里五份成立**：
#:
#:     desertsun.com          200  picture-gallery 1 条    /gcdn/ 40 次
#:     azcentral.com          200                  2 条              40 次
#:     providencejournal.com  200                 14 条              40 次
#:     lohud.com              200                  7 条              40 次
#:     cincinnati.com         200                  7 条              40 次   ← 已经在用的那份
#:     statesman.com          **410**              0 条               0 次   ← 这份没了
#:
#: ⚠️ **「报纸站活着」不等于「这一站有网球图集」**：上表量的是这个域名还认不认
#: `/picture-gallery/`，不是它拍不拍网球。真有没有要 `--paper <域名>` 跑一次
#: 才知道——和赛事图库那条一样，**查空要自证是真空**。
_LOCAL_PAPERS = {
    "cincinnati": "www.cincinnati.com",          # ✅ 已经出过图（4813×3209）
    "indian wells": "www.desertsun.com",         # 形状对得上，网球图集没验过
    "phoenix": "www.azcentral.com",
    "newport": "www.providencejournal.com",
    "new york": "www.lohud.com",                 # 美网这一带的 Gannett 报
    # ⚠️ 美网别指望 lohud（那是威郡本地报，不派人去法拉盛）——USA TODAY 自己
    #    派摄影师，2025 决赛周那两辑实测 **6000×4000**，比 WTA 那档还大一档。
    "us open": "www.usatoday.com",
}


def gannett_original(url: str) -> str:
    """把图集说明里那个 406 的地址换成真正拿得到原图的那个。

    ⚠️ `https://www.cincinnati.com/gcdn/authoring/…` 和
    `https://www.usatoday.com/gcdn/…` **恒 406**（带不带 Referer 都一样）；
    换成 `https://www.gannett-cdn.com/authoring/…` 才是无水印原图（实测 4813×3209，
    美网那两辑到 **6283×4189**）。取的时候还要带 `Accept: image/*`。

    ⚠️⚠️ **换完域名之后仍然会撞 406，而那是限流不是「这张图没了」。**
    2026-08-25 实测：同一个 URL 一分钟内 406 → 200，而同一辑里上一分钟还 200 的
    另一张变成了 406——**失败的是哪几张一直在换**。12 张连着取只有 4 张成功，
    而且 1~5 秒的退避重试一次都没救回来（窗口比那长）。
    所以判据是「**换一张再试**」，不是「重试这一张」：封面只要一张，一辑有三十几
    张候选，走一遍必然拿得到。**别把 406 读成「这张图不存在」然后退回抽帧。**
    """
    return re.sub(r"^https://[a-z0-9.-]+/gcdn/", _GANNETT_CDN, url)


def sweep_local_paper(paper: str, event: str | None, player: str | None,
                      day: str | None) -> dict:
    """扫当地报纸的每日图集：说明自带四要素，原图 4800~6000px 级。

    `paper` 是报纸域名（`www.cincinnati.com`）——**以前这个值写死在代码里**，
    于是这条渠道只对辛辛那提成立；现在从 `_LOCAL_PAPERS` 查或者用 `--paper` 给。
    `day` 给 `2026-08-16` 这种；不给就把索引页上翻得到的图集都看一遍。

    返回 `{"rows": [...], "notes": [...]}`。⚠️ **`notes` 不是装饰**：这一档
    一天能翻出十几辑（USA TODAY 2025-09-06 那天连棒球带网球一起），按赛事名
    筛掉的那些必须报出数来——CLAUDE.md「打印被丢弃的原因和数量」。
    """
    site = f"https://{paper.lstrip('https://').lstrip('/')}"
    query = (event or "tennis").replace(" ", "%20")
    days = [day] if day else None
    galleries: list[str] = []
    try:
        idx = _get(f"{site}/search/?q=photos%20{query}", timeout=40)
        galleries += _GALLERY_RE.findall(idx)
    except Exception:                                           # noqa: BLE001
        pass
    if days:
        y, m, d = days[0].split("-")
        month = ("january february march april may june july august september "
                 "october november december").split()[int(m) - 1]
        try:
            sm = _get(f"{site}/sitemap/{y}/{month}/{int(d)}/", timeout=40)
            galleries += _GALLERY_RE.findall(sm)
        except Exception:                                       # noqa: BLE001
            pass

    notes: list[str] = []
    found = sorted(set(galleries))
    if days:
        found = [g for g in found if f"/{days[0].replace('-', '/')}/" in g]

    # ⚠️ **同一天的图集不止这项运动。** 正则放宽到认得出 `sports/tennis/…`
    # 之后，USA TODAY 2025-09-06 那天一次翻出 5 辑，网球只占 1 辑，其余是棒球
    # ——不筛的话拿回来 49 张卡尔·里普肯。按赛事 slug 筛，**但要报出筛掉几辑**：
    # 「非空 ≠ 对题」和「扫得太窄和真的没有长得一模一样」这两个坑各在一头。
    picked = found
    if event and found:
        slug = re.sub(r"[^a-z0-9]+", "-", event.lower()).strip("-")
        hit = [g for g in found if slug and slug in g]
        if hit:
            picked = hit
            if len(hit) < len(found):
                notes.append(f"这一天翻到 {len(found)} 辑，按「{slug}」筛剩 "
                             f"{len(hit)} 辑（其余是别的项目）")
        else:
            notes.append(f"这一天翻到 {len(found)} 辑，**没有一辑的名字里带"
                         f"「{slug}」**——下面这些是同日全部图集，自己看对不对题")

    out: list[dict] = []
    for path in picked:
        try:
            html = _get(site + path, timeout=60)
        except Exception:                                       # noqa: BLE001
            continue
        for blob in re.findall(r"<script type=application/ld\+json>(.*?)</script>",
                               html, re.S):
            try:
                data = json.loads(blob)
            except Exception:                                   # noqa: BLE001
                continue
            for item in (data if isinstance(data, list) else [data]):
                images = item.get("image") if isinstance(item, dict) else None
                if isinstance(images, dict):
                    images = [images]
                for img in images or []:
                    if not isinstance(img, dict) or not img.get("url"):
                        continue
                    cap = img.get("caption") or ""
                    if player and player.lower() not in cap.lower():
                        continue
                    out.append({
                        "gallery": path,
                        "caption": cap,
                        "credit": img.get("copyrightHolder"),
                        "url": gannett_original(img["url"]),
                    })
    return {"rows": out, "notes": notes}


_AP = "https://apnews.com"
#: AP 的图走一个动态缩放器：
#: `dims.apnews.com/dims4/default/<hash>/…/resize/980x653!/…?url=<原图>`
#: ——**原图地址就挂在 `?url=` 上**，而缩放器给的是 980 宽的版面图。
_AP_DIMS = re.compile(r"https://dims\.apnews\.com/dims4/[^\"'\s\\]+")


def ap_original(dims_url: str) -> str | None:
    """从 AP 缩放器的地址里把原图抠出来。

    ⚠️ **别直接用 `dims.apnews.com` 那个地址**：它是按版面缩好的（实测
    `980x653` / `767x511`），铺 1080×1440 连一半都不到。`?url=` 后面那个
    `assets.apnews.com/...` 才是原图——实测 **8640×5760** 和 **4714×3143**。
    """
    q = urllib.parse.parse_qs(urllib.parse.urlparse(
        dims_url.replace("&amp;", "&")).query)
    got = (q.get("url") or [None])[0]
    return got if got and got.startswith("http") else None


def usopen_player_ids(player: str, year: str) -> list[dict]:
    """把球员名解析成美网的 `playerId`（`wta328120` / `atpn552` 这种）。

    ⚠️ **返回全部同姓命中，不替调用方挑一个。** 同一站两个中国选手都姓 Wang
    时挑错人，在产物上和挑对了长得一模一样（CLAUDE.md 那条老坑）。
    """
    last_exc: Exception | None = None
    for attempt in range(_USO_PLAYERS_TRIES):
        try:
            raw = json.loads(_get(_USO_PLAYERS.format(year=year), timeout=40))
            break
        except Exception as exc:                                # noqa: BLE001
            last_exc = exc
            if attempt + 1 < _USO_PLAYERS_TRIES:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise UsoPlayersUnavailable(str(last_exc))
    people = raw.get("players") if isinstance(raw, dict) else raw
    want = player.lower().strip()
    out = []
    for p in people or []:
        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        full = f"{first} {last}".strip()
        if not p.get("id"):
            continue
        # ⚠️ **按词集匹配，不按词序。** players.json 是「名 姓」
        # （`Qinwen Zheng`），而中文习惯和 flashscore 都写「姓 名」——
        # 用 `want in full` 会把 `Zheng Qinwen` 判成查无此人，而那个空结果
        # 和「这一年还没发图」长得一模一样（2026-08-25 第一版就是这么错的）。
        toks = [t for t in re.split(r"[\s,]+", want) if t]
        low = full.lower()
        if (want == last.lower()
                or (toks and all(t in low for t in toks))):
            out.append({"id": p["id"], "name": full,
                        "country": p.get("nation_code") or p.get("country") or ""})
    return out


def sweep_usopen(player: str | None, date: str | None, year: str) -> dict:
    """美网官方图片接口。**这一档是保底：每场都有，但封顶 1280×720。**

    两条路：给了球员就按 `playerId` 的 tag 查（**结果是确定的**，可以拿来当
    「真空」的证据用——郑钦文全部 263 条里 2026 年只有两条，8/24 资格赛的
    握拳和场外签名各一张）；没给就按日期扫 `byType/photo`。

    文件名自带日期戳（`USTA<资产号>_<YYYYMMDD>_<摄影师机身>.jpg`），
    `description` 里四要素 ＋ 署名全齐，例如：

        「Qinwen Zheng reacts during a women's qualifying singles match during
         Fan Week as part of the 2026 US Open at USTA Billie Jean King National
         Tennis Center on Monday, August 24, 2026 in Flushing, NY.
         (Photo by David Nemec/USTA)」
    """
    def rows_of(payload: str) -> list[dict]:
        try:
            body = json.loads(payload)
        except Exception:                                       # noqa: BLE001
            return []
        out = []
        for it in body.get("content") or []:
            imgs = (it.get("images") or [{}])[0]
            stamp = it.get("displayDate") or it.get("sortDate") or 0
            try:
                day = _dt.datetime.utcfromtimestamp(stamp / 1000).strftime("%Y-%m-%d")
            except Exception:                                   # noqa: BLE001
                day = ""
            out.append({"cms": it.get("cmsId") or "", "date": day,
                        "title": it.get("title") or "",
                        "caption": it.get("description") or "",
                        "credit": imgs.get("credit") or "",
                        "url": imgs.get("xlarge") or imgs.get("large") or ""})
        return out, body.get("totalRows")

    found: list[dict] = []
    notes: list[str] = []
    try:
        who = usopen_player_ids(player, year) if player else []
    except UsoPlayersUnavailable as exc:
        who = []
        notes.append(f"⚠️ players.json 取不到（{exc}）——**这不是「没有这个人」，"
                     f"是取数失败**（这个接口间歇 403，已经重试 "
                     f"{_USO_PLAYERS_TRIES} 次）。这一档没跑，别读成查空")
    else:
        if player and not who:
            notes.append(f"players.json 里没有叫 {player!r} 的人——"
                         f"**先怀疑查询词**（要姓或姓名，不是 slug），再怀疑没有照片")
    for person in who:
        try:
            payload = _get(f"{_USO_REST}/tag?tags={person['id']}"
                           f"&type=photo&count=200&skip=0", timeout=40)
        except Exception as exc:                                # noqa: BLE001
            notes.append(f"{person['name']}（{person['id']}）取不到：{exc}")
            continue
        rows, total = rows_of(payload)
        mine = [r for r in rows if r["date"].startswith(year)]
        notes.append(f"{person['name']}（{person['id']}，{person['country']}）"
                     f"：全部 {total} 条，其中 {year} 年 {len(mine)} 条")
        found.extend(mine)
    if not player:
        for skip in (0, 200, 400):
            try:
                payload = _get(f"{_USO_REST}/content/byType/photo"
                               f"?count=200&skip={skip}", timeout=40)
            except Exception:                                   # noqa: BLE001
                break
            rows, _ = rows_of(payload)
            found.extend(rows)
    if date:
        found = [r for r in found if r["date"] == date]
    seen, uniq = set(), []
    for r in found:
        if r["cms"] in seen:
            continue
        seen.add(r["cms"])
        uniq.append(r)
    uniq.sort(key=lambda r: r["date"], reverse=True)
    return {"rows": uniq, "notes": notes}


def _event_key(text: str) -> str:
    """赛事名归一：抹掉非字母数字，`U.S. Open` 和 `US Open` 都变成 `usopen`。"""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def sweep_ap(player: str | None, event: str | None, limit: int = 8) -> list[dict]:
    """⭐⭐ **通讯社这一档：AP。这是唯一一条「换个赛事照样有」的高清渠道。**

    2026-08-17 挖出来的，来路是账号所有者那句「多找几个渠道，**不然下一个赛事
    就不一定有了啊**」——去量了一遍才发现分辨率最高的那两条
    （赛事图库 5541px、当地报纸 4813px）**都不跨赛事**：前者 11 个赛事官网只有
    辛辛那提一个开着 WP REST，后者得先知道当地哪份报纸。
    **而 AP 是通讯社，每站都派人。**

    实测（`apnews.com/hub/tennis`）：

        原图      assets.apnews.com/...   **8640×5760**（8.0 MB）／ 4714×3143
        说明      `<img alt>` 里，四要素全齐 ＋ 署名：
                  「Ben Shelton of the United States hoists the trophy following
                   his win over compatriot Brandon Nakashima during final tennis
                   action at the National Bank Open in Montreal on Thursday,
                   Aug. 13, 2026. (Christinne Muschi/The Canadian Press via AP)」

    ⚠️ **搜索是真的在筛，但结果里混着一批固定的边栏稿。** `?q=` 三个完全无关的
    词各回 69~70 篇，**三者交集 40 篇**——那 40 篇是每页都挂的推荐位。
    独有的才是搜出来的（`Svitolina` 独有 29 篇）。**「非空 ≠ 对题」**：
    只数条数会以为搜索没生效，只信条数又会把边栏稿当成命中。这里靠
    **说明里有没有这个人**来筛，不靠搜索结果本身。

    ⚠️ **版权是 AP 的**（属于四类源里第 ③ 档「新闻站／图片社转载」），
    署名照实记进 credits，发布前人工判断。
    """
    want = (player or "").lower()
    queries = [q for q in (f"{player} tennis" if player else None,
                           f"{event} tennis" if event else None,
                           "tennis") if q]
    slugs: list[str] = []
    for q in queries:
        try:
            html = _get(f"{_AP}/search?q={urllib.parse.quote(q)}", timeout=40)
        except Exception:                                       # noqa: BLE001
            continue
        for u in re.findall(r"https://apnews\.com/article/[a-z0-9-]+", html):
            if u not in slugs:
                slugs.append(u)
    try:
        hub = _get(f"{_AP}/hub/tennis", timeout=40)
        for u in re.findall(r"https://apnews\.com/article/[a-z0-9-]+", hub):
            if u not in slugs:
                slugs.append(u)
    except Exception:                                           # noqa: BLE001
        pass

    # 先按 slug 粗筛，别为了那 40 篇边栏稿去拉 70 个页面
    def looks_relevant(u: str) -> bool:
        tail = u.rsplit("/", 1)[-1]
        if want and want.split()[-1] in tail:
            return True
        return bool(re.search(r"tennis|open|wimbledon|slam", tail))

    out: list[dict] = []
    for url in [u for u in slugs if looks_relevant(u)][:limit]:
        try:
            html = _get(url, timeout=40)
        except Exception:                                       # noqa: BLE001
            continue
        pairs = re.findall(
            r'<img[^>]*?src="(https://dims\.apnews\.com/[^"]+)"[^>]*?alt="([^"]{30,400})"',
            html)
        pairs += [(b, a) for a, b in re.findall(
            r'<img[^>]*?alt="([^"]{30,400})"[^>]*?src="(https://dims\.apnews\.com/[^"]+)"',
            html)]
        seen: set[str] = set()
        for dims, cap in pairs:
            orig = ap_original(dims)
            if not orig or orig in seen:
                continue
            seen.add(orig)
            cap = html_mod.unescape(cap)
            # ⚠️ 判据是**说明里有没有这个人**，不是「这篇稿子搜出来了」——
            # 边栏稿混在结果里，而它们的图跟这场球毫无关系。
            if want and want.split()[-1] not in cap.lower():
                continue
            # ⚠️⚠️ **光按人筛会拿回一堆资料图**，而它们和本场图长得一模一样。
            # 实测 `--player Svitolina`：不筛赛事时头三张分别是温网的捧杯、
            # 多伦多半决赛（两张，还是斯瓦泰克赢的那场）——**每一张都是她，
            # 每一张都不是这一场**。这正是 Getty 那条「看见就先查说明」的同一个坑，
            # 只不过 AP 把说明直接给了，所以能机筛。
            # ⚠️⚠️ **这里一度写的是 `event.split()[0]`，而它对「US Open」
            # 退化成了「us」——「United States」「Australian」里都有，
            # 于是这道闸对美网整个失效。** 2026-08-25 实测：`--event "US Open"`
            # 拿回来六张，温网、马德里、法网各有，**一张美网都没有**，
            # 而它和「这一档没图」在输出里长得一模一样。
            # 现在比**整个赛事名**，两边都抹掉非字母数字（AP 有时写「U.S. Open」，
            # 抹完两边都是 usopen）。
            if event and _event_key(event) not in _event_key(cap):
                continue
            out.append({"article": url, "caption": cap, "url": orig})
    return out


def original_url(url: str) -> str | None:
    """⭐ WordPress 的 `-scaled` **不是原图，是 2560 的封顶版**——去掉它才是原图。

    实测（`cincinnatiopen.com`，2026-08-16）：

        CincinnatiOpen_20260813_JM010573_JW1-scaled.jpg   2560×1707
        CincinnatiOpen_20260813_JM010573_JW1.jpg          **4991×3328**
        081326_DAY-SIX_MIKE-BAKER-25-of-48-scaled.jpg     2560×1707
        081326_DAY-SIX_MIKE-BAKER-25-of-48.jpg            **5541×3694**

    ⚠️ **反过来不成立**：`source_url` 里**没有** `-scaled` 的那些（上传时就
    ≤2560，如 `081526_DAY-EIGHT_MIKE-BAKER-149-of-229.jpg` 的 2000×1333），
    去猜一个 `-scaled` 是 404——那个就已经是原图了。

    ⚠️ 这条同时纠正 CLAUDE.md 里两处打架的旧注（一处说「`-scaled` 比裸名大」、
    一处说「2026 这一批没有 `-scaled`」）：**判据是 `source_url` 自己带不带
    `-scaled`**，带就去掉、不带就用它，别按年份或按印象猜。
    """
    if url.endswith("-scaled.jpg"):
        return url[: -len("-scaled.jpg")] + ".jpg"
    return None


#: `--discover` 要挨个敲的门。**这张表是「怎么问」，不是「有什么」**——
#: 一个都不通才叫这个站没有照片接口，而那要跑一次才知道。
_DISCOVER = (
    ("WP 媒体库", "/wp-json/wp/v2/media?per_page=1"),
    ("WP 备用入口", "/?rest_route=/wp/v2/media&per_page=1"),
    ("图片 sitemap", "/sitemap-image.xml"),
    ("sitemap 索引", "/sitemap_index.xml"),
    ("robots（里面写着 sitemap 在哪）", "/robots.txt"),
)


def discover(site: str) -> list[str]:
    """这个赛事官网到底有没有照片接口——**下一个赛事的第一条命令**。

    ⚠️⚠️ **2026-08-17 量出来的账，这条渠道基本不通用**：拿这张表扫了 11 个
    赛事官网，**只有 `cincinnatiopen.com` 一个开着 WP REST**：

        cincinnatiopen.com      WP 媒体库 200 json=1        ✅
        usopen.org              200 但不是 json（是首页 HTML）
        winstonsalemopen.com / tennisintheland.com /
        nationalbankopen.com / mubadalacitidcopen.com /
        japanopentennis.com     WP 404，备用入口回的是 HTML
        abiertogdl.com.mx / monterreyopen.mx /
        koreaopentennis.com     沙箱出网就够不着
        chengduopen.com         SSL 握手失败

    也就是说「赛事官网媒体库」**是辛辛那提的特例，不是一条通用渠道**——账号
    所有者那句「不然下一个赛事就不一定有了啊」是对的，而且比预想的更糟。
    真正跨赛事成立的只有 **WTA `photo-resources`**（巡回赛级）和**当地报纸**
    （按城市换域名，见 `_LOCAL_PAPERS`）。

    ⚠️ **`200` 不等于「通了」**：不是 WordPress 的站会拿首页 HTML 回你一个 200
    （`usopen.org` 就是），只看状态码会把它读成「有接口」。判据是**回来的是不是
    JSON**——所以这里解析一次再报。
    """
    out = [f"=== {site} 有没有照片接口"]
    for label, path in _DISCOVER:
        try:
            resp = requests.get(f"https://{site}{path}", headers=_UA, timeout=25)
        except Exception as exc:                                # noqa: BLE001
            out.append(f"  {label:32} 够不着：{type(exc).__name__}")
            continue
        tag = f"{resp.status_code} {len(resp.content)}B"
        if label.startswith("WP") and resp.status_code == 200:
            try:
                tag += f"　✅ JSON，{len(json.loads(resp.text))} 条"
            except Exception:                                   # noqa: BLE001
                tag += "　❌ **回的是 HTML 不是 JSON**——这个站不是 WordPress"
        if label.startswith("robots") and resp.status_code == 200:
            found = re.findall(r"(?i)^sitemap:\s*(\S+)", resp.text, re.M)
            tag += "　| " + (", ".join(found[:3]) if found else "没写 sitemap")
        out.append(f"  {label:32} {tag}")
    out.append("  ⚠️ 一条都不通**不代表这一站没有照片**——它只说明这几扇门没开。"
               "还有 WTA `photo-resources`（巡回赛级，永远该试）和当地报纸"
               "（`--paper <域名>`）两条。")
    return out


def sweep_tournament(site: str, date: str | None, player: str | None = None) -> dict:
    """赛事官网的 WP 媒体库 ＋ 图库上线时刻。

    ⚠️ **两条各扫一遍**：按日期拿当天全量，按 `?search=<姓>` 拿命名和元数据两种。
    第二条 2026-08-17 才补上——在那之前这个函数只按日期扫，而模块 docstring 里
    写着「文件名没有球员名，所以 search 是空的」。**那句话是错的**：WordPress 的
    search 还搜 `title` / `alt_text` / `caption`，而赛事方给图填了 title——
    搜 `Fonseca` 回来三张文件名里根本不含 `Fonseca` 的比赛照。
    """
    base = f"https://{site}/wp-json/wp/v2"
    res: dict = {"media": [], "galleries": [], "by_name": []}
    if player:
        try:
            named = json.loads(_get(
                f"{base}/media?per_page=40&search={player}"
                "&_fields=date,source_url,media_details,title"))
            for m in named:
                md = m.get("media_details") or {}
                if not md.get("width"):
                    continue
                url = m.get("source_url") or ""
                res["by_name"].append({
                    "date": m.get("date"), "wh": f"{md.get('width')}x{md.get('height')}",
                    "title": (m.get("title") or {}).get("rendered", ""),
                    "url": url, "original": original_url(url),
                })
        except Exception:                                       # noqa: BLE001
            pass
    try:
        media = json.loads(_get(f"{base}/media?per_page=100&orderby=date&order=desc"))
    except Exception as exc:                                    # noqa: BLE001
        res["error"] = f"媒体库读不到：{exc}"
        return res
    for m in media:
        d = (m.get("date") or "")[:10]
        if date and d != date:
            continue
        md = m.get("media_details") or {}
        if not md.get("width"):
            continue                                            # PDF 之类
        url = m.get("source_url") or ""
        res["media"].append(
            {"date": m.get("date"), "wh": f"{md.get('width')}x{md.get('height')}",
             "url": url, "original": original_url(url)}
        )
    try:
        posts = json.loads(
            _get(f"{base}/posts?per_page=100&orderby=date&order=desc"
                 "&_fields=date,date_gmt,slug")
        )
        res["galleries"] = [
            p for p in posts if "best-of-photos" in (p.get("slug") or "")
        ]
    except Exception:                                           # noqa: BLE001
        pass
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", help="按球员姓过滤（文件名或 Getty 说明里出现）")
    ap.add_argument("--event", help="按赛事名过滤，如 Cincinnati（⚠️ 是名字不是 id）")
    ap.add_argument("--day", help="按第几个比赛日过滤，如 6")
    ap.add_argument("--site", help="赛事官网域名，如 cincinnatiopen.com")
    ap.add_argument("--date", help="赛事图库按这一天筛，如 2026-08-16")
    ap.add_argument("--getty", help="只查一个 Getty 编号是哪一场")
    ap.add_argument("--paper", help="当地报纸域名（不给就按 --event 从 "
                                    "_LOCAL_PAPERS 查；查不到就跳过这一档并说明）")
    ap.add_argument("--discover", help="**新赛事的第一条命令**：敲一遍这个赛事"
                                       "官网有没有照片接口，别再手搓 curl")
    ap.add_argument("--year", default="2026",
                    help="美网那一档按哪一年查（默认 2026）")
    args = ap.parse_args()

    if args.discover:
        for line in discover(args.discover):
            print(line)
        return 0

    if args.getty:
        print(getty_caption(args.getty) or "（这个编号查不到说明）")
        return 0

    # ⚠️ `--event` 比的是**赛事名**（文件名里写的是 `Cincinnati_Open_2026`、
    # Getty 说明里写的是 `Cincinnati Open`），不是 WTA 的数字赛事 id。
    # 传 `--event 1017` 不会报错，只会**一张都匹配不上**——而那个空结果和
    # 「今天真的还没发图」长得一模一样（CLAUDE.md「空结果先自证是真空」／
    # 「零命中先怀疑自己的查询词」）。2026-08-17 就是这么白判过一次
    # `wangxiyu-fernandez` 的封面。
    if args.event and args.event.isdigit():
        ap.error(f"--event 要给赛事名不是 id：把 {args.event!r} 换成 "
                 f"'Cincinnati' 这样的名字（图库文件名里写的是 "
                 f"`<球员>_-_Cincinnati_Open_2026_-_Day_N-DSC_1234.jpg`）")

    print("=== WTA photo-resources（文件名带四要素；Getty 的去查说明）")
    rows = sweep_wta(args.player, args.event, args.day)
    if not rows:
        print("  没有对得上的。⚠️ 这是「还没发」不是「没有」——"
              "WTA 一批只发几个人，赛事图库另有上线时刻，见下。")
    for r in rows:
        print(f"  {r['name']}")
        if r["caption"]:
            print(f"     说明：{r['caption']}")
        print(f"     {r['url']}")

    # ⭐⭐ 通讯社这一档**每站都有**，所以它无条件跑——不像下面两档要先知道
    # 这一站在哪个城市、官网是不是 WordPress。
    print("\n=== AP 通讯社（唯一一条**又高清又跨得过赛事**的，原图 4700~8600px）")
    ap = sweep_ap(args.player, args.event)
    if not ap:
        print("  没有对得上的。⚠️ AP 一天只发几场的图，**「这一场没有」不等于"
              "「这条渠道不行」**；隔几小时或换个赛事名再试。")
    for r in ap[:8]:
        print(f"  {r['caption'][:160]}")
        print(f"     {r['url']}")

    # ⭐⭐ **大满贯这一档：只有美网有，而且它是保底——每场都有，但封顶 1280×720。**
    # 上面 WTA 那一档**不收大满贯**，下面赛事官网那一档要 WordPress，
    # 而美网不是 WordPress 站。所以这三档对美网只有这一条走得通。
    is_uso = bool(args.event and "us open" in args.event.lower())
    if is_uso:
        print("\n=== 美网官方图片接口（保底：每场都有；⚠️ 封顶 1280×720）")
        res = sweep_usopen(args.player, args.date, args.year)
        for n in res["notes"]:
            print(f"  · {n}")
        rows = res["rows"]
        if not rows:
            print("  没有对得上的。⚠️ 分清两件事：**「还没发」**（夜场的官方图约 24 "
                  "小时才上线）和**「真的没有」**——上面那行「全部 N 条，其中 <年> "
                  "M 条」就是判据，M=0 才是这一年真没有。")
        for r in rows[:10]:
            print(f"  {r['date']}  {r['title'][:46]}")
            print(f"     {r['caption'][:150]}")
            print(f"     {r['credit']} · {r['url']}")
        if rows:
            print("  ⚠️ `xlarge`（`f_` 前缀）就是顶，1280×720，铺 1080×1440 只有 "
                  "0.50×——**这一档的图默认要写 `cover.portrait._low_res_why`**。"
                  "十二个前缀、六个目录、三种 `?width=` 参数都试过（第三组返回 200 "
                  "但尺寸一个像素没变），别再重探。")
    else:
        print("\n=== 美网官方图片接口　⚠️ **这一档没跑**")
        print("  `--event` 里没有 `US Open`。大满贯不进 WTA/ATP 图库，"
              "美网另有自己的接口——查美网请传 --event \"US Open\"。")

    # ⚠️ 这一档以前把 `cincinnati.com` 写死在代码里，也就是**只对辛辛那提成立**。
    # 现在按办赛城市查 `_LOCAL_PAPERS`，查不到就明说这一档没跑——
    # 跳过的那一档和查空的那一档在输出里长得一模一样（上面 `--site` 那次的教训）。
    paper = args.paper
    if not paper and args.event:
        for city, dom in _LOCAL_PAPERS.items():
            if city in args.event.lower():
                paper = dom
                break
    if paper:
        print(f"\n=== {paper} 每日图集（说明自带四要素，原图 4800px 级）")
        got = sweep_local_paper(paper, args.event, args.player, args.date)
        enq = got["rows"]
        for note in got["notes"]:
            print(f"  ⚠️ {note}")
        if not enq:
            print("  没有对得上的。⚠️ 这一辑**按比赛日出**，当天的往往次日才上线；"
                  "而且它和赛事图库一样偏主球场——**有这条渠道不等于有这个人**。")
        for r in enq[:10]:
            print(f"  {r['caption'][:150]}")
            print(f"     {r['credit']} · {r['url']}")
    else:
        print("\n=== 当地报纸每日图集　⚠️ **这一档没跑**")
        print(f"  不知道这一站在哪个城市——`_LOCAL_PAPERS` 里现有 "
              f"{'、'.join(_LOCAL_PAPERS)}。")
        print("  补一句就有：--paper <报纸域名，如 www.cincinnati.com>；"
              "新城市查一次 Gannett／USA TODAY 网络里当地那份，加进 `_LOCAL_PAPERS`。")

    # ⚠️⚠️ **不给 `--site` 时这一档整个不跑，而它正是三条里最常有图的一条。**
    # 2026-08-17 就是这么白判过一次：`--player Svitolina --event Cincinnati`
    # 只跑了上面两档、都报「没有对得上的」，我据此在 `_frame_why` 里写下
    # 「四类源都翻过」——而赛事媒体库当天其实躺着 18 张实拍。**跳过的那一档
    # 和查空的那一档在输出里长得一模一样**（CLAUDE.md「空结果先自证是真空」／
    # 「扫得太窄和真的没有长得一模一样」）。所以现在**没跑的要出声**，
    # 而且末尾那份清单把「这一趟到底查了哪几档」逐条列出来。
    if not args.site:
        print("\n=== 赛事官网的 WordPress 媒体库　⚠️ **这一档没跑**")
        print("  没给 `--site`，而它当日实拍最全（原图 2000px 级，"
              "去掉 `-scaled` 能到 5541×3694）。")
        print("  补一句就有：--site <赛事域名，如 cincinnatiopen.com> "
              "--date <这场球的**当地**日期>")
        print("  ⚠️ 当地日期不是北京日期：夜场（当地 21:00 之后开打）在北京是次日。")
    if args.site:
        print(f"\n=== {args.site} 的 WordPress 媒体库")
        res = sweep_tournament(args.site, args.date, args.player)
        if res.get("error"):
            print("  " + res["error"])
        else:
            # ⚠️ 先报按名字搜到的那一批。**这一条 2026-08-17 才补上**——在那之前
            # 这一档只按日期扫，而模块 docstring 断言 search 是空的（错的）。
            named = res.get("by_name") or []
            if args.player:
                print(f"  ⭐ 按名字搜（`?search={args.player}`，搜的是文件名 ＋ "
                      f"title/alt/caption）：{len(named)} 张")
                for m in named[:8]:
                    print(f"    {m['date'][:10]}  {m['wh']:11} "
                          f"{m['url'].rsplit('/', 1)[-1][:44]}  title={m['title'][:20]}")
                    if m["original"]:
                        print(f"      ⭐ 去掉 -scaled 才是原图：{m['original']}")
                if not named:
                    print("    没有。⚠️ 这不等于当天没图——赛事图库多数文件名和 title "
                          "都不带球员名，按日期那一档还要看。")
                elif all(int(m["wh"].split("x")[0]) < 1200 for m in named):
                    print("    ⚠️ **全是小图**（492×656 那种是官方头像，不是比赛照）。"
                          "「search 有命中」不等于「有能用的图」。")
            hits = res["media"]
            print(f"  {args.date or '最近 100 条'}：{len(hits)} 张")
            for m in hits[:8]:
                print(f"    {m['date']}  {m['wh']:11} {m['url'].rsplit('/', 1)[-1][:56]}")
                if m["original"]:
                    print(f"      ⭐ 去掉 -scaled 才是原图（实测能到 5541×3694）："
                          f"{m['original']}")
            if res["galleries"]:
                print("  图库上线时刻（判据：当天那一辑在次日 UTC 00:00–03:00 之间）：")
                for g in sorted(res["galleries"], key=lambda x: x["date"])[-6:]:
                    print(f"    {g['slug']:26} UTC {g['date_gmt']}")

    # **这一趟到底查了哪几档，明着写出来。** 写 `cover.portrait._frame_why`
    # 的人要照抄这份清单，不许写成「四类源都翻过」——没跑的那一档不算翻过。
    ran = ["WTA photo-resources", "AP 通讯社"]
    skipped = []
    (ran if is_uso else skipped).append("美网官方图片接口")
    (ran if paper else skipped).append("当地报纸每日图集")
    (ran if args.site else skipped).append("赛事官网 WordPress 媒体库")
    print("\n=== 这一趟查了什么")
    print(f"  跑过：{'、'.join(ran)}")
    if skipped:
        print(f"  ⚠️ **没跑**：{'、'.join(skipped)}——这几档的结果是**未知**，不是「没有」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
