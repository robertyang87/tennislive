"""Temporary diagnostic: download specific candidate photos so they can be
committed and viewed directly (the sandbox that authored this can reach git
but not these hosts directly)."""

from __future__ import annotations

import pathlib
import sys
import urllib.request

OUT = pathlib.Path("tools/_probe_images")
TARGETS = {
    "ausopen-gold-raw.jpg": (
        "https://ausopen.com/sites/default/files/202408/4/"
        "zheng-qinwen-gold-paris-2024-olympics.jpg"
    ),
    "ausopen-gold-large.jpg": (
        "https://ausopen.com/sites/default/files/styles/large/public/"
        "202408/4/zheng-qinwen-gold-paris-2024-olympics.jpg"
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
