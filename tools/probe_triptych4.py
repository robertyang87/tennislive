"""Correction: fetch the actual Djokovic trophy-KISS close-up (outdoor,
tree background) from the si.com 2016 retrospective article, not the
speech-at-microphone photo already used for the explainer page."""

from __future__ import annotations

import sys
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

ARTICLE_URL = "https://www.si.com/tennis/2016/01/15/novak-djokovic-grand-slam-history-treble"
DEST = "tools/_probetrip4_djokovic_kiss.jpg"

import re

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def fetch(url: str, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {url}: {exc}")
        return None


def main() -> int:
    html_bytes = fetch(ARTICLE_URL)
    if html_bytes is None:
        return 1
    html = html_bytes.decode("utf-8", errors="ignore")
    m = OG_IMAGE_RE.search(html)
    if not m:
        print("no og:image found")
        return 1
    img_url = m.group(1)
    print(f"og:image = {img_url}")
    data = fetch(img_url)
    if data is None:
        return 1
    with open(DEST, "wb") as f:
        f.write(data)
    print(f"{img_url} -> {DEST} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
