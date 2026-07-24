"""Find a tighter Federer trophy-kiss close-up (matching the close-up
style of the Nadal/Djokovic panels) instead of the wide arms-raised
celebration shot, which crops badly at narrow triptych-strip width."""

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
    "federer_si_tribute": "https://www.si.com/tennis/2017/07/16/roger-federer-wins-wimbledon-athletes-reactions",
    "federer_si_grace": "https://www.si.com/tennis/2017/07/19/roger-federer-wimbledon-venus-williams",
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
    for key, article_url in ARTICLES.items():
        print(f"== {key} :: {article_url}")
        html_bytes = fetch(article_url)
        if html_bytes is None:
            continue
        html = html_bytes.decode("utf-8", errors="ignore")
        candidates = []
        og = OG_IMAGE_RE.search(html)
        if og:
            candidates.append(("og", og.group(1)))
        for i, u in enumerate(IMG_TAG_RE.findall(html)[:5]):
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
            dest = f"tools/_probetrip3_{key}_{tag}.jpg"
            with open(dest, "wb") as f:
                f.write(data)
            print(f"    saved -> {dest} ({len(data)} bytes)")
            saved += 1
            if saved >= 2:
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
