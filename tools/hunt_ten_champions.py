"""Find the frames the "ten women's champions, five men's" explainer needs.

The argument is a list, so the deck only needs faces: the newest champion
(Nosková, 2026), one of the women she extended the streak past, and one of
the five men who kept sharing the men's title. Plus the court itself for the
closing beat.

Category-walk first, search second. Searching by name returns whatever the
index feels like; a player's own Commons category is curated and its files
carry the year in their titles, which is what decides whether a frame is
current enough to use.

Prints licence, size and the source's own description, and downloads what
clears the bar. Picks nothing — a human still looks at every frame.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image, ImageOps

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll/tenfive")
UA = {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive; robertyang.ustb@gmail.com)"}
FREE = ("cc by", "cc0", "public domain", "pd-")
MIN_W, MIN_H = 900, 700

SLOTS: dict[str, dict] = {
    # the 2026 champion — the peg the whole deck hangs on
    "noskova": {
        "searches": ["Linda Noskova", "Noskova tennis 2025", "Noskova Wimbledon"],
        "categories": ["Category:Linda Nosková"],
    },
    # one of the other nine, to show the streak is not a one-off
    "women": {
        "searches": [
            "Iga Swiatek Wimbledon 2025",
            "Barbora Krejcikova Wimbledon 2024",
            "Elena Rybakina Wimbledon",
            "Karolina Muchova 2026",
        ],
        "categories": [
            "Category:Iga Świątek",
            "Category:Markéta Vondroušová",
            "Category:Elena Rybakina",
            "Category:Karolína Muchová",
        ],
    },
    # the men's side: whoever is currently sharing the five
    "men": {
        "searches": [
            "Jannik Sinner Wimbledon",
            "Carlos Alcaraz Wimbledon trophy",
            "Novak Djokovic Wimbledon Centre Court",
        ],
        "categories": [
            "Category:Jannik Sinner",
            "Category:Carlos Alcaraz",
        ],
    },
    # the place, for the closing beat
    "court": {
        "searches": [
            "Wimbledon Centre Court crowd",
            "Wimbledon Centre Court 2024",
            "Wimbledon ladies singles trophy",
            "Venus Rosewater Dish",
        ],
        "categories": ["Category:Centre Court"],
    },
}


def _get(**params) -> dict:
    last = None
    for attempt in range(6):
        try:
            time.sleep(0.35)
            r = requests.get(API, params=params, timeout=40, headers=UA)
            if r.status_code == 429:
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
        data = _get(action="query", format="json", maxlag=5,
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
                "author": _plain((meta.get("Artist") or {}).get("value", ""))[:70],
                "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", ""))[:12],
                "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:200],
            })
    return rows


def _members(title: str, kind: str, cap: int = 300) -> list[str]:
    out: list[str] = []
    cont: dict = {}
    while len(out) < cap:
        data = _get(action="query", format="json", maxlag=5, list="categorymembers",
                    cmtitle=title, cmtype=kind, cmlimit="max", **cont)
        got = (data.get("query") or {}).get("categorymembers", [])
        out += [m["title"] for m in got]
        cont = data.get("continue") or {}
        if not cont or not got:
            break
    return out[:cap]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}

    for slot, spec in SLOTS.items():
        print("\n" + "#" * 72)
        print(f"########## {slot.upper()}")
        pool: dict[str, dict] = {}

        for cat in spec["categories"]:
            files = _members(cat, "file", cap=200)
            subs = _members(cat, "subcat", cap=30)
            # An empty category is a real answer only when the category
            # exists — print which it was so a typo cannot read as absence.
            print(f"\n=== {cat}: {len(files)} files, {len(subs)} subcats")
            for sc in subs[:14]:
                print(f"    sub: {sc}")
                files += _members(sc, "file", cap=80)
            for r in _describe(list(dict.fromkeys(files))[:220]):
                print(f"  {r['size']} {r['licence'][:15]:15} {r['date']:12} | {r['title'][:62]}")
                if r["desc"]:
                    print(f"       {r['desc'][:110]}")
                pool.setdefault(r["url"], r)

        for term in spec["searches"]:
            data = _get(action="query", format="json", maxlag=5, list="search",
                        srsearch=term, srnamespace=6, srlimit=25)
            titles = [h["title"] for h in (data.get("query") or {}).get("search", [])]
            rows = _describe(titles)
            print(f"\n=== search '{term}': {len(rows)}")
            for r in rows:
                blob = f"{r['title']} {r['desc']}".lower()
                if ".pdf" in blob or not any(
                    k in blob for k in ("tennis", "wimbledon", "noskov", "swiatek",
                                        "świątek", "sinner", "alcaraz", "djokovic",
                                        "rybakina", "muchov", "krejcik", "court")):
                    continue
                print(f"  {r['size']} {r['licence'][:15]:15} {r['date']:12} | {r['title'][:62]}")
                if r["desc"]:
                    print(f"       {r['desc'][:110]}")
                pool.setdefault(r["url"], r)

        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        kept, dropped = 0, {"licence": 0, "small": 0, "failed": 0}
        for r in sorted(pool.values(), key=lambda x: -(x["date"] or "")[:4].count("2") or 0):
            if kept >= 16:
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
                img = ImageOps.exif_transpose(Image.open(io.BytesIO(resp.content))).convert("RGB")
            except Exception:  # noqa: BLE001
                dropped["failed"] += 1
                continue
            img.thumbnail((1600, 1600))
            img.save(slot_dir / f"{kept:02d}.jpg", quality=88)
            r["file"] = f"{slot}/{kept:02d}.jpg"
            print(f"  saved {kept:02d}.jpg {img.size} {r['date']:12} | {r['title'][:56]}")
            kept += 1
        print(f"\n[{slot}] pool {len(pool)}, kept {kept}, dropped {dropped}")
        report[slot] = {"pool": len(pool), "kept": kept, "dropped": dropped,
                        "rows": list(pool.values())}

    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "report.json")


if __name__ == "__main__":
    main()
