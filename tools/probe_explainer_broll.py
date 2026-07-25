"""Gather real, licensed B-roll for the hawkeye explainer, slot by slot.

The explainer must be image-first AND each hero photo must actually match the
beat it illustrates — a Wimbledon grass shot cannot illustrate "Roland-Garros
still keeps human line judges". So this probe is organised by SLOT (the beat
that needs a picture), each with queries aimed at that slot's exact subject.

It downloads candidates and writes a metadata sheet. It never selects on its
own: a human eyeballs every frame before it is promoted into assets/.
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

# Each slot names the beat that needs a picture, then the queries that would
# surface that exact subject. Queries are ordered most-specific first.
SLOTS: dict[str, list[str]] = {
    # 法网例外：红土 + 人工司线 + 球印，这是整条视频最关键的一张
    "roland_garros": [
        "roland garros clay court match",
        "french open philippe chatrier court",
        "roland garros line judge",
        "french open clay court player",
        "roland garros stadium clay",
    ],
    # 红土球印特写——法网坚持人工的“底气”
    "ball_mark": [
        "tennis ball mark clay court",
        "clay court ball mark umpire check",
        "tennis clay court line ball print",
        "tennis umpire inspecting clay mark",
    ],
    # 百年人工司线员
    "line_judge": [
        "tennis line judge court",
        "wimbledon line judge uniform",
        "tennis lineswoman official",
        "tennis line umpire standing court",
    ],
    # 挑战回放大屏
    "challenge": [
        "tennis hawkeye challenge screen stadium",
        "tennis stadium big screen replay",
        "tennis player challenge call crowd",
        "tennis review screen court",
    ],
    # 电子司线 / 硬地空无司线员
    "electronic": [
        "us open court electronic line calling",
        "australian open court camera",
        "tennis hard court line camera",
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
# Full-bleed hero on a 1080x1440 card -> reject anything that would look mushy.
MIN_W, MIN_H = 900, 600
PER_SLOT = 10


def _download(url: str, session: requests.Session):
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:  # noqa: BLE001 - a bad candidate is just skipped
        return None


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (tennislive explainer b-roll probe)"}
    )
    manifest: dict = {}
    for slot, queries in SLOTS.items():
        slot_dir = OUT / slot
        slot_dir.mkdir(parents=True, exist_ok=True)
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
                    print(f"[{slot}] {provider.__name__} '{query}' failed: {exc}")
        gathered.sort(key=lambda c: c.get("relevance", 0), reverse=True)

        kept: list[dict] = []
        for cand in gathered:
            if len(kept) >= PER_SLOT:
                break
            img = _download(cand["image_url"], session)
            if img is None or img.width < MIN_W or img.height < MIN_H:
                continue
            idx = len(kept)
            name = f"{slot}_{idx:02d}_{cand.get('provider', 'x')}.jpg"
            img.save(slot_dir / name, quality=88)
            kept.append(
                {
                    "file": f"broll/{slot}/{name}",
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
        manifest[slot] = kept
        print(f"[{slot}] kept {len(kept)} of {len(gathered)} gathered candidates")

    (OUT / "candidates.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote tools/broll/candidates.json")


if __name__ == "__main__":
    main()
