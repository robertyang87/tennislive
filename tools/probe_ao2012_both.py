"""Look for a genuine photo showing BOTH Djokovic and Nadal together
from the 2012 Australian Open final -- the trophy-ceremony "chairs"
moment is the best-documented candidate. Also check for a genuine
photo of all three (Federer, Nadal, Djokovic) together, e.g. the
2022 Laver Cup reunion, for the cover/today pages."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

URLS = [
    "https://www.sportskeeda.com/tennis/news-even-let-rafael-nadal-get-chair-first-olive-branch-extended-fans-recall-novak-djokovic-s-classy-gesture-6-hour-australian-open-final",
    "https://www.perfect-tennis.com/novak-djokovic-vs-rafael-nadal-australian-open-2012/",
    "https://www.npr.org/2022/09/22/1124272575/laver-cup-federer-nadal-djokovic",
    "https://www.tennis.com/news/articles/federer-nadal-djokovic-murray-together-one-last-time-laver-cup",
]

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    for url in URLS:
        print(f"=== {url} ===")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            og_images = OG_IMAGE_PATTERN.findall(html)
            print(f"og:image: {og_images[:3]}")
            if og_images:
                img_url = og_images[0].replace("&amp;", "&")
                img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
                with urllib.request.urlopen(img_req, timeout=15) as resp:
                    data = resp.read()
                image = Image.open(io.BytesIO(data))
                print(f"  -> {image.width}x{image.height} ({len(data)} bytes)")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
