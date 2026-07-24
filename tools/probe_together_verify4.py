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
    "ao2012_sportskeeda_chair": "https://www.sportskeeda.com/tennis/news-even-let-rafael-nadal-get-chair-first-olive-branch-extended-fans-recall-novak-djokovic-s-classy-gesture-6-hour-australian-open-final",
    "ao2012_sportskeeda_badass": "https://www.sportskeeda.com/tennis/news-top-tier-badass-moment-tennis-fan-recall-novak-djokovic-rafael-nadal-s-struggle-stand-6-hour-australian-open-final",
    "ao2012_sportskeeda_destroy": "https://www.sportskeeda.com/tennis/news-defeat-destroy-me-rafael-nadal-opens-heartbreaking-australian-open-2012-final-loss-novak-djokovic-okay",
    "ao2012_washingtonpost": "https://www.washingtonpost.com/sports/tennis/australian-open-djokovic-outlasts-nadal-in-longest-grand-slam-singles-final-ever/2012/01/29/gIQAYDHgaQ_story.html",
    "ao2012_wikipedia": "https://en.wikipedia.org/wiki/2012_Australian_Open_%E2%80%93_Men%27s_singles_final",
    "ao2012_foxnews": "https://www.foxnews.com/sports/novak-djokovic-tops-rafa-nadal-in-straight-sets-to-win-australian-open-mens-title",
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
        dest = f"tools/_probe4_{key}.jpg"
        with open(dest, "wb") as f:
            f.write(img_bytes)
        print(f"  saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
