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
