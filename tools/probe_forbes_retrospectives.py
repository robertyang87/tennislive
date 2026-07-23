"""Forbes' 'By The Numbers' articles reliably have a properly-sized
hero photo (confirmed for the 2019 Wimbledon final). Check two more
of the same series for 2008 Wimbledon and 2012 Australian Open
retrospective coverage."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

URLS = [
    "https://www.forbes.com/sites/adamzagoria/2019/07/10/wimbledon-roger-federer-vs-rafael-nadal-by-the-numbers/",
    "https://www.forbes.com/sites/adamzagoria/2019/01/25/rafael-nadal-vs-novak-djokovic-the-australian-open-final-by-the-numbers/",
]

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    for url in URLS:
        req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            og_images = OG_IMAGE_PATTERN.findall(html)
            print(f"=== {url} ===")
            print(f"og:image: {og_images[:3]}")
            if og_images:
                img_url = og_images[0].replace("&amp;", "&")
                img_req = urllib.request.Request(
                    img_url, headers={"User-Agent": "tennislive-probe/1.0"}
                )
                with urllib.request.urlopen(img_req, timeout=15) as resp:
                    data = resp.read()
                image = Image.open(io.BytesIO(data))
                print(f"  -> {image.width}x{image.height} ({len(data)} bytes)")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
