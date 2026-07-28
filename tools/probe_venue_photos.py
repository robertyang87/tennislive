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

用法：
    python tools/probe_venue_photos.py wimbledon roland-garros
    python tools/probe_venue_photos.py --all
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


def _get(url: str, *, timeout: int = 35, tries: int = 4, referer: str | None = None) -> bytes | None:
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception:  # noqa: BLE001 - 每个渠道各自降级，不互相拖累
            time.sleep(2 * (attempt + 1))
    return None


def commons(query: str, limit: int = 8) -> list[str]:
    params = urllib.parse.urlencode({
        "format": "json", "action": "query", "list": "search",
        "srsearch": f"{query} filetype:bitmap", "srnamespace": "6", "srlimit": str(limit),
    })
    raw = _get(f"{COMMONS}?{params}")
    if raw is None:
        return []
    hits = json.loads(raw).get("query", {}).get("search", [])
    return [h["title"] for h in hits]


def openverse(query: str, limit: int = 8) -> list[str]:
    url = f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(query)}&page_size={limit}"
    raw = _get(url)
    if raw is None:
        return []
    return [f"{r.get('width')}x{r.get('height')} {r.get('title')}"
            for r in (json.loads(raw).get("results") or [])]


def ddg_images(query: str, limit: int = 10) -> list[str]:
    page = _get("https://duckduckgo.com/?q=" + urllib.parse.quote(query) + "&iax=images&ia=images")
    if page is None:
        return []
    token = re.search(rb"vqd=([\d-]+)", page)
    if not token:
        return []
    url = (f"https://duckduckgo.com/i.js?l=us-en&o=json&q={urllib.parse.quote(query)}"
           f"&vqd={token.group(1).decode()}&f=,,,&p=1")
    raw = _get(url, referer="https://duckduckgo.com/")
    if raw is None:
        return []
    out = []
    for r in (json.loads(raw).get("results") or [])[:limit]:
        out.append(f"{r.get('width')}x{r.get('height')} {str(r.get('title'))[:52]} {r.get('image')}")
    return out


def wordpress_media(site: str, query: str, limit: int = 20) -> list[str]:
    """官网多半是 WordPress——/en/photos 是 404 不代表没有图库。"""
    url = (f"{site.rstrip('/')}/wp-json/wp/v2/media?search={urllib.parse.quote(query)}"
           f"&per_page={limit}&_fields=source_url,media_details")
    raw = _get(url, tries=2)
    if raw is None:
        return []
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


CHANNELS = {
    "commons": lambda q, site: commons(q),
    "openverse": lambda q, site: openverse(q),
    "ddg": lambda q, site: ddg_images(q),
    "wp": lambda q, site: wordpress_media(site, q) if site else [],
}


def probe(slug: str) -> None:
    spec = VENUES[slug]
    print(f"\n{'=' * 68}\n### {slug}   官网 {spec['site'] or '（未知）'}")
    for name, fn in CHANNELS.items():
        canary = fn(CANARY, spec["site"])
        if not canary and name != "wp":
            print(f"  [{name}] 对照查询 `{CANARY}` 也是 0 —— 渠道本身有问题，这轮的 0 不作数")
            continue
        for query in spec["queries"]:
            hits = fn(query, spec["site"])
            print(f"  [{name}] 「{query}」 → {len(hits)}")
            for hit in hits[:6]:
                print(f"        {hit[:150]}")
            time.sleep(1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
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
