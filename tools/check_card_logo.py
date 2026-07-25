"""Say which published decks are actually carrying the new brand mark.

Written after two false all-clears in one session. Watching for a commit
whose message names the slug matched the *previous* generation's commits;
watching for the slug's output path to change matched a run that had started
before the change and checked out the older ref. Both reported done for
decks that still shipped the old logo.

So ask the picture. The mark is the one thing on the card whose colour is
fixed, and the two versions are far apart: the old clock face is pure yellow
(239,238,4), the new ball is lime (195,220,74). Sample where the icon sits
and compare.

Reads only what is committed on origin/main — the same bytes the audience
would get — and prints every deck, including the ones still on the old mark,
so silence can never read as success.
"""

from __future__ import annotations

import io
import subprocess
import sys

from PIL import Image

# Where the brand icon lands on a rendered card (2160x2880, device scale 2).
PROBES = ((196, 128), (205, 150), (200, 140), (190, 160))
NEW = (195, 220, 74)  # lime ball
OLD = (239, 238, 4)  # yellow clock face
SLUGS = (
    "hawkeye",
    "yellow-ball",
    "longest-match",
    "wimbledon-whites",
    "rufus",
    "queue",
    "masters-format",
    "ten-champions",
)


def _near(px, ref, tol=45) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px, ref))


def verdict(png: bytes) -> str:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    seen = [img.getpixel(p) for p in PROBES]
    if any(_near(p, NEW) for p in seen):
        return "new"
    if any(_near(p, OLD) for p in seen):
        return "old"
    return f"unknown {seen}"


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-26"
    ref = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
    stale = []
    for slug in SLUGS:
        path = f"output/{date}/explainer/{slug}/slide_01.png"
        try:
            png = subprocess.run(
                ["git", "show", f"{ref}:{path}"],
                capture_output=True, check=True).stdout
        except subprocess.CalledProcessError:
            print(f"  ?? {slug:18} 没有成片")
            stale.append(slug)
            continue
        got = verdict(png)
        print(f"  {'OK' if got == 'new' else '!!'} {slug:18} {got}")
        if got != "new":
            stale.append(slug)
    print(f"\n{len(SLUGS) - len(stale)}/{len(SLUGS)} 已用新 logo")
    if stale:
        print("仍是旧 logo：" + " ".join(stale))
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
