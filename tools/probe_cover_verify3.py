"""Check whether a larger source resolution exists for the chosen
Laver Cup gala-dinner group photo, by requesting the wp.com Photon
proxy with an explicit large width, and by trying the raw origin URL
directly (bypassing the proxy)."""

from __future__ import annotations

import sys
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

CANDIDATES = {
    "tools/_probecover3_proxy_w2000.jpg": (
        "https://i1.wp.com/rafaelnadalfans.com/wp-content/uploads/2022/09/"
        "Nadal-Murray-Djokovic-Federer-2022-Gala-Dinner-Laver-Cup-photo.jpg"
        "?w=2000&ssl=1"
    ),
    "tools/_probecover3_origin.jpg": (
        "https://rafaelnadalfans.com/wp-content/uploads/2022/09/"
        "Nadal-Murray-Djokovic-Federer-2022-Gala-Dinner-Laver-Cup-photo.jpg"
    ),
    "tools/_probecover3_proxy2_w2000.jpg": (
        "https://i1.wp.com/rafaelnadalfans.com/wp-content/uploads/2022/09/"
        "Nadal-Murray-Djokovic-Federer-2022-Gala-Dinner-Laver-Cup-3.jpg"
        "?w=2000&ssl=1"
    ),
}


def fetch(url: str, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {url}: {exc}")
        return None


def main() -> int:
    for dest, url in CANDIDATES.items():
        data = fetch(url)
        if data is None:
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print(f"{url} -> {dest} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
