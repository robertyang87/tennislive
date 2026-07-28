"""Say whether the published cover is the one this code renders.

The lesson from the brand-mark evening: every indirect signal lied. A
commit message matched the previous generation, a changed output path
matched a run that started before the change, and a guess about the cause
was simply wrong. Only the picture told the truth.

So render the cover locally from the current code and compare it with the
one committed on origin/main. The comparison is the mean brightness of the
band where the cover scrim was lightened — the upper middle, which the old
62% wash held dark and the new one lets the photo through. A published
cover built from older code sits far below its local twin; a matching one
sits within a couple of levels.

Prints every deck, stale ones included, so silence cannot pass for success.

One limit worth knowing: the test only has power where the scrim changed
the picture. A cover whose photo is already very dark (masters-format's
Sinner on shaded clay) barely moves either way, so an OK there means "not
shown to be stale" rather than "confirmed current" — check that one by eye.
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.render.tournament_story import find_story_by_slug  # noqa: E402
from tennislive.video.explainer import (  # noqa: E402
    _OPENINGS,
    _SCRIPTS,
    explainer_script,
    render_explainer_slides,
)

BAND = (0, 380, 2160, 1150)  # upper middle of the 2160x2880 card
TOL = 6.0  # levels of mean brightness


def _brightness(png: bytes) -> float:
    img = Image.open(io.BytesIO(png)).convert("L").crop(BAND)
    return ImageStat.Stat(img).mean[0]


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-26"
    ref = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
    stale: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for slug in _SCRIPTS:
            story = find_story_by_slug(slug)
            out = Path(tmp) / slug
            out.mkdir(parents=True, exist_ok=True)
            render_explainer_slides(
                explainer_script(story)[:1], out,
                topic=(_OPENINGS.get(slug) or {}).get("topic", ""),
            )
            want = _brightness((out / "slide_00.png").read_bytes())
            path = f"output/{date}/explainer/{slug}/slide_00.png"
            try:
                got = _brightness(subprocess.run(
                    ["git", "show", f"{ref}:{path}"],
                    capture_output=True, check=True).stdout)
            except subprocess.CalledProcessError:
                print(f"  ?? {slug:18} 没有成片")
                stale.append(slug)
                continue
            ok = abs(got - want) <= TOL
            print(f"  {'OK' if ok else '!!'} {slug:18} 已发布 {got:6.1f}  本地 {want:6.1f}"
                  f"  差 {got - want:+5.1f}")
            if not ok:
                stale.append(slug)
    print(f"\n{len(_SCRIPTS) - len(stale)}/{len(_SCRIPTS)} 封面与当前代码一致")
    if stale:
        print("仍是旧封面：" + " ".join(stale))
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
