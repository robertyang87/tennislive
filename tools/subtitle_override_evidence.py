"""Check deliberate per-film subtitle anchors against retained QC/ASS evidence.

A single-film adjustment is not a new global default. This verifier does not
approve geometry automatically: a concrete written collision assessment remains
required, together with the matching rendered subtitle artifact and hash chain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def override_problem(spec_path: Path, root: Path) -> str | None:
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    top = spec.get("subtitle_top")
    if not isinstance(top, int) or isinstance(top, bool) or not 0 < top < 1440:
        return "subtitle_top must be an explicit in-canvas integer"
    why = str(spec.get("_subtitle_top_why") or "").strip()
    if len(why) < 20:
        return "subtitle override needs a concrete collision assessment"
    for out in sorted((root / "output").glob(f"*/reel/{spec_path.stem}"), reverse=True):
        try:
            qc_raw = (out / "qc_attestation.json").read_bytes()
            qc = json.loads(qc_raw)
            render = json.loads((out / "render.json").read_bytes())
            ass_raw = (out / "subtitles.ass").read_bytes()
        except (OSError, ValueError):
            continue
        if (qc.get("status") != "pass" or qc.get("slug") != spec_path.stem
                or qc.get("spec_sha256") != _sha(raw)
                or qc.get("ass_sha256") != _sha(ass_raw)
                or render.get("qc_attestation_sha256") != _sha(qc_raw)
                or not qc.get("film_sha256")
                or render.get("film_sha256") != qc["film_sha256"]):
            continue
        fields = None
        for line in ass_raw.decode("utf-8").splitlines():
            if line.startswith("Format: Name,"):
                fields = [field.strip() for field in line.split(":", 1)[1].split(",")]
            if line.startswith("Style: TL,") and fields:
                style = dict(zip(fields, line.split(":", 1)[1].strip().split(",")))
                if style.get("MarginV") == str(top):
                    return None
    return "no matching QC-bound ASS proves this exact per-film subtitle anchor"
