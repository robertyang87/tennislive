from __future__ import annotations

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
    TimelineDeclaration,
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


def test_default_concat_refuses_real_acrossfade_that_would_shorten_timeline():
    with pytest.raises(AudioJoinError, match="changes the programme duration"):
        concat_av_filter(
            [AVSegment(10.0, "a"), AVSegment(8.0, "b")],
            audio_role="music",
            join_overrides={0: AudioJoinPolicy.acrossfade(0.50)},
        )


def test_real_acrossfade_requires_and_reports_matching_video_timeline():
    segments = [AVSegment(10.0), AVSegment(8.0), AVSegment(6.0)]
    policies = [
        AudioJoinPolicy.acrossfade(0.50),
        AudioJoinPolicy.acrossfade(0.25, curve="hsin"),
    ]
    timeline = TimelineDeclaration(
        video_overlaps=(0.50, 0.25),
        expected_output_duration=23.25,
    )

    result = build_acrossfade_audio_filter(
        segments, policies, audio_role="music", timeline=timeline
    )

    assert result.output_duration == pytest.approx(23.25)
    assert result.duration_delta == pytest.approx(-0.75)
    assert result.overlaps == (0.50, 0.25)
    assert result.filtergraph.count("acrossfade=") == 2
    assert "acrossfade=d=0.500:c1=qsin:c2=qsin[ax0]" in result.filtergraph
    assert "acrossfade=d=0.250:c1=hsin:c2=hsin[aout]" in result.filtergraph


def test_real_acrossfade_rejects_missing_or_mismatched_video_timeline():
    segments = [AVSegment(10.0), AVSegment(8.0)]
    policies = [AudioJoinPolicy.acrossfade(0.50)]

    with pytest.raises(AudioJoinError, match="explicit matching video"):
        build_acrossfade_audio_filter(
            segments, policies, audio_role="music", timeline=None
        )
    with pytest.raises(AudioJoinError, match="does not match video"):
        build_acrossfade_audio_filter(
            segments,
            policies,
            audio_role="music",
            timeline=TimelineDeclaration((0.40,), 17.60),
        )
    with pytest.raises(AudioJoinError, match="output duration"):
        build_acrossfade_audio_filter(
            segments,
            policies,
            audio_role="music",
            timeline=TimelineDeclaration((0.50,), 17.60),
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
    assert skipped["transition_count"] == 0
    assert skipped["fallback_count"] == 0
    assert skipped["joins"] == []
    with pytest.raises(AudioJoinError, match="requires a reason"):
        not_applicable_audio_qa(audio_role="silence", reason="")


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


def test_every_ffmpeg_renderer_declares_audio_qa_and_no_raw_audio_concat_escapes():
    root = Path(__file__).resolve().parents[1]
    candidates = list((root / "src").rglob("*.py"))
    candidates.extend((root / "tools").glob("build_*.py"))
    renderers = []
    for path in candidates:
        source = path.read_text(encoding="utf-8")
        if "ffmpeg" not in source or path.name in {"audio.py", "cli.py"}:
            continue
        renderers.append(path)
        assert "audio_qa" in source or "audio-qa" in source, path.relative_to(root)
        assert "acrossfade=" not in source, path.relative_to(root)
        assert not __import__("re").search(
            r"concat=n=[^\n\"']*:a=1", source
        ), path.relative_to(root)
    assert renderers, "没有找到任何 FFmpeg renderer，扫描规则失效"


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
