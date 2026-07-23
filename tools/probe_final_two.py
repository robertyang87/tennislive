"""Find properly-sized real photos for the two remaining big-three
moments: 2008 Wimbledon final (Nadal d. Federer) and 2012 Australian
Open final (Djokovic d. Nadal)."""

from __future__ import annotations

import re
import sys
import urllib.request

URLS = [
    "https://gulfnews.com/sport/tennis/six-memorable-rafael-nadal-grand-slam-finals-1.104342970",
    "https://www.tennis.com/news/articles/20-for-20-no-12-djokovic-d-nadal-2012-australian-open",
    "https://www.ibtimes.com/djokovic-nadal-australian-open-final-2012-djokovic-wins-epic-battle-402228",
]

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    for url in URLS:
        req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            og_images = OG_IMAGE_PATTERN.findall(html)
            print(f"=== {url} ===")
            print(f"og:image: {og_images[:3]}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
