"""Check the raw AP source dimensions (before Yahoo's resize proxy)
so a correct crop rectangle can be computed in a follow-up round."""

from __future__ import annotations

import io
import sys
import urllib.request

from PIL import Image

RAW = "https://media.zenfs.com/en/ap.org/6fdd29b6c4652e81e4168562a0653db9"


def main() -> int:
    req = urllib.request.Request(RAW, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    image = Image.open(io.BytesIO(data))
    print(f"{RAW} -> {image.width}x{image.height} ({len(data)} bytes)")
    with open("tools/_probe_zenfs_raw.jpg", "wb") as f:
        f.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
