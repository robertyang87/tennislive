"""Find real, distinct editorial photo URLs for the cincinnati knowledge
post's three non-cover pages: the 2023 Djokovic-Alcaraz final (story) and
two distinct shots from Gauff's 2023 Cincinnati title run (explainer +
today, since both anchor to the same moment)."""

from __future__ import annotations

import re
import sys
import urllib.request

URLS = [
    "https://www.atptour.com/en/news/alcaraz-djokovic-cincinnati-2023-final",
    "https://www.wtatennis.com/news/3644720/coco-gauff-bests-muchova-in-cincinnati-to-win-first-wta-1000-title",
    "https://cincinnatiopen.com/news/coco-gauff-captures-2023-western-southern-open-for-biggest-career-title/",
    "https://www.wtatennis.com/news/3642199/gauff-vs-muchova-everything-you-need-to-know-about-the-2023-cincy-final",
]

PHOTO_PATTERN = re.compile(
    r'https://[^"\'\s\\]*(?:photoresources\.atptour\.com|photoresources\.wtatennis\.com/wta/photo|'
    r'atptour\.com/[^"\'\s\\]*\.(?:jpg|jpeg|png)|cincinnatiopen\.com/[^"\'\s\\]*\.(?:jpg|jpeg|png))[^"\'\s\\]*',
    re.IGNORECASE,
)
OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)


def main() -> int:
    for url in URLS:
        req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
            continue
        photos = sorted(set(PHOTO_PATTERN.findall(html)))
        og_images = OG_IMAGE_PATTERN.findall(html)
        print(f"=== {url} ===")
        print(f"photo-pattern matches: {photos}")
        print(f"og:image: {og_images[:2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
