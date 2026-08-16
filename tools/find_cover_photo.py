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

## 实测走不通的，别再试

| 路 | 结果 |
|---|---|
| Getty 自己的 comp 图 `media.gettyimages.com/id/…` | 脱离页面上下文一律 **400**（签名参数绑上下文）；而且 `w=gi` 是**带水印**的 |
| Getty API `api.gettyimages.com` | **401**，要 key |
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
import urllib.request

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
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


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
        res["media"].append(
            {"date": m.get("date"), "wh": f"{md.get('width')}x{md.get('height')}",
             "url": m.get("source_url")}
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
    ap.add_argument("--event", help="按赛事名过滤，如 Cincinnati")
    ap.add_argument("--day", help="按第几个比赛日过滤，如 6")
    ap.add_argument("--site", help="赛事官网域名，如 cincinnatiopen.com")
    ap.add_argument("--date", help="赛事图库按这一天筛，如 2026-08-16")
    ap.add_argument("--getty", help="只查一个 Getty 编号是哪一场")
    args = ap.parse_args()

    if args.getty:
        print(getty_caption(args.getty) or "（这个编号查不到说明）")
        return 0

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
            if res["galleries"]:
                print("  图库上线时刻（判据：当天那一辑在次日 UTC 00:00–03:00 之间）：")
                for g in sorted(res["galleries"], key=lambda x: x["date"])[-6:]:
                    print(f"    {g['slug']:26} UTC {g['date_gmt']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
