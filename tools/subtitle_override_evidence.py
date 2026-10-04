"""Check deliberate per-film subtitle anchors against retained QC/ASS evidence.

A single-film adjustment is not a new global default. This verifier does not
approve geometry automatically: a concrete written collision assessment remains
required, together with the matching rendered subtitle artifact and hash chain.
This proves retained subtitle geometry only; current-film publication still
requires the separate complete spec/film QC chain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _same_subtitle_inputs(spec: dict, out: Path, qc: dict, render: dict) -> bool:
    """封面文案不改变已烧字幕；源片、段落或布局变化不能借旧证据。"""
    from render_inputs import canonical, project

    try:
        raw = (out / "render_inputs.json").read_bytes()
        manifest = json.loads(raw)
        digest = _sha(raw)
        projection = manifest["projection"]
        if (qc.get("render_inputs_sha256") != digest
                or render.get("render_inputs_sha256") != digest
                or manifest.get("spec_sha256") != qc.get("spec_sha256")
                or manifest.get("film_sha256") != qc.get("film_sha256")
                or manifest.get("projection_sha256") != _sha(canonical(projection).encode())
                or (manifest.get("artifacts") or {}).get("subtitles.ass") != qc.get("ass_sha256")):
            return False
        # 只放与正片字幕无关的封面/编辑计划；其他渲染输入全部逐字节相等。
        current = project(spec)
        retained = dict(projection)
        for key in ("cover", "editorial"):
            current.pop(key, None)
            retained.pop(key, None)
        return canonical(current) == canonical(retained)
    except (OSError, ValueError, KeyError, TypeError):
        return False


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
                or qc.get("ass_sha256") != _sha(ass_raw)
                or render.get("qc_attestation_sha256") != _sha(qc_raw)
                or not qc.get("film_sha256")
                or render.get("film_sha256") != qc["film_sha256"]):
            continue
        if qc.get("spec_sha256") != _sha(raw) and not _same_subtitle_inputs(spec, out, qc, render):
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
