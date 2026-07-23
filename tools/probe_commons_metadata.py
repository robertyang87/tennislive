"""Temporary diagnostic: fetch real Wikimedia Commons imageinfo (license,
author, dimensions, direct file URL) for specific File: pages so a curated
knowledge-post visual entry can be built from verified data instead of a
guess. Run via GitHub Actions, which has broader egress than the sandbox
this was authored in (Commons is unreachable directly from there)."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

TITLES = [
    "File:Qinwen Zheng - 2024 Olympics.jpg",
    "File:Zheng Qinwen (2024 US Open) 01 (cropped).jpg",
    "File:Zheng Qinwen (2023 US Open) 01 (cropped).jpg",
]


def list_category(category: str) -> None:
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "file",
        "cmlimit": "200",
        "format": "json",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    print(f"\n===== category members: {category} =====")
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
            for member in data.get("query", {}).get("categorymembers", []):
                print("-", member.get("title"))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc!r}")


def fetch(title: str) -> None:
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "format": "json",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    print(f"\n===== {title} =====")
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                info = (page.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata", {})
                print("url:", info.get("url"))
                print("width x height:", info.get("width"), "x", info.get("height"))
                print("LicenseShortName:", meta.get("LicenseShortName", {}).get("value"))
                print("Artist:", meta.get("Artist", {}).get("value"))
                print("Credit:", meta.get("Credit", {}).get("value"))
                print("ImageDescription:", meta.get("ImageDescription", {}).get("value"))
                print("DateTimeOriginal:", meta.get("DateTimeOriginal", {}).get("value"))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc!r}")


def search(query: str) -> None:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": "20",
        "format": "json",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    print(f"\n===== search: {query} =====")
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                print("-", page.get("title"))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc!r}")


def main() -> int:
    list_category("Category:Zheng Qinwen")
    search("Zheng Qinwen 2024 Olympics")
    search("Zheng Qinwen Australian Open")
    search("Zheng Qinwen Roland Garros")
    for title in TITLES:
        fetch(title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
