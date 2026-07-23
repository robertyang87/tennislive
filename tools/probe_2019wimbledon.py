"""Find a real photo for the 2019 Wimbledon final (Djokovic def. Federer,
first-ever fifth-set tiebreak) -- restructuring big-three to use a THIRD
distinct moment for the "today" page instead of reusing the 2012 AO
final, since sourcing two visually distinct real photos of one match
proved difficult."""

from __future__ import annotations

import re
import sys
import urllib.request

URLS = [
    "https://www.atptour.com/en/news/djokovic-federer-wimbledon-2019-final-match-analysis",
    "https://www.nbcsports.com/olympics/news/roger-federer-novak-djokovic-wimbledon",
    "https://www.forbes.com/sites/adamzagoria/2019/07/14/wimbledon-novak-djokovics-championship-win-over-roger-federer-by-the-numbers/",
    "https://www.tennis.com/pro-game/2019/12/top-moments-2019-no-2-wimbledon-final-set-tiebreak-djokovic-federer/86188/",
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
