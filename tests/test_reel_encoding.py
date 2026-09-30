"""Exercise the actual final export call, not just its ffprobe level label."""
import ast
from fractions import Fraction
import inspect
import json
import re
import subprocess

import pytest

from tools import build_match_reel as reel


def _options(width=1080, height=1440, fps="25"):
    args = reel.final_video_compat_args(width, height, fps)
    return dict(zip(args[::2], args[1::2]))


@pytest.mark.parametrize("fps,level", [
    ("25", "4.1"), ("30", "4.1"), ("30000/1001", "4.1"),
    ("50", "4.2"), ("60", "4.2"), ("60000/1001", "4.2"),
])
def test_export_level_uses_macroblock_rate_without_changing_fps(fps, level):
    options = _options(fps=fps)
    assert options["-level:v"] == level
    assert Fraction(options["-r"]) == Fraction(fps)
    assert Fraction(options["-enc_time_base"].replace(":", "/")) == 1 / Fraction(fps)
    assert int(options["-video_track_timescale"]) % Fraction(fps).numerator == 0
    assert options["-fps_mode"] == "cfr"
    assert options["-profile:v"] == "high"
    params = dict(p.split("=", 1) for p in options["-x264-params"].split(":"))
    assert params == {"ref": "3", "mvrange": "511", "vbv-maxrate": "12000", "vbv-bufsize": "24000"}


@pytest.mark.parametrize("width,height,fps", [
    (3840, 2160, "25"), (1080, 1440, "120"), (16000, 16, "25"),
    (1081, 1440, "25"), (0, 1440, "25"), (1080, 1440, "0"),
])
def test_unsupported_resources_are_not_mislabeled_as_level_41(width, height, fps):
    with pytest.raises(reel.ReelError):
        reel.final_video_compat_args(width, height, fps)


def _run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    return result


def _sps(path):
    trace = _run("ffmpeg", "-hide_banner", "-i", str(path), "-map", "0:v:0",
                 "-c:v", "copy", "-bsf:v", "trace_headers", "-frames:v", "1",
                 "-f", "null", "-").stderr
    fields = ("profile_idc", "level_idc", "frame_mbs_only_flag", "num_units_in_tick",
              "time_scale", "pic_width_in_mbs_minus1", "pic_height_in_map_units_minus1",
              "max_num_ref_frames", "max_dec_frame_buffering", "log2_max_mv_length_vertical")
    return {field: int(re.search(r"\b" + field + r"\s+\S+\s+=\s+(\d+)", trace)[1])
            for field in fields}


@pytest.mark.parametrize("fps,topbar,level", [
    ("25", True, 41), ("30000/1001", True, 41), ("60", False, 42),
])
def test_native_export_has_genuine_sps_timing_resources_and_frame_timestamps(
        tmp_path, monkeypatch, fps, topbar, level):
    # A tiny synthetic input at full delivery dimensions; never read old releases.
    source = tmp_path / "input.mp4"
    _run("ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         f"testsrc2=size=1080x1440:rate={fps}:duration=1.2", "-f", "lavfi",
         "-i", "sine=frequency=1000:sample_rate=48000:duration=1.2",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-threads", "2",
         "-c:a", "aac", "-y", str(source))
    ass = tmp_path / "empty.ass"
    ass.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1440\n"
                   "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
                   "SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
                   "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                   "Alignment, MarginL, MarginR, MarginV, Encoding\n"
                   "Style: Default,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
                   "0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1\n[Events]\n"
                   "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    monkeypatch.setattr(reel, "LAYOUT", "full")
    graph = (reel.topbar_filtergraph(.24, .72, ass, ass) if topbar
             else reel.plain_filtergraph(ass, .24, .96, None))
    final = tmp_path / "export.mp4"
    # Evaluate the real render() export call with local inputs. This catches a
    # helper that passes unit tests but is forgotten at the production call site.
    calls = [node for node in ast.walk(ast.parse(inspect.getsource(reel.render)))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "run" and any(
                 isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name)
                 and arg.value.id == "video_args" for arg in node.args)]
    assert len(calls) == 1
    logs = []

    def export(*args):
        args = list(args)
        args[args.index("-loglevel") + 1] = "info"
        args[1:1] = ["-filter_complex_threads", "1"]
        args[-1:-1] = ["-threads", "2"]
        result = _run(*args)
        logs.append(result.stderr)
        return result

    context = dict(vars(reel), run=export, silent=source, mixed=source, final=final,
                   foot_inputs=[], wm_inputs=[], scrim_inputs=[], FPS_EXPR=fps,
                   video_args=["-filter_complex", graph, "-map", "[out]"])
    eval(compile(ast.Expression(calls[0]), "native-final-export", "eval"), context)
    assert "vbv_maxrate=12000 vbv_bufsize=24000" in logs[0]
    assert not re.search(r"(?:MB rate|DPB size|frame MB size|VBV).*level limit", logs[0])
    sps = _sps(final)
    assert sps["profile_idc"] == 100 and sps["level_idc"] == level
    assert sps["frame_mbs_only_flag"] == 1
    assert Fraction(sps["time_scale"], 2 * sps["num_units_in_tick"]) == Fraction(fps)
    mbs = (sps["pic_width_in_mbs_minus1"] + 1) * (sps["pic_height_in_map_units_minus1"] + 1)
    max_fs, max_mbps, max_dpb = (8192, 245760, 32768) if level == 41 else (8704, 522240, 34816)
    assert mbs <= max_fs and mbs * Fraction(fps) <= max_mbps
    assert mbs * max(sps["max_num_ref_frames"], sps["max_dec_frame_buffering"]) <= max_dpb
    # SPS uses quarter-pixel MV units. Actual decoded MV validation is a separate
    # full-frame audit; this assertion alone is not proof of decoder conformance.
    assert sps["log2_max_mv_length_vertical"] <= 11
    data = json.loads(_run("ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_streams", "-show_frames", "-of", "json", str(final)).stdout)
    stream = data["streams"][0]
    assert (stream["width"], stream["height"], stream["pix_fmt"]) == (1080, 1440, "yuv420p")
    times = [int(f["best_effort_timestamp"]) * Fraction(stream["time_base"]) for f in data["frames"]]
    assert len(times) >= 25 and times[0] == 0
    assert all(b - a == 1 / Fraction(fps) for a, b in zip(times, times[1:]))
    original = json.loads(_run("ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-count_frames", "-show_entries", "stream=nb_read_frames",
                              "-of", "json", str(source)).stdout)
    assert len(times) == int(original["streams"][0]["nb_read_frames"])
    _run("ffmpeg", "-v", "error", "-xerror", "-i", str(final), "-f", "null", "-")
