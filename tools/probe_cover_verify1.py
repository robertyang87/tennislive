"""Cover photo re-search: user wants a POSED, frontal-facing group photo
of the three (Federer/Nadal/Djokovic) instead of the candid RG2025
embrace crop. Try the rafaelnadalfans.com gala-dinner article, which
should re-host Getty photos from the posed 2022 Laver Cup gala dinner
photocall (all four -- Federer/Nadal/Djokovic/Murray -- facing camera)."""

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

ARTICLE_URL = (
    "https://rafaelnadalfans.com/2022/09/22/photos-rafael-nadal-roger-"
    "federer-novak-djokovic-andy-murray-enjoy-gala-dinner-before-laver-cup/"
)

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def fetch(url: str, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED fetch {url}: {exc}")
        return None


def main() -> int:
    html_bytes = fetch(ARTICLE_URL)
    if html_bytes is None:
        return 1
    html = html_bytes.decode("utf-8", errors="ignore")
    og = OG_IMAGE_RE.search(html)
    urls = []
    if og:
        urls.append(("og", og.group(1)))
    for i, u in enumerate(IMG_TAG_RE.findall(html)):
        if "logo" in u.lower() or "icon" in u.lower() or "avatar" in u.lower():
            continue
        urls.append((f"img{i}", u))
    seen = set()
    saved = 0
    for tag, url in urls:
        if url in seen:
            continue
        seen.add(url)
        print(f"[{tag}] {url}")
        data = fetch(url)
        if data is None or len(data) < 8000:
            print("  too small/failed, skipping")
            continue
        dest = f"tools/_probecover_{tag}.jpg"
        with open(dest, "wb") as f:
            f.write(data)
        print(f"  saved -> {dest} ({len(data)} bytes)")
        saved += 1
        if saved >= 10:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
