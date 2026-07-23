"""Check for a taller crop of the AusOpen 2012-final photo (the raw file
is an unusually wide 1600x523 banner, 17px short of the 540 minimum),
and check BBC/Sportskeeda articles for an alternate real photo of the
same match."""

from __future__ import annotations

import re
import sys
import urllib.request

from PIL import Image
import io

STYLE_CANDIDATES = [
    "https://ausopen.com/sites/default/files/styles/large/public/nadal_djokovic_mm%20_h_h.jpg",
    "https://ausopen.com/sites/default/files/styles/hero/public/nadal_djokovic_mm%20_h_h.jpg",
    "https://ausopen.com/sites/default/files/styles/wide/public/nadal_djokovic_mm%20_h_h.jpg",
    "https://ausopen.com/sites/default/files/styles/max_1300x1300/public/nadal_djokovic_mm%20_h_h.jpg",
]

ARTICLE_URLS = [
    "https://feeds.bbci.co.uk/sport/tennis/16773908",
    "https://www.sportskeeda.com/tennis/australian-open-history-5-memorable-moments-past-editions-ft-novak-djokovic-vs-rafael-nadal-epic-2012-final",
]

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def check_size(url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        image = Image.open(io.BytesIO(data))
        print(f"OK {url} -> {image.width}x{image.height} ({len(data)} bytes)")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {url}: {exc}")


def main() -> int:
    for url in STYLE_CANDIDATES:
        check_size(url)

    for url in ARTICLE_URLS:
        req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            og_images = OG_IMAGE_PATTERN.findall(html)
            print(f"=== {url} ===")
            print(f"og:image: {og_images[:3]}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
