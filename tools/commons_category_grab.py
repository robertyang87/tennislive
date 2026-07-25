"""Pull candidate photos out of Wikimedia Commons *categories*, not free text.

Free-text search kept missing the obvious: querying "Court Philippe Chatrier"
returned nothing usable, while Commons has a whole category of exactly those
photos. For a named venue or a named event, the category IS the answer — and it
doubles as the provenance we need, since a file sitting in
"Category:Court Philippe Chatrier" is documented as that court by the source
itself rather than by our reading of the pixels.

For each seed term this searches the category namespace, then downloads the
files inside the best-matching categories together with their licence and
description. Selection stays human: every frame is eyeballed before use.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll")
MIN_W, MIN_H = 1000, 700
PER_SEED = 10

# slot -> category seed terms (most specific first)
SEEDS: dict[str, list[str]] = {
    "chatrier": [
        "Court Philippe Chatrier",
        "Stade Roland Garros",
    ],
    "us_open_match": [
        "2004 US Open (tennis)",
        "Serena Williams",
        "Arthur Ashe Stadium",
        "US Open (tennis)",
        "USTA Billie Jean King National Tennis Center",
    ],
}

FREE = ("cc by", "cc by-sa", "cc0", "public domain", "pd-")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {"User-Agent": "tennislive/1.0 (contact: github.com/robertyang87/tennislive)"}
    )
    return s


def _api(session: requests.Session, **params) -> dict:
    """Query the API, returning {} instead of raising on a bad response.

    One malformed reply (an HTML error page, a throttle notice) must not take
    down a whole gathering run, so callers get an empty result and move on.
    """
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    for attempt in range(3):
        try:
            resp = session.post(API, data=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                print(f"  !! api {params.get('list') or params.get('prop')}: {exc}")
                return {}
    return {}


def _find_categories(session: requests.Session, seed: str) -> list[str]:
    data = _api(
        session, list="search", srsearch=seed, srnamespace=14, srlimit=6
    )
    hits = [h["title"] for h in data.get("query", {}).get("search", [])]
    exact = f"Category:{seed}"
    return [exact] + [h for h in hits if h != exact]


def _category_files(session: requests.Session, category: str) -> list[str]:
    data = _api(
        session,
        list="categorymembers",
        cmtitle=category,
        cmtype="file",
        cmlimit=60,
    )
    return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]


def _file_info(session: requests.Session, titles: list[str]) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(titles), 10):
        chunk = titles[i : i + 10]
        data = _api(
            session,
            titles="|".join(chunk),
            prop="imageinfo",
            iiprop="url|extmetadata|size",
        )
        for page in data.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("url"):
                continue
            meta = info.get("extmetadata") or {}

            def val(key: str) -> str:
                raw = str((meta.get(key) or {}).get("value", ""))
                keep, buf = True, []
                for ch in raw:
                    if ch == "<":
                        keep = False
                    elif ch == ">":
                        keep = True
                    elif keep:
                        buf.append(ch)
                return " ".join("".join(buf).split())

            out.append(
                {
                    "title": page.get("title"),
                    "url": info["url"],
                    "width": info.get("width", 0),
                    "height": info.get("height", 0),
                    "desc": val("ImageDescription")[:300],
                    "date": val("DateTimeOriginal") or val("DateTime"),
                    "artist": val("Artist"),
                    "license": val("LicenseShortName"),
                }
            )
    return out


def main() -> None:
    session = _session()
    slots = sys.argv[1:] or list(SEEDS)
    manifest: dict = {}
    for slot in slots:
        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
        kept: list[dict] = []
        seen: set[str] = set()
        rejects: dict[str, int] = {}
        for seed in SEEDS[slot]:
            for category in _find_categories(session, seed):
                try:
                    titles = _category_files(session, category)
                except Exception as exc:  # noqa: BLE001
                    print(f"[{slot}] {category}: {exc}")
                    continue
                if not titles:
                    continue
                print(f"[{slot}] {category}: {len(titles)} files")
                for info in _file_info(session, titles):
                    if len(kept) >= PER_SEED:
                        break
                    if info["url"] in seen:
                        continue
                    seen.add(info["url"])
                    lic = (info["license"] or "").lower()
                    if not any(lic.startswith(f) or f in lic for f in FREE):
                        rejects["licence"] = rejects.get("licence", 0) + 1
                        continue
                    if info["width"] < MIN_W or info["height"] < MIN_H:
                        rejects["size"] = rejects.get("size", 0) + 1
                        continue
                    try:
                        resp = session.get(info["url"], timeout=30)
                        resp.raise_for_status()
                        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    except Exception:  # noqa: BLE001
                        continue
                    if img.width < MIN_W or img.height < MIN_H:
                        continue
                    name = f"{slot}_{len(kept):02d}.jpg"
                    img.save(slot_dir / name, quality=88)
                    info["file"] = f"broll/{slot}/{name}"
                    info["category"] = category
                    info["size"] = [img.width, img.height]
                    kept.append(info)
                if len(kept) >= PER_SEED:
                    break
            if len(kept) >= PER_SEED:
                break
        manifest[slot] = kept
        print(f"[{slot}] kept {len(kept)}; dropped {rejects or 'none'}")

    path = OUT / "categories.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
