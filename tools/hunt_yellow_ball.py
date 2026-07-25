"""Find the photos the yellow-ball explainer needs, one slot at a time.

Five beats, five very different pictures:

  white      a white tennis ball — the century before the switch
  tv         colour broadcast of tennis, or a period colour set
  switch     optic yellow balls, close enough to read the colour
  wimbledon  Wimbledon, which held out for white until 1986
  eye        yellow against grass/clay, i.e. why this colour wins

Each slot gets its own searches and categories, in English, French and
German, because a photo of a white ball is as likely to be described as
"Tennisball" or "balle de tennis" as anything else. Everything that clears
the licence and size bar is downloaded so a human can look at it; this
script picks nothing.

Prints why candidates were dropped, so an empty slot can prove it is empty
rather than merely looking that way.
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
OUT = Path("tools/broll/yellowball")
UA = {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive; robertyang.ustb@gmail.com)"}
FREE = ("cc by", "cc by-sa", "cc0", "public domain", "pd-", "no restrictions")
MIN_W, MIN_H = 800, 600
PER_SLOT = 14

SLOTS: dict[str, dict] = {
    "white": {
        "searches": [
            "white tennis ball",
            "vintage tennis ball",
            "antique tennis ball",
            "tennis ball 1960s",
            "balle de tennis blanche",
            "weisser Tennisball",
        ],
        "categories": [
            "Category:Tennis balls",
            "Category:History of tennis",
            "Category:Tennis in the 1960s",
            "Category:Tennis in the 1950s",
        ],
        "want": ("white", "blanche", "weiss", "vintage", "antique", "old", "historic"),
    },
    "tv": {
        "searches": [
            "tennis television broadcast",
            "colour television set 1970s",
            "television camera tennis",
            "BBC colour television",
        ],
        "categories": [
            "Category:Television cameras",
            "Category:Colour television",
            "Category:Sports broadcasting",
        ],
        "want": ("television", "broadcast", "camera", "colour", "color", "tv"),
    },
    "switch": {
        "searches": [
            "optic yellow tennis ball",
            "tennis balls close up",
            "new tennis balls",
            "balles de tennis jaunes",
        ],
        "categories": ["Category:Tennis balls"],
        "want": ("yellow", "jaune", "gelb", "ball"),
    },
    "wimbledon": {
        "searches": [
            "Wimbledon Championships 1986",
            "Wimbledon centre court grass",
            "Wimbledon Championships 1980s",
        ],
        "categories": [
            "Category:Wimbledon Championships by year",
            "Category:Centre Court",
            "Category:All England Lawn Tennis and Croquet Club",
        ],
        "want": ("wimbledon", "centre court", "all england", "grass"),
    },
    "eye": {
        "searches": [
            "tennis ball on clay court",
            "tennis ball on grass court",
            "tennis ball in flight",
            "tennis ball bouncing",
        ],
        "categories": ["Category:Tennis balls", "Category:Clay tennis courts"],
        "want": ("ball", "clay", "grass", "court"),
    },
}


def _get(url: str, **params) -> dict:
    last = None
    for attempt in range(6):
        try:
            time.sleep(0.35)
            r = requests.get(url, params=params, timeout=40, headers=UA)
            if r.status_code == 429:
                print(f"    429, backing off {3 * (attempt + 1)}s")
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"    !! gave up: {last}")
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
    rows = []
    for i in range(0, len(titles), 20):
        data = _get(API, action="query", format="json", maxlag=5,
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
                "artist": _plain((meta.get("Artist") or {}).get("value", ""))[:70],
                "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", ""))[:40],
                "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:240],
            })
    return rows


def _members(title: str, kind: str, cap: int = 400) -> list[str]:
    out: list[str] = []
    cont: dict = {}
    while len(out) < cap:
        data = _get(API, action="query", format="json", maxlag=5,
                    list="categorymembers", cmtitle=title, cmtype=kind,
                    cmlimit="max", **cont)
        members = (data.get("query") or {}).get("categorymembers", [])
        out += [m["title"] for m in members]
        cont = data.get("continue") or {}
        if not cont or not members:
            break
    return out[:cap]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}

    for slot, spec in SLOTS.items():
        print("\n" + "#" * 72)
        print(f"########## {slot.upper()}")
        print("#" * 72)
        pool: dict[str, dict] = {}

        for term in spec["searches"]:
            data = _get(API, action="query", format="json", maxlag=5,
                        list="search", srsearch=term, srnamespace=6, srlimit=25)
            titles = [h["title"] for h in (data.get("query") or {}).get("search", [])]
            rows = _describe(titles)
            print(f"\n=== search '{term}': {len(rows)} files")
            for r in rows:
                print(f"  {r['size']} {r['licence'][:18]:18} | {r['title'][:72]}")
                pool.setdefault(r["url"], r)

        for cat in spec["categories"]:
            files = _members(cat, "file", cap=160)
            subs = _members(cat, "subcat", cap=40)
            print(f"\n=== {cat}: {len(files)} files, {len(subs)} subcats")
            for sc in subs[:12]:
                print(f"    sub: {sc}")
                files += _members(sc, "file", cap=60)
            rows = _describe(list(dict.fromkeys(files))[:220])
            for r in rows:
                blob = f"{r['title']} {r['desc']}".lower()
                if any(w in blob for w in spec["want"]):
                    print(f"  * {r['size']} {r['licence'][:18]:18} | {r['title'][:70]}")
                    pool.setdefault(r["url"], r)

        print(f"\n--- {slot}: {len(pool)} unique candidates, downloading ---")
        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        kept, dropped = 0, {"licence": 0, "small": 0, "failed": 0}
        saved = []
        for r in pool.values():
            if kept >= PER_SLOT:
                break
            if not any(f in (r["licence"] or "").lower() for f in FREE):
                dropped["licence"] += 1
                continue
            if r["size"][0] < MIN_W or r["size"][1] < MIN_H:
                dropped["small"] += 1
                continue
            try:
                resp = requests.get(r["url"], timeout=60, headers=UA)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception as exc:  # noqa: BLE001
                print(f"    download failed ({exc}): {r['title'][:60]}")
                dropped["failed"] += 1
                continue
            name = f"{kept:02d}.jpg"
            img.thumbnail((1600, 1600))
            img.save(slot_dir / name, quality=88)
            r["file"] = f"{slot}/{name}"
            saved.append(r)
            print(f"  saved {name} {img.size} | {r['title'][:64]}")
            kept += 1
        print(f"  kept {kept}; dropped {dropped}")
        report[slot] = {"saved": saved, "dropped": dropped, "pool": len(pool)}

    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "report.json")


if __name__ == "__main__":
    main()
