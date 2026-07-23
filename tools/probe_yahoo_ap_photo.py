"""Temporary: download the Yahoo-proxied AP photo of Zheng Qinwen's Olympic
semifinal action shot vs Iga Swiatek, verify its real dimensions, and save
it locally for visual inspection before using it as the "today" page photo."""

from __future__ import annotations

import sys
import urllib.request

from PIL import Image

URL = (
    "https://s.yimg.com/ny/api/res/1.2/Gef3DdfgjCxkbdARWhTF0g--/"
    "YXBwaWQ9aGlnaGxhbmRlcjt3PTEyMDA7aD04MDA7Y2Y9d2VicA--/"
    "https://media.zenfs.com/en/ap.org/af74ba83d3fbb019753043d716cc1282"
)
DEST = "tools/_probe_yahoo_ap.jpg"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(DEST, "wb") as f:
        f.write(data)
    image = Image.open(DEST)
    print(f"downloaded {len(data)} bytes -> {DEST} ({image.width}x{image.height}, format={image.format})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
