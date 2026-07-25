"""Gather real, licensed B-roll candidates for the hawkeye explainer video.

The explainer must be image-first, not text-only. Abstract topics have no
exact-event photo, but topically-fitting, licensed images DO exist (Hawk-Eye
challenge screens, line judges, electronic line calling on court). This probe
queries every discovery provider for each of the three beats, downloads the
top candidates, and commits them plus a metadata sheet so a human can eyeball
and pick the fitting, correctly-licensed ones. It never selects on its own.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import requests
from PIL import Image

from tennislive.research.visual_sources import (
    _bing_candidates,
    _commons_candidates,
    _duckduckgo_candidates,
    _flickr_candidates,
    _official_archive_candidates,
    _openverse_candidates,
)

BEATS = {
    "mechanism": [
        "tennis player challenge call",
        "tennis hawkeye challenge point",
        "tennis review screen stadium",
        "tennis umpire overrule",
        "tennis ball mark clay",
        "tennis serve speed radar",
    ],
    "today": [
        "tennis line judge chair empty",
        "tennis stadium big screen",
        "wimbledon centre court roof",
        "tennis hard court line",
        "us open night session court",
    ],
}

PROVIDERS = (
    _commons_candidates,
    _openverse_candidates,
    _flickr_candidates,
    _official_archive_candidates,
    _bing_candidates,
    _duckduckgo_candidates,
)

OUT = Path("tools/broll")
MIN_W, MIN_H = 640, 360


def _download(url: str, session: requests.Session):
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        return img
    except Exception:  # noqa: BLE001 - a bad candidate is just skipped
        return None


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (tennislive explainer b-roll probe)"}
    )
    manifest: dict = {}
    for beat, queries in BEATS.items():
        beat_dir = OUT / beat
        beat_dir.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        gathered: list[dict] = []
        for query in queries:
            for provider in PROVIDERS:
                try:
                    for cand in provider(query, session):
                        url = str(cand.get("image_url") or "")
                        if not url or url in seen:
                            continue
                        seen.add(url)
                        cand["query"] = query
                        gathered.append(cand)
                except Exception as exc:  # noqa: BLE001
                    print(f"[{beat}] {provider.__name__} '{query}' failed: {exc}")
        gathered.sort(key=lambda c: c.get("relevance", 0), reverse=True)

        kept: list[dict] = []
        for cand in gathered:
            if len(kept) >= 8:
                break
            img = _download(cand["image_url"], session)
            if img is None or img.width < MIN_W or img.height < MIN_H:
                continue
            idx = len(kept)
            name = f"{beat}_{idx:02d}_{cand.get('provider', 'x')}.jpg"
            img.save(beat_dir / name, quality=88)
            kept.append(
                {
                    "file": f"broll/{beat}/{name}",
                    "provider": cand.get("provider"),
                    "query": cand.get("query"),
                    "source_url": cand.get("source_url"),
                    "image_url": cand.get("image_url"),
                    "credit": cand.get("credit"),
                    "license": cand.get("license"),
                    "relevance": cand.get("relevance"),
                    "size": [img.width, img.height],
                    "image_text": (cand.get("image_text") or "")[:200],
                }
            )
        manifest[beat] = kept
        print(f"[{beat}] kept {len(kept)} of {len(gathered)} gathered candidates")

    (OUT / "candidates.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote tools/broll/candidates.json")


if __name__ == "__main__":
    main()
