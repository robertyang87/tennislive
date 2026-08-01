import json
from pathlib import Path

import pytest

from tools import check_package_audio_qa as package_gate
from tools.check_audio_qa import AudioQAGateError


def _report(path: Path) -> None:
    path.write_text(json.dumps({"status": "not_applicable"}), encoding="utf-8")


def test_package_gate_uses_per_stem_sidecars(tmp_path, monkeypatch):
    first = tmp_path / "first.mp4"
    second = tmp_path / "nested" / "second.mp4"
    second.parent.mkdir()
    first.write_bytes(b"video")
    second.write_bytes(b"video")
    _report(tmp_path / "first.audio-qa.json")
    _report(second.with_suffix(".audio-qa.json"))
    calls = []
    monkeypatch.setattr(
        package_gate,
        "validate_delivery",
        lambda payload, video: calls.append((payload, video)),
    )

    checked = package_gate.validate_package(tmp_path)

    assert [video for video, _ in checked] == [first, second]
    assert [video for _, video in calls] == [first, second]


def test_package_gate_persists_final_media_evidence(tmp_path, monkeypatch):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    report = tmp_path / "final.audio-qa.json"
    _report(report)

    def validate(payload, _video):
        payload["final_video_end_seconds"] = 3.0

    monkeypatch.setattr(package_gate, "validate_delivery", validate)
    package_gate.validate_package(tmp_path)

    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["final_video_end_seconds"] == 3.0


def test_package_gate_allows_generic_report_for_single_video(tmp_path, monkeypatch):
    video = tmp_path / "grand-slam.mp4"
    video.write_bytes(b"video")
    _report(tmp_path / "audio-qa.json")
    monkeypatch.setattr(package_gate, "validate_delivery", lambda *_: None)

    assert package_gate.validate_package(tmp_path) == [
        (video, tmp_path / "audio-qa.json")
    ]


def test_package_gate_rejects_ambiguous_or_missing_sidecars(tmp_path):
    (tmp_path / "one.mp4").write_bytes(b"video")
    (tmp_path / "two.mp4").write_bytes(b"video")
    _report(tmp_path / "audio-qa.json")

    with pytest.raises(AudioQAGateError, match="不能共用"):
        package_gate.validate_package(tmp_path)


def test_publish_workflows_gate_replay_before_push():
    root = Path(__file__).resolve().parents[1]
    daily = (root / ".github/workflows/daily.yml").read_text("utf-8")
    existing = (root / ".github/workflows/push-existing.yml").read_text("utf-8")

    daily_gate = daily.index("python tools/check_package_audio_qa.py")
    daily_push = daily.index("- name: PushPlus 推送到微信")
    assert daily_gate < daily_push
    assert "steps.guard.outputs.push_pending == 'true'" in daily[
        daily.rfind("- name:", 0, daily_gate):daily_gate
    ]

    existing_gate = existing.index("python tools/check_package_audio_qa.py")
    existing_push = existing.index("tennislive publish pushplus")
    assert existing_gate < existing_push
