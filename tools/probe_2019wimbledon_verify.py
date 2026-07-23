"""Download and verify the two 2019 Wimbledon final photo candidates
found via NBC Sports and Forbes -- check real dimensions and save
locally for visual inspection."""

from __future__ import annotations

import sys
import urllib.request

from PIL import Image

NBC_IMG = (
    "https://nbcsports.brightspotcdn.com/dims4/default/e09ff05/2147483647/strip/true/"
    "crop/1024x576+0+0/resize/1440x810!/quality/90/?url=https%3A%2F%2Fnbc-sports-production-nbc-sports.s3.us-east-1.amazonaws.com"
    "%2Fbrightspot%2Ff5%2Ff8%2F71d160729c4dd618a3df756b1702%2Fgettyimages-1161676219-e1563106684632.jpg"
)
FORBES_IMG = (
    "https://imageio.forbes.com/specials-images/dam/imageserve/"
    "b65f9e6451bb47419994e84c6900655f/0x0.jpg?format=jpg&height=900&width=1600&fit=bounds"
)


def download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    image = Image.open(dest)
    print(f"{url} -> {dest} ({len(data)} bytes, {image.width}x{image.height})")


def main() -> int:
    try:
        download(NBC_IMG, "tools/_probe_wimbledon2019_nbc.jpg")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED NBC: {exc}")
    try:
        download(FORBES_IMG, "tools/_probe_wimbledon2019_forbes.jpg")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED Forbes: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
