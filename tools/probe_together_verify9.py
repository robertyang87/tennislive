"""Round 9: broaden sources further for a clean 2012 AO Djokovic+Nadal
trophy-ceremony photo (si.com, Fox News AMP, BBC feed, WaPo retry)."""

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
    "ao2012_si_thetoss": "https://www.si.com/tennis/2012/02/02/the-toss-measuring-2012-aussie-final-against-tennis-best-matches",
    "ao2012_foxnews_amp": "https://www.foxnews.com/sports/novak-djokovic-beats-rafael-nadal-to-win-australian-open-in-longest-final.amp",
    "ao2012_bbc_feed": "https://feeds.bbci.co.uk/sport/tennis/16782987",
    "ao2012_washingtonpost": "https://www.washingtonpost.com/sports/tennis/australian-open-djokovic-outlasts-nadal-in-longest-grand-slam-singles-final-ever/2012/01/29/gIQAYDHgaQ_story.html",
}

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def fetch(url: str, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        dest = f"tools/_probe9_{key}.jpg"
        with open(dest, "wb") as f:
            f.write(img_bytes)
        print(f"  saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
