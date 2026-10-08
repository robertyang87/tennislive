import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from subtitle_override_evidence import override_problem  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SLUG = "yuan-oliynykova-beijing-2026-r1"


def test_yuan_override_is_proved_by_real_retained_ass():
    assert override_problem(ROOT / "specs/reels" / f"{SLUG}.json", ROOT) is None


def _fixture(tmp_path):
    spec = {"slug": "demo", "subtitle_top": 860,
            "_subtitle_top_why": "Measured result board begins at y950; subtitle ink ends at y924."}
    raw = json.dumps(spec).encode()
    path = tmp_path / "specs/reels/demo.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    out = tmp_path / "output/2026-09-30/reel/demo"
    out.mkdir(parents=True)
    ass = b"Format: Name, MarginV\nStyle: TL,860\n"
    sha = lambda b: hashlib.sha256(b).hexdigest()
    qc = {"status": "pass", "slug": "demo", "spec_sha256": sha(raw),
          "ass_sha256": sha(ass), "film_sha256": "film"}
    qraw = json.dumps(qc).encode()
    (out / "subtitles.ass").write_bytes(ass)
    (out / "qc_attestation.json").write_bytes(qraw)
    (out / "render.json").write_text(json.dumps({"film_sha256": "film", "qc_attestation_sha256": sha(qraw)}))
    return path, out


def test_override_without_collision_assessment_is_rejected(tmp_path):
    path, _ = _fixture(tmp_path)
    spec = json.loads(path.read_text()); spec.pop("_subtitle_top_why")
    path.write_text(json.dumps(spec))
    assert "collision assessment" in override_problem(path, tmp_path)


def test_changed_anchor_cannot_borrow_old_qc(tmp_path):
    path, _ = _fixture(tmp_path)
    assert override_problem(path, tmp_path) is None
    spec = json.loads(path.read_text()); spec["subtitle_top"] = 870
    path.write_text(json.dumps(spec))
    assert override_problem(path, tmp_path)


def test_tampered_ass_cannot_prove_anchor(tmp_path):
    path, out = _fixture(tmp_path)
    (out / "subtitles.ass").write_text("Format: Name, MarginV\nStyle: TL,900\n")
    assert override_problem(path, tmp_path)


def _retained_manifest(path, out):
    from render_inputs import canonical, project
    projection = project(json.loads(path.read_text()))
    qc = json.loads((out / "qc_attestation.json").read_text())
    manifest = {"spec_sha256": qc["spec_sha256"], "film_sha256": qc["film_sha256"],
                "projection": projection,
                "projection_sha256": hashlib.sha256(canonical(projection).encode()).hexdigest(),
                "artifacts": {"subtitles.ass": qc["ass_sha256"]}}
    raw = json.dumps(manifest).encode()
    (out / "render_inputs.json").write_bytes(raw)
    qc["render_inputs_sha256"] = hashlib.sha256(raw).hexdigest()
    qraw = json.dumps(qc).encode()
    (out / "qc_attestation.json").write_bytes(qraw)
    render = {"film_sha256": qc["film_sha256"], "render_inputs_sha256": qc["render_inputs_sha256"],
              "qc_attestation_sha256": hashlib.sha256(qraw).hexdigest()}
    (out / "render.json").write_text(json.dumps(render))


def test_cover_copy_change_keeps_only_retained_subtitle_geometry_proof(tmp_path):
    path, out = _fixture(tmp_path)
    _retained_manifest(path, out)
    spec = json.loads(path.read_text())
    spec["cover"] = {"hook": "Revised cover copy"}
    path.write_text(json.dumps(spec))
    assert override_problem(path, tmp_path) is None
    # 这不是新 spec 的成片质检凭证；发布闸仍会拦住旧 spec 哈希。
    qc = json.loads((out / "qc_attestation.json").read_text())
    assert qc["spec_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
    spec["source_url"] = "https://example.test/other-source"
    path.write_text(json.dumps(spec))
    assert override_problem(path, tmp_path)


def test_retained_geometry_cannot_borrow_tampered_manifest(tmp_path):
    path, out = _fixture(tmp_path)
    _retained_manifest(path, out)
    spec = json.loads(path.read_text()); spec["cover"] = {"hook": "Changed"}
    path.write_text(json.dumps(spec))
    manifest = json.loads((out / "render_inputs.json").read_text())
    manifest["projection"]["subtitle_top"] = 900
    (out / "render_inputs.json").write_text(json.dumps(manifest))
    assert override_problem(path, tmp_path)
