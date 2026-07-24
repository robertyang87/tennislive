"""Fetch the confirmed Djokovic trophy-kiss photo (already used for the
explainer page research) to complete the triptych's third panel."""

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
    "https://www.si.com/.image/c_fill,w_1440,ar_1440:810,f_auto,q_auto,"
    "g_auto/MTY4MjYyNDk4OTcyODA0MjYx/novak-djokovic.jpg"
)
DEST = "tools/_probetrip2_djokovic.jpg"


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
