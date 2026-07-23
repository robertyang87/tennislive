"""Temporary: check dimensions of the AusOpen "twitter" crop style of the
cover photo, and save it locally so it can be visually compared against
the raw cover image to judge whether it reads as a distinct shot."""

from __future__ import annotations

import sys
import urllib.request

from PIL import Image

URL = (
    "https://ausopen.com/sites/default/files/styles/twitter/public/"
    "202408/4/zheng-qinwen-gold-paris-2024-olympics.jpg?itok=1M9Hn2sV"
)
DEST = "tools/_probe_twitter_crop.jpg"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(DEST, "wb") as f:
        f.write(data)
    image = Image.open(DEST)
    print(f"downloaded {len(data)} bytes -> {DEST} ({image.width}x{image.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
