"""Extract ALL image URLs (not just og:image) from the Yahoo AU article
about the 2012 AO chairs/water-bottle moment, looking for a second,
cleaner trophy-ceremony photo embedded further down in the article."""

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

ARTICLE_URL = (
    "https://au.sports.yahoo.com/aus-open-fans-notice-stunning-detail-"
    "rafa-nadals-post-match-act-014150880.html"
)

IMG_SRC_RE = re.compile(r'"(https://s\.yimg\.com/[^"]+creatr-uploaded-images[^"]+)"')


def fetch(url: str, timeout: int = 25) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED fetch {url}: {exc}")
        return None


def main() -> int:
    html_bytes = fetch(ARTICLE_URL)
    if html_bytes is None:
        return 1
    html = html_bytes.decode("utf-8", errors="ignore")
    urls = sorted(set(IMG_SRC_RE.findall(html)))
    print(f"found {len(urls)} distinct creatr-uploaded-images urls")
    for i, url in enumerate(urls):
        print(f"  [{i}] {url}")
        img_bytes = fetch(url)
        if img_bytes is None:
            continue
        dest = f"tools/_probe8_yahoo_img{i}.jpg"
        with open(dest, "wb") as f:
            f.write(img_bytes)
        print(f"    saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
