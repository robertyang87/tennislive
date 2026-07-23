"""Temporary diagnostic: fetch the real og:image (and alt text) from the
zheng-qinwen story's own official source articles, so a curated
knowledge-post visual entry can cite a real event photo instead of relying
on Wikimedia Commons search results. Run via GitHub Actions -- these
official tennis-media domains are unreachable directly from the sandbox
this was authored in."""

from __future__ import annotations

import html
import re
import sys
import urllib.request

URLS = [
    "https://www.wtatennis.com/news/3868599/sabalenka-overpowers-zheng-qinwen-to-defend-australian-open-title",
    "https://www.olympics.com/en/news/zheng-qinwen-wins-gold-paris-2024-tennis-women-singles",
    "https://ausopen.com/articles/news/rebounding-ao-final-zheng-qinwen-wins-olympic-gold-china",
]


def fetch(url: str) -> None:
    print(f"\n===== {url} =====")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read(500_000).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc!r}")
        return
    og_image = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', text, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', text, re.I
    )
    og_alt = re.search(
        r'<meta[^>]+property=["\']og:image:alt["\'][^>]+content=["\']([^"\']+)', text, re.I
    )
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    print("og:image:", html.unescape(og_image.group(1)) if og_image else None)
    print("og:image:alt:", html.unescape(og_alt.group(1)) if og_alt else None)
    print("title:", re.sub(r"\s+", " ", html.unescape(title.group(1))).strip() if title else None)


def main() -> int:
    for url in URLS:
        fetch(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
