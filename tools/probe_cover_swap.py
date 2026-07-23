"""Temporary: fetch Zheng Qinwen's most iconic real photo -- collapsing on
the clay in celebration right after winning 2024 Paris Olympics gold -- and
use it as the committed cover asset too (the same photo already backs the
"today" page of the knowledge post; reusing it as the cover teaser is an
accepted tradeoff since no second distinct high-res Olympics photo of her
could be verified this session)."""

from __future__ import annotations

import sys
import urllib.request

URL = (
    "https://ausopen.com/sites/default/files/202408/4/"
    "zheng-qinwen-gold-paris-2024-olympics.jpg"
)
DEST = "assets/players/zheng-qinwen.jpg"


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
