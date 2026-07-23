"""Check tennis.com's "20 for 20" retrospective on the 2012 Australian
Open final for a real (non-placeholder) hero photo."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

URL = "https://www.tennis.com/news/articles/20-for-20-no-12-djokovic-d-nadal-2012-australian-open"

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
