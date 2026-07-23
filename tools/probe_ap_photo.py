"""Temporary: check a few mainstream outlets' AP wire coverage of the
Zheng Qinwen vs Iga Swiatek Olympic semifinal for an embedded hero photo
URL -- a genuinely different real action photo of the same event, needed
because Wikimedia has proven unreliable and the WTA semifinal article has
no static-HTML photo."""

from __future__ import annotations

import re
import sys
import urllib.request

URLS = [
    "https://abcnews.go.com/Sports/wireStory/1-iga-swiatek-loses-zheng-qinwen-china-semifinals-112471247",
    "https://www.usnews.com/news/sports/articles/2024-08-01/no-1-iga-swiatek-loses-to-zheng-qinwen-of-china-in-the-semifinals-at-the-paris-olympics",
    "https://sports.yahoo.com/no-1-iga-swiatek-loses-120600551.html",
    "https://gulfnews.com/sport/tennis/zheng-stuns-swiatek-at-olympics-as-alcaraz-closes-in-on-djokovic-clash-1.103691769",
]

IMG_PATTERN = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)
OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    for url in URLS:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36 tennislive-probe/1.0"
                )
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
            continue
        og_images = OG_IMAGE_PATTERN.findall(html)
        print(f"=== {url} ===")
        print(f"og:image -> {og_images[:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
