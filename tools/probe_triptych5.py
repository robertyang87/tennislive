"""Correction round 2: user wants ON-COURT trophy-ceremony photos only,
not post-match staged photocalls. Both the Federer black-background
kiss and the Djokovic outdoor-tree kiss turned out to be staged
photocalls. Re-fetch confirmed on-court alternatives:
- Federer: cbssports.com's 2017 Wimbledon recap (arms raised, Centre
  Court crowd clearly visible behind him -- genuinely on-court).
- Djokovic: si.com's 2012 AO recap (holding trophy at the microphone
  during the actual podium ceremony, Nadal blurred behind, crowd/flags
  visible -- the same photo already used for the explainer page,
  confirmed on-court).
Nadal's photo (biting trophy, blurred stadium crowd) is already
confirmed on-court and does not need re-fetching."""

from __future__ import annotations

import re
import sys
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

ARTICLE_URLS = {
    "tools/_probetrip5_federer_oncourt.jpg": (
        "https://www.cbssports.com/tennis/news/wimbledon-2017-roger-"
        "federer-rolls-to-a-record-eighth-title-19th-grand-slam-win/"
    ),
    "tools/_probetrip5_djokovic_oncourt.jpg": (
        "https://www.si.com/tennis/2012/01/29/29-0australian-open-2012"
    ),
}

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
        print(f"  FAILED fetch {url}: {exc}")
        return None


def main() -> int:
    for dest, article_url in ARTICLE_URLS.items():
        print(f"== {dest} :: {article_url}")
        html_bytes = fetch(article_url)
        if html_bytes is None:
            continue
        html = html_bytes.decode("utf-8", errors="ignore")
        m = OG_IMAGE_RE.search(html)
        if not m:
            print("  no og:image found")
            continue
        img_url = m.group(1)
        print(f"  og:image = {img_url}")
        data = fetch(img_url)
        if data is None:
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print(f"  saved -> {dest} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
