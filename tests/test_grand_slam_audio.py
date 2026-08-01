from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_grand_slam_ambience_uses_global_duration_safe_audio_joins():
    source = (ROOT / "tools" / "build_grand_slam_v2.py").read_text("utf-8")

    assert "concat_audio_filter(" in source
    assert 'channel_layout="mono"' in source
    assert "graph.output_duration" in source
    assert 'AudioJoinPolicy.keep()' in source
    assert '"-f", "concat"' not in source


def test_grand_slam_tts_stems_are_never_crossfaded_or_overlapped():
    source = (ROOT / "tools" / "build_grand_slam_v2.py").read_text("utf-8")
    final_join = source[source.index("# These files already contain") :]

    assert "AudioJoinPolicy.keep()" in final_join
    assert "concat_audio_filter(" in final_join
    assert "audio_qa_for_graph(" in final_join
    assert 'audio_role="speech"' in final_join
    assert 'OUT / "audio-qa.json"' in final_join
    assert "aggregate_audio_qa_layers(audio_layers)" in final_join
    assert '"layer_type": "scene_ambience"' in final_join
    assert '"layer_type": "scene_mix"' in final_join
    assert '"layer_type": "speech_timeline"' in final_join
    assert "acrossfade" not in final_join
    assert '"check_audio_qa.py"' in final_join


def test_grand_slam_v2_qa_preserves_ambience_and_speech_joins(monkeypatch):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace())
    from tennislive.video.audio import (
        AVSegment,
        AudioJoinPolicy,
        audio_qa_for_graph,
        concat_audio_filter,
    )
    from tools import build_grand_slam_v2 as v2
    from tools.check_audio_qa import validate_report

    ambience_graph = concat_audio_filter(
        [
            AVSegment(1.0, "cut-a"),
            AVSegment(1.0, "cut-b"),
            AVSegment(1.0, "cut-c"),
        ],
        audio_role="ambience",
    )
    speech_graph = concat_audio_filter(
        [
            AVSegment(1.0, "scene-a"),
            AVSegment(1.0, "scene-b"),
            AVSegment(1.0, "scene-c"),
        ],
        audio_role="speech",
        join_overrides={0: AudioJoinPolicy.keep(), 1: AudioJoinPolicy.keep()},
    )
    result = v2.aggregate_audio_qa_layers(
        [
            {
                "layer_id": "scene:open:ambience",
                "layer_type": "scene_ambience",
                "scene_id": "open",
                "audio_qa": audio_qa_for_graph(
                    ambience_graph,
                    audio_role="ambience",
                    reason="test ambience cuts",
                ),
            },
            {
                "layer_id": "programme:speech-timeline",
                "layer_type": "speech_timeline",
                "scene_id": None,
                "audio_qa": audio_qa_for_graph(
                    speech_graph,
                    audio_role="speech",
                    reason="test speech timeline",
                ),
            },
        ]
    )
    validate_report(result)

    assert result["status"] == "pass"
    assert result["role"] == "mixed"
    assert result["duration_delta_seconds"] == 0.0
    assert result["hard_cut_count"] == 0
    assert result["transition_count"] == len(result["joins"]) == 4
    assert result["fade_through_silence_count"] == 2
    assert result["fallback_count"] == 2
    assert result["keep_count"] == 2
    assert result["declick_count"] == result["lcut_crossfade_count"] == 0
    assert result["layer_count"] == 2
    assert {join["layer_id"] for join in result["joins"]} == {
        "scene:open:ambience",
        "programme:speech-timeline",
    }
    layers = {layer["layer_id"]: layer for layer in result["layers"]}
    assert layers["scene:open:ambience"]["audio_qa"][
        "fade_through_silence_count"
    ] == 2
    assert layers["programme:speech-timeline"]["audio_qa"]["keep_count"] == 2


def test_grand_slam_v2_scene_ambience_returns_its_own_qa(tmp_path, monkeypatch):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace())
    from tools import build_grand_slam_v2 as v2

    def run(cmd, **_kwargs):
        output = Path(cmd[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"audio" * 300)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(v2, "ROOT", tmp_path)
    monkeypatch.setattr(v2.subprocess, "run", run)
    output, qa = v2.build_scene_ambient(
        [("source.mp4", 0.0, 1.0), ("source.mp4", 4.0, 1.0)],
        2.0,
        tmp_path / "scene.wav",
    )

    assert output == tmp_path / "scene.wav"
    assert qa["status"] == "pass"
    assert qa["role"] == "ambience"
    assert qa["duration_delta_seconds"] == 0.0
    assert qa["hard_cut_count"] == 0
    assert qa["transition_count"] == 1
    assert qa["fade_through_silence_count"] == 1
    assert qa["joins"][0]["mode"] == "fade_through_silence"
    assert qa["joins"][0]["previous_source"] != qa["joins"][0]["next_source"]


def test_grand_slam_short_tts_uses_speech_role_and_not_concat_demuxer():
    source = (ROOT / "tools" / "build_grand_slam_short.py").read_text("utf-8")
    tts_join = source[source.index("def try_tts") : source.index("def storyboard_sheet")]

    assert "concat_audio_filter(" in tts_join
    assert 'audio_role="speech"' in tts_join
    assert "AudioJoinPolicy.keep()" in tts_join
    assert '"-f", "concat"' not in tts_join
    assert "acrossfade" not in tts_join
    assert '"check_audio_qa.py"' in source


def test_grand_slam_short_tts_writes_duration_safe_audio_qa(tmp_path, monkeypatch):
    import json

    from tools import build_grand_slam_short as short

    commands: list[list[str]] = []

    def synth(_text, dst, *_args):
        Path(dst).write_bytes(b"speech")

    def run(cmd, **_kwargs):
        commands.append(list(cmd))
        output = Path(cmd[-1])
        if output.suffix in {".mp3", ".wav", ".m4a", ".mp4"}:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"rendered")
        return type("R", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr(short, "_piper_model", lambda: None)
    monkeypatch.setattr(short, "_synth_edge", synth)
    monkeypatch.setattr(short, "_audio_dur", lambda *_: 0.5)
    monkeypatch.setattr(short.subprocess, "run", run)

    scenes = [
        {"vo": "第一句。", "dur": 1.25},
        {"vo": "第二句。", "dur": 0.75},
        {"vo": "第三句。", "dur": 1.0},
    ]
    result = short.try_tts(scenes, {}, tmp_path, "ffmpeg")

    assert result == tmp_path / "voiceover.mp3"
    join_command = next(cmd for cmd in commands if "-filter_complex" in cmd)
    graph = join_command[join_command.index("-filter_complex") + 1]
    assert "[aj0][aj1][aj2]concat=n=3:v=0:a=1[speechout]" in graph
    assert "acrossfade" not in graph
    assert "afade=" not in graph

    qa = json.loads((tmp_path / "audio-qa.json").read_text("utf-8"))
    assert qa["status"] == "pass"
    assert qa["role"] == "speech"
    assert qa["transition_count"] == qa["keep_count"] == 2
    assert qa["duration_delta_seconds"] == 0.0
    assert qa["expected_duration_seconds"] == 3.0
    assert all(join["mode"] == "keep" for join in qa["joins"])
    assert all(join["overlap"] == 0.0 for join in qa["joins"])
    assert all(
        max(join["fade_in"], join["fade_out"]) <= 0.02
        for join in qa["joins"]
    )
