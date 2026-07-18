"""下载"赛事一分钟"用的场馆图（Wikimedia Commons，逐条固定授权）.

前三个场馆为人工挑选的固定文件（探测日志核对过授权与画质）；
美网条目因检索限流未固定，运行时按许可白名单自动挑选并记录到
assets/venues/credits.json 供人工复核。CI 运行（见 assets.yml）。
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "assets" / "venues"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "tennislive-venue-fetch/1.0 (github.com/robertyang87/tennislive)"}
OK_LICENSES = ("CC0", "CC BY", "Public domain", "PD")

# (输出文件名, Commons 文件名或 None=检索, 检索词)
PINNED = [
    ("washington-fitzgerald-tennis-center.jpg", "File:FitzGerald Tennis Center.jpg", None),
    ("canada-national-bank-open-stadium.jpg", "File:RogersCup2011-2.jpg", None),
    ("cincinnati-lindner-tennis-center.jpg", "File:Lindner Family Tennis Center 2025.jpg", None),
    ("usopen-arthur-ashe-stadium.jpg", None, "Arthur Ashe Stadium"),
]


def api(params: dict) -> dict:
    params = {"format": "json", **params}
    r = requests.get(API, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def imageinfo(titles: list[str]) -> list[dict]:
    data = api({
        "action": "query", "prop": "imageinfo", "titles": "|".join(titles),
        "iiprop": "url|extmetadata|size", "iiurlwidth": 1920,
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
                "url": ii.get("thumburl") or ii.get("url"),
                "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote((p.get('title') or '').replace(' ', '_'))}",
            })
    return out


def pick_by_search(term: str) -> dict | None:
    data = api({
        "action": "query", "list": "search", "srsearch": term,
        "srnamespace": 6, "srlimit": 10,
    })
    titles = [h["title"] for h in data["query"]["search"] if h["title"].lower().endswith((".jpg", ".jpeg"))]
    time.sleep(1)
    for cand in imageinfo(titles[:8]):
        if (any(s in cand["license"] for s in OK_LICENSES)
                and cand["width"] >= 1600 and cand["width"] > cand["height"]):
            return cand
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    credits = {}
    failed = []
    for out_name, pinned_title, term in PINNED:
        dest = OUT / out_name
        try:
            if pinned_title:
                cand = next(iter(imageinfo([pinned_title])), None)
            else:
                cand = pick_by_search(term)
            if not cand or not cand.get("url"):
                raise RuntimeError("无可用候选")
            if not dest.exists():
                img = requests.get(cand["url"], headers=UA, timeout=60)
                img.raise_for_status()
                dest.write_bytes(img.content)
            credits[out_name] = {k: cand[k] for k in ("title", "license", "artist", "page")}
            print(f"OK {out_name} <- {cand['title']} [{cand['license']}] by {cand['artist']}")
        except Exception as e:  # noqa: BLE001
            failed.append(f"{out_name}: {e}")
            print(f"FAIL {out_name}: {e}")
        time.sleep(1.5)
    (OUT / "credits.json").write_text(
        json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
