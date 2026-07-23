"""Temporary: the pipeline's repeated "download-or-resolution-failed" for
this Wikimedia file always hit the /thumb/.../1600px-... URL, which forces
MediaWiki to generate that thumbnail on demand. Test whether the direct
original-file URL (no on-demand resize) downloads reliably instead, and
report its actual pixel dimensions."""

from __future__ import annotations

import io
import sys
import time
import urllib.request

from PIL import Image

URL = "https://upload.wikimedia.org/wikipedia/commons/c/cf/Qinwen_Zheng_-_2024_Olympics.jpg"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=18) as resp:
        data = resp.read()
    elapsed = time.monotonic() - start
    image = Image.open(io.BytesIO(data))
    print(f"downloaded {len(data)} bytes in {elapsed:.2f}s -> {image.width}x{image.height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
