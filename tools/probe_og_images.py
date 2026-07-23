"""Temporary: fetch og:image for the WTA article about Zheng Qinwen's
Olympic gold-medal final win, as a non-Wikimedia alternative source (Commons
appears to be rate-limited/unreachable from this runner right now)."""

from __future__ import annotations

import html
import re
import sys
import urllib.request

URL = "https://www.wtatennis.com/news/4074958/zheng-holds-off-vekic-in-olympic-gold-medal-final"


def main() -> int:
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read(500_000).decode("utf-8", errors="replace")
    og_image = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', text, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', text, re.I
    )
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    print("og:image:", html.unescape(og_image.group(1)) if og_image else None)
    print("title:", re.sub(r"\s+", " ", html.unescape(title.group(1))).strip() if title else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
