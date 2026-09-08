#!/usr/bin/env python3
"""Render reusable story annotations with the existing brand typography.

The manifest supplies semantic roles, not pixel styling. Output entries plug
into build_match_reel's inset field. Position remains a per-shot decision;
generated PNGs alone do not certify that a moving subject is unobstructed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from render_story_info_band import render

ROLES = {"context": "timeline", "number": "stat", "translation": "chapter"}


def build(manifest: Path, outdir: Path) -> list[dict]:
    items = json.loads(manifest.read_text(encoding="utf-8"))
    outdir.mkdir(parents=True, exist_ok=True)
    output = []
    names = set()
    for item in items:
        name = item["name"]
        if not name or Path(name).name != name or name in names:
            raise ValueError("Annotation names must be unique path basenames")
        names.add(name)
        role = item["role"]
        if role not in ROLES:
            raise ValueError(f"Unknown role: {role}")
        path = outdir / f"{name}.png"
        render(item["kicker"], item["headline"], item["detail"], path,
               metric=item.get("metric", ""), variant=ROLES[role])
        output.append({"name": name, "role": role, "placement_verified": False,
                       "inset": {"image": path.as_posix(), "kind": "story_text",
                                 "corner": "tr", "width": 0.60, "pad": 0.085,
                                 "show_for": 3.8, "motion": "editorial"}})
    (outdir / "insets.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    print(f"Rendered {len(build(args.manifest, args.outdir))} annotations")
