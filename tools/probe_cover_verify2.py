"""Round 2: previous round's URLs all 404'd because the extracted
wp.com proxy URLs contained literal HTML-entity-encoded ampersands
(&#038;) instead of &. This round unescapes HTML entities, and also
tries the original rafaelnadalfans.com host directly (bypassing the
wp.com proxy) for the most promising filenames."""

from __future__ import annotations

import html
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

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

# Best-looking filenames from round 1 (group / three-or-four together).
PRIORITY_KEYWORDS = (
    "big-four",
    "team-europe",
    "nadal-murray-djokovic-federer",
    "andy-murray-rafael-nadal-roger-federernovak-djokovic",
    "tsitsipas-norrie-murray-nadal-djokovic-federer",
    "nadal-and-djokovic-at-gala",
)


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
    page = html_bytes.decode("utf-8", errors="ignore")
    raw_urls = IMG_TAG_RE.findall(page)
    urls = []
    seen = set()
    for u in raw_urls:
        u = html.unescape(u)
        if u in seen or "logo" in u.lower() or "avatar" in u.lower():
            continue
        seen.add(u)
        urls.append(u)

    priority = [u for u in urls if any(k in u.lower() for k in PRIORITY_KEYWORDS)]
    print(f"found {len(urls)} total, {len(priority)} priority group-photo urls")

    saved = 0
    for i, url in enumerate(priority):
        print(f"[p{i}] {url}")
        data = fetch(url)
        if data is None or len(data) < 8000:
            print("  too small/failed, skipping")
            # Fallback: try origin host directly instead of the wp.com proxy.
            m = re.search(r"rafaelnadalfans\.com(/wp-content/[^?]+)", url)
            if m:
                direct = "https://rafaelnadalfans.com" + m.group(1)
                print(f"  retry direct: {direct}")
                data = fetch(direct)
                if data is None or len(data) < 8000:
                    print("  direct also failed/too small, skipping")
                    continue
                url = direct
        dest = f"tools/_probecover2_p{i}.jpg"
        with open(dest, "wb") as f:
            f.write(data)
        print(f"  saved -> {dest} ({len(data)} bytes) from {url}")
        saved += 1
    print(f"saved {saved} priority images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
