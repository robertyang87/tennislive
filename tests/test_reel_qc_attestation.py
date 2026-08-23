from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_reel_landed as landed  # noqa: PLC0415
    return landed


def test_L2凭证绑定spec字幕与成片并回写render(tmp_path):
    landed = _tool()
    spec_path = tmp_path / "demo.json"
    spec = {"slug": "demo", "segments": []}
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    film = tmp_path / "demo.mp4"
    film.write_bytes(b"the-checked-film")
    ass = tmp_path / "subtitles.ass"
    ass.write_text("Dialogue: 0,0:00:00,0:00:01,Default,,0,0,0,,字幕\n",
                   encoding="utf-8")
    (tmp_path / "render.json").write_text('{"film_seconds": 1}', encoding="utf-8")

    qc_path = landed.write_attestation(film, spec_path, spec)
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    render = json.loads((tmp_path / "render.json").read_text(encoding="utf-8"))
    assert qc["status"] == "pass"
    assert qc["spec_sha256"] == hashlib.sha256(spec_path.read_bytes()).hexdigest()
    assert qc["ass_sha256"] == hashlib.sha256(ass.read_bytes()).hexdigest()
    assert qc["film_sha256"] == hashlib.sha256(film.read_bytes()).hexdigest()
    assert qc["film_bytes"] == film.stat().st_size
    assert render["film_sha256"] == qc["film_sha256"]
    assert render["film_bytes"] == qc["film_bytes"]
    assert render["qc_attestation_sha256"] == hashlib.sha256(qc_path.read_bytes()).hexdigest()
