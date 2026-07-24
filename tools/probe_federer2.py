"""Federer needs a genuine close-up on-court trophy photo (matching the
Nadal-bite/Djokovic-at-mic framing) instead of a wide celebration shot.
si.com has a dedicated photo GALLERY for the 2017 Wimbledon final --
grab multiple images from it, not just og:image. Also re-fetch Nadal
and Djokovic sources (needed again for the headroom-fix recrop)."""

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

GALLERY_ARTICLES = {
    "federer_si_gallery": "https://www.si.com/tennis/2017/07/16/wimbledon-2017-mens-final-photos-roger-federer-marin-cilic",
    "federer_si_history": "https://www.si.com/tennis/2017/07/16/roger-federer-beats-marin-cilic-wimbledon-grand-slam-title",
}

DIRECT_ARTICLES = {
    "tools/_src_djokovic.jpg": "https://www.si.com/tennis/2012/01/29/29-0australian-open-2012",
    "tools/_src_nadal.jpg": "https://www.si.com/tennis/revisiting-all-14-of-rafael-nadal-s-roland-garros-wins",
}

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
    for dest, article_url in DIRECT_ARTICLES.items():
        print(f"== {dest} :: {article_url}")
        html_bytes = fetch(article_url)
        if html_bytes is None:
            continue
        html = html_bytes.decode("utf-8", errors="ignore")
        m = OG_IMAGE_RE.search(html)
        if not m:
            print("  no og:image found")
            continue
        img_url = m.group(1)
        print(f"  og:image = {img_url}")
        data = fetch(img_url)
        if data is None:
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print(f"  saved -> {dest} ({len(data)} bytes)")

    for key, article_url in GALLERY_ARTICLES.items():
        print(f"== {key} :: {article_url}")
        html_bytes = fetch(article_url)
        if html_bytes is None:
            continue
        html = html_bytes.decode("utf-8", errors="ignore")
        candidates = []
        og = OG_IMAGE_RE.search(html)
        if og:
            candidates.append(("og", og.group(1)))
        for i, u in enumerate(IMG_TAG_RE.findall(html)[:15]):
            candidates.append((f"img{i}", u))
        seen = set()
        saved = 0
        for tag, url in candidates:
            if url in seen or "logo" in url.lower():
                continue
            seen.add(url)
            print(f"  [{tag}] {url}")
            data = fetch(url)
            if data is None or len(data) < 8000:
                print("    too small/failed, skipping")
                continue
            dest2 = f"tools/_probefed2_{key}_{tag}.jpg"
            with open(dest2, "wb") as f:
                f.write(data)
            print(f"    saved -> {dest2} ({len(data)} bytes)")
            saved += 1
            if saved >= 10:
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
