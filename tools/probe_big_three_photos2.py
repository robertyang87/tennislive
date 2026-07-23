"""Second round: find a real photo for the 2008 Wimbledon final (story
page) and a second distinct real photo for the 2012 Australian Open
final (explainer/today already have the AusOpen memorable-moments shot
as one candidate). Check tennis.com's own article, and resolve the
direct original-file URL for the Wikimedia Commons file found via
search (avoiding the /thumb/ on-demand-resize path that proved
unreliable earlier this session)."""

from __future__ import annotations

import re
import sys
import urllib.request

TENNIS_COM_URL = (
    "https://www.tennis.com/news/articles/"
    "2008-rafael-nadal-and-roger-federer-produced-a-quantum-leap-in-quality-and-enter"
)
COMMONS_FILE_PAGE = (
    "https://commons.wikimedia.org/wiki/"
    "File:Wimbledon_Men's_final_2008,_Federer_serves_for_3rd_set.jpg"
)

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)
ORIGINAL_FILE_PATTERN = re.compile(
    r'https://upload\.wikimedia\.org/wikipedia/commons/[0-9a-f]/[0-9a-f]{2}/[^"\'\s]+'
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main() -> int:
    try:
        html = fetch(TENNIS_COM_URL)
        print(f"=== {TENNIS_COM_URL} ===")
        print(f"og:image: {OG_IMAGE_PATTERN.findall(html)[:3]}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {TENNIS_COM_URL}: {exc}")

    try:
        html = fetch(COMMONS_FILE_PAGE)
        originals = sorted(set(ORIGINAL_FILE_PATTERN.findall(html)))
        # Drop any /thumb/ variants -- only keep true original-file links.
        originals = [u for u in originals if "/thumb/" not in u]
        print(f"=== {COMMONS_FILE_PAGE} ===")
        print(f"original file candidates: {originals}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {COMMONS_FILE_PAGE}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
