"""Search for a genuine, reliably-hosted photo of Nadal's Nov 2024
Davis Cup retirement ceremony for the big-three "today" page (revised
to focus on Nadal's farewell rather than requiring an all-three photo,
which proved consistently unavailable after many search rounds)."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

URLS = [
    "https://www.rappler.com/sports/tears-flow-fans-salute-retiring-rafael-nadal-after-davis-cup-defeat-2024/",
    "https://www.rolandgarros.com/en-us/article/rafael-nadal-farewell-davis-cup-2024-spain-netherlands-malaga",
    "https://secure-www.cbssports.com/tennis/news/rafael-nadal-22-time-grand-slam-champion-announces-his-retirement-from-professional-tennis/",
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
