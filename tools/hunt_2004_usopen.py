"""Enumerate everything Commons/Flickr hold on the 2004 US Open Williams-Capriati QF.

Earlier passes sampled a category and stopped at the first few files that met a
size/licence bar, which cannot answer "does a photo of this match exist at all".
This lists exhaustively and prints titles + descriptions so a human can read the
whole shelf: the full 2004 US Open category, every upload by the people who were
shooting there that fortnight, file-namespace searches for both players, and a
CC-licensed Flickr sweep. It downloads nothing and picks nothing.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from tennislive.research.visual_sources import _flickr_candidates

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll")

CATEGORIES = [
    "Category:2004 US Open (tennis)",
    "Category:Serena Williams",
    "Category:Jennifer Capriati",
]
FILE_SEARCHES = [
    "Capriati US Open",
    "Serena Williams 2004",
    "Serena Williams US Open 2004",
    "Capriati Williams 2004",
    "Mariana Alves tennis",
]
FLICKR_QUERIES = [
    "Serena Williams 2004 US Open",
    "Jennifer Capriati 2004 US Open",
    "US Open 2004 tennis",
]


def _api(session: requests.Session, **params):
    """Query Commons politely.

    The first sweep hammered the API and every search came back 429, which
    reads exactly like "no such photo exists" — the most dangerous kind of
    wrong answer here. Space the calls out and back off hard on 429 so an
    empty result means empty, not throttled.
    """
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    params.setdefault("maxlag", 5)
    last = None
    for attempt in range(6):
        try:
            time.sleep(0.6)
            r = session.get(API, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(4 * (attempt + 1))
                last = "429 throttled"
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    print(f"  !! gave up: {last}")
    return {}


def _plain(raw: str) -> str:
    keep, buf = True, []
    for ch in str(raw):
        if ch == "<":
            keep = False
        elif ch == ">":
            keep = True
        elif keep:
            buf.append(ch)
    return " ".join("".join(buf).split())


def _describe(session: requests.Session, titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 10):
        data = _api(
            session,
            titles="|".join(titles[i : i + 10]),
            prop="imageinfo",
            iiprop="url|extmetadata|size|user",
        )
        for page in data.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            out.append(
                {
                    "title": page.get("title", ""),
                    "uploader": info.get("user", ""),
                    "size": [info.get("width", 0), info.get("height", 0)],
                    "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                    "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:220],
                    "url": info.get("url", ""),
                }
            )
    return out


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"}
    )
    report: dict = {}
    uploaders: set[str] = set()

    # The parent category for a player is often near-empty; the photographs sit
    # in per-year / per-event subcategories, so walk one level down first.
    expanded: list[str] = []
    for category in CATEGORIES:
        expanded.append(category)
        data = _api(session, list="categorymembers", cmtitle=category,
                    cmtype="subcat", cmlimit="max")
        subs = [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        interesting = [
            c for c in subs
            if any(k in c.lower() for k in ("2003", "2004", "2005", "us open", "usopen"))
        ]
        if subs:
            print(f"\n--- {category}: {len(subs)} subcats, {len(interesting)} relevant")
            for c in interesting:
                print(f"      -> {c}")
        expanded += interesting

    for category in expanded:
        titles, cont = [], {}
        while True:
            data = _api(
                session,
                list="categorymembers",
                cmtitle=category,
                cmtype="file",
                cmlimit="max",
                **cont,
            )
            titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
            cont = data.get("continue") or {}
            if not cont:
                break
        rows = _describe(session, titles)
        print(f"\n===== {category}: {len(rows)} files =====")
        for r in rows:
            if r["uploader"]:
                uploaders.add(r["uploader"])
            print(f"  {r['title']}")
            print(f"     by {r['uploader']} | {r['licence']} | {r['size']}")
            if r["desc"]:
                print(f"     {r['desc']}")
        report[category] = rows

    # Anyone who uploaded from that fortnight may have shot the match too.
    for user in sorted(uploaders):
        data = _api(
            session,
            list="allimages",
            aiuser=user,
            ailimit="max",
            aiprop="url|extmetadata|size",
        )
        imgs = data.get("query", {}).get("allimages", [])
        hits = [
            i
            for i in imgs
            if any(
                k in (i.get("title", "") + _plain((i.get("extmetadata") or {}).get("ImageDescription", {}).get("value", ""))).lower()
                for k in ("us open", "capriati", "williams", "2004")
            )
        ]
        if hits:
            print(f"\n===== uploads by {user} matching 2004/US Open: {len(hits)} =====")
            for i in hits:
                print(f"  {i.get('title')} | {i.get('width')}x{i.get('height')}")
        report[f"uploader:{user}"] = [i.get("title") for i in hits]

    for term in FILE_SEARCHES:
        data = _api(session, list="search", srsearch=term, srnamespace=6, srlimit=25)
        rows = _describe(session, [h["title"] for h in data.get("query", {}).get("search", [])])
        print(f"\n===== file search '{term}': {len(rows)} =====")
        for r in rows:
            print(f"  {r['title']} | {r['licence']} | {r['size']}")
            if r["desc"]:
                print(f"     {r['desc']}")
        report[f"search:{term}"] = rows

    for q in FLICKR_QUERIES:
        try:
            cands = list(_flickr_candidates(q, session))
        except Exception as exc:  # noqa: BLE001
            print(f"\n===== flickr '{q}': failed {exc} =====")
            continue
        print(f"\n===== flickr '{q}': {len(cands)} =====")
        for c in cands[:15]:
            print(f"  {str(c.get('credit'))[:50]} | {c.get('license')}")
            print(f"     {str(c.get('image_text'))[:150]}")
        report[f"flickr:{q}"] = [
            {k: c.get(k) for k in ("source_url", "image_url", "license", "credit")}
            for c in cands[:15]
        ]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hunt_2004.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nwrote tools/broll/hunt_2004.json")


if __name__ == "__main__":
    main()
