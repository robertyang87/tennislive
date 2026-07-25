"""Look for a clay ball mark by browsing categories, not by guessing keywords.

Keyword searches for "ball mark" returned 1920s rulebooks, because whoever
uploaded such a photo probably described it as an umpire checking a call, or
in French, or not at all. So instead of guessing the words, list the
categories where such a frame would be filed and look at everything in them.

Downloads every plausible candidate for a human to eyeball; picks nothing.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
OUT = Path("tools/broll/ballmark")
FREE = ("cc by", "cc by-sa", "cc0", "public domain", "pd-")
MIN_W, MIN_H = 900, 600

CATEGORIES = [
    "Category:Tennis officials",
    "Category:Tennis umpires",
    "Category:Tennis chair umpires",
    "Category:Clay tennis courts",
    "Category:Tennis line judges",
    "Category:Tennis balls",
]
# Words that would appear if the frame shows a mark being read.
WANT = (
    "mark", "trace", "marque", "bounce", "impression", "impact",
    "check", "inspect", "arbitre", "vérifie", "umpire", "clay", "terre battue",
)
SEARCHES = [
    "umpire checks the mark clay court",
    "chair umpire inspects mark",
    "arbitre trace terre battue tennis",
    "tennis bounce mark clay",
    "empreinte balle terre battue",
]
OPENVERSE_QUERIES = [
    "clay court umpire mark",
    "tennis umpire checking mark",
    "terre battue arbitre trace",
]


def _get(url, **params):
    last = None
    for attempt in range(5):
        try:
            time.sleep(0.25)
            r = requests.get(url, params=params, timeout=30,
                             headers={"User-Agent": "tennislive/1.0 (github.com/robertyang87)"})
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.0 * (attempt + 1))
    print(f"    !! {last}")
    return {}


def _plain(raw) -> str:
    keep, buf = True, []
    for ch in str(raw):
        if ch == "<":
            keep = False
        elif ch == ">":
            keep = True
        elif keep:
            buf.append(ch)
    return " ".join("".join(buf).split())


def _members(title: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        data = _get(API, action="query", format="json", list="categorymembers",
                    cmtitle=title, cmtype=kind, cmlimit="max", **cont)
        out += [m["title"] for m in (data.get("query") or {}).get("categorymembers", [])]
        cont = data.get("continue") or {}
        if not cont:
            return out


def _describe(titles: list[str]) -> list[dict]:
    rows = []
    for i in range(0, len(titles), 20):
        data = _get(API, action="query", format="json",
                    titles="|".join(titles[i : i + 20]),
                    prop="imageinfo", iiprop="url|extmetadata|size")
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("url"):
                continue
            meta = info.get("extmetadata") or {}
            rows.append({
                "title": page.get("title", ""),
                "url": info["url"],
                "size": [info.get("width", 0), info.get("height", 0)],
                "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:220],
            })
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates, seen = [], set()

    print("########## CATEGORIES ##########")
    for cat in CATEGORIES:
        files = _members(cat, "file")
        subs = _members(cat, "subcat")
        print(f"\n=== {cat}: {len(files)} files, {len(subs)} subcats")
        for sc in subs[:15]:
            print(f"    sub: {sc}")
            files += _members(sc, "file")[:60]
        rows = _describe(list(dict.fromkeys(files))[:200])
        for r in rows:
            blob = f"{r['title']} {r['desc']}".lower()
            hit = [w for w in WANT if w in blob]
            if hit:
                print(f"  [{','.join(hit[:3])}] {r['size']} {r['licence']} | {r['title']}")
                if r["desc"]:
                    print(f"       {r['desc'][:110]}")
                if r["url"] not in seen:
                    seen.add(r["url"])
                    candidates.append(r)

    print("\n########## SEARCHES ##########")
    for q in SEARCHES:
        data = _get(API, action="query", format="json", list="search",
                    srsearch=q, srnamespace=6, srlimit=25)
        titles = [h["title"] for h in (data.get("query") or {}).get("search", [])]
        for r in _describe(titles):
            blob = f"{r['title']} {r['desc']}".lower()
            if "tennis" in blob or "terre" in blob or "clay" in blob:
                print(f"  {r['size']} {r['licence']} | {r['title']}")
                if r["url"] not in seen:
                    seen.add(r["url"])
                    candidates.append(r)

    print("\n########## OPENVERSE ##########")
    for q in OPENVERSE_QUERIES:
        data = _get(OPENVERSE, q=q, page_size=20)
        for r in data.get("results") or []:
            print(f"  {r.get('license')} | {str(r.get('title'))[:70]}")

    print("\n########## DOWNLOADING ##########")
    kept = 0
    for r in candidates:
        if kept >= 16:
            break
        if not any(f in (r["licence"] or "").lower() for f in FREE):
            continue
        if r["size"][0] < MIN_W or r["size"][1] < MIN_H:
            continue
        try:
            resp = requests.get(r["url"], timeout=40, headers={"User-Agent": "tennislive/1.0"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        img.save(OUT / f"{kept:02d}.jpg", quality=88)
        r["file"] = f"ballmark/{kept:02d}.jpg"
        print(f"  saved {kept:02d}.jpg {img.size} | {r['title']}")
        kept += 1
    print(f"kept {kept} of {len(candidates)} candidates")

    (OUT / "ballmark.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT / "ballmark.json")


if __name__ == "__main__":
    main()
