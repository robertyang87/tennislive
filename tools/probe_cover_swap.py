"""Temporary diagnostic: fetch the cropped variant of the current
zheng-qinwen cover photo so it can be viewed before deciding whether to
replace the uncropped asset (which has a bystander prominent in frame)."""

from __future__ import annotations

import sys
import urllib.request

URL = (
    "https://upload.wikimedia.org/wikipedia/commons/0/0d/"
    "Zheng_Qinwen_%282024_US_Open%29_01_%28cropped%29.jpg"
)


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    dest = "tools/_probe_cover.jpg"
    with open(dest, "wb") as f:
        f.write(data)
    print(f"downloaded {len(data)} bytes -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
