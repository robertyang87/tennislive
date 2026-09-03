"""Render an HTML file to a PNG so a human can look at it before it ships.

Written after a push went out with the caption printed twice. Every string
assertion passed — the text was there, the hint was there, the tags were
there — because assertions check for presence, and the bug was duplication.
One screenshot would have caught it.

So: before sending any page (push body, copy page), render it and open the
PNG. Images will be broken offline; that is fine, the layout is the point.

    python tools/preview_html.py output/<date>/explainer/<slug>/push.html
    python tools/preview_html.py push.html --width 420 --tail 3000

--tail additionally writes a crop of the last N pixels, since the part worth
checking is usually the bottom of a very long page.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The sandbox ships Chromium under a versioned directory that Playwright's own
# lookup misses. `tennislive.chromium.launch_chromium` is the single place that
# solves it — never keep a second copy here that can drift.


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--width", type=int, default=420, help="phone-ish viewport")
    ap.add_argument("--tail", type=int, default=0, help="also crop the last N px")
    args = ap.parse_args()

    if not args.html.is_file():
        print(f"没有这个文件：{args.html}", file=sys.stderr)
        return 2
    out = args.out or args.html.with_suffix(".preview.png")

    from playwright.sync_api import sync_playwright

    from tennislive.chromium import launch_chromium

    with sync_playwright() as pw:
        browser = launch_chromium(pw, args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": args.width, "height": 900}, device_scale_factor=2
        )
        page.goto(args.html.resolve().as_uri())
        page.wait_for_timeout(600)
        page.screenshot(path=str(out), full_page=True)
        browser.close()

    from PIL import Image

    with Image.open(out) as im:
        print(f"{out}  {im.size[0]}x{im.size[1]}")
        if args.tail:
            crop = out.with_name(out.stem + f".tail{out.suffix}")
            im.crop((0, max(0, im.height - args.tail), im.width, im.height)).save(crop)
            print(f"{crop}  （末 {args.tail}px）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
