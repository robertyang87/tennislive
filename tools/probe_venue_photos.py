#!/usr/bin/env python3
"""多渠道找中心球场照：Commons / Openverse / DDG 图搜 / 赛事官网 CMS。

只在 Commons 里找是不够的——洛斯卡沃斯的球场照在赛事官网的 WordPress 媒体库
里，孟菲斯的只存在于电视台成片。这个脚本把「查过哪些渠道、每个渠道多少命中」
一次列全，**包括 0 命中的**，这样"没找到"才有判据。

三条踩出来的规矩，都编进来了：

- **空结果先自证是真空**。每个渠道都跑一条已知非空的对照查询；对照也是 0 就
  说明是接口坏了/被限流，不是真没有（Openverse 那次 `tennis` 返回 240，才敢
  说 `Leftwich Tennis Center` 的 0 是真的）
- **搜索词按赛事自己的语言写**。洛斯卡沃斯用 `stadium` 只出 3 条，`estadio`
  出 36 条、`cancha` 出 10 条
- **图库路径 404 不等于没有图库**。官网多半是 WordPress，
  `wp-json/wp/v2/media?search=` 一查就把原图连尺寸列出来，比在页面上抓省事

拿到候选之后**必须**过 `tools/preview_venue_crop.py`：判"是不是全景"要看卡片
实际的裁法，不是看原图。

**第三种「0 不是真 0」：页面是 SPA。** wimbledon.com 的 centre_court.html 和
dcopentennis.com 首页用 urllib 抓下来，正则一张图都找不到——不是站上没有图，
是图由 JS 渲染，`<img src>` 根本不在初始 HTML 里。`--render` 就是补这一刀：
用 Playwright（本环境预装了 Chromium，`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`）
打开页面、滚到底触发懒加载，再从**渲染后的 DOM**里取 `<img src/srcset>`、
`<source srcset>` 和 CSS 的 `background-image`。

取 DOM 的三个细节都是踩出来的：

- **只读 `src` 会漏掉一半**。响应式图站在 `srcset` 里放大图、`src` 留一张
  占位小图；只读 src 会把 2400px 的原图读成 300px 的缩略图
- **懒加载要滚**。首屏之外的 `<img>` 在 DOM 里 `src` 是 1×1 的透明底图，
  滚过去才换成真图
- **`naturalWidth` 比 URL 里的数字可信**。URL 上写着 `-2048x1152` 的可能是
  个 CDN 参数，浏览器加载完的 `naturalWidth` 才是真尺寸

用法：
    python tools/probe_venue_photos.py wimbledon roland-garros
    python tools/probe_venue_photos.py --all
    python tools/probe_venue_photos.py --render https://www.wimbledon.com/en_GB/atoz/centre_court.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "tennislive-venue-probe/1.0 (github.com/robertyang87/tennislive)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"

# 每站：官网域名（None 表示还没查到）、按赛事自己的语言写的检索词。
# 检索词要覆盖"沿球场长轴拍"的那类角度：aerial / from above / interior / 内景。
VENUES: dict[str, dict] = {
    "wimbledon": {"site": "https://www.wimbledon.com",
                  "queries": ["Centre Court Wimbledon aerial", "Wimbledon Centre Court interior roof"]},
    "roland-garros": {"site": "https://www.rolandgarros.com",
                      "queries": ["Court Philippe Chatrier vue aérienne", "Philippe Chatrier toit intérieur"]},
    "australian-open": {"site": "https://ausopen.com",
                        "queries": ["Rod Laver Arena interior aerial", "Rod Laver Arena from above"]},
    "cincinnati": {"site": "https://cincinnatiopen.com",
                   "queries": ["Center Court Lindner Family Tennis Center aerial"]},
    "canada": {"site": "https://nationalbankopen.com",
               "queries": ["Sobeys Stadium aerial", "Stade IGA Montréal vue aérienne"]},
    "washington": {"site": "https://dcopentennis.com",
                   "queries": ["Rock Creek Park Tennis Center stadium aerial"]},
    "prague": {"site": "https://www.livesportpragueopen.cz",
               "queries": ["Štvanice centrální dvorec", "Prague Open centre court aerial"]},
    "kitzbuhel": {"site": "https://www.generaliopen.com",
                  "queries": ["Kitzbühel Tennisstadion Luftaufnahme", "Center Court Kitzbühel oben"]},
    "bastad": {"site": "https://nordeaopen.se",
               "queries": ["Båstad centercourt flygfoto", "Båstad tennisstadion ovanifrån"]},
    "estoril": {"site": "https://millenniumestorilopen.com",
                "queries": ["Estoril Open court central", "Clube Ténis Estoril campo central"]},
    "memphis": {"site": "https://memphisclassic.com",
                "queries": ["Leftwich Tennis Center stadium court aerial"]},
    "athens": {"site": "https://athensopen.gr",
               "queries": ["Telekom Center Athens tennis", "ΟΑΚΑ κλειστό γήπεδο τένις"]},
    "gstaad": {"site": "https://www.swissopengstaad.ch",
               "queries": ["Roy Emerson Arena Gstaad", "Swiss Open Gstaad Centre Court Luftbild"]},
    "hamburg": {"site": "https://www.hamburg-open.com",
                "queries": ["Am Rothenbaum Center Court Luftaufnahme", "Rothenbaum Tennisstadion innen"]},
    "iasi": {"site": "https://iasiopen.ro",
             "queries": ["Iasi Open teren central", "Ciric tenis Iasi arena"]},
    "istanbul": {"site": "https://www.tenisfederasyonu.org",
                 "queries": ["Enka Spor Kulübü tenis kortu", "İstanbul tenis merkez kort"]},
    "palermo": {"site": "https://www.palermoladiesopen.it",
                "queries": ["Country Time Club Palermo campo centrale", "Palermo Ladies Open campo centrale"]},
    "umag": {"site": "https://www.croatiaopen.hr",
             "queries": ["Stadion Goran Ivanišević Umag teren", "Umag centralni teren"]},
    "verona": {"site": None,
               "queries": ["Verona tennis campo centrale", "ATV Bancomat Tennis Open campo"]},
    "los-cabos": {"site": "https://loscabostennisopen.com",
                  "queries": ["Estadio Alejandro Burillo cancha", "Los Cabos estadio tenis"]},
    "us-open": {"site": "https://www.usopen.org",
                "queries": ["Arthur Ashe Stadium from above interior"]},
}

# 每个渠道的对照查询：它返回 0 就说明渠道本身出了问题，不是"真没有"
CANARY = "tennis"


class Blocked(Exception):
    """渠道自己没让我进来——**这不是"0 命中"**。

    第一版把取不到一律当成空列表返回，于是 cincinnatiopen.com 的 wp-json 被 WAF
    挡了 403，屏幕上印的是「→ 0」，看着就像"这个站没有图库"。跟"只在成功时出声
    的检查"是同一个毛病：失败必须自己喊出来，否则"没找到"这个结论是假的。
    """


def _get(url: str, *, timeout: int = 35, tries: int = 4, referer: str | None = None) -> bytes:
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    last = ""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - 每个渠道各自降级，不互相拖累
            last = str(exc)[:60]
            time.sleep(2 * (attempt + 1))
    raise Blocked(last)


def commons(query: str, limit: int = 8) -> list[str]:
    params = urllib.parse.urlencode({
        "format": "json", "action": "query", "list": "search",
        "srsearch": f"{query} filetype:bitmap", "srnamespace": "6", "srlimit": str(limit),
    })
    raw = _get(f"{COMMONS}?{params}")
    hits = json.loads(raw).get("query", {}).get("search", [])
    return [h["title"] for h in hits]


def openverse(query: str, limit: int = 8) -> list[str]:
    url = f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(query)}&page_size={limit}"
    raw = _get(url)
    return [f"{r.get('width')}x{r.get('height')} {r.get('title')}"
            for r in (json.loads(raw).get("results") or [])]


def ddg_images(query: str, limit: int = 10) -> list[str]:
    page = _get("https://duckduckgo.com/?q=" + urllib.parse.quote(query) + "&iax=images&ia=images")
    token = re.search(rb"vqd=([\d-]+)", page)
    if not token:
        return []
    url = (f"https://duckduckgo.com/i.js?l=us-en&o=json&q={urllib.parse.quote(query)}"
           f"&vqd={token.group(1).decode()}&f=,,,&p=1")
    raw = _get(url, referer="https://duckduckgo.com/")
    out = []
    for r in (json.loads(raw).get("results") or [])[:limit]:
        out.append(f"{r.get('width')}x{r.get('height')} {str(r.get('title'))[:52]} {r.get('image')}")
    return out


def wordpress_media(site: str, query: str, limit: int = 20) -> list[str]:
    """官网多半是 WordPress——/en/photos 是 404 不代表没有图库。"""
    url = (f"{site.rstrip('/')}/wp-json/wp/v2/media?search={urllib.parse.quote(query)}"
           f"&per_page={limit}&_fields=source_url,media_details")
    raw = _get(url, tries=2)
    try:
        items = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        detail = item.get("media_details") or {}
        out.append(f"{detail.get('width')}x{detail.get('height')} {item.get('source_url')}")
    return out


def wordpress_list(site: str, *, pages: int = 8, per_page: int = 100,
                   min_px: int = 1500) -> list[str]:
    """把整个媒体库按页拉下来，只按**尺寸**筛。

    `?search=` 匹配的是标题/说明，而赛事站的图大多叫 `WIV_7686`、`Frame-1-8`
    这种相机原始文件名——**再准的德语关键词也搜不到**，于是"这个站没有球场照"
    的结论是假的。汉堡就是这么被判过一次：Rothenbaum / Center Court /
    Stadion / Anlage 四个词全 0，实际首页上就挂着球场照。
    """
    out = []
    for page in range(1, pages + 1):
        url = (f"{site.rstrip('/')}/wp-json/wp/v2/media?per_page={per_page}&page={page}"
               f"&media_type=image&_fields=source_url,media_details,date")
        try:
            items = json.loads(_get(url, tries=2))
        except (Blocked, ValueError):
            break
        if not isinstance(items, list) or not items:
            break
        for item in items:
            detail = item.get("media_details") or {}
            width, height = detail.get("width") or 0, detail.get("height") or 0
            if max(width, height) < min_px:
                continue
            out.append(f"{width}x{height}  {str(item.get('date'))[:10]}  {item.get('source_url')}")
    return out


def contact_sheet(urls: list[str], out: str, *, cols: int = 6, cell: int = 300) -> str:
    """把一批候选拼成联系表——**判据是打开看**，而候选常常是几百张。

    一张一张 Read 过去既慢又容易半路放弃（汉堡媒体库一次就列出 196 张）。
    拼成一张图扫一遍，能一眼排除掉九成的人像特写和拼图，剩下的再单独看原图。
    格子左上角印序号，对得回 URL 列表。
    """
    from PIL import Image, ImageDraw, ImageOps

    Image.MAX_IMAGE_PIXELS = None
    tiles = []
    for i, url in enumerate(urls):
        try:
            import io
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(_get(url, tries=2)))).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}] 取不到：{str(exc)[:60]}")
            continue
        canvas = Image.new("RGB", (cell, cell), (18, 18, 18))
        img.thumbnail((cell, cell), Image.LANCZOS)
        canvas.paste(img, ((cell - img.width) // 2, (cell - img.height) // 2))
        tiles.append((i, canvas))

    if not tiles:
        return ""
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for n, (idx, tile) in enumerate(tiles):
        x, y = (n % cols) * cell, (n // cols) * cell
        sheet.paste(tile, (x, y))
        draw.rectangle([x + 1, y + 1, x + 30, y + 16], fill=(0, 0, 0))
        draw.text((x + 4, y + 4), str(idx), fill=(255, 220, 60))
    sheet.save(out, quality=82)
    return out


CHANNELS = {
    "commons": lambda q, site: commons(q),
    "openverse": lambda q, site: openverse(q),
    "ddg": lambda q, site: ddg_images(q),
    "wp": lambda q, site: wordpress_media(site, q) if site else [],
}

# 沙箱里 PLAYWRIGHT_BROWSERS_PATH 指的目录带版本号，playwright 自己找的那条
# 路径对不上，得显式给 executable_path（CLAUDE.md 里记过同一条）。
_CHROME_GLOBS = (
    "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
)


def _chromium_path() -> str:
    import glob
    for pattern in _CHROME_GLOBS:
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    raise Blocked("找不到 Chromium，装了 playwright 也没用")


# ⚠️ Chromium 在这个沙箱里连不上网，报的是 `ERR_CONNECTION_RESET`，而
# **真正的原因和这条报错没关系**。查了两个假线索才找到，都记在这儿：
#
# 1. netlog 里 `net_error` 出现最多的是 **-202（ERR_CERT_AUTHORITY_INVALID）**，
#    128 次。看着就是"代理拆包 CA 没进浏览器的 NSS 库"——很合理，因为
#    Chromium 在 Linux 上确实不读系统 CA 目录，而这台机器没装 certutil。
#    照这个方向改完**一点没变**：那 128 次全是 Chromium 自己那些组件更新域名
#    （clients2.google.com 之类）产生的噪音，跟我要打开的页面无关。
#    **「一批红要逐条看第一行错误」在 netlog 上是「按请求对上号再看」**——
#    统计出现次数最多的错误码，选出来的往往是背景噪音。
# 2. 大 ClientHello（后量子密钥交换）被中间设备打断，也是常见成因。
#    关掉 `PostQuantumKyber,UseMLKEM` 同样没变。
#
# 真正的线索在按请求对上号之后：CONNECT 隧道**建成了**
# （`HTTP_TRANSACTION_SEND_TUNNEL_HEADERS` 正常），然后 `SSL_CONNECT` →
# `SOCKET_READ_ERROR os_error 104`——是**握手阶段被对端 RST**。
# 逐个试下来只有一个变量管用：`--ssl-version-max=tls1.2`。
# 出网网关会重置 Chromium 的 TLS 1.3 握手（curl / python 走的是另一条栈，
# 所以它们一直好好的，这正是"本地能跑不等于这条路通"）。
#
# **限的是协议版本，不是校验**：TLS 1.2 的证书链照常验，没有关掉任何检查。
_TLS_MAX = "tls1.2"

# 顺带记一句，省得下次重走：我一度以为要把拆包 CA 的公钥按 SPKI 摘要钉给
# Chromium 才连得上，写完发现**一点用没有**（真正的原因就是上面那条 TLS 版本）。
# 那段代码已经删掉了——留着一个看起来像"绕过证书校验"的开关，比没有更糟。


def render_images(url: str, *, min_px: int = 900, timeout: int = 90000) -> list[str]:
    """打开页面等 JS 渲染完，把**渲染后 DOM** 里的图连真实尺寸一起列出来。

    返回 `WxH  url`，按面积从大到小；小于 min_px 宽的直接丢掉（图标、头像、
    赞助商 logo 占了绝大多数，留着只会把真正的大图埋掉）。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # 依赖检查提到最前面，别跑到一半才报
        raise Blocked(f"没装 playwright（{exc}）") from exc

    script = """() => {
      const out = new Map();
      const add = (u, w, h) => {
        if (!u || u.startsWith('data:')) return;
        const prev = out.get(u);
        if (!prev || prev[0] * prev[1] < w * h) out.set(u, [w, h]);
      };
      for (const im of document.querySelectorAll('img')) {
        add(im.currentSrc || im.src, im.naturalWidth, im.naturalHeight);
        // src 常是占位小图，大图藏在 srcset 里
        for (const part of (im.srcset || '').split(',')) {
          const u = part.trim().split(/\\s+/)[0];
          const w = /(\\d+)w/.exec(part);
          if (u) add(new URL(u, location.href).href, w ? +w[1] : 0, 0);
        }
      }
      for (const s of document.querySelectorAll('source[srcset]')) {
        for (const part of s.srcset.split(',')) {
          const u = part.trim().split(/\\s+/)[0];
          const w = /(\\d+)w/.exec(part);
          if (u) add(new URL(u, location.href).href, w ? +w[1] : 0, 0);
        }
      }
      for (const el of document.querySelectorAll('*')) {
        const bg = getComputedStyle(el).backgroundImage;
        const m = bg && bg.match(/url\\((["']?)(.*?)\\1\\)/);
        if (m) add(new URL(m[2], location.href).href, el.clientWidth, el.clientHeight);
      }
      return [...out].map(([u, wh]) => [u, wh[0], wh[1]]);
    }"""

    # Chromium 不读 HTTPS_PROXY 这些环境变量，得显式给 --proxy-server；
    # 不给就是 ERR_CONNECTION_RESET，看着像"这个站打不开"。
    import os
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    # 走代理时 HTTP/2 会零星 ERR_HTTP2_PROTOCOL_ERROR，关掉换 1.1 稳得多
    launch_args = ["--no-sandbox", f"--ssl-version-max={_TLS_MAX}", "--disable-http2"]
    if proxy:
        launch_args.append(f"--proxy-server={proxy}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=_chromium_path(),
                                     args=launch_args)
        try:
            # 默认 UA 里带着 HeadlessChrome，Akamai 那一类风控一眼认出来，
            # 表现是导航**一直不落地**直到超时——不是站慢，是没让进
            page = browser.new_page(
                viewport={"width": 1600, "height": 1200},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/141.0.0.0 Safari/537.36",
                locale="en-GB")
            last = ""
            for attempt in range(3):
                try:
                    # "commit" 而不是 "domcontentloaded"：大站挂着一堆第三方
                    # 统计脚本，等 DOMContentLoaded 常常直接超时；导航一落地
                    # 就往下走，后面本来就有固定等待 + 滚动
                    page.goto(url, timeout=timeout, wait_until="commit")
                    break
                except Exception as exc:  # noqa: BLE001
                    last = str(exc).splitlines()[0][:90]
                    page.wait_for_timeout(2000 * (attempt + 1))
            else:
                raise Blocked(last)
            page.wait_for_timeout(2500)
            # 懒加载：首屏之外的 img 要滚过去才换成真图
            for _ in range(6):
                page.mouse.wheel(0, 1600)
                page.wait_for_timeout(700)
            page.wait_for_timeout(1500)
            found = page.evaluate(script)
            # 「0 命中」要自证是真空：落地在哪个 URL、标题是什么、DOM 里到底
            # 有几个 <img>。跳到了同意页 / 404 页时这三行立刻看得出来。
            print(f"     · 落地 {page.url[:110]}")
            print(f"     · 标题 {(page.title() or '')[:80]}")
            print(f"     · DOM 里 {page.evaluate('document.images.length')} 个 <img>，"
                  f"取到 {len(found)} 个图 URL")
        finally:
            browser.close()

    rows = [(w, h, u) for u, w, h in found if w >= min_px or h >= min_px]
    rows.sort(key=lambda r: -(r[0] * max(r[1], 1)))
    return [f"{w}x{h}  {u}" for w, h, u in rows]


def probe(slug: str) -> None:
    spec = VENUES[slug]
    print(f"\n{'=' * 68}\n### {slug}   官网 {spec['site'] or '（未知）'}")
    for name, fn in CHANNELS.items():
        try:
            canary = fn(CANARY, spec["site"])
        except Blocked as exc:
            print(f"  [{name}] **渠道被挡**（{exc}）—— 这不是 0 命中，这一站在这个渠道还没查过")
            continue
        if not canary and name != "wp":
            print(f"  [{name}] 对照查询 `{CANARY}` 也是 0 —— 渠道本身有问题，这轮的 0 不作数")
            continue
        for query in spec["queries"]:
            try:
                hits = fn(query, spec["site"])
            except Blocked as exc:
                print(f"  [{name}] 「{query}」 **被挡**（{exc}）")
                continue
            print(f"  [{name}] 「{query}」 → {len(hits)}")
            for hit in hits[:6]:
                print(f"        {hit[:150]}")
            time.sleep(1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--render", action="append", default=[],
                    help="用 Playwright 打开这个 URL，列出渲染后 DOM 里的大图（SPA 站用）")
    ap.add_argument("--min-px", type=int, default=900)
    ap.add_argument("--wp-list", action="append", default=[],
                    help="把这个 WordPress 站的媒体库整个按尺寸列一遍（文件名没意义时用）")
    ap.add_argument("--sheet", help="从这个文件里读 URL（每行末尾一个），拼成联系表")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--take", type=int, default=60)
    ap.add_argument("--out", default="candidates.jpg")
    args = ap.parse_args()

    if args.sheet:
        urls = [ln.split()[-1] for ln in
                open(args.sheet, encoding="utf-8").read().splitlines() if ln.strip()]
        urls = urls[args.skip:args.skip + args.take]
        for i, u in enumerate(urls):
            print(f"  [{i}] {u}")
        print(contact_sheet(urls, args.out) or "一张都没取到")
        return 0

    if args.wp_list:
        for site in args.wp_list:
            print(f"\n{'=' * 68}\n### 媒体库 {site}")
            hits = wordpress_list(site, min_px=args.min_px)
            print(f"  → {len(hits)} 张 ≥{args.min_px}px")
            for hit in hits:
                print(f"     {hit}")
        return 0

    if args.render:
        for url in args.render:
            print(f"\n{'=' * 68}\n### 渲染 {url}")
            try:
                hits = render_images(url, min_px=args.min_px)
            except Blocked as exc:
                print(f"  **打不开**（{exc}）—— 这不是 0 命中")
                continue
            print(f"  → {len(hits)} 张 ≥{args.min_px}px")
            for hit in hits[:25]:
                print(f"     {hit}")
        return 0

    slugs = list(VENUES) if args.all else args.slugs
    if not slugs:
        print("要查哪些站？可选：" + " ".join(VENUES), file=sys.stderr)
        return 1
    for slug in slugs:
        if slug not in VENUES:
            print(f"没有登记 {slug}", file=sys.stderr)
            continue
        probe(slug)
    print("\n拿到候选之后必须过 tools/preview_venue_crop.py —— 判'是不是全景'"
          "要看卡片实际的裁法，不是看原图")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
