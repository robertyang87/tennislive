"""Confirm the replacement (non-Wikipedia) citation URLs for big-three
actually resolve, and fetch Commons extmetadata (license + author) for
the 2008 Wimbledon final photo."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

CITATION_URLS = [
    "https://www.espn.com/tennis/story/_/id/23977542/roger-federer-rafael-nadal-epic-2008-wimbledon-final",
    "https://www.espn.com/tennis/aus12/story/_/id/7515950/2012-australian-open-novak-djokovic-outlasts-rafael-nadal-longest-grand-slam-final",
    "https://www.atptour.com/en/news/atp-no-1-club-docuseries-part-4-big-3-feature",
    "https://www.forbes.com/sites/adamzagoria/2019/07/14/wimbledon-novak-djokovics-championship-win-over-roger-federer-by-the-numbers/",
]

TITLE = "File:Wimbledon Men's final 2008, Federer serves for 3rd set.jpg"
API_URL = (
    "https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo"
    "&iiprop=extmetadata%7Curl&format=json&titles="
    + urllib.parse.quote(TITLE)
)


def check_url(url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"{resp.status} {url}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {url}: {exc}")


def wikimedia_credit() -> None:
    req = urllib.request.Request(API_URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        print("descriptionurl:", info.get("descriptionurl"))
        print("url:", info.get("url"))
        for key in ("Artist", "LicenseShortName", "License", "Credit", "ImageDescription"):
            if key in meta:
                print(f"{key}: {meta[key].get('value')}")


def main() -> int:
    print("=== citation URLs ===")
    for url in CITATION_URLS:
        check_url(url)
    print("=== wikimedia credit ===")
    try:
        wikimedia_credit()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED wikimedia credit: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
