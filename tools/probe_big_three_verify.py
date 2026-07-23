"""Download and verify the three big-three photo candidates: tennis.com's
2008 Wimbledon final photo, AusOpen's raw (non-cropped) 2012 final photo,
and tennismajors.com's photo for the same 2012 final (a second, distinct
shot) -- check real dimensions and save locally for visual inspection."""

from __future__ import annotations

import re
import sys
import urllib.request

from PIL import Image

TENNIS_COM_IMG = "https://tennis.com/images/articles/69553cda-89ad-4d63-a31c-5f1410929300/web.jpg"
AUSOPEN_RAW_IMG = "https://ausopen.com/sites/default/files/nadal_djokovic_mm%20_h_h.jpg"
TENNISMAJORS_URL = (
    "https://www.tennismajors.com/australian-open-news/"
    "january-30-2012-the-day-novak-djokovic-beat-rafael-nadal-in-the-longest-australian-open-final-317708.html"
)

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
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
        download(TENNIS_COM_IMG, "tools/_probe_wimbledon2008.jpg")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {TENNIS_COM_IMG}: {exc}")

    try:
        download(AUSOPEN_RAW_IMG, "tools/_probe_ao2012.jpg")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {AUSOPEN_RAW_IMG}: {exc}")

    try:
        req = urllib.request.Request(
            TENNISMAJORS_URL, headers={"User-Agent": "tennislive-probe/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        og_images = OG_IMAGE_PATTERN.findall(html)
        print(f"=== {TENNISMAJORS_URL} ===")
        print(f"og:image: {og_images[:3]}")
        if og_images:
            download(og_images[0], "tools/_probe_ao2012_alt.jpg")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {TENNISMAJORS_URL}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
