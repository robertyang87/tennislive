"""Re-fetch the confirmed 4-person Tower Bridge gala-dinner photo so it
can be shown to the user for a direct side-by-side comparison against
the Big-3-only (but non-frontal, low-res) Laver Cup huddle photo."""

from __future__ import annotations

import sys
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

URL = (
    "https://i1.wp.com/rafaelnadalfans.com/wp-content/uploads/2022/09/"
    "Nadal-Murray-Djokovic-Federer-2022-Gala-Dinner-Laver-Cup-photo.jpg"
    "?ssl=1"
)
DEST = "tools/_probecoverfinal_towerbridge.jpg"


def main() -> int:
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = resp.read()
    with open(DEST, "wb") as f:
        f.write(data)
    print(f"{URL} -> {DEST} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
