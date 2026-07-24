"""Scrape og:image from more 2012 Australian Open candidate articles,
looking for a clean (non-annotated) both-players-together trophy photo."""

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
    "ao2012_bleacherreport": "https://bleacherreport.com/articles/1042561-nadal-vs-djokovic-score-and-highlights-from-australian-open-2012-mens-final",
    "ao2012_cbsnews_gallery2": "https://www.cbsnews.com/pictures/2012-australian-open/",
    "ao2012_fox13memphis": "https://www.fox13memphis.com/photos-novak-djokovic-through-the-years/collection_49c33f99-e1e8-53ff-a1e3-bfcd5bccebfb.html",
}

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def fetch(url: str, timeout: int = 25) -> bytes | None:
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
        dest = f"tools/_probe7_{key}.jpg"
        with open(dest, "wb") as f:
            f.write(img_bytes)
        print(f"  saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
