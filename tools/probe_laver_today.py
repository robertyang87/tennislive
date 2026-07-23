"""Search for a second, genuine all-three (or bench-reaction) photo for
the "today" page -- distinct from the NPR headshot composite already
chosen for "cover". The 2022 Laver Cup farewell doubles (Federer/Nadal
vs Tsitsipas/Rublev, with Djokovic and Murray on the bench) is the
best-documented moment with all of them present."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

URLS = [
    "https://www.si.com/tennis/2022/09/28/federer-explains-story-behind-the-memorable-photo-of-him-nadal-at-laver-cup",
    "https://www.essentiallysports.com/atp-tennis-news-inject-this-photograph-in-my-veins-tennis-world-gets-emotionally-overwhelmed-as-roger-federer-rafael-nadal-novak-djokovic-and-andy-murray-get-together-for-one-last-dance-at-laver/",
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
