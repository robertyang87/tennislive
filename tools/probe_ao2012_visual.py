"""Download the two size-eligible candidates for visual inspection:
perfect-tennis.com's AO-2012 article image and NPR's Laver Cup
"composites" image (name suggests a multi-photo collage, worth
checking whether it actually shows all three players)."""

from __future__ import annotations

import sys
import urllib.request

CANDIDATES = {
    "tools/_probe_ao2012_perfecttennis.jpg": (
        "https://www.perfect-tennis.com/wp-content/uploads/2020/04/Djokovic.jpg"
    ),
    "tools/_probe_laver_npr.jpg": (
        "https://media.npr.org/assets/img/2022/09/22/"
        "copy-of-composites_wide-44c1798792c6e052aa486f6921450f371c212c5b.jpg?s=1400&c=85&f=jpeg"
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
