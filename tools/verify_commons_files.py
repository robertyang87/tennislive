"""Confirm what a Wikimedia Commons photo actually depicts, before publishing it.

Visual inspection tells us a frame shows red clay and a line judge; it cannot
tell us *which tournament* it was shot at. Claiming "Roland-Garros" over a frame
from some other clay event would misrepresent it, so the claim has to come from
the file's own description/categories — not from our reading of the pixels.

Prints the description, date, author, licence and categories for each file so a
human can confirm the caption is true. Run in Actions (Commons is unreachable
from the sandbox).
"""

from __future__ import annotations

import json
import sys

import requests

API = "https://commons.wikimedia.org/w/api.php"

FILES = [
    "File:Leonardo Mayer (8334068684).jpg",
    "File:Line judges.JPG",
    "File:ND DN 2006FO.jpg",
]


def main() -> None:
    files = sys.argv[1:] or FILES
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "tennislive/1.0 (contact: github.com/robertyang87/tennislive)"}
    )
    for title in files:
        params = {
            "action": "query",
            "titles": title,
            "prop": "imageinfo|categories",
            "iiprop": "extmetadata|url",
            "cllimit": "max",
            "format": "json",
        }
        try:
            data = session.get(API, params=params, timeout=30).json()
        except Exception as exc:  # noqa: BLE001
            print(f"!! {title}: {exc}")
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            print("=" * 72)
            print("TITLE   :", page.get("title"))
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}

            def val(key: str) -> str:
                raw = str((meta.get(key) or {}).get("value", ""))
                # strip the HTML Commons wraps descriptions in
                out, keep = [], True
                for ch in raw:
                    if ch == "<":
                        keep = False
                    elif ch == ">":
                        keep = True
                    elif keep:
                        out.append(ch)
                return " ".join("".join(out).split())

            print("DESC    :", val("ImageDescription")[:400])
            print("DATE    :", val("DateTimeOriginal") or val("DateTime"))
            print("AUTHOR  :", val("Artist"))
            print("LICENCE :", val("LicenseShortName"), "|", val("UsageTerms"))
            print("CREDIT  :", val("Credit")[:200])
            cats = [c.get("title", "") for c in page.get("categories") or []]
            print("CATS    :", json.dumps(cats, ensure_ascii=False))


if __name__ == "__main__":
    main()
