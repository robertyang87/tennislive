"""Visually verify the SI.com and EssentiallySports candidates before
use. The EssentiallySports Getty ID (168087103) looks anomalously low
for a 2022 photo -- Getty IDs climb roughly with time, and IDs in that
range are typically far older -- so it may be a mismatched stock image
despite the article being about Laver Cup 2022."""

from __future__ import annotations

import sys
import urllib.request

CANDIDATES = {
    "tools/_probe_laver_si.jpg": (
        "https://www.si.com/.image/c_fill,w_1440,ar_1440:810,f_auto,q_auto,g_auto/"
        "MTkyNjYyMDM4MjU2ODIxNjg0/roger-federer-rafael-nadal.jpg"
    ),
    "tools/_probe_laver_essentiallysports.jpg": (
        "https://image-cdn.essentiallysports.com/wp-content/uploads/GettyImages-168087103.jpg"
    ),
}


def download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    print(f"{url} -> {dest} ({len(data)} bytes)")


def main() -> int:
    for dest, url in CANDIDATES.items():
        try:
            download(url, dest)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {url}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
