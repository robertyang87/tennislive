"""List images used on Wikipedia's "Big Three (tennis)" article --
might include a genuine Commons photo showing all three together,
distinct from the NPR headshot composite already picked for cover."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

TITLE = "Big Three (tennis)"

API_URL = (
    "https://en.wikipedia.org/w/api.php?action=query&prop=images&imlimit=100"
    "&format=json&titles=" + urllib.parse.quote(TITLE)
)


def main() -> int:
    req = urllib.request.Request(API_URL, headers={"User-Agent": "tennislive-probe/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        for img in page.get("images", []):
            print(img.get("title"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
