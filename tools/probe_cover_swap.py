"""Temporary: fetch the real, already-verified 2024 Australian Open
quarterfinal photo of Zheng Qinwen and overwrite the committed cover asset
with it (the previous cover had a bystander prominent in frame; its Commons
"cropped" variant turned out to be a rotated, unusable close-up)."""

from __future__ import annotations

import sys
import urllib.request

URL = (
    "https://photoresources.wtatennis.com/wta/photo/2024/01/24/"
    "77cc89de-5003-44c6-a221-c3db1b6a04af/Zheng-QF-Paul-Crock-AFP.jpg"
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
