"""Temporary: fetch the ausopen.com article HTML about Zheng Qinwen's
Olympic gold medal and list every distinct sites/default/files image URL
referenced, to find a second real photo distinct from the one already
used as the knowledge post's cover image."""

from __future__ import annotations

import re
import sys
import urllib.request

URL = (
    "https://ausopen.com/articles/news/"
    "rebounding-ao-final-zheng-qinwen-wins-olympic-gold-china"
)

PATTERN = re.compile(r"https://ausopen\.com/sites/default/files/[^\"'\s\\]+")


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    found = sorted(set(PATTERN.findall(html)))
    print(f"=== {URL} ({len(found)} image urls) ===")
    for u in found:
        print(u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
