"""Careful verification round: the two new Forbes 'By The Numbers'
candidates might actually be about DIFFERENT (2019) matches despite
similar title patterns to what's needed (2008 Wimbledon final,
2012 Australian Open final) -- download them plus the Wikimedia
original for the 2008 final so all three can be visually checked
for actual content before use."""

from __future__ import annotations

import sys
import urllib.request

from PIL import Image

CANDIDATES = {
    "tools/_probe_verify_forbes_wimbledon.jpg": (
        "https://imageio.forbes.com/specials-images/dam/imageserve/"
        "cad5faba90c84cfe9148515eadf48ffa/0x0.jpg?format=jpg&height=900&width=1600&fit=bounds"
    ),
    "tools/_probe_verify_forbes_ao.jpg": (
        "https://imageio.forbes.com/blogs-images/adamzagoria/files/2019/01/"
        "3000-1-1200x713.jpeg?format=jpg&height=900&width=1600&fit=bounds"
    ),
    "tools/_probe_verify_wikimedia_2008.jpg": (
        "https://upload.wikimedia.org/wikipedia/commons/0/0d/"
        "Wimbledon_Men%27s_final_2008%2C_Federer_serves_for_3rd_set.jpg"
    ),
}


def download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    image = Image.open(dest)
    print(f"{url} -> {dest} ({len(data)} bytes, {image.width}x{image.height})")


def main() -> int:
    for dest, url in CANDIDATES.items():
        try:
            download(url, dest)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
