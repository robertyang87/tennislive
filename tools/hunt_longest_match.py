"""Find the frames the Isner-Mahut explainer needs.

The one that matters is the Court 18 scoreboard reading 70-68 — the image
the whole match is remembered by. If it is not freely licensed, the beat has
to be carried another way, so this asks the question directly instead of
assuming either answer.

Also looks for the commemorative plaque installed beside Court 18, the two
players, and Court 18 itself, in English and French (Mahut is French, so a
French photographer's upload will be described in French).

Prints everything with licence, size and the source's own description, and
downloads what clears the bar. Picks nothing.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll/longest")
UA = {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive; robertyang.ustb@gmail.com)"}
FREE = ("cc by", "cc0", "public domain", "pd-")
MIN_W, MIN_H = 900, 700

SLOTS: dict[str, dict] = {
    # the scoreboard, the image the match is remembered by
    "board": {
        "searches": [
            "Isner Mahut scoreboard",
            "Isner Mahut 70-68",
            "Wimbledon 2010 scoreboard court 18",
            "longest tennis match scoreboard",
            "tableau Isner Mahut",
        ],
        "categories": ["Category:Isner–Mahut match at the 2010 Wimbledon Championships"],
    },
    # the plaque the All England Club put up beside the court
    "plaque": {
        "searches": [
            "Court 18 plaque Wimbledon",
            "Isner Mahut plaque",
            "Wimbledon commemorative plaque longest match",
        ],
        "categories": ["Category:Court 18 (Wimbledon)"],
    },
    # the two players
    "players": {
        "searches": [
            "John Isner 2010 Wimbledon",
            "Nicolas Mahut Wimbledon",
            "John Isner serve",
        ],
        "categories": ["Category:John Isner", "Category:Nicolas Mahut"],
    },
    # the court itself, and Wimbledon outside courts
    "court": {
        "searches": [
            "Court 18 Wimbledon",
            "Wimbledon outside courts",
            "Wimbledon grass court scoreboard",
        ],
        "categories": ["Category:Courts of the All England Lawn Tennis and Croquet Club"],
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
                "author": _plain((meta.get("Artist") or {}).get("value", ""))[:60],
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
            files = _members(cat, "file", cap=150)
            subs = _members(cat, "subcat", cap=25)
            # An empty category is a real answer only if the category exists;
            # say which it was so nobody reads a typo as an absence.
            print(f"\n=== {cat}: {len(files)} files, {len(subs)} subcats")
            for sc in subs[:12]:
                print(f"    sub: {sc}")
                files += _members(sc, "file", cap=60)
            for r in _describe(list(dict.fromkeys(files))[:180]):
                print(f"  {r['size']} {r['licence'][:15]:15} {r['date']:12} | {r['title'][:60]}")
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
                if not any(k in blob for k in ("tennis", "wimbledon", "isner", "mahut", "court")):
                    continue
                print(f"  {r['size']} {r['licence'][:15]:15} {r['date']:12} | {r['title'][:60]}")
                if r["desc"]:
                    print(f"       {r['desc'][:110]}")
                pool.setdefault(r["url"], r)

        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        kept, dropped = 0, {"licence": 0, "small": 0, "failed": 0}
        for r in pool.values():
            if kept >= 12:
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
            except Exception:  # noqa: BLE001
                dropped["failed"] += 1
                continue
            img.thumbnail((1600, 1600))
            img.save(slot_dir / f"{kept:02d}.jpg", quality=88)
            r["file"] = f"{slot}/{kept:02d}.jpg"
            print(f"  saved {kept:02d}.jpg {img.size} | {r['title'][:56]}")
            kept += 1
        print(f"\n[{slot}] pool {len(pool)}, kept {kept}, dropped {dropped}")
        report[slot] = {"pool": len(pool), "kept": kept, "dropped": dropped,
                        "rows": list(pool.values())}

    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "report.json")


if __name__ == "__main__":
    main()
