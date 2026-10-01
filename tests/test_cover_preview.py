"""Contract checks for the isolated, temporary native-cover preview route."""
import copy
import json
from pathlib import Path
import sys

import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_cover_preview as preview


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "repo"
    (root / "specs/reels").mkdir(parents=True)
    (root / "assets/reel").mkdir(parents=True)
    (root / "assets/fonts").symlink_to(ROOT / "assets/fonts")
    photo = root / "assets/reel/photo.jpg"
    Image.new("RGB", (2000, 3000), "white").save(photo)
    spec = {
        "slug": "preview-example", "segments": [], "source_url": "https://example.org/source",
        "push": {"auto": False},
        "stats": {"a": {"winners": None, "ue": None}, "b": {"winners": None, "ue": None}},
        "cover": {
            "eyebrow": "赛场之上", "layout": "solo", "subject": "郑钦文",
            "hook": "一盘优势被追平\n郑钦文主场过关", "hook_accent": "被追平",
            "hook_accent_color": "#FFD600", "topic": "WTA1000 北京 首轮 · 郑钦文 VS 施晗",
            "winner": "郑钦文", "result": "7-6(6) 4-6 6-2",
            "portrait": {"image": str(photo)},
            "scoreboard": {"court": "Capital Group Diamond", "duration_source": {"url": "https://example.org/duration"}},
            "matchup": [{"name": "郑钦文", "name_en": "Qinwen Zheng", "country": None, "rank": 54},
                        {"name": "施晗", "name_en": "Han Shi", "country": None, "rank": 231}],
        },
    }
    path = root / "specs/reels/preview-example.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return root, path, spec


def test_inputs_check_is_read_only_and_keeps_missing_wue(inputs):
    root, path, spec = inputs
    before = path.read_bytes()
    assert preview.read_inputs(root, spec["slug"])[1] == spec
    assert path.read_bytes() == before
    assert spec["stats"]["a"]["winners"] is None


@pytest.mark.parametrize("slug", ("", "../main", "-x", "x;echo", "a/b", "a\nb"))
def test_unsafe_slug_rejected(inputs, slug):
    with pytest.raises(ValueError, match="slug"):
        preview.read_inputs(inputs[0], slug)


@pytest.mark.parametrize("mutation", (
    lambda s: s["push"].update(auto=True),
    lambda s: s["cover"].update(layout="cutout"),
    lambda s: s["cover"].update(approved_image="anything.jpg"),
    lambda s: s["cover"]["portrait"].update(frame_at=1),
    lambda s: s["cover"]["portrait"].update(image="../outside.jpg"),
    lambda s: s["cover"].update(hook_accent_color="#c6f65a"),
    lambda s: s["cover"].update(hook_accent=""),
))
def test_unsafe_input_rejected(inputs, mutation):
    root, path, spec = inputs
    mutation(spec)
    path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ValueError):
        preview.read_inputs(root, spec["slug"])


def test_native_cover_checks_leave_final_video_gate_intact(inputs):
    import winners_ue_gate
    spec = inputs[2]
    before = copy.deepcopy(spec)
    assert preview.check_cover(spec)
    assert spec == before
    assert winners_ue_gate.problem(spec), "Final missing-WUE gate must still block"


@pytest.mark.parametrize("mutation", (
    lambda s: s["cover"].update(topic="2026 ATP500 东京 首轮"),
    lambda s: s["cover"].update(hook_accent="一盘优势被追平"),
    lambda s: s["cover"].update(hook="一发百分之六十\n郑钦文主场过关"),
    lambda s: s["cover"].update(result="7-6 4-6 6-2"),
    lambda s: s["cover"]["portrait"].update(fit="width"),
    lambda s: s["cover"]["scoreboard"].update(court="钻石球场"),
    lambda s: s["cover"]["scoreboard"].pop("duration_source"),
))
def test_native_cover_failures_are_not_ignored(inputs, mutation):
    spec = inputs[2]
    mutation(spec)
    with pytest.raises((ValueError, RuntimeError, SystemExit)):
        preview.check_cover(spec)


def test_report_is_preview_only_with_original_hashes(inputs, tmp_path):
    _, spec_path, spec = inputs
    out = tmp_path / "preview"
    out.mkdir()
    Image.new("RGB", (1080, 1440), "white").save(out / "preview.jpg")
    report_path = out / "preview-report.json"
    preview.write_report(report_path, spec_path, spec, ["test_fixture_only"])
    report = json.loads(report_path.read_text())
    assert report["final_video_qc"] == "NOT_RUN"
    assert report["publication_eligible"] is False
    assert report["status"] == "rendered_pending_human_visual_review"
    assert report["winners_ue"] == spec["stats"]
    assert set(p.name for p in out.iterdir()) == {"preview.jpg", "preview-report.json"}


def test_workflow_has_no_publication_capability():
    text = (ROOT / ".github/workflows/noskova-final-review-export.yml").read_text()
    doc = yaml.safe_load(text)
    assert doc["name"] == "native-cover-preview"
    assert doc["run-name"] == "native-cover-preview · ${{ inputs.slug }} · preview-only"
    assert set(doc.get("on", doc.get(True))) == {"workflow_dispatch"}
    assert doc["permissions"] == {"contents": "read"}
    job = doc["jobs"]["cover-preview"]
    assert job["permissions"] == {"contents": "read"}
    assert job["steps"][0]["with"]["persist-credentials"] is False
    assert "preview/native-cover-*" in text
    for forbidden in ("secrets.", "git push", "git commit", "gh release", "dispatches", "push_reel", "build_match_reel.py", "playwright install", "apt install"):
        assert forbidden not in text
    assert text.index("--inputs-only") < text.index("pip install")
    assert text.index("command -v google-chrome") < text.index("pip install")
    artifact = job["steps"][-1]["with"]
    assert artifact["path"].splitlines() == ["${{ runner.temp }}/cover-preview/preview.jpg", "${{ runner.temp }}/cover-preview/preview-report.json"]
    assert artifact["if-no-files-found"] == "error"


def test_main_uses_native_loader(inputs, monkeypatch):
    root, _, spec = inputs
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["check_cover_preview.py", "--slug", spec["slug"]])
    assert preview.main() == 0


@pytest.mark.parametrize("key,value", (("voice", "zh-CN-YunjianNeural"), ("rate", "+6%")))
def test_native_loader_dead_voice_keys_rejected(inputs, monkeypatch, key, value):
    root, path, spec = inputs
    spec[key] = value
    path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["check_cover_preview.py", "--slug", spec["slug"]])
    with pytest.raises(RuntimeError, match="没有任何代码读"):
        preview.main()
