"""Scrape og:image from candidate articles for 2012 AO / 2019 Wimbledon
'both players together' photos, then download each found image for
visual verification."""

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
    "wimbledon2019_yahoo_reacts": "https://sports.yahoo.com/the-world-sports-reacts-to-epic-djokovic-federer-wimbledon-final-185101781.html",
    "wimbledon2019_pbs": "https://www.pbs.org/newshour/world/djokovic-edges-federer-in-5-sets-for-5th-wimbledon-trophy",
    "wimbledon2019_atp": "https://www.atptour.com/en/news/djokovic-federer-wimbledon-2019-final-match-analysis",
    "wimbledon2019_foxnews": "https://www.foxnews.com/sports/novak-djokovic-beats-roger-federerin-epic-five-set-match-to-win-wimbledon-mens-title",
    "ao2012_sportsrush_water": "https://thesportsrush.com/tennis-news-villain-novak-djokovic-wins-hearts-rare-photo-of-serb-offering-rafael-nadal-water-bottle-after-epic-australian-open-2012-final-goes-viral/",
    "ao2012_cbsnews": "https://www.cbsnews.com/news/djokovic-wears-down-nadal-at-aussie-open/",
    "ao2012_espn": "https://www.espn.com/tennis/aus12/story/_/id/7515950/2012-australian-open-novak-djokovic-outlasts-rafael-nadal-longest-grand-slam-final",
    "ao2012_nytennismag": "https://newyorktennismagazine.com/article/djokovic-claims-2012-australian-open-title-after-six-hour-win-over-nadal/",
    "ao2012_yahoo_detail": "https://au.sports.yahoo.com/aus-open-fans-notice-stunning-detail-rafa-nadals-post-match-act-014150880.html",
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
        dest = f"tools/_probe3_{key}.jpg"
        with open(dest, "wb") as f:
            f.write(img_bytes)
        print(f"  saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
