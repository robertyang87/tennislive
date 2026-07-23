"""Temporary: download the WTA-hosted Getty photo of Zheng Qinwen's Olympic
gold-medal final so it can be viewed directly and checked for an actual
visible watermark before deciding whether to use it."""

from __future__ import annotations

import sys
import urllib.request

URL = (
    "https://photoresources.wtatennis.com/wta/photo/2024/08/03/"
    "13c7b92f-6767-4ed3-9a14-a78cd46642b9/GettyImages-2165120786.jpg"
)
DEST = "tools/_probe_getty.jpg"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(DEST, "wb") as f:
        f.write(data)
    print(f"downloaded {len(data)} bytes -> {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
