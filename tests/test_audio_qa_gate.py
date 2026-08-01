from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.check_audio_qa import (
    AudioQAGateError,
    main,
    validate_delivery,
    validate_report,
)


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
        ({"hard_cut_count": 1}, "resolved joins"),
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
    with pytest.raises(AudioQAGateError, match="受控枚举"):
        validate_report(report)


@pytest.mark.parametrize(
    ("mode", "fade_out", "fade_in"),
    [
        ("declick", 0.0, 0.0),
        ("declick", 0.004, 0.020),
        ("fade_through_silence", 0.400, 0.004),
    ],
)
def test_gate_rejects_zero_or_sub_5ms_transition_rows(mode, fade_out, fade_in):
    report = _pass_report(
        lcut_crossfade_count=0,
        fade_through_silence_count=int(mode == "fade_through_silence"),
        declick_count=int(mode == "declick"),
    )
    report["joins"][0].update(
        mode=mode,
        fade_out=fade_out,
        fade_in=fade_in,
        overlap=0.0,
        tail_handle_label=None,
    )
    with pytest.raises(AudioQAGateError, match="至少 0.005s"):
        validate_report(report)


def test_gate_derives_cross_source_keep_as_a_hard_cut():
    report = _pass_report(
        lcut_crossfade_count=0,
        keep_count=1,
    )
    report["joins"][0].update(
        mode="keep",
        fade_out=0.0,
        fade_in=0.0,
        overlap=0.0,
        tail_handle_label=None,
    )
    with pytest.raises(AudioQAGateError, match="resolved joins 推导为 1"):
        validate_report(report)


def test_gate_requires_a_reason_for_fade_through_silence_fallback():
    report = _pass_report(
        reason="",
        lcut_crossfade_count=0,
        fade_through_silence_count=1,
        fallback_count=1,
    )
    report["joins"][0].update(
        mode="fade_through_silence",
        fade_out=0.4,
        fade_in=0.3,
        overlap=0.0,
        tail_handle_label=None,
    )
    with pytest.raises(AudioQAGateError, match="非空 reason"):
        validate_report(report)


@pytest.mark.parametrize(
    ("media", "message"),
    [
        ({
            "has_video": True,
            "has_audio": True,
            "video_start_seconds": 0.0,
            "audio_start_seconds": 0.08,
            "video_duration_seconds": 12.0,
            "audio_duration_seconds": 11.92,
            "video_end_seconds": 12.0,
            "audio_end_seconds": 12.0,
        }, "起点时差"),
        ({
            "has_video": True,
            "has_audio": True,
            "video_start_seconds": 0.0,
            "audio_start_seconds": 0.0,
            "video_duration_seconds": 12.0,
            "audio_duration_seconds": 11.92,
            "video_end_seconds": 12.0,
            "audio_end_seconds": 11.92,
        }, "终点时差"),
    ],
)
def test_delivery_gate_checks_final_stream_edges(monkeypatch, tmp_path, media, message):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media",
        lambda *_args, **_kwargs: media,
    )
    report = _pass_report()
    with pytest.raises(AudioQAGateError, match=message):
        validate_delivery(report, video)
    assert report["av_start_delta_seconds"] == pytest.approx(
        abs(media["video_start_seconds"] - media["audio_start_seconds"])
    )
    assert report["av_end_delta_seconds"] == pytest.approx(
        abs(media["video_end_seconds"] - media["audio_end_seconds"])
    )


def test_delivery_gate_writes_start_end_metrics(monkeypatch, tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    media = {
        "has_video": True,
        "has_audio": True,
        "video_start_seconds": 0.0,
        "audio_start_seconds": 0.01,
        "video_duration_seconds": 12.0,
        "audio_duration_seconds": 11.98,
        "video_end_seconds": 12.0,
        "audio_end_seconds": 11.99,
    }
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media", lambda *_args, **_kwargs: media
    )
    report = _pass_report(expected_duration_seconds=12.0)
    result = validate_delivery(report, video)
    assert result["av_start_delta_seconds"] == pytest.approx(0.01)
    assert result["av_end_delta_seconds"] == pytest.approx(0.01)
    assert report["final_video_start_seconds"] == 0.0
    assert report["final_audio_start_seconds"] == 0.01
    assert report["final_video_end_seconds"] == 12.0
    assert report["final_audio_end_seconds"] == 11.99
    assert report["av_start_delta_seconds"] == 0.01
    assert report["av_end_delta_seconds"] == 0.01


def test_delivery_cli_persists_measured_edges(monkeypatch, tmp_path):
    report_path = tmp_path / "audio-qa.json"
    report_path.write_text(json.dumps(_pass_report()), encoding="utf-8")
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media",
        lambda *_args, **_kwargs: {
            "has_video": True,
            "has_audio": True,
            "video_start_seconds": 0.0,
            "audio_start_seconds": 0.02,
            "video_duration_seconds": 12.0,
            "audio_duration_seconds": 11.98,
            "video_end_seconds": 12.0,
            "audio_end_seconds": 12.0,
        },
    )
    assert main(["--report", str(report_path), "--video", str(video)]) == 0
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["final_audio_start_seconds"] == 0.02
    assert saved["final_audio_end_seconds"] == 12.0
    assert saved["av_start_delta_seconds"] == 0.02
    assert saved["av_end_delta_seconds"] == 0.0


def test_delivery_cli_persists_edge_evidence_when_gate_fails(monkeypatch, tmp_path):
    report_path = tmp_path / "audio-qa.json"
    report_path.write_text(json.dumps(_pass_report()), encoding="utf-8")
    video = tmp_path / "offset.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media",
        lambda *_args, **_kwargs: {
            "has_video": True,
            "has_audio": True,
            "video_start_seconds": 0.0,
            "audio_start_seconds": 0.28,
            "video_duration_seconds": 2.0,
            "audio_duration_seconds": 1.72,
            "video_end_seconds": 2.0,
            "audio_end_seconds": 2.0,
        },
    )
    with pytest.raises(SystemExit):
        main(["--report", str(report_path), "--video", str(video)])
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["final_audio_start_seconds"] == 0.28
    assert saved["final_audio_end_seconds"] == 2.0
    assert saved["av_start_delta_seconds"] == 0.28
    assert saved["av_end_delta_seconds"] == 0.0


def test_delivery_gate_matches_no_audio_to_real_media(monkeypatch, tmp_path):
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "tools.check_audio_qa.probe_media",
        lambda *_args, **_kwargs: {
            "has_video": True,
            "has_audio": False,
            "video_start_seconds": 0.0,
            "video_duration_seconds": 3.0,
            "video_end_seconds": 3.0,
        },
    )
    report = {
        "policy_version": 1,
        "status": "not_applicable",
        "role": "silence",
        "reason": "no_audio",
        "reason_detail": "",
        "expected_audio_stream": "absent",
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


@pytest.mark.parametrize(
    ("reason", "expected_audio", "has_audio", "message"),
    [
        ("not_a_contract", "absent", False, "受控枚举"),
        ("no_audio", "present", False, "expected_audio_stream"),
        ("single_continuous_source", "present", False, "没有音频流"),
        ("no_audio", "absent", True, "存在音频流"),
    ],
)
def test_not_applicable_reason_is_closed_and_matches_actual_audio(
    monkeypatch,
    tmp_path,
    reason,
    expected_audio,
    has_audio,
    message,
):
    video = tmp_path / "delivery.mp4"
    video.write_bytes(b"video")
    media = {
        "has_video": True,
        "has_audio": has_audio,
        "video_start_seconds": 0.0,
        "video_duration_seconds": 3.0,
        "video_end_seconds": 3.0,
    }
    if has_audio:
        media.update(
            audio_start_seconds=0.0,
            audio_duration_seconds=3.0,
            audio_end_seconds=3.0,
        )
    monkeypatch.setattr("tools.check_audio_qa.probe_media", lambda *_a, **_k: media)
    report = {
        "policy_version": 1,
        "status": "not_applicable",
        "role": "silence" if reason == "no_audio" else "mixed",
        "reason": reason,
        "reason_detail": "test contract",
        "expected_audio_stream": expected_audio,
        "duration_delta_seconds": 0.0,
        "transition_count": 0,
        "hard_cut_count": 0,
        "lcut_crossfade_count": 0,
        "fade_through_silence_count": 0,
        "declick_count": 0,
        "keep_count": 0,
        "joins": [],
    }
    with pytest.raises(AudioQAGateError, match=message):
        validate_delivery(report, video)


_VIDEO_RENDER_MARKERS = (
    "tools/build_match_reel.py",
    "tools/build_interview_clip.py",
    "tools/build_grand_slam_short.py",
    "tools/build_grand_slam_v2.py",
    "tools/build_video_story.py",
    "tennislive digest",
    "tennislive explainer",
    "tennislive video",
    "tennislive point",
)

_KNOWN_VIDEO_DELIVERY_WORKFLOWS = {
    "daily.yml",
    "explainer.yml",
    "interview-clip.yml",
    "match-reel.yml",
    "push-existing.yml",
    "video-localize.yml",
    "yesterday-point.yml",
}

# These jobs upload diagnostics, not playable media.  Keep this closed and
# documented instead of teaching the scanner broad filename exceptions.
_NON_VIDEO_DELIVERY_WORKFLOW_ALLOWLIST = {
    "probe.yml": "data-source probe uploads coverage.txt only (--no-cards)",
}

_CHECKER_COMMAND_RE = re.compile(
    r"^[ \t]*(?:[A-Za-z_][A-Za-z0-9_]*=\S+[ \t]+)*"
    r"(?:python(?:3(?:\.\d+)?)?|uv[ \t]+run[ \t]+python)[ \t]+"
    r"tools/(?P<checker>check_audio_qa|check_package_audio_qa)\.py(?:[ \t]|\\|$)"
)
_DELIVERY_COMMAND_RE = re.compile(
    r"^[ \t]*(?:[A-Za-z_][A-Za-z0-9_]*=\S+[ \t]+)*"
    r"(?:git[ \t]+add(?:[ \t]|$)|"
    r"tennislive[ \t]+publish(?:[ \t]|$)|"
    r"(?:python(?:3(?:\.\d+)?)?|uv[ \t]+run[ \t]+python)[ \t]+"
    r"tools/push_reel\.py(?:[ \t]|\\|$))"
)


def _active_run_lines(step: dict) -> list[tuple[int, str]]:
    """Return executable-looking lines; workflow comments are not evidence."""
    return [
        (line_number, line)
        for line_number, line in enumerate(str(step.get("run", "")).splitlines())
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _shell_command(lines: list[tuple[int, str]], start: int) -> str:
    """Collect one shell command, including backslash continuations."""
    parts: list[str] = []
    for _line_number, line in lines[start:]:
        parts.append(line.strip())
        if not line.rstrip().endswith("\\"):
            break
    return "\n".join(parts)


def _workflow_gate_positions(steps: list[dict]) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for step_number, step in enumerate(steps):
        lines = _active_run_lines(step)
        for index, (line_number, line) in enumerate(lines):
            match = _CHECKER_COMMAND_RE.match(line)
            if match is None:
                continue
            command = _shell_command(lines, index)
            required_flag = (
                "--video"
                if match.group("checker") == "check_audio_qa"
                else "--dir"
            )
            assert required_flag in command, (
                f"{step.get('name')}: final checker 缺少 {required_flag}"
            )
            assert "|| true" not in command, (
                f"{step.get('name')}: final checker 不得吞掉失败"
            )
            assert step.get("continue-on-error") not in (True, "true"), (
                f"{step.get('name')}: final checker 不得 continue-on-error"
            )
            positions.append((step_number, line_number))
    return positions


def _workflow_delivery_positions(steps: list[dict]) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for step_number, step in enumerate(steps):
        if "actions/upload-artifact" in str(step.get("uses", "")):
            positions.append((step_number, -1))
        positions.extend(
            (step_number, line_number)
            for line_number, line in _active_run_lines(step)
            if _DELIVERY_COMMAND_RE.match(line)
        )
    return positions


def _workflow_render_positions(steps: list[dict]) -> list[tuple[int, int]]:
    return [
        (step_number, line_number)
        for step_number, step in enumerate(steps)
        for line_number, line in _active_run_lines(step)
        if any(marker in line for marker in _VIDEO_RENDER_MARKERS)
    ]


def _job_has_video_delivery_contract(workflow_name: str, steps: list[dict]) -> bool:
    runtime = "\n".join(
        "\n".join(line for _number, line in _active_run_lines(step))
        + "\n"
        + str(step.get("with", ""))
        for step in steps
    )
    return (
        workflow_name in {"daily.yml", "push-existing.yml"}
        or ".mp4" in runtime
        or any(marker in runtime for marker in _VIDEO_RENDER_MARKERS)
    )


def test_every_video_delivery_workflow_runs_final_audio_gate_before_delivery():
    """Discover all video jobs; a comment cannot masquerade as a QA command."""
    import yaml

    root = Path(__file__).resolve().parents[1]
    discovered: set[str] = set()
    for workflow_path in sorted((root / ".github/workflows").glob("*.yml")):
        if workflow_path.name in _NON_VIDEO_DELIVERY_WORKFLOW_ALLOWLIST:
            assert _NON_VIDEO_DELIVERY_WORKFLOW_ALLOWLIST[workflow_path.name].strip()
            continue
        payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job_name, job in (payload.get("jobs") or {}).items():
            steps = job.get("steps", []) or []
            deliveries = _workflow_delivery_positions(steps)
            if not deliveries or not _job_has_video_delivery_contract(
                workflow_path.name, steps
            ):
                continue
            discovered.add(workflow_path.name)
            gates = _workflow_gate_positions(steps)
            label = f"{workflow_path.name}:{job_name}"
            assert gates, f"{label}: MP4 交付/补推路径缺少最终音频 checker"
            renders = _workflow_render_positions(steps)
            for delivery in deliveries:
                earlier_renders = [render for render in renders if render < delivery]
                final_render = max(earlier_renders) if earlier_renders else None
                assert any(
                    gate < delivery and (final_render is None or final_render < gate)
                    for gate in gates
                ), (
                    f"{label}: {delivery} 交付前没有成功即失败的最终音频 checker"
                )

    # This makes the discovery test fail if its own heuristics accidentally stop
    # seeing one of today's production/replay workflows.
    assert _KNOWN_VIDEO_DELIVERY_WORKFLOWS <= discovered


def test_daily_and_push_existing_replay_paths_are_audio_gated():
    """Pin the two package/replay routes most easily missed by render-only QA."""
    import yaml

    root = Path(__file__).resolve().parents[1]
    daily = yaml.safe_load(
        (root / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    )
    daily_steps = daily["jobs"]["digest"]["steps"]
    daily_gate = next(
        step
        for step in daily_steps
        if any(
            "check_package_audio_qa.py" in line
            for _number, line in _active_run_lines(step)
        )
    )
    daily_condition = str(daily_gate.get("if", ""))
    assert "steps.guard.outputs.skip != 'true'" in daily_condition
    assert "steps.guard.outputs.push_pending == 'true'" in daily_condition

    push_existing = yaml.safe_load(
        (root / ".github/workflows/push-existing.yml").read_text(encoding="utf-8")
    )
    replay_steps = push_existing["jobs"]["push-existing"]["steps"]
    replay_gates = _workflow_gate_positions(replay_steps)
    replay_deliveries = _workflow_delivery_positions(replay_steps)
    assert replay_gates
    assert replay_deliveries
    assert all(
        any(gate < delivery for gate in replay_gates)
        for delivery in replay_deliveries
    )


def test_render_and_push_share_final_delivery_gate():
    """Every mode capable of delivering an MP4 must run the same final gate."""
    import yaml

    root = Path(__file__).resolve().parents[1]
    for relative in (
        ".github/workflows/match-reel.yml",
        ".github/workflows/interview-clip.yml",
    ):
        payload = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        steps = next(iter(payload["jobs"].values()))["steps"]
        gate_index, gate = next(
            (index, step) for index, step in enumerate(steps)
            if "check_audio_qa.py" in str(step.get("run", ""))
        )
        condition = str(gate.get("if", ""))
        assert "mode == 'render'" in condition, relative
        assert "mode == 'push'" in condition, relative
        ffmpeg = next(step for step in steps if "install -y -qq ffmpeg" in str(
            step.get("run", "")
        ))
        assert "mode != 'push'" not in str(ffmpeg.get("if", "")), relative
        guard = next(step for step in steps if "push 模式先确认" in str(
            step.get("name", "")
        ))
        guard_code = str(guard.get("run", ""))
        assert "git ls-files" in guard_code, relative
        assert "audio-qa.json" in guard_code, relative
        for index, step in enumerate(steps):
            run = str(step.get("run", ""))
            if ("git add" in run
                    or "push_reel.py" in run
                    or "actions/upload-artifact" in str(step.get("uses", ""))):
                assert gate_index < index, f"{relative}: {step.get('name')}"


def test_gate_cli_report_is_json_serialisable(tmp_path):
    path = tmp_path / "audio-qa.json"
    path.write_text(json.dumps(_pass_report()), encoding="utf-8")
    validate_report(json.loads(path.read_text(encoding="utf-8")))
