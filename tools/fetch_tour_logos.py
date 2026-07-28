# -*- coding: utf-8 -*-
"""抓取 ATP / WTA 官方 logo，规范化成可内联的 SVG，并记录出处。

卡片上的巡回赛标记原来是"WTA1000"这种文字药丸（实心底色）。改成官方 logo
之后底色也去掉了，所以 logo 必须能跟着文字颜色走——深绿底上要浅色，
html.light 下要深色。做法是把 SVG 里写死的品牌色换成 currentColor，再**内联**
进 HTML（<img> 里的 SVG 是独立文档，拿不到外面的 currentColor）。

两个 logo 在 Commons 上都标为 Public domain（PD-textlogo，未达独创性门槛），
同时标注 trademarked——体育联盟 logo 的常态。许可名、作者、来源 URL 全部
写进 assets/logo/tours/credits.json，发布前的权利判断交给人工检验环节。

用法：python tools/fetch_tour_logos.py
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "logo" / "tours"
UA = "tennislive-card-assets/1.0 (https://github.com/robertyang87/tennislive)"
API = "https://commons.wikimedia.org/w/api.php"

SOURCES = {
    # slug: Commons 文件名
    "atp": "File:ATP Tour logo.svg",
    "wta": "File:WTA 2025.svg",
}


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _imageinfo(titles: list[str]) -> dict:
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "imageinfo",
        "iiprop": "url|extmetadata", "titles": "|".join(titles),
    })
    data = json.loads(_get(f"{API}?{query}").decode("utf-8"))
    return data.get("query", {}).get("pages", {})


def _plain(value: str) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def normalize(svg: str) -> str:
    """去掉 XML 声明/注释/标题，把所有填充色换成 currentColor。

    两个源文件一个用 style="fill:#04014f"，一个用 <style> 里的 .st0 类，
    所以三种写法都要处理，不能只 replace 一个色值。
    """
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<title>.*?</title>", "", svg, flags=re.S)
    svg = re.sub(r"<defs>.*?</defs>", "", svg, flags=re.S)
    svg = re.sub(r'\sclass="[^"]*"', "", svg)
    svg = re.sub(r'\sstyle="[^"]*"', "", svg)
    svg = re.sub(r'\sfill="(?!none)[^"]*"', "", svg)
    svg = re.sub(r"\sid=\"[^\"]*\"", "", svg)
    # 统一由根节点给色，子节点继承
    svg = svg.replace("<svg ", '<svg fill="currentColor" ', 1)
    return " ".join(svg.split())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pages = _imageinfo(list(SOURCES.values()))
    by_title = {p["title"]: p for p in pages.values() if "imageinfo" in p}

    credits = {}
    for slug, title in SOURCES.items():
        page = by_title.get(title)
        if page is None:
            raise SystemExit(f"Commons 上找不到 {title}")
        info = page["imageinfo"][0]
        meta = info.get("extmetadata", {})
        raw = _get(info["url"]).decode("utf-8")
        svg = normalize(raw)
        if "currentColor" not in svg or "<path" not in svg:
            raise SystemExit(f"{title} 规范化后不含 path 或 currentColor，请检查")
        (OUT / f"{slug}.svg").write_text(svg, encoding="utf-8")
        credits[f"{slug}.svg"] = {
            "title": title,
            "license": _plain(meta.get("LicenseShortName", {}).get("value")),
            "artist": _plain(meta.get("Artist", {}).get("value")) or "unknown",
            "page": info.get("descriptionurl", ""),
            "restrictions": _plain(meta.get("Restrictions", {}).get("value")) or "none",
            "note": "品牌色已替换为 currentColor，用于深色卡面上的单色反白",
        }
        print(f"  {slug}.svg  {len(svg)} bytes  license={credits[f'{slug}.svg']['license']}")

    (OUT / "credits.json").write_text(
        json.dumps(credits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"完成 → {OUT}")


if __name__ == "__main__":
    main()
