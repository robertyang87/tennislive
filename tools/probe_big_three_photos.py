"""Find real, distinct editorial photo URLs for the big-three knowledge
post: the 2008 Wimbledon final (story) and two distinct shots from the
2012 Australian Open final -- the famous chairs/trophy-ceremony moment
and a match-action shot (explainer + today, since both anchor to the
same moment)."""

from __future__ import annotations

import re
import sys
import urllib.request

URLS = [
    "https://www.atptour.com/en/news/atp-no-1-club-docuseries-part-4-big-3-feature",
    "https://www.espn.com/tennis/story/_/id/23977542/roger-federer-rafael-nadal-epic-2008-wimbledon-final",
    "https://ausopen.com/history/memorable-moments/2012-great-tennis-match-all-time",
    "https://www.espn.com/tennis/aus12/story/_/id/7515950/2012-australian-open-novak-djokovic-outlasts-rafael-nadal-longest-grand-slam-final",
]

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)
IMG_PATTERN = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)


def main() -> int:
    for url in URLS:
        req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
            continue
        og_images = OG_IMAGE_PATTERN.findall(html)
        print(f"=== {url} ===")
        print(f"og:image: {og_images[:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
