#!/usr/bin/env python3
"""封面实拍的**中文媒体**这一档：搜狗微信（公众号推文）＋ 赛事所在地的省级网站。

## 来路（2026-09-27 取证）

亚洲赛季（新加坡、比利·简·金杯、成都、杭州、拉沃尔杯）38 条「赛场之上」里 11 条
走过抽帧封面，后来换成照片的 6 条中 **3 条的照片来自中文媒体**，而
`find_cover_photo.py` 一条中文渠道都没有：

| slug | 换上的那张从哪儿来 | assets/reel/credits.json 里记的 |
|---|---|---|
| `hu-kopriva-chengdu-2026-r1` | **四川在线**（ent.scol.com.cn）首轮稿配图，「图据ATP250成都公开赛组委会」 | 1600×1067 |
| `zhang-wong-hangzhou-2026-r1` | 公众号「网球来啦」推文配图，经**搜狗微信**定位 | 1280×853 |
| `bu-majchrzak-hangzhou-2026-r2` | 公众号「网球之家」本场赛后稿配图（mmbiz `/0` 原图） | 1280×1829 |

`bu-majchrzak` 推了三次（12:51 / 13:13 / 13:37Z），13:23Z 才换封面（5beecfa6）——
**中文媒体那张图本来一条命令就能列出来**。而这几条的 `_frame_why` 里，有的会话
手动去搜狗微信翻过（wong-vallejo），有的一句没提（medvedev-royer）：
**没有工具的渠道，查不查全凭当天记不记得**。

## 两条路（都在沙箱里实测过，2026-09-27）

① **搜狗微信** `https://weixin.sogou.com/weixin?type=2&query=<中文名> <城市/对手>`
   → 每条结果：标题、公众号、发文时刻（`timeConvert('<epoch>')`）、`/link?url=…` 跳转
   → `/link` 回的是一段 JS，把 `https://mp.weixin.qq.com/s?…` **拆成十几段拼起来**
     （`url += '…'`），拼回去就是文章地址（**要带着搜索页那一趟的 cookie**，
     链接几分钟就过期，所以只在当场解析、不存）
   → 文章里 `data-src="https://mmbiz.qpic.cn/…/640?wx_fmt=jpeg"`：**把尾巴换成
     `/0?wx_fmt=jpeg` 就是原图**。实测一篇「体坛报」稿里有张 **6000×3376**
   ⚠️ 搜狗按词切分：「布云朝克特 八强」**0 条**，「布云朝克特 杭州」10 条——
     **零命中先换查询词**（CLAUDE.md「零命中先怀疑自己的查询词」），所以这里
     一次按「名字＋对手」「名字＋城市」「名字」三组问
   ⚠️ 会出同名的别人（「胡佳」查出一位心外科教授）——**按标题里有没有这个名字
     ＋ 发文时刻在不在比赛日窗口里**两道一起筛，筛掉几条要报出来
   ⚠️ 撞上反爬（跳到 `antispider`）要说「这一档没跑完」，**不是「没有」**

② **赛事所在地的省级网站**（`CN_OUTLETS`，按城市认）——目前只有成都一家有证据：
   四川在线体育频道 `https://ent.scol.com.cn/ty/`（`index_2.html` 起翻页），
   文章里 `https://imgcdn.scol.com.cn/media/<年>/<月>/<日>/<id>.jpg` 就是原图
   ⚠️ `imgcdn.scol.com.cn` 的 **https 在沙箱里握手就被重置，http 能取**
     （2026-09-27：`curl -r 0-2047 http://…` 206、`https://…` 000）——
     量尺寸时 https 失败自动退回 http，**别把「https 连不上」读成「图没了」**
   ⚠️ 杭州那一站的中文稿（「杭州市体育产业发展集团」这类主办方公众号）
     搜狗微信那条路已经能扫到，所以表里没为杭州另开一行

## 不做的

- **不替人认这是不是这一场**。bu-majchrzak 那次是拿 dHash 对首轮七篇稿子的图
  排除了资料图——那一步仍然要做（打开看 ＋ 对前几轮的稿子），这里只把候选和
  发文时刻列出来。发文时刻在比赛之前的图，**一定不是这一场**，工具会标出来
- **授权**：公众号配图多半没署名，照 CLAUDE.md「授权不做检索闸门」记
  `unknown`，发布前人工判断

    python3 tools/cover_cn_media.py --zh 布云朝克特 --zh 迈赫扎克 --city 杭州 --date 2026-09-26
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html as html_mod
import re
import sys
import urllib.parse

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}
SOGOU = "https://weixin.sogou.com"

#: 城市 → 当地省级网站的体育频道列表页。**只收有证据的**（hu-kopriva 那张出自
#: 四川在线）；别的城市先靠搜狗微信，真撞上一家当地站再补一行并写来路。
CN_OUTLETS: dict[str, tuple[str, ...]] = {
    "成都": ("https://ent.scol.com.cn/ty/", "https://ent.scol.com.cn/ty/index_2.html"),
}
#: 列表页所在站点的中文名——「这一趟查了什么」按它印，那份清单要照抄进 `_frame_why`，
#: 印一串裸 URL（「中文媒体·https://ent.scol.com.cn/ty/」）读的人还得自己翻译一遍
CN_OUTLET_NAMES: dict[str, str] = {"ent.scol.com.cn": "四川在线"}


def outlet_label(listing: str) -> str:
    """`https://ent.scol.com.cn/ty/index_2.html` → `当地网站（四川在线 ty/index_2.html）`。"""
    parts = urllib.parse.urlparse(listing)
    name = CN_OUTLET_NAMES.get(parts.netloc, parts.netloc)
    return f"当地网站（{name} {parts.path.lstrip('/') or '/'}）"


def _http_failed(resp) -> int | None:
    """回了一页但状态码 ≥ 400（502 Bad Gateway、403）——返回状态码；正常页返回 None。

    ⚠️ 不抛异常的失败：`requests` 拿到 502 照样回一个 Response，`.text` 是一页
    「Bad Gateway」，解析出 0 条——和「这一档真的没有」长得一模一样。
    """
    code = getattr(resp, "status_code", 200) or 200
    return code if code >= 400 else None

_SOGOU_ITEM = re.compile(r'<li id="sogou_vr_11002601_box_\d+".*?</li>', re.DOTALL)
_MMBIZ = re.compile(r'data-src="(https://mmbiz\.qpic\.cn/[^"]+)"')


#: 「赛场之上」封面的画布（和 `build_match_reel.COVER_FILL_W/H` 同一对数）。
COVER_W, COVER_H = 1080, 1440


def fill_note(wh) -> str:
    """一张图铺 1080×1440 要不要放大——候选列表里**每张都标**，别等选完才发现。

    zverev-deminaur 那张同场 Getty 在拉沃尔杯媒体库里只有 1200×727：对得上这一场，
    可铺封面要放大 1.98 倍，比 1080p 抽帧（1.33 倍）还软。**「找到了」和「能用」
    是两件事**，列候选时就得看得见。
    """
    try:
        w, h = (int(x) for x in (wh.split("x") if isinstance(wh, str) else wh))
    except Exception:                                           # noqa: BLE001
        return ""
    fill = min(w / COVER_W, h / COVER_H)
    if fill >= 1:
        return "铺满不放大"
    return f"要放大 {1 / fill:.2f}×（写 _low_res_why）"


def _clean(text: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def parse_sogou_results(page: str) -> list[dict]:
    """搜狗微信结果页 → `[{title, account, ts, link}]`（`ts` 是 UTC datetime 或 None）。"""
    out: list[dict] = []
    for item in _SOGOU_ITEM.findall(page or ""):
        head = re.search(r'<h3>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', item, re.DOTALL)
        if not head:
            continue
        acc = re.search(r'<span class="all-time-y2">(.*?)</span>', item, re.DOTALL)
        stamp = re.search(r"timeConvert\('(\d+)'\)", item)
        link = html_mod.unescape(head.group(1)).strip()
        out.append({
            "title": _clean(head.group(2)),
            "account": _clean(acc.group(1)) if acc else "",
            "ts": (_dt.datetime.fromtimestamp(int(stamp.group(1)), _dt.timezone.utc)
                   if stamp else None),
            "link": link if link.startswith("http") else SOGOU + link,
        })
    return out


def sogou_link_target(js: str) -> str | None:
    """`/link?url=…` 回的 JS 把目标地址拆成 `url += '…'` 十几段——拼回去。"""
    parts = re.findall(r"url \+= '([^']*)'", js or "")
    url = "".join(parts).replace("@", "")
    return url if url.startswith("https://mp.weixin.qq.com/") else None


def mmbiz_original(url: str) -> str:
    """`…/640?wx_fmt=jpeg&from=appmsg` → `…/0?wx_fmt=jpeg`（原图）。"""
    url = html_mod.unescape(url)
    fmt = re.search(r"wx_fmt=(\w+)", url)
    # 尾巴上那一段尺寸（`/640`、`/0`）去掉；实测也有不带尺寸段的 data-src
    base = re.sub(r"/\d+$", "", url.split("?", 1)[0])
    return f"{base}/0?wx_fmt={fmt.group(1) if fmt else 'jpeg'}"


def weixin_article(page: str) -> dict:
    """公众号文章页 → 标题、公众号、发文时刻、全部配图原图地址。"""
    title = re.search(r'<meta property="og:title" content="([^"]*)"', page or "")
    nick = re.search(r'var nickname = htmlDecode\("([^"]*)"\)', page or "") or \
        re.search(r'nickname = "([^"]*)"', page or "")
    ct = re.search(r'var ct = "(\d+)"', page or "")
    seen: list[str] = []
    for raw in _MMBIZ.findall(page or ""):
        if "wx_fmt=gif" in raw:
            continue                                            # 动图多半是分割线/二维码
        orig = mmbiz_original(raw)
        if orig not in seen:
            seen.append(orig)
    return {
        "title": html_mod.unescape(title.group(1)) if title else "",
        "account": html_mod.unescape(nick.group(1)) if nick else "",
        "ts": (_dt.datetime.fromtimestamp(int(ct.group(1)), _dt.timezone.utc)
               if ct else None),
        "images": seen,
    }


def parse_outlet_listing(page: str, base: str) -> list[tuple[str, str]]:
    """四川在线这类列表页 → `[(文章 URL, 标题)]`。"""
    host = urllib.parse.urlparse(base)
    out: list[tuple[str, str]] = []
    for href, body in re.findall(r'<a[^>]+href="([^"]*/\d{6}/\d+\.html)"[^>]*>(.*?)</a>',
                                 page or "", re.DOTALL):
        url = urllib.parse.urljoin(f"{host.scheme}://{host.netloc}/", href)
        title = re.sub(r"\s+", "", _clean(body))
        if title and (url, title) not in out:
            out.append((url, title))
    return out


def outlet_article_images(page: str) -> tuple[list[str], str | None]:
    """省级网站文章页 → 正文配图（`/media/<年>/<月>/<日>/` 下的 jpg/png）＋ 发文时刻文本。"""
    imgs = []
    for src in re.findall(r'<img[^>]+src="([^"]+)"', page or ""):
        if re.search(r"/media/\d{4}/\d{2}/\d{2}/[^/]+\.(?:jpe?g|png)$", src, re.IGNORECASE) \
                and src not in imgs:
            imgs.append(src)
    when = re.search(r"(20\d\d-\d\d-\d\d \d\d:\d\d)", page or "")
    return imgs, when.group(1) if when else None


def image_size(url: str, session: requests.Session | None = None) -> tuple[int, int] | None:
    """只下头 64 KB 读出尺寸（JPEG 的 SOF 在前面）。https 被重置时退回 http（scol 那条）。"""
    from PIL import ImageFile

    session = session or requests.Session()
    tries = [url]
    if url.startswith("https://imgcdn.scol.com.cn/"):
        tries.append("http://" + url[len("https://"):])
    for target in tries:
        # ⚠️ Referer 只给 mmbiz：scol 的图床见到 `mp.weixin.qq.com` 的 Referer 回 403
        # （防盗链），不带反而 206——带错一个头，「有图」就变成「尺寸未知」
        head = {**UA, "Range": "bytes=0-65535"}
        if "mmbiz.qpic.cn" in target:
            head["Referer"] = "https://mp.weixin.qq.com/"
        try:
            resp = session.get(target, headers=head, timeout=30, stream=True)
            if resp.status_code >= 400:
                resp.close()
                continue
            parser = ImageFile.Parser()
            got = 0
            for chunk in resp.iter_content(8192):
                parser.feed(chunk)
                got += len(chunk)
                if parser.image:
                    resp.close()
                    return parser.image.size
                if got >= 65536:
                    break
            resp.close()
        except Exception:                                       # noqa: BLE001
            continue
    return None


def _window(date: str | None, days: int) -> tuple[_dt.datetime, _dt.datetime] | None:
    if not date:
        return None
    start = _dt.datetime.fromisoformat(f"{date}T00:00:00+08:00") - _dt.timedelta(hours=12)
    return start, start + _dt.timedelta(hours=12) + _dt.timedelta(days=days)


def sweep_cn_media(names: list[str], *, date: str | None = None, days: int = 2,
                   city: str | None = None, max_articles: int = 6,
                   session: requests.Session | None = None, sizes: bool = True) -> dict:
    """两条中文渠道一起扫。返回 `{"rows": [...], "notes": [...], "ran": [...], "skipped": [...]}`。

    `ran` 只收**真拿回过一页结果**的那几档；取不到（抛异常**或状态码 ≥ 400**）、撞反爬、
    没登记的进 `skipped`——`find_cover_photo` 的「这一趟查了什么」按这两张单子印，
    而那份清单要照抄进 `_frame_why`，所以当地网站按 `outlet_label` 记名字，不记裸 URL。

    `names[0]` 是**要找谁的封面**（标题里必须有它）；其余是对手，只用来拼查询词。
    日期窗口按**北京时间**：比赛日前 12 小时起、往后 `days` 天（赛后稿常常次日才发）。
    """
    session = session or requests.Session()
    notes: list[str] = []
    ran: list[str] = []
    skipped: list[str] = []
    rows: list[dict] = []
    who = names[0] if names else ""
    if not who:
        return {"rows": rows, "notes": ["没给中文名（--zh），中文媒体这一档没跑"],
                "ran": ran, "skipped": ["搜狗微信", "当地网站"]}
    win = _window(date, days)

    # ① 搜狗微信
    queries = [" ".join(names[:2])] if len(names) > 1 else []
    queries += [f"{who} {city}"] if city else []
    queries += [who]
    found: dict[tuple[str, str], dict] = {}
    blocked = False
    # ⚠️ 「跑过」要按**真拿回一页结果**的查询数算，不是按「没撞上反爬」算：
    # 代理 403、断网时每一条查询都抛异常，`blocked` 一直是 False，原来照样记
    # 「跑过：中文媒体·搜狗微信」——而那份清单是要照抄进 `_frame_why` 的。
    answered = 0
    for query in queries:
        try:
            resp = session.get(f"{SOGOU}/weixin", params={"type": 2, "query": query},
                               headers=UA, timeout=30)
        except Exception as exc:                                # noqa: BLE001
            notes.append(f"搜狗微信「{query}」取不到（{exc}）")
            continue
        if "antispider" in resp.url:
            blocked = True
            notes.append(f"搜狗微信「{query}」撞上反爬（antispider）——**这一档没跑完，"
                         "不是没有**；隔几分钟再跑")
            break
        # ⚠️ 回了页不等于回了结果页：502/403 也是一个 Response，不抛异常，
        # 解析出 0 条，原来照样 `answered += 1`、记「跑过」
        code = _http_failed(resp)
        if code:
            notes.append(f"搜狗微信「{query}」取不到（HTTP {code}）")
            continue
        answered += 1
        hits = parse_sogou_results(resp.text)
        notes.append(f"搜狗微信「{query}」：{len(hits)} 条")
        for hit in hits:
            found.setdefault((hit["title"], hit["account"]), {**hit, "_ref": resp.url})
    if not blocked and answered:
        ran.append("搜狗微信")
    else:
        skipped.append("搜狗微信")
        if not blocked:
            notes.append(f"搜狗微信 {len(queries)} 条查询一条结果页都没取到——"
                         "**这一档没跑**，不是没有")
    kept, off_name, off_date = [], 0, 0
    for hit in found.values():
        if who not in hit["title"]:
            off_name += 1
            continue
        if win and hit["ts"] and not (win[0] <= hit["ts"] < win[1]):
            off_date += 1
            continue
        kept.append(hit)
    if found:
        notes.append(f"去重后 {len(found)} 条：标题里没有「{who}」的 {off_name} 条、"
                     f"发文时刻不在窗口里的 {off_date} 条筛掉，剩 {len(kept)} 条")
    # 标题里连对手都点了名的（多半就是这一场的赛后稿）排前面，其余按发文时刻新到旧
    others = [n for n in names[1:] if n]
    kept.sort(key=lambda h: (any(n in h["title"] for n in others),
                             h["ts"] or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc)),
              reverse=True)
    for hit in kept[:max_articles]:
        row = {"channel": "搜狗微信", "title": hit["title"], "account": hit["account"],
               "ts": hit["ts"], "article": None, "images": []}
        try:
            jump = session.get(hit["link"], headers={**UA, "Referer": hit["_ref"]},
                               timeout=30)
            if _http_failed(jump):
                raise RuntimeError(f"跳转页 HTTP {_http_failed(jump)}")
            target = sogou_link_target(jump.text)
            if target:
                page = session.get(target, headers=UA, timeout=40)
                if _http_failed(page):
                    raise RuntimeError(f"HTTP {_http_failed(page)}")
                art = weixin_article(page.text)
                row["article"] = target.split("&signature=")[0] + "…（带时效签名，未存）"
                row["images"] = [(u, image_size(u, session) if sizes else None)
                                 for u in art["images"][:12]]
            else:
                row["error"] = "跳转页里拼不出文章地址（搜狗改了 JS？）"
        except Exception as exc:                                # noqa: BLE001
            row["error"] = f"文章取不到：{exc}"
        rows.append(row)

    # ② 当地省级网站
    outlets = CN_OUTLETS.get(city or "", ())
    if city and not outlets:
        notes.append(f"「{city}」没有登记当地网站（CN_OUTLETS 只有 "
                     f"{'、'.join(CN_OUTLETS)}）——这一档没跑")
        skipped.append(f"当地网站（{city}没登记）")
    elif not city:
        skipped.append("当地网站（没给 --city）")
    seen_urls: set[str] = set()
    for listing in outlets:
        label = outlet_label(listing)
        try:
            resp = session.get(listing, headers=UA, timeout=30)
            code = _http_failed(resp)
            if code:
                raise RuntimeError(f"HTTP {code}")
            resp.encoding = resp.apparent_encoding
            arts = parse_outlet_listing(resp.text, listing)
        except Exception as exc:                                # noqa: BLE001
            notes.append(f"{listing} 取不到（{exc}）——这一页没跑")
            # 进「没跑」的是**能照抄进 `_frame_why` 的名字**，不是裸 URL
            skipped.append(label[:-1] + " 取不到）")
            continue
        mine = [(u, t) for u, t in arts if who in t and u not in seen_urls]
        seen_urls.update(u for u, _ in mine)
        notes.append(f"{listing}：{len(arts)} 篇，标题里有「{who}」的 {len(mine)} 篇")
        ran.append(label)
        for url, title in mine[:max_articles]:
            row = {"channel": urllib.parse.urlparse(listing).netloc, "title": title,
                   "account": "", "ts": None, "article": url, "images": []}
            try:
                page = session.get(url, headers=UA, timeout=30)
                if _http_failed(page):
                    raise RuntimeError(f"HTTP {_http_failed(page)}")
                page.encoding = page.apparent_encoding
                imgs, when = outlet_article_images(page.text)
                row["when"] = when
                row["images"] = [(u, image_size(u, session) if sizes else None)
                                 for u in imgs[:12]]
            except Exception as exc:                            # noqa: BLE001
                row["error"] = f"文章取不到：{exc}"
            rows.append(row)
    return {"rows": rows, "notes": notes, "ran": ran, "skipped": skipped}


def report(res: dict) -> list[str]:
    out = [f"  · {n}" for n in res["notes"]]
    for row in res["rows"]:
        when = row["ts"].astimezone(_dt.timezone(_dt.timedelta(hours=8))).strftime(
            "%m-%d %H:%M 北京") if row.get("ts") else (row.get("when") or "")
        out.append(f"  [{row['channel']}] {when}  {row['account']}  {row['title'][:48]}")
        if row.get("article"):
            out.append(f"     {row['article']}")
        if row.get("error"):
            out.append(f"     ⚠️ {row['error']}")
        for url, wh in row["images"]:
            size = f"{wh[0]}×{wh[1]}" if wh else "尺寸未知"
            out.append(f"     {size:>11}  {fill_note(wh) if wh else '':<22} {url}")
    if not res["rows"]:
        out.append("  没有对得上的。⚠️ 先换查询词（名字＋城市／名字＋对手），"
                   "再说「中文媒体没有」")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zh", action="append", required=True,
                    help="中文名，第一个是要找谁的封面，其余是对手（可重复）")
    ap.add_argument("--city", help="办赛城市（中文），如 杭州 / 成都")
    ap.add_argument("--date", help="比赛日（北京日期），如 2026-09-26")
    ap.add_argument("--days", type=int, default=2)
    args = ap.parse_args()
    res = sweep_cn_media(args.zh, date=args.date, days=args.days, city=args.city)
    print("\n".join(report(res)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
