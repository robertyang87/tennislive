from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.check_audio_qa import AudioQAGateError, validate_delivery, validate_report


def _pass_report(**updates):
    report = {
        "policy_version": 1,
        "status": "pass",
        "role": "mixed",
        "reason": "two official windows",
        "duration_delta_seconds": 0.0,
        "transition_count": 1,
        "hard_cut_count": 0,
        "lcut_crossfade_count": 1,
        "fade_through_silence_count": 0,
        "declick_count": 0,
        "keep_count": 0,
        "joins": [
            {
                "boundary": 0,
                "mode": "lcut_crossfade",
                "fade_out": 0.0,
                "fade_in": 0.45,
                "curve": "qsin",
                "previous_source": "a",
                "next_source": "b",
                "overlap": 0.45,
                "tail_handle_label": "tail",
            }
        ],
    }
    report.update(updates)
    return report


def test_gate_accepts_duration_safe_softened_plan():
    validate_report(_pass_report())


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"hard_cut_count": 1}, "硬切"),
        ({"duration_delta_seconds": -0.45}, "改变时间线"),
        ({"transition_count": 2}, "joins 有"),
        ({"lcut_crossfade_count": 0}, "lcut_crossfade"),
    ],
)
def test_gate_rejects_bad_transition_accounting(updates, message):
    with pytest.raises(AudioQAGateError, match=message):
        validate_report(_pass_report(**updates))


def test_gate_rejects_long_speech_fade():
    report = _pass_report(
        role="speech",
        lcut_crossfade_count=0,
        fade_through_silence_count=1,
    )
    report["joins"][0].update(
        mode="fade_through_silence", fade_out=0.4, fade_in=0.3
    )
    with pytest.raises(AudioQAGateError, match="只能 keep"):
        validate_report(report)


def test_gate_requires_na_reason_and_no_transitions():
    report = _pass_report(
        status="not_applicable",
        role="silence",
        reason="",
        transition_count=0,
        lcut_crossfade_count=0,
        joins=[],
    )
    with pytest.raises(AudioQAGateError, match="必须说明"):
        validate_report(report)


def test_delivery_gate_checks_final_streams(monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media",
        lambda *_args, **_kwargs: {
            "has_video": True,
            "has_audio": True,
            "video_duration_seconds": 12.0,
            "audio_duration_seconds": 11.92,
        },
    )
    with pytest.raises(AudioQAGateError, match="A/V 时差"):
        validate_delivery(_pass_report(), video)


def test_delivery_gate_matches_no_audio_to_real_media(monkeypatch, tmp_path):
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media",
        lambda *_args, **_kwargs: {
            "has_video": True,
            "has_audio": False,
            "video_duration_seconds": 3.0,
        },
    )
    report = {
        "policy_version": 1,
        "status": "not_applicable",
        "role": "silence",
        "reason": "no_audio",
        "duration_delta_seconds": 0.0,
        "transition_count": 0,
        "hard_cut_count": 0,
        "lcut_crossfade_count": 0,
        "fade_through_silence_count": 0,
        "declick_count": 0,
        "keep_count": 0,
        "joins": [],
    }
    assert validate_delivery(report, video)["has_audio"] is False


def test_workflows_gate_audio_before_upload_or_commit():
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflows = (
        ".github/workflows/daily.yml",
        ".github/workflows/match-reel.yml",
        ".github/workflows/interview-clip.yml",
        ".github/workflows/explainer.yml",
        ".github/workflows/video-localize.yml",
        ".github/workflows/yesterday-point.yml",
    )
    for relative in workflows:
        payload = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        jobs = payload["jobs"]
        all_steps = [step for job in jobs.values() for step in job.get("steps", [])]
        gate_positions = [
            index for index, step in enumerate(all_steps)
            if "check_audio_qa.py" in str(step.get("run", ""))
        ]
        delivery_positions = [
            index for index, step in enumerate(all_steps)
            if "actions/upload-artifact" in str(step.get("uses", ""))
            or "git add" in "\n".join(
                line for line in str(step.get("run", "")).splitlines()
                if not line.lstrip().startswith("#")
            )
        ]
        assert gate_positions, relative
        assert delivery_positions, relative
        assert min(gate_positions) < min(delivery_positions), relative


def test_gate_cli_report_is_json_serialisable(tmp_path):
    path = tmp_path / "audio-qa.json"
    path.write_text(json.dumps(_pass_report()), encoding="utf-8")
    validate_report(json.loads(path.read_text(encoding="utf-8")))
