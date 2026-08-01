from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

from tennislive.video.audio import (
    AVSegment,
    AudioJoinError,
    AudioJoinPolicy,
    AudioTailHandle,
    DEFAULT_FADE_CURVE,
    DEFAULT_FADE_IN,
    DEFAULT_FADE_OUT,
    audio_qa_for_graph,
    build_acrossfade_audio_filter,
    concat_audio_filter,
    concat_av_filter,
    not_applicable_audio_qa,
    resolve_join_policy,
)


def test_cross_source_default_fades_inside_segments_without_changing_duration():
    result = concat_av_filter(
        [AVSegment(10.0, "official-a"), AVSegment(8.0, "official-b")],
        audio_role="mixed",
    )

    assert result.output_duration == 18.0
    assert result.duration_delta == 0.0
    assert result.video_label == "[vout]"
    assert result.audio_label == "[aout]"
    assert len(result.joins) == 1
    join = result.joins[0]
    assert join.mode == "fade_through_silence"
    assert join.fade_out == DEFAULT_FADE_OUT
    assert join.fade_in == DEFAULT_FADE_IN
    assert join.curve == DEFAULT_FADE_CURVE
    assert "afade=t=out:st=9.600:d=0.400:curve=qsin" in result.filtergraph
    assert "afade=t=in:st=0:d=0.300:curve=qsin" in result.filtergraph
    assert "[0:v]trim=duration=10.000" in result.filtergraph
    assert "atrim=duration=10.000" in result.filtergraph
    assert "[1:v]trim=duration=8.000" in result.filtergraph
    assert "atrim=duration=8.000" in result.filtergraph
    assert "concat=n=2:v=1:a=1[vout][aout]" in result.filtergraph
    assert "acrossfade=" not in result.filtergraph


def test_unknown_source_ids_are_treated_as_cross_source():
    policy = resolve_join_policy(None, None)

    assert policy.mode == "fade_through_silence"
    assert policy.fade_out == 0.40
    assert policy.fade_in == 0.30


def test_short_segments_clamp_each_fade_to_its_own_quarter_duration():
    result = concat_av_filter(
        [AVSegment(0.20, "a"), AVSegment(0.16, "b")],
        audio_role="music",
    )

    join = result.joins[0]
    assert join.fade_out == pytest.approx(0.05)
    assert join.fade_in == pytest.approx(0.04)
    assert "afade=t=out:st=0.150:d=0.050:curve=qsin" in result.filtergraph
    assert "afade=t=in:st=0:d=0.040:curve=qsin" in result.filtergraph
    assert result.output_duration == pytest.approx(0.36)


def test_same_source_defaults_to_declick_and_can_explicitly_keep():
    segments = [AVSegment(3.0, "same"), AVSegment(4.0, "same")]

    declick = concat_av_filter(segments, audio_role="ambience")
    keep = concat_av_filter(
        segments, audio_role="ambience", same_source_strategy="keep"
    )

    assert declick.joins[0].mode == "declick"
    assert declick.joins[0].fade_out == pytest.approx(0.02)
    assert declick.joins[0].fade_in == pytest.approx(0.02)
    assert declick.filtergraph.count("afade=") == 2
    assert keep.joins[0].mode == "keep"
    assert keep.joins[0].fade_out == 0.0
    assert keep.joins[0].fade_in == 0.0
    assert "afade=" not in keep.filtergraph


def test_boundary_override_can_keep_a_verified_cross_source_join():
    result = concat_av_filter(
        [AVSegment(2.0, "a"), AVSegment(2.0, "b")],
        audio_role="mixed",
        join_overrides={0: "keep"},
    )

    assert result.joins[0].mode == "keep"
    assert "afade=" not in result.filtergraph


def test_lcut_overlays_an_external_tail_on_next_main_and_preserves_timeline():
    result = concat_av_filter(
        [AVSegment(4.0, "a"), AVSegment(5.0, "b")],
        audio_role="music",
        join_overrides={0: AudioJoinPolicy.lcut_crossfade(0.40)},
        tail_handles={0: AudioTailHandle("2:a", 0.75)},
    )

    join = result.joins[0]
    assert join.mode == "lcut_crossfade"
    assert join.overlap == pytest.approx(0.40)
    assert join.fade_out == 0.0
    assert join.fade_in == pytest.approx(0.40)
    assert join.tail_handle_label == "2:a"
    assert result.output_duration == 9.0
    assert result.duration_delta == 0.0
    assert "[1:a]aresample=48000" in result.filtergraph
    assert "afade=t=in:st=0:d=0.400:curve=qsin[ab1]" in result.filtergraph
    assert "[2:a]aresample=48000" in result.filtergraph
    assert "atrim=duration=0.400" in result.filtergraph
    assert "afade=t=out:st=0:d=0.400:curve=qsin[ah0]" in result.filtergraph
    assert (
        "[ab1][ah0]amix=inputs=2:normalize=0:duration=first:"
        "dropout_transition=0,alimiter=limit=0.950:level=0:latency=1,"
        "atrim=duration=5.000,asetpts=PTS-STARTPTS[aj1]"
    ) in result.filtergraph
    assert "acrossfade=" not in result.filtergraph


def test_lcut_overlap_is_clamped_and_requires_a_matching_handle():
    segments = [AVSegment(0.80, "a"), AVSegment(3.0, "b")]
    policy = AudioJoinPolicy.lcut_crossfade(0.50)

    result = concat_av_filter(
        segments,
        audio_role="music",
        join_overrides={0: policy},
        tail_handles={0: AudioTailHandle("tail", 0.40)},
    )
    assert result.joins[0].overlap == pytest.approx(0.20)
    assert result.joins[0].fade_in == pytest.approx(0.20)

    with pytest.raises(AudioJoinError, match="requires an AudioTailHandle"):
        concat_av_filter(
            segments, audio_role="music", join_overrides={0: policy}
        )


def test_unused_tail_handle_and_invalid_boundary_are_rejected():
    segments = [AVSegment(2.0, "a"), AVSegment(2.0, "b")]

    with pytest.raises(AudioJoinError, match="not an L-cut"):
        concat_av_filter(
            segments,
            audio_role="mixed",
            tail_handles={0: AudioTailHandle("tail", 0.4)},
        )
    with pytest.raises(AudioJoinError, match="invalid boundary"):
        concat_av_filter(
            segments, audio_role="mixed", join_overrides={1: "keep"}
        )


def test_acrossfade_is_explicitly_rejected_until_full_av_qa_exists():
    with pytest.raises(AudioJoinError, match="repository-wide QA contract"):
        AudioJoinPolicy.acrossfade(0.50)
    with pytest.raises(AudioJoinError, match="repository-wide QA contract"):
        build_acrossfade_audio_filter(
            [AVSegment(10.0), AVSegment(8.0)],
            [],
            audio_role="music",
            timeline=None,
        )


def test_single_segment_is_normalized_without_an_artificial_edge_fade():
    result = concat_av_filter(
        [AVSegment(3.25, "only")], audio_role="mixed"
    )

    assert result.output_duration == 3.25
    assert result.joins == ()
    assert "afade=" not in result.filtergraph
    assert "[vj0]null[vout]" in result.filtergraph
    assert "[aj0]anull[aout]" in result.filtergraph


def test_audio_only_concat_softens_bed_edits_without_moving_timeline():
    result = concat_audio_filter(
        [
            AVSegment(1.25, "ambient-cut-a", audio_label="0:a"),
            AVSegment(0.75, "ambient-cut-b", audio_label="1:a"),
        ],
        audio_role="ambience",
        channel_layout="mono",
        output_audio_label="bed",
    )

    assert result.output_duration == pytest.approx(2.0)
    assert result.duration_delta == 0.0
    assert result.audio_label == "[bed]"
    assert result.joins[0].mode == "fade_through_silence"
    assert "atrim=duration=1.250" in result.filtergraph
    assert "afade=t=out:st=0.938:d=0.312:curve=qsin" in result.filtergraph
    assert "afade=t=in:st=0:d=0.188:curve=qsin" in result.filtergraph
    assert "[aj0][aj1]concat=n=2:v=0:a=1[bed]" in result.filtergraph
    assert "acrossfade=" not in result.filtergraph


def test_audio_only_keep_does_not_fade_or_overlap_narration_stems():
    result = concat_audio_filter(
        [AVSegment(2.0, "speech-a"), AVSegment(3.0, "speech-b")],
        audio_role="speech",
        join_overrides={0: AudioJoinPolicy.keep()},
        channel_layout="mono",
    )

    assert result.output_duration == pytest.approx(5.0)
    assert result.duration_delta == 0.0
    assert result.joins[0].mode == "keep"
    assert "afade=" not in result.filtergraph
    assert "amix=" not in result.filtergraph
    assert "concat=n=2:v=0:a=1[aout]" in result.filtergraph


def test_speech_role_rejects_music_fades_and_long_declicks():
    segments = [AVSegment(2.0, "speaker-a"), AVSegment(2.0, "speaker-b")]

    with pytest.raises(AudioJoinError, match="audio_role=speech forbids"):
        concat_audio_filter(segments, audio_role="speech")
    with pytest.raises(AudioJoinError, match="audio_role=speech forbids"):
        concat_audio_filter(
            segments,
            audio_role="speech",
            join_overrides={0: AudioJoinPolicy.declick(0.031)},
        )
    safe = concat_audio_filter(
        segments,
        audio_role="speech",
        join_overrides={0: AudioJoinPolicy.declick(0.02)},
    )
    assert safe.joins[0].mode == "declick"
    assert safe.joins[0].fade_out == pytest.approx(0.02)


@pytest.mark.parametrize(
    "policy",
    [
        lambda: AudioJoinPolicy.declick(0.0),
        lambda: AudioJoinPolicy.declick(0.004),
        lambda: AudioJoinPolicy.fade_through_silence(
            fade_out=0.004, fade_in=0.30
        ),
        lambda: AudioJoinPolicy.fade_through_silence(
            fade_out=0.40, fade_in=0.0
        ),
    ],
)
def test_zero_or_sub_5ms_fades_are_not_valid_transition_policies(policy):
    with pytest.raises(AudioJoinError, match="at least 0.005s"):
        policy()


@pytest.mark.parametrize("audio_only", [False, True])
def test_short_segment_clamping_cannot_turn_a_fade_into_a_noop(audio_only):
    builder = concat_audio_filter if audio_only else concat_av_filter
    with pytest.raises(AudioJoinError, match="resolved.*at least 0.005s"):
        builder(
            [AVSegment(0.019, "a"), AVSegment(1.0, "b")],
            audio_role="mixed",
        )
    graph = builder(
        [AVSegment(0.020, "a"), AVSegment(1.0, "b")],
        audio_role="mixed",
    )
    assert graph.joins[0].fade_out == pytest.approx(0.005)


def test_audio_role_is_mandatory_and_validated():
    with pytest.raises(TypeError, match="audio_role"):
        concat_av_filter([AVSegment(1.0)])
    with pytest.raises(AudioJoinError, match="audio_role must be one of"):
        concat_av_filter([AVSegment(1.0)], audio_role="voice")


def test_global_audio_qa_schema_covers_pass_and_not_applicable():
    graph = concat_audio_filter(
        [AVSegment(1.0, "one"), AVSegment(1.0, "two")],
        audio_role="ambience",
    )
    passed = audio_qa_for_graph(
        graph, audio_role="ambience", reason="two ambient edits"
    )

    assert passed["policy_version"] == 1
    assert passed["status"] == "pass"
    assert passed["role"] == "ambience"
    assert passed["duration_delta_seconds"] == 0.0
    assert passed["transition_count"] == 1
    assert passed["fade_through_silence_count"] == 1
    assert passed["fallback_count"] == 1
    assert passed["hard_cut_count"] == 0
    assert len(passed["joins"]) == 1

    skipped = not_applicable_audio_qa(
        audio_role="mixed", reason="single_continuous_source"
    )
    assert skipped["status"] == "not_applicable"
    assert skipped["reason"] == "single_continuous_source"
    assert skipped["expected_audio_stream"] == "present"
    assert skipped["transition_count"] == 0
    assert skipped["fallback_count"] == 0
    assert skipped["joins"] == []
    with pytest.raises(AudioJoinError, match="reason must be one of"):
        not_applicable_audio_qa(audio_role="silence", reason="")


def test_audio_qa_derives_hard_cuts_from_resolved_joins():
    graph = concat_audio_filter(
        [AVSegment(1.0, "a"), AVSegment(1.0, "b")],
        audio_role="mixed",
        join_overrides={0: AudioJoinPolicy.keep()},
    )
    report = audio_qa_for_graph(
        graph, audio_role="mixed", reason="deliberate test boundary"
    )
    assert report["hard_cut_count"] == 1


def test_fallback_qa_requires_a_non_empty_reason():
    graph = concat_audio_filter(
        [AVSegment(1.0, "a"), AVSegment(1.0, "b")],
        audio_role="ambience",
    )
    with pytest.raises(AudioJoinError, match="fallback requires a non-empty reason"):
        audio_qa_for_graph(graph, audio_role="ambience")


def test_audio_qa_cannot_relabel_a_graph_after_the_edit():
    graph = concat_audio_filter(
        [AVSegment(1.0, "voice")], audio_role="speech"
    )
    with pytest.raises(AudioJoinError, match="does not match graph role"):
        audio_qa_for_graph(graph, audio_role="mixed")


def test_global_audio_contract_is_linked_and_covers_every_renderer():
    root = Path(__file__).resolve().parents[1]
    assert "docs/video-audio-quality.md" in (root / "README.md").read_text("utf-8")
    assert "docs/video-audio-quality.md" in (root / "CLAUDE.md").read_text("utf-8")

    joined_renderers = {
        "tools/build_match_reel.py": ("concat_av_filter(", 'audio_role="mixed"'),
        "src/tennislive/video/official.py": (
            "concat_av_filter(", 'audio_role="mixed"'
        ),
        "tools/build_interview_clip.py": (
            "concat_audio_filter(", 'audio_role="speech"'
        ),
        "src/tennislive/video/explainer.py": (
            "concat_audio_filter(", 'audio_role="speech"'
        ),
        "tools/build_grand_slam_v2.py": (
            "concat_audio_filter(", 'audio_role="ambience"', 'audio_role="speech"'
        ),
        "tools/build_grand_slam_short.py": (
            "concat_audio_filter(", 'audio_role="speech"'
        ),
    }
    for relative, required in joined_renderers.items():
        source = (root / relative).read_text("utf-8")
        assert all(token in source for token in required), relative

    n_a_renderers = (
        "src/tennislive/video/daily_point.py",
        "src/tennislive/video/pipeline.py",
        "src/tennislive/render/video_digest.py",
    )
    for relative in n_a_renderers:
        source = (root / relative).read_text("utf-8")
        assert "not_applicable_audio_qa(" in source, relative


_FFMPEG_EXECUTORS = {
    "call",
    "check_call",
    "check_output",
    "popen",
    "run",
    "runner",
    "system",
}


def _call_leaf(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id.casefold()
    if isinstance(function, ast.Attribute):
        return function.attr.casefold()
    return ""


def _names_in(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _mentions_ffmpeg(node: ast.AST) -> bool:
    """Inspect executable syntax, not comments or an arbitrary source substring."""
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and "ffmpeg" in item.id.casefold():
            return True
        if isinstance(item, ast.Attribute) and "ffmpeg" in item.attr.casefold():
            return True
        if (
            isinstance(item, ast.Constant)
            and isinstance(item.value, str)
            and "ffmpeg" in item.value.casefold()
        ):
            return True
    return False


def _assignment_targets(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {
        item.id
        for target in targets
        for item in ast.walk(target)
        if isinstance(item, ast.Name)
    }


def _ffmpeg_execution_calls(tree: ast.AST) -> list[ast.Call]:
    """Find actual process-launch calls, following simple command variables."""
    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            if not (_mentions_ffmpeg(value) or (_names_in(value) & tainted)):
                continue
            for target in _assignment_targets(node):
                if target not in tainted:
                    tainted.add(target)
                    changed = True

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_leaf(node) not in _FFMPEG_EXECUTORS:
            continue
        if _mentions_ffmpeg(node) or (_names_in(node) & tainted):
            calls.append(node)
    return calls


def test_every_python_ffmpeg_delivery_renderer_calls_unified_audio_qa():
    root = Path(__file__).resolve().parents[1]
    candidates = sorted(
        [*(root / "src").rglob("*.py"), *(root / "tools").rglob("*.py")]
    )
    # These files execute FFmpeg only to inspect media or exercise a synthetic
    # self-test.  The reason is deliberately next to the path: adding a new
    # exception must be an explicit review decision, never a filename pattern.
    diagnostic_allowlist = {
        "tools/check_crowd_rise.py": "measure crowd-level changes; no delivery MP4",
        "tools/check_reel_landed.py": "inspect an existing final reel",
        "tools/find_point_ends.py": "locate candidate point boundaries",
        "tools/interview_clip_selftest.py": "synthetic renderer self-test only",
    }
    known_delivery_renderers = {
        "src/tennislive/render/video_digest.py",
        "src/tennislive/video/daily_point.py",
        "src/tennislive/video/explainer.py",
        "src/tennislive/video/official.py",
        "src/tennislive/video/pipeline.py",
        "tools/build_grand_slam_short.py",
        "tools/build_grand_slam_v2.py",
        "tools/build_interview_clip.py",
        "tools/build_match_reel.py",
    }

    detected: dict[str, ast.AST] = {}
    for path in candidates:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not _ffmpeg_execution_calls(tree):
            continue
        relative = path.relative_to(root).as_posix()
        detected[relative] = tree

    assert known_delivery_renderers <= detected.keys(), (
        "FFmpeg 自动发现器漏掉既有交付入口："
        + ", ".join(sorted(known_delivery_renderers - detected.keys()))
    )
    assert diagnostic_allowlist.keys() <= detected.keys(), (
        "诊断 allowlist 已过期，应删除不再执行 FFmpeg 的条目："
        + ", ".join(sorted(diagnostic_allowlist.keys() - detected.keys()))
    )
    assert all(reason.strip() for reason in diagnostic_allowlist.values())

    delivery_renderers = set(detected) - diagnostic_allowlist.keys()
    assert delivery_renderers, "没有找到任何 FFmpeg delivery renderer，扫描规则失效"
    for relative in sorted(delivery_renderers):
        tree = detected[relative]
        calls = {
            _call_leaf(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert calls & {"audio_qa_for_graph", "not_applicable_audio_qa"}, (
            f"{relative} 执行 FFmpeg 交付，但没有真实调用统一 audio QA；"
            "注释或只出现 audio_qa 字样不能通过"
        )
        # The final report must be materialised, not merely computed and lost.
        assert "write_text" in calls, f"{relative} 没有把 audio QA sidecar 落盘"


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="FFmpeg is not installed",
)
def test_generated_duration_preserving_filtergraph_is_accepted_by_ffmpeg(tmp_path):
    inputs = []
    for index, (colour, frequency) in enumerate((("red", 440), ("blue", 880))):
        path = tmp_path / f"part-{index}.mkv"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={colour}:s=32x32:r=10:d=0.4",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=0.4",
                "-shortest",
                "-c:v",
                "ffv1",
                "-c:a",
                "pcm_s16le",
                str(path),
            ],
            check=True,
        )
        inputs.append(path)

    graph = concat_av_filter(
        [AVSegment(0.4, "a"), AVSegment(0.4, "b")],
        audio_role="mixed",
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path in inputs:
        command.extend(["-i", str(path)])
    command.extend(
        [
            "-filter_complex",
            graph.filtergraph,
            "-map",
            graph.video_label,
            "-map",
            graph.audio_label,
            "-f",
            "null",
            "-",
        ]
    )

    subprocess.run(command, check=True)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg is not installed",
)
def test_audio_only_filtergraph_keeps_exact_declared_duration(tmp_path):
    inputs = []
    for index, frequency in enumerate((440, 880)):
        path = tmp_path / f"tone-{index}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=0.4",
                str(path),
            ],
            check=True,
        )
        inputs.append(path)

    output = tmp_path / "joined.wav"
    graph = concat_audio_filter(
        [AVSegment(0.4, "one"), AVSegment(0.4, "two")],
        audio_role="ambience",
        channel_layout="mono",
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path in inputs:
        command.extend(["-i", str(path)])
    command.extend(
        [
            "-filter_complex",
            graph.filtergraph,
            "-map",
            graph.audio_label,
            str(output),
        ]
    )
    subprocess.run(command, check=True)
    duration = float(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    assert duration == pytest.approx(0.8, abs=1 / 48_000)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg is not installed",
)
def test_audio_only_filtergraph_pads_short_stems_to_declared_duration(tmp_path):
    inputs = []
    for index, frequency in enumerate((440, 880)):
        path = tmp_path / f"short-{index}.wav"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=0.2",
                str(path),
            ],
            check=True,
        )
        inputs.append(path)

    output = tmp_path / "padded.wav"
    graph = concat_audio_filter(
        [AVSegment(0.4, "one"), AVSegment(0.4, "two")],
        audio_role="ambience",
        channel_layout="mono",
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path in inputs:
        command.extend(["-i", str(path)])
    command.extend(
        ["-filter_complex", graph.filtergraph, "-map", graph.audio_label, str(output)]
    )
    subprocess.run(command, check=True)
    duration = float(
        subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    assert graph.output_duration == pytest.approx(0.8)
    assert duration == pytest.approx(0.8, abs=1 / 48_000)
