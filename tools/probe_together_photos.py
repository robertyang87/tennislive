"""Look for genuine posed/frontal 'both finalists together' photos for
each of big-three's three historic matches (trophy ceremonies, not
mid-action shots) -- user explicitly wants together-photos, not solo
shots, for story/explainer/today."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

CANDIDATES = {
    "2008 Wimbledon (Federer/Nadal)": [
        "https://www.espn.com/tennis/story/_/id/23977542/roger-federer-rafael-nadal-epic-2008-wimbledon-final",
        "https://www.wimbledon.com/en_GB/news/articles/2019-07-11/federer_nadal_2008_the_greatest_match_of_all_time.html",
        "https://www.tennis365.com/tennis-news/t365-recalls-roger-federer-rafael-nadal-wimbledon-trilogy-2008",
    ],
    "2012 Australian Open (Djokovic/Nadal)": [
        "https://ausopen.com/history/memorable-moments/2012-great-tennis-match-all-time",
        "https://www.espn.com/tennis/aus12/story/_/id/7515950/2012-australian-open-novak-djokovic-outlasts-rafael-nadal-longest-grand-slam-final",
    ],
    "2019 Wimbledon (Djokovic/Federer)": [
        "https://sports.yahoo.com/back-to-back-djokovic-defeats-federer-in-epic-match-for-fifth-wimbledon-title-180831567.html",
        "https://www.nbcsports.com/olympics/news/roger-federer-novak-djokovic-wimbledon",
    ],
}

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    for label, urls in CANDIDATES.items():
        print(f"\n##### {label} #####")
        for url in urls:
            print(f"=== {url} ===")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                og_images = OG_IMAGE_PATTERN.findall(html)
                print(f"og:image: {og_images[:3]}")
                if og_images:
                    img_url = og_images[0].replace("&amp;", "&")
                    img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
                    with urllib.request.urlopen(img_req, timeout=15) as resp:
                        data = resp.read()
                    image = Image.open(io.BytesIO(data))
                    print(f"  -> {image.width}x{image.height} ({len(data)} bytes)")
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
