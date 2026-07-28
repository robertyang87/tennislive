"""Fetch the named yellow-ball candidates, with the metadata that justifies them.

The broad hunt listed far more than it downloaded — the size floor dropped
some good frames and the noise words pulled in seed catalogues. Rather than
re-sweep, name the files worth a look and print each one's own description,
date and licence so the pick can be checked against the source rather than
against what the picture seems to show.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll/yellowball/shortlist")
UA = {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive; robertyang.ustb@gmail.com)"}

FILES = {
    # beat 1 — the century of white balls
    "white": [
        "File:Vintage White tennis balls.png",
        "File:NewandOldTennisBalls.jpg",
        "File:Tennis balls, advertisement, 19th century.jpg",
    ],
    # beat 2 — television, the force that ended it
    "tv": [
        "File:SteadyCamOp-USO-2020.png",
    ],
    # beat 3 — optic yellow as the tournament ball
    "switch": [
        "File:Cans of tennis balls.jpg",
        "File:Head Tour tournament tennis balls by Head Sport GMBH Austria.jpg",
        "File:Cmglee tennis balls.jpg",
        "File:US Open 2010 Official Ball (4980403466).jpg",
        "File:Balles officielles Roland Garros 2011.jpg",
    ],
    # beat 4 — Wimbledon, which kept white until 1986. A frame from 1986
    # itself would match the year the beat is about, not merely the place.
    "wimbledon": [
        "File:Anne White at Wimbledon 1986.jpg",
        "File:Far shot of Wimbledon Centre Court.jpg",
        "File:Right side of Centre Court, Wimbledon.jpg",
        'File:Flickr - Carine06 - "I love this grass.".jpg',
        "File:Centre Court.jpg",
    ],
    # beat 5 — one ball, two colours
    "color": [
        "File:Closeup of a tennis ball (2).jpg",
        "File:Tennis ball on tennis court 20170619.jpg",
        "File:Tennis ball on ground.jpg",
        "File:A type of tennis ball.jpg",
        "File:Tennis ball in hand - 2011 Japan Open.jpg",
    ],
}


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


def _get(**params) -> dict:
    for attempt in range(5):
        time.sleep(0.4)
        r = requests.get(API, params=params, timeout=40, headers=UA)
        if r.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    return {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for slot, titles in FILES.items():
        print("\n" + "=" * 74)
        print(f"===== {slot.upper()}")
        for index, title in enumerate(titles):
            data = _get(action="query", format="json", titles=title,
                        prop="imageinfo|categories", iiprop="url|extmetadata|size",
                        cllimit="max")
            for page in (data.get("query") or {}).get("pages", {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                if not info.get("url"):
                    print(f"  !! missing: {title}")
                    continue
                meta = info.get("extmetadata") or {}
                row = {
                    "slot": slot,
                    "title": page.get("title"),
                    "desc": _plain((meta.get("ImageDescription") or {}).get("value", "")),
                    "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", "")),
                    "artist": _plain((meta.get("Artist") or {}).get("value", "")),
                    "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                    "credit": _plain((meta.get("Credit") or {}).get("value", ""))[:120],
                    "size": [info.get("width"), info.get("height")],
                    "cats": [c.get("title", "") for c in (page.get("categories") or [])],
                    "url": info["url"],
                }
                print("-" * 74)
                print("TITLE :", row["title"])
                print("DESC  :", row["desc"][:260] or "(none)")
                print("DATE  :", row["date"] or "(none)", "| ARTIST:", row["artist"][:60])
                print("LIC   :", row["licence"], "| SIZE:", row["size"])
                print("CATS  :", ", ".join(c.replace("Category:", "") for c in row["cats"])[:220])
                try:
                    resp = requests.get(row["url"], timeout=60, headers=UA)
                    resp.raise_for_status()
                    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    img.thumbnail((1800, 1800))
                    name = f"{slot}_{index:02d}.jpg"
                    img.save(OUT / name, quality=90)
                    row["file"] = name
                    print("SAVED :", name, img.size)
                except Exception as exc:  # noqa: BLE001
                    print("!! download failed:", exc)
                report.append(row)

    (OUT / "shortlist.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "shortlist.json")


if __name__ == "__main__":
    main()
