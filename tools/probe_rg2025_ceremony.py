"""Check for a genuine photo of the May 2025 Roland Garros ceremony
honoring Nadal's retirement, where Federer, Djokovic, and Murray all
joined him on Court Philippe-Chatrier -- looking for a shot where all
three subjects are close together (not a wide side-by-side composite,
which crops badly into a portrait card)."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

URLS = [
    "https://www.olympics.com/en/news/rafael-nadal-receives-emotional-roland-garros-send-off-murray-federer-djokovic",
    "https://sports.yahoo.com/article/french-open-roger-federer-novak-180837132.html",
    "https://www.aol.com/rafael-nadal-sheds-tears-emotional-182359195.html",
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
