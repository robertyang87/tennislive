"""Download a named shortlist of Commons files, verifying each as it goes.

The wide hunt found what we needed but only tallied the category results
instead of pooling them for download. Rather than re-run the whole sweep,
fetch the handful of files by name.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll/named2")

FILES = [
    # Roland-Garros, players awaiting a decision — very likely the mark being read
    'File:Flickr - Carine06 - "How many umpires does it take to...".jpg',
    "File:Court Philippe Chatrier 001.jpg",
    "File:Tennis Racquets and Balls on a Clay Court.jpg",
    # 2026 Roland-Garros — the line judges' own chair, i.e. the post still exists
    "File:Line judges' chair at the 2026 Roland Garros.jpg",
    "File:Umpire's chair at the 2026 Roland Garros (1).jpg",
    "File:Scoreboards at the 2026 Roland Garros (1).jpg",
    "File:Net repairing at the 2026 Roland Garros (1).jpg",
    "File:Giovanni Mpetshi-Perricard.jpg",
    "File:Rafa-jodar-roland-garros-2026-profile.jpg",
    # 2025 chair umpire on clay, as a fallback for the same beat
    "File:Chair umpire - Roland-Garros (1).jpg",
    "File:Chair umpire - Roland-Garros (2).jpg",
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
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for idx, title in enumerate(FILES):
        time.sleep(0.4)
        data = requests.get(
            API,
            params={
                "action": "query", "format": "json", "titles": title,
                "prop": "imageinfo|categories", "iiprop": "url|extmetadata|size",
                "cllimit": "max",
            },
            timeout=30,
            headers={"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"},
        ).json()
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("url"):
                print(f"!! missing: {title}")
                continue
            meta = info.get("extmetadata") or {}
            row = {
                "title": page.get("title"),
                "desc": _plain((meta.get("ImageDescription") or {}).get("value", "")),
                "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", "")),
                "artist": _plain((meta.get("Artist") or {}).get("value", ""))[:70],
                "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                "size": [info.get("width"), info.get("height")],
                "cats": [c.get("title") for c in page.get("categories") or []],
                "url": info["url"],
            }
            print("=" * 70)
            print("TITLE  :", row["title"])
            print("DESC   :", row["desc"][:200])
            print("DATE   :", row["date"], "| LIC:", row["licence"], "| SIZE:", row["size"])
            print("CATS   :", json.dumps(row["cats"], ensure_ascii=False)[:220])
            try:
                resp = requests.get(row["url"], timeout=60,
                                    headers={"User-Agent": "tennislive/1.0"})
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                name = f"{idx:02d}.jpg"
                img.save(OUT / name, quality=90)
                row["file"] = f"named/{name}"
                print("SAVED  :", name, img.size)
            except Exception as exc:  # noqa: BLE001
                print("!! download failed:", exc)
            report.append(row)

    (OUT / "named.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "named.json")


if __name__ == "__main__":
    main()
