"""Download the Yahoo/AP wire photo of the 2025 Roland Garros Nadal
farewell ceremony for visual verification."""

from __future__ import annotations

import sys
import urllib.request

URL = (
    "https://s.yimg.com/ny/api/res/1.2/u0o1TsoeOJBfQQu9D2a2Jg--/"
    "YXBwaWQ9aGlnaGxhbmRlcjt3PTEyMDA7aD04MDA7Y2Y9d2VicA--/"
    "https://media.zenfs.com/en/ap.org/6fdd29b6c4652e81e4168562a0653db9"
)
DEST = "tools/_probe_rg2025.jpg"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(DEST, "wb") as f:
        f.write(data)
    print(f"{URL} -> {DEST} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
