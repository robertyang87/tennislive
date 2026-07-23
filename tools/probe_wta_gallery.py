"""Temporary: fetch a WTA article page's HTML and list every distinct
photoresources.wtatennis.com image URL referenced on it, so a genuinely
different real photo (not the one already used for the cover/explainer)
can be found for the "today" page of the zheng-qinwen knowledge post."""

from __future__ import annotations

import re
import sys
import urllib.request

URLS = [
    "https://www.wtatennis.com/news/4074958/zheng-holds-off-vekic-in-olympic-gold-medal-final",
    "https://www.wtatennis.com/news/3867402/zheng-qinwen-bests-yastremska-makes-first-slam-final-at-australian-open",
]

PATTERN = re.compile(r"https://photoresources\.wtatennis\.com/[^\"'\s\\]+")


def main() -> int:
    for url in URLS:
        req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
            continue
        found = sorted(set(PATTERN.findall(html)))
        print(f"=== {url} ({len(found)} image urls) ===")
        for u in found:
            print(u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
