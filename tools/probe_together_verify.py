"""Round 2: check more 2012 AO candidates for a larger photo, and
download the promising 2008/2019 candidates for visual verification."""

from __future__ import annotations

import io
import re
import sys
import urllib.request

from PIL import Image

OG_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE
)

AO2012_URLS = [
    "https://www.tennismajors.com/atp/january-29-2012-the-day-djokovic-and-nadal-played-5-hours-and-53-minutes-in-the-final-of-the-australian-open-805883.html",
    "https://www.tennis.com/news/articles/moment-6-1-37-a-m-djokovic-topples-nadal-grandiose-grunt-filled-australian-open",
    "https://www.sportskeeda.com/tennis/news-even-let-rafael-nadal-get-chair-first-olive-branch-extended-fans-recall-novak-djokovic-s-classy-gesture-6-hour-australian-open-final",
    "https://www.cbsnews.com/pictures/2012-australian-open/",
]

DOWNLOAD_CANDIDATES = {
    "tools/_probe_2008_tennis365.jpg": (
        "https://d2me2qg8dfiw8u.cloudfront.net/content/uploads/2022/04/06115036/"
        "Roger-Federer-and-Rafael-Nadal-at-Wimbledon-2008.jpg"
    ),
    "tools/_probe_2019_yahoo.jpg": (
        "https://s.yimg.com/ny/api/res/1.2/RMNSjMso1KhVL7ZB7fLZpA--/"
        "YXBwaWQ9aGlnaGxhbmRlcjt3PTEyMDA7aD04MTc7Y2Y9d2VicA--/"
        "https://s.yimg.com/os/creatr-images/2019-07/59432fa0-a684-11e9-af9f-a2f392d9a228"
    ),
}


def check_og(url: str) -> None:
    print(f"=== {url} ===")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        og_images = OG_IMAGE_PATTERN.findall(html)
        print(f"og:image: {og_images[:3]}")
        if og_images:
            img_url = og_images[0].replace("&amp;", "&")
            img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
            with urllib.request.urlopen(img_req, timeout=15) as resp:
                data = resp.read()
            image = Image.open(io.BytesIO(data))
            print(f"  -> {image.width}x{image.height} ({len(data)} bytes)")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED {url}: {exc}")


def download(dest: str, url: str) -> None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennislive-probe/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"{url} -> {dest} ({len(data)} bytes)")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED download {url}: {exc}")


def main() -> int:
    print("##### 2012 Australian Open round 2 #####")
    for url in AO2012_URLS:
        check_og(url)
    print("\n##### download candidates for visual check #####")
    for dest, url in DOWNLOAD_CANDIDATES.items():
        download(dest, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
