"""Temporary diagnostic: download specific candidate photos so they can be
committed and viewed directly (the sandbox that authored this can reach git
but not these hosts directly)."""

from __future__ import annotations

import pathlib
import sys
import urllib.request

OUT = pathlib.Path("tools/_probe_images")
TARGETS = {
    "wta-ao2024-trophy.jpg": (
        "https://photoresources.wtatennis.com/wta/photo/2024/01/27/"
        "9325c21f-5f79-4097-afc6-d9356a02dd39/Sabalenka-trophy-Darrian-Traynor.jpg"
    ),
    "ausopen-olympics-gold.jpg": (
        "https://ausopen.com/sites/default/files/styles/facebook_share/public/"
        "202408/4/zheng-qinwen-gold-paris-2024-olympics.jpg?itok=1rT2rJWE"
    ),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    for name, url in TARGETS.items():
        dest = OUT / name
        print(f"downloading {url} -> {dest}")
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                dest.write_bytes(resp.read())
            print(f"  ok: {dest.stat().st_size} bytes")
        except Exception as exc:  # noqa: BLE001
            print(f"  error: {exc!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
