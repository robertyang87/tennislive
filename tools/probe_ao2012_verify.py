"""Download the Sky Sports and Fox News AO-2012 candidates for visual
inspection. The Sky Sports CDN path (19/01) suggests a 2019 upload,
so its actual content needs checking before use -- same caution as the
earlier Forbes false positives."""

from __future__ import annotations

import sys
import urllib.request

CANDIDATES = {
    "tools/_probe_ao2012_skysports.jpg": (
        "https://e0.365dm.com/19/01/1600x900/skysports-rafael-nadal-novak-djokovic_4556818.jpg?20190125124546"
    ),
    "tools/_probe_ao2012_foxnews.jpg": (
        "https://static.foxnews.com/foxnews.com/content/uploads/2018/09/nadal-1-australia.jpg"
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
