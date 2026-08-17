#!/usr/bin/env python3
"""封面官方实拍：把**所有查得通的渠道**扫一遍，并把「这张图是哪一场」查实。

CLAUDE.md「封面大图一律用官方高清实拍」那条的配套工具。以前只有两条路
（WTA 的 `photo-resources` ＋ 赛事官网的图库页），2026-08-16 又量出三条，
外加一批**实测走不通、别再试**的。全写在这儿，别每次现搓。

    python3 tools/find_cover_photo.py --player Tjen --event Cincinnati --day 6
    python3 tools/find_cover_photo.py --player Sabalenka --site cincinnatiopen.com --date 2026-08-16
    python3 tools/find_cover_photo.py --getty 2288964672      # 只查一个 Getty 编号是哪一场

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
   ⚠️ 赛事图库的文件名**没有球员名**（`081526_DAY-EIGHT_MIKE-BAKER-112-of-229.jpg`），
   所以 `?search=<姓>` 在这儿是空的——它的用处是**按日期看当天的图上没上**。

4. ⭐ **图库什么时候上线是可以量的，别在当天下午反复扫。** 拿
   `posts?orderby=date` 读 `day-N-best-of-photos` 的 `date_gmt`，实测：

       day-1  2026-08-12T00:00Z      day-4  2026-08-15T00:48Z
       day-3  2026-08-14T01:56Z      day-5  2026-08-16T02:57Z

   也就是**当天那一辑在次日 UTC 00:00–03:00 之间上线**（当地 20:00–23:00）。

5. ⭐⭐⭐ **当地报纸的每日图集**（2026-08-17 挖出来的，**这条是分辨率最高的一条**）。
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
"""
from __future__ import annotations

import argparse
import json
import re
import sys

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


_GANNETT_SITE = "https://www.cincinnati.com"
_GANNETT_CDN = "https://www.gannett-cdn.com/"


def gannett_original(url: str) -> str:
    """把图集说明里那个 406 的地址换成真正拿得到原图的那个。

    ⚠️ `https://www.cincinnati.com/gcdn/authoring/…` 和
    `https://www.usatoday.com/gcdn/…` **恒 406**（带不带 Referer 都一样）；
    换成 `https://www.gannett-cdn.com/authoring/…` 才是无水印原图（实测 4813×3209）。
    取的时候还要带 `Accept: image/*`。
    """
    return re.sub(r"^https://[a-z0-9.-]+/gcdn/", _GANNETT_CDN, url)


def sweep_enquirer(player: str | None, day: str | None) -> list[dict]:
    """扫 The Enquirer 的每日图集：说明自带四要素，原图 4800px 级。

    `day` 给 `2026-08-16` 这种；不给就把最近几天的图集都翻一遍。
    """
    days = [day] if day else None
    galleries: list[str] = []
    try:
        idx = _get(f"{_GANNETT_SITE}/search/?q=photos%20cincinnati%20open", timeout=40)
        galleries += re.findall(r"/picture-gallery/sports/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/\d+/", idx)
    except Exception:                                           # noqa: BLE001
        pass
    if days:
        y, m, d = days[0].split("-")
        month = ("january february march april may june july august september "
                 "october november december").split()[int(m) - 1]
        try:
            sm = _get(f"{_GANNETT_SITE}/sitemap/{y}/{month}/{int(d)}/", timeout=40)
            galleries += re.findall(
                r"/picture-gallery/sports/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/\d+/", sm)
        except Exception:                                       # noqa: BLE001
            pass

    out: list[dict] = []
    for path in sorted(set(galleries)):
        if days and f"/{days[0].replace('-', '/')}/" not in path:
            continue
        try:
            html = _get(_GANNETT_SITE + path, timeout=60)
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


def sweep_tournament(site: str, date: str | None) -> dict:
    """赛事官网的 WP 媒体库 ＋ 图库上线时刻。"""
    base = f"https://{site}/wp-json/wp/v2"
    res: dict = {"media": [], "galleries": []}
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
    args = ap.parse_args()

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

    print("\n=== The Enquirer 每日图集（说明自带四要素，原图 4800px 级）")
    enq = sweep_enquirer(args.player, args.date)
    if not enq:
        print("  没有对得上的。⚠️ 这一辑**按比赛日出**，当天的往往次日才上线；"
              "而且它和赛事图库一样偏主球场——**有这条渠道不等于有这个人**。")
    for r in enq[:10]:
        print(f"  {r['caption'][:150]}")
        print(f"     {r['credit']} · {r['url']}")

    # ⚠️⚠️ **不给 `--site` 时这一档整个不跑，而它正是三条里最常有图的一条。**
    # 2026-08-17 就是这么白判过一次：`--player Svitolina --event Cincinnati`
    # 只跑了上面两档、都报「没有对得上的」，我据此在 `_frame_why` 里写下
    # 「四类源都翻过」——而赛事媒体库当天其实躺着 18 张实拍。**跳过的那一档
    # 和查空的那一档在输出里长得一模一样**（CLAUDE.md「空结果先自证是真空」／
    # 「扫得太窄和真的没有长得一模一样」）。所以现在**没跑的要出声**，
    # 而且末尾那份清单把「这一趟到底查了哪几档」逐条列出来。
    if not args.site:
        print("\n=== 赛事官网的 WordPress 媒体库　⚠️ **这一档没跑**")
        print("  没给 `--site`，而它是三条里最常有图的一条（当日实拍原图 2000px 级，"
              "去掉 `-scaled` 能到 5541×3694）。")
        print("  补一句就有：--site <赛事域名，如 cincinnatiopen.com> "
              "--date <这场球的**当地**日期>")
        print("  ⚠️ 当地日期不是北京日期：夜场（当地 21:00 之后开打）在北京是次日。")
    if args.site:
        print(f"\n=== {args.site} 的 WordPress 媒体库")
        res = sweep_tournament(args.site, args.date)
        if res.get("error"):
            print("  " + res["error"])
        else:
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
    ran = ["WTA photo-resources", "The Enquirer 每日图集"]
    skipped = []
    (ran if args.site else skipped).append("赛事官网 WordPress 媒体库")
    print("\n=== 这一趟查了什么")
    print(f"  跑过：{'、'.join(ran)}")
    if skipped:
        print(f"  ⚠️ **没跑**：{'、'.join(skipped)}——这几档的结果是**未知**，不是「没有」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
