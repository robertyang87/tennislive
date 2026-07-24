"""Round 10: si.com had a clean, unedited photo (round 9) so it's clearly
not bot-blocked -- try more si.com articles specifically about the
2012 AO trophy/result, looking for the trophy-ceremony photo itself."""

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

ARTICLES = {
    "ao2012_si_recap": "https://www.si.com/tennis/2012/01/29/29-0australian-open-2012",
    "ao2012_si_treble2016": "https://www.si.com/tennis/2016/01/15/novak-djokovic-grand-slam-history-treble",
}

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
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
    for key, article_url in ARTICLES.items():
        print(f"== {key} :: {article_url}")
        html_bytes = fetch(article_url)
        if html_bytes is None:
            continue
        html = html_bytes.decode("utf-8", errors="ignore")
        match = OG_IMAGE_RE.search(html) or OG_IMAGE_RE2.search(html)
        candidates = []
        if match:
            candidates.append(("og", match.group(1)))
        # Also grab the first couple of in-article <img> tags -- si.com
        # articles often show a caption photo separate from og:image.
        for i, img_url in enumerate(IMG_TAG_RE.findall(html)[:4]):
            candidates.append((f"img{i}", img_url))
        seen = set()
        for tag, img_url in candidates:
            if img_url in seen or "logo" in img_url.lower():
                continue
            seen.add(img_url)
            print(f"  [{tag}] {img_url}")
            img_bytes = fetch(img_url)
            if img_bytes is None:
                continue
            if len(img_bytes) < 5000:
                print("    too small, skipping save")
                continue
            dest = f"tools/_probe10_{key}_{tag}.jpg"
            with open(dest, "wb") as f:
                f.write(img_bytes)
            print(f"    saved -> {dest} ({len(img_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
