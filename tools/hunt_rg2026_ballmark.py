"""Find two specific frames: Roland-Garros 2026, and a ball mark on clay.

Earlier passes searched a narrow slice and read the empty result as absence.
Widen it:

  * list every child of "French Open by year" with its real name and file
    count, so the 2026 edition is found whatever it is called (Commons uses
    both "French Open" and the hyphenated "Roland-Garros")
  * search the file namespace for the tournament and for ball marks, in
    English and French ("trace", "marque"), since a French photographer's
    upload will be described in French
  * ask the 2026 tournament's own Wikipedia articles what images they use
  * sweep Openverse for the same terms

Prints everything with licence and size, downloads what clears the bar, and
picks nothing on its own.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
OUT = Path("tools/broll")
FREE = ("cc by", "cc by-sa", "cc0", "public domain", "pd-")
MIN_W, MIN_H = 900, 600

FILE_SEARCHES = [
    # the tournament, both spellings
    "Roland-Garros 2026",
    "Roland Garros 2026",
    "French Open 2026",
    # the ball mark, both languages
    "tennis ball mark clay",
    "trace de balle terre battue",
    "marque balle terre battue",
    "tennis umpire ball mark",
    "clay court ball mark",
]
WIKI_PAGES = [("en", "2026 French Open"), ("fr", "Internationaux de France de tennis 2026")]
OPENVERSE_QUERIES = [
    "Roland Garros 2026",
    "tennis ball mark clay court",
    "terre battue trace balle",
]


def _get(url, **params):
    last = None
    for attempt in range(5):
        try:
            time.sleep(0.25)
            r = requests.get(url, params=params, timeout=30,
                             headers={"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"})
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.0 * (attempt + 1))
    print(f"    !! {url.split('/')[2]}: {last}")
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


def _describe(titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 20):
        data = _get(COMMONS, action="query", format="json",
                    titles="|".join(titles[i : i + 20]),
                    prop="imageinfo", iiprop="url|extmetadata|size")
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("url"):
                continue
            meta = info.get("extmetadata") or {}
            out.append({
                "title": page.get("title", ""),
                "url": info["url"],
                "size": [info.get("width", 0), info.get("height", 0)],
                "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                "artist": _plain((meta.get("Artist") or {}).get("value", ""))[:60],
                "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:200],
            })
    return out


def _members(title: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        data = _get(COMMONS, action="query", format="json", list="categorymembers",
                    cmtitle=title, cmtype=kind, cmlimit="max", **cont)
        out += [m["title"] for m in (data.get("query") or {}).get("categorymembers", [])]
        cont = data.get("continue") or {}
        if not cont:
            return out


def main() -> None:
    report: dict = {}
    pool: dict[str, list[dict]] = {"rg2026": [], "ballmark": []}

    print("########## 1. WHAT THE BY-YEAR CONTAINER ACTUALLY HOLDS ##########")
    editions = _members("Category:French Open by year", "subcat")
    print(f"{len(editions)} editions:")
    recent = [c for c in editions if any(y in c for y in ("2023", "2024", "2025", "2026"))]
    for c in editions:
        print(f"  {c}")
    report["editions"] = editions
    for cat in recent:
        files = _members(cat, "file")
        subs = _members(cat, "subcat")
        print(f"\n=== {cat}: {len(files)} files, {len(subs)} subcats")
        for sc in subs[:20]:
            print(f"    sub: {sc}")
        rows = _describe(files[:120])
        for r in rows:
            print(f"    {r['size']} {r['licence']} | {r['title']}")
            if "2026" in cat:
                pool["rg2026"].append(r)
        report[f"cat:{cat}"] = rows

    print("\n########## 2. FILE SEARCH (EN + FR) ##########")
    for term in FILE_SEARCHES:
        data = _get(COMMONS, action="query", format="json", list="search",
                    srsearch=term, srnamespace=6, srlimit=25)
        titles = [h["title"] for h in (data.get("query") or {}).get("search", [])]
        rows = _describe(titles)
        print(f"\n=== '{term}': {len(rows)}")
        for r in rows:
            print(f"  {r['size']} {r['licence']} | {r['title']}")
            if r["desc"]:
                print(f"     {r['desc'][:120]}")
            blob = f"{r['title']} {r['desc']}".lower()
            if any(k in blob for k in ("mark", "trace", "marque")) and "tennis" in blob:
                pool["ballmark"].append(r)
            if "2026" in blob and ("roland" in blob or "french open" in blob):
                pool["rg2026"].append(r)
        report[f"search:{term}"] = rows

    print("\n########## 3. THE 2026 TOURNAMENT'S OWN ARTICLES ##########")
    for lang, title in WIKI_PAGES:
        data = _get(f"https://{lang}.wikipedia.org/w/api.php", action="query",
                    format="json", prop="images", titles=title, imlimit="max")
        names = []
        for page in ((data.get("query") or {}).get("pages") or {}).values():
            for im in page.get("images") or []:
                n = im.get("title", "")
                if n.lower().endswith((".jpg", ".jpeg", ".png")):
                    names.append(n)
        print(f"\n=== {lang}:{title}: {len(names)}")
        for n in names:
            print(f"  {n}")
        if names:
            for r in _describe(names):
                pool["rg2026"].append(r)
        report[f"wiki:{lang}"] = names

    print("\n########## 4. OPENVERSE ##########")
    for q in OPENVERSE_QUERIES:
        data = _get(OPENVERSE, q=q, page_size=20)
        results = data.get("results") or []
        print(f"\n=== openverse '{q}': {len(results)}")
        for r in results:
            print(f"  {r.get('license')} {r.get('license_version')} | {str(r.get('title'))[:70]}")
        report[f"openverse:{q}"] = [
            {"title": r.get("title"), "url": r.get("url"),
             "licence": f"{r.get('license')} {r.get('license_version')}",
             "size": [r.get("width"), r.get("height")]}
            for r in results
        ]

    print("\n########## DOWNLOADING WHAT CLEARS THE BAR ##########")
    for slot, rows in pool.items():
        seen, kept = set(), 0
        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        for r in rows:
            if kept >= 12 or r["url"] in seen:
                continue
            seen.add(r["url"])
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
            img.save(slot_dir / f"{slot}_{kept:02d}.jpg", quality=88)
            print(f"  saved {slot}_{kept:02d}.jpg  {img.size}  {r['title']}")
            kept += 1
        print(f"[{slot}] kept {kept}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rg2026_ballmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote tools/broll/rg2026_ballmark.json")


if __name__ == "__main__":
    main()
