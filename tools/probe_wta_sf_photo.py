"""Temporary: find the hero photo embedded in the WTA article about Zheng
Qinwen's Olympic semifinal win over Swiatek -- a genuinely different real
photo of the same event (Paris 2024 Olympics), on the same reliable
photoresources.wtatennis.com CDN already used for story/explainer."""

from __future__ import annotations

import re
import sys
import urllib.request

URL = (
    "https://www.wtatennis.com/news/4073042/"
    "zheng-shocks-no-1-swiatek-to-reach-olympic-gold-medal-final-faces-vekic"
)

PATTERN = re.compile(r"https://photoresources\.wtatennis\.com/wta/photo/[^\"'\s\\]+")


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    found = sorted(set(PATTERN.findall(html)))
    print(f"=== {URL} ({len(found)} editorial photo urls) ===")
    for u in found:
        print(u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
