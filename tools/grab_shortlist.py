"""Verify and download a hand-picked shortlist of Commons files.

Two leads worth chasing for the 2004 US Open beat: Serena Williams photographed
at the US Open (the player the bad calls were made against, at the tournament
where it happened), and files named for Mariana Alves — the chair umpire stood
down after that quarter-final. The name is common, so the file's own
description and categories decide whether it is her, not the pixels.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll/shortlist")

FILES = [
    "File:Serena Williams serves at the US Open (9665931630).jpg",
    "File:Serena Williams US Open 2013.jpg",
    "File:Mariana Alves (27002551794).jpg",
    "File:Umpires (27004198923).jpg",
    "File:Hawk-Eye at Wimbledon (7508887344).jpg",
]


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


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"}
    )
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for idx, title in enumerate(FILES):
        time.sleep(0.8)
        data = session.get(
            API,
            params={
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "imageinfo|categories",
                "iiprop": "url|extmetadata|size",
                "cllimit": "max",
            },
            timeout=30,
        ).json()
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            row = {
                "title": page.get("title"),
                "desc": _plain((meta.get("ImageDescription") or {}).get("value", "")),
                "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", "")),
                "artist": _plain((meta.get("Artist") or {}).get("value", "")),
                "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                "size": [info.get("width"), info.get("height")],
                "cats": [c.get("title") for c in page.get("categories") or []],
                "url": info.get("url"),
            }
            print("=" * 72)
            print("TITLE  :", row["title"])
            print("DESC   :", row["desc"][:400])
            print("DATE   :", row["date"], "| ARTIST:", row["artist"][:60])
            print("LICENCE:", row["licence"], "| SIZE:", row["size"])
            print("CATS   :", json.dumps(row["cats"], ensure_ascii=False))
            if row["url"]:
                try:
                    r = session.get(row["url"], timeout=40)
                    r.raise_for_status()
                    img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    name = f"{idx:02d}.jpg"
                    img.save(OUT / name, quality=88)
                    row["file"] = f"shortlist/{name}"
                    print("SAVED  :", name, img.size)
                except Exception as exc:  # noqa: BLE001
                    print("!! download failed:", exc)
            report.append(row)

    (OUT / "shortlist.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nwrote", OUT / "shortlist.json")


if __name__ == "__main__":
    main()
