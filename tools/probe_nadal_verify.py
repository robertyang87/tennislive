"""Download the Rappler/Reuters Nadal retirement photo for visual
verification before committing to it."""

from __future__ import annotations

import sys
import urllib.request

URL = "https://www.rappler.com/tachyon/2024/11/reuters-rafael-nadal-tribute-november-20-2024-scaled.jpg"
DEST = "tools/_probe_nadal_retirement.jpg"


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
