"""Scrape og:image from more 2012 Australian Open candidate articles,
looking for a clean (non-annotated) both-players-together photo."""

from __future__ import annotations

import re
import sys
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

ARTICLES = {
    "ao2012_tenniscom_20for20": "https://www.tennis.com/news/articles/20-for-20-no-12-djokovic-d-nadal-2012-australian-open",
    "ao2012_tennisworldusa_legends": "https://www.tennisworldusa.org/tennis/news/Novak_Djokovic/152085/novak-djokovic-vs-rafael-nadal-historic-final-turns-13-when-legends-collided/",
    "ao2012_tennisworldusa_unbelievable": "https://www.tennisworldusa.org/tennis/news/Rafael_Nadal/108894/novak-djokovic-the-2012-ao-final-against-rafael-nadal-was-unbelievable-and-historic/",
}

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED fetch {url}: {exc}")
        return None


def main() -> int:
    for key, article_url in ARTICLES.items():
        print(f"== {key} :: {article_url}")
        html_bytes = fetch(article_url)
        if html_bytes is None:
            continue
        html = html_bytes.decode("utf-8", errors="ignore")
        match = OG_IMAGE_RE.search(html) or OG_IMAGE_RE2.search(html)
        if not match:
            print("  no og:image found")
            continue
        img_url = match.group(1)
        print(f"  og:image = {img_url}")
        img_bytes = fetch(img_url)
        if img_bytes is None:
            continue
        dest = f"tools/_probe5_{key}.jpg"
        with open(dest, "wb") as f:
            f.write(img_bytes)
        print(f"  saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
