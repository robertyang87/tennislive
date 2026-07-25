"""Walk Commons category trees to depth, instead of only their top level.

Every previous pass listed a category's direct members and concluded from a
thin result that the photographs did not exist. Commons does not work that
way: "Category:US Open (tennis)" holds almost no files itself, because the
pictures live in year and event subcategories several levels down. This walks
the tree, collects every image with its licence and shooting year, ranks
newest-first and downloads the best of each root for human review.

Also asks PetScan, which can do the same traversal server-side, as a check
that the local walk is not missing branches.
"""

from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
PETSCAN = "https://petscan.wmcloud.org/"
OUT = Path("tools/broll")

# root -> how deep to walk
# Commons keeps the per-year tournaments under a "... by year" container, not
# directly under the tournament — which is why three passes walking from
# "Category:French Open" found nothing recent and were misread as "no photos".
# Guessing year-category names has now failed four times ("2025 French Open",
# "2025 Roland Garros", "2026 French Open"...). Ask the by-year container which
# editions it actually holds and walk the newest ones.
YEAR_CONTAINERS = {
    "rg": "Category:French Open by year",
}
# Beat 5 says clay keeps the ball's mark; these categories are where a frame
# of an actual mark, or an umpire reading one, would live.
EXTRA_ROOTS = {
    "ballmark": ("Category:Tennis ball marks", 1),
    "clay": ("Category:Clay tennis courts", 1),
}
NEWEST_EDITIONS = 2
ROOTS: dict[str, tuple[str, int]] = {}

FREE = ("cc by", "cc by-sa", "cc0", "public domain", "pd-")
MIN_W, MIN_H = 1200, 800
PER_ROOT = 16
MAX_CATEGORIES = 40  # keep a deep walk from turning into a full crawl


def _api(**params):
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    last = None
    for attempt in range(5):
        try:
            time.sleep(0.2)
            r = requests.get(
                API,
                params=params,
                timeout=30,
                headers={"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"},
            )
            if r.status_code == 429:
                time.sleep(4 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.2 * (attempt + 1))
    print(f"    !! {last}")
    return {}


def _members(title: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        data = _api(list="categorymembers", cmtitle=title, cmtype=kind,
                    cmlimit="max", **cont)
        out += [m["title"] for m in (data.get("query") or {}).get("categorymembers", [])]
        cont = data.get("continue") or {}
        if not cont:
            return out


def _plain(raw) -> str:
    keep, buf = True, []
    for ch in str(raw):
        if ch == "<":
            keep = False
        elif ch == ">":
            keep = True
        elif keep:
            buf.append(ch)
    return " ".join("".join(buf).split())


def _year(text: str) -> int:
    """First plausible four-digit year in `text`.

    Splitting on whitespace missed every category, because "Category:2024
    French Open" tokenises to "Category:2024" — not a bare number — so all 38
    editions of each tournament were discarded as undated.
    """
    for match in re.findall(r"(?<!\d)(19|20)(\d{2})(?!\d)", str(text)):
        y = int(match[0] + match[1])
        if 1970 < y < 2100:
            return y
    return 0


def _walk(root: str, depth: int) -> tuple[list[str], list[str]]:
    """Return (file titles, categories visited) for the tree under `root`."""
    seen_cats, files, frontier = set(), [], [(root, 0)]
    while frontier and len(seen_cats) < MAX_CATEGORIES:
        cat, level = frontier.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        files += _members(cat, "file")
        if level < depth:
            for sub in _members(cat, "subcat"):
                if sub not in seen_cats:
                    frontier.append((sub, level + 1))
    return list(dict.fromkeys(files)), sorted(seen_cats)


def _describe(titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 20):
        data = _api(titles="|".join(titles[i : i + 20]), prop="imageinfo|categories",
                    iiprop="url|extmetadata|size", cllimit="max")
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("url"):
                continue
            meta = info.get("extmetadata") or {}
            cats = [c.get("title", "") for c in page.get("categories") or []]
            date = _plain((meta.get("DateTimeOriginal") or {}).get("value", "")) or _plain(
                (meta.get("DateTime") or {}).get("value", "")
            )
            year = _year(date) or max((_year(c) for c in cats), default=0)
            out.append(
                {
                    "title": page.get("title", ""),
                    "url": info["url"],
                    "size": [info.get("width", 0), info.get("height", 0)],
                    "licence": _plain((meta.get("LicenseShortName") or {}).get("value", "")),
                    "artist": _plain((meta.get("Artist") or {}).get("value", ""))[:80],
                    "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:200],
                    "year": year,
                    "cats": cats[:8],
                }
            )
    return out


def _petscan(category: str, depth: int) -> list[str]:
    try:
        r = requests.get(
            PETSCAN,
            params={
                "language": "commons",
                "project": "wikimedia",
                "categories": category.removeprefix("Category:"),
                "depth": depth,
                "ns[6]": 1,
                "format": "json",
                "doit": "1",
            },
            timeout=60,
            headers={"User-Agent": "tennislive/1.0"},
        )
        r.raise_for_status()
        rows = (r.json().get("*") or [{}])[0].get("a", {}).get("*", [])
        return [x.get("title", "") for x in rows]
    except Exception as exc:  # noqa: BLE001
        print(f"    !! petscan {category}: {exc}")
        return []


def _discover_roots() -> dict[str, tuple[str, int]]:
    """Name the newest editions from the by-year container itself."""
    roots: dict[str, tuple[str, int]] = {}
    for prefix, container in YEAR_CONTAINERS.items():
        editions = _members(container, "subcat")
        dated = sorted(
            ((_year(c), c) for c in editions if _year(c)),
            reverse=True,
        )
        print(f"\n##### {container}: {len(editions)} editions; newest:")
        for year, cat in dated[:6]:
            print(f"    {year}  {cat}")
        for year, cat in dated[:NEWEST_EDITIONS]:
            roots[f"{prefix}{year}"] = (cat, 2)
    roots.update(EXTRA_ROOTS)
    return roots


def main() -> None:
    manifest: dict = {}
    for slot, (root, depth) in _discover_roots().items():
        titles, cats = _walk(root, depth)
        # Describing thousands of files is what pushed the job past its
        # timeout; a couple of hundred is plenty to choose from.
        titles = titles[:240]
        print(f"\n===== {slot}: walked {len(cats)} categories, {len(titles)} files")
        for c in cats[:40]:
            print(f"    {c}")
        rows = _describe(titles)
        usable = [
            r for r in rows
            if any(f in (r["licence"] or "").lower() for f in FREE)
            and r["size"][0] >= MIN_W and r["size"][1] >= MIN_H
        ]
        usable.sort(key=lambda r: r["year"], reverse=True)
        print(f"  -> {len(usable)} usable of {len(rows)} described")

        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        kept = []
        for r in usable:
            if len(kept) >= PER_ROOT:
                break
            try:
                resp = requests.get(r["url"], timeout=40,
                                    headers={"User-Agent": "tennislive/1.0"})
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:  # noqa: BLE001
                continue
            name = f"{slot}_{len(kept):02d}_{r['year']}.jpg"
            img.save(slot_dir / name, quality=88)
            r["file"] = f"{slot}/{name}"
            kept.append(r)
            print(f"  [{len(kept)-1}] {r['year']} {r['size']} {r['licence']}")
            print(f"      {r['title']}")
            print(f"      {r['desc'][:120]}")
        manifest[slot] = kept

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "deep_commons.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nwrote tools/broll/deep_commons.json")


if __name__ == "__main__":
    main()
