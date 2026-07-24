"""Download the NBC Sports 2019 Wimbledon candidate, plus the two
2012 Australian Open candidates, for visual verification."""

from __future__ import annotations

import sys
import urllib.request

CANDIDATES = {
    "tools/_probe_2019_nbc.jpg": (
        "https://nbcsports.brightspotcdn.com/dims4/default/e09ff05/2147483647/"
        "strip/true/crop/1024x576+0+0/resize/1440x810!/quality/90/"
        "?url=https%3A%2F%2Fnbc-sports-production-nbc-sports.s3.us-east-1.amazonaws.com"
        "%2Fbrightspot%2Ff5%2Ff8%2F71d160729c4dd618a3df756b1702%2Fgettyimages-1161676219-e1563106684632.jpg"
    ),
    "tools/_probe_2012_tennismajors.jpg": (
        "https://www.tennismajors.com/app/uploads/2025/01/Nadal-Djoko-OTD-01_30-copy.jpg"
    ),
    "tools/_probe_2012_cbsnews.jpg": (
        "https://assets1.cbsnewsstatic.com/hub/i/r/2012/01/30/13b6895f-a644-11e2-a3f0-029118418759/"
        "thumbnail/1200x630/0f14879c6472043873d30136fe685a8a/sports_aptopix_AP120129027906.jpg"
    ),
}


def main() -> int:
    for dest, url in CANDIDATES.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"{url} -> {dest} ({len(data)} bytes)")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
