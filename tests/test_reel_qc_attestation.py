from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_reel_landed as landed  # noqa: PLC0415
    return landed


def test_L2凭证绑定spec字幕与成片并回写render(tmp_path):
    landed = _tool()
    spec_path = tmp_path / "demo.json"
    spec = {"slug": "demo", "segments": []}
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    film = tmp_path / "demo.mp4"
    film.write_bytes(b"the-checked-film")
    ass = tmp_path / "subtitles.ass"
    ass.write_text("Dialogue: 0,0:00:00,0:00:01,Default,,0,0,0,,字幕\n",
                   encoding="utf-8")
    (tmp_path / "render.json").write_text('{"film_seconds": 1}', encoding="utf-8")

    qc_path = landed.write_attestation(film, spec_path, spec)
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    render = json.loads((tmp_path / "render.json").read_text(encoding="utf-8"))
    assert qc["status"] == "pass"
    assert qc["spec_sha256"] == hashlib.sha256(spec_path.read_bytes()).hexdigest()
    assert qc["ass_sha256"] == hashlib.sha256(ass.read_bytes()).hexdigest()
    assert qc["film_sha256"] == hashlib.sha256(film.read_bytes()).hexdigest()
    assert qc["film_bytes"] == film.stat().st_size
    assert render["film_sha256"] == qc["film_sha256"]
    assert render["film_bytes"] == qc["film_bytes"]
    assert render["qc_attestation_sha256"] == hashlib.sha256(qc_path.read_bytes()).hexdigest()


# Actual media tests: an intentional silent but complete audio stream now passes
# the owner's no-loudness policy; missing/truncated streams still must fail.


@pytest.fixture(scope="module")
def audio_structure_films(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("actual ffmpeg/ffprobe required")
    directory = tmp_path_factory.mktemp("reel-no-loudness")
    films = {}
    for label, audio_length in (("complete", 3.0), ("missing", None), ("truncated", .5)):
        path = directory / f"{label}.mp4"
        args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "color=black:s=1080x1440:r=10:d=3"]
        if audio_length is not None:
            args += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={audio_length}",
                     "-map", "0:v", "-map", "1:a", "-c:a", "aac"]
        args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)]
        subprocess.run(args, capture_output=True, check=True)
        films[label] = path
    return films


@pytest.mark.parametrize("kind,want", [("complete", 0), ("missing", 1), ("truncated", 1), ("late_same_tail", 1)])
def test_normal_qc_probes_actual_audio_structure_without_loudness(
        tmp_path, monkeypatch, capsys, audio_structure_films, kind, want):
    landed = _tool()
    film = tmp_path / "demo.mp4"
    shutil.copy2(audio_structure_films["complete" if kind == "late_same_tail" else kind], film)
    spec = {"slug": "demo", "segments": [{"source": "main", "start": 0, "end": 2.6}]}
    sp = tmp_path / "demo.json"
    sp.write_text(json.dumps(spec))
    (tmp_path / "render.json").write_text(json.dumps({"cover_seconds": .4, "outro_seconds": 0}))
    (tmp_path / "subtitles.ass").write_text("[Events]\n")
    # Isolate audio structure, preserving the production call to the unrelated
    # hash/caption gate (its actual artifact checks have dedicated regressions).
    import foreground_audio_gate
    import production_style
    import winners_ue_gate
    verified = []
    monkeypatch.setattr(foreground_audio_gate, "verify_final", lambda *a, **kw: verified.append(kw["film"]))
    monkeypatch.setattr(production_style, "match_footage_problem", lambda spec: None)
    monkeypatch.setattr(winners_ue_gate, "problem", lambda spec: None)
    monkeypatch.setattr(landed, "stat_card_headshot_problem", lambda *a, **kw: None)
    def forbidden(*a, **kw):
        pytest.fail("normal QC called a removed loudness scan")
    for name in ("per_second_db", "dead_seconds", "quiet_windows", "evidence_windows", "legacy_loudness_checks"):
        monkeypatch.setattr(landed, name, forbidden)
    original_sh = landed.sh
    probes = []
    def structural_only(*args):
        assert args[0] == "ffprobe", "normal QC must not decode PCM through ffmpeg"
        probes.append(args)
        result = original_sh(*args)
        if kind == "late_same_tail":
            data = json.loads(result)
            audio = next(s for s in data["streams"] if s["codec_type"] == "audio")
            audio.update(start_time="1.5", duration="1.5")
            result = json.dumps(data)
        return result
    monkeypatch.setattr(landed, "sh", structural_only)
    monkeypatch.setattr(sys, "argv", ["check_reel_landed.py", "--film", str(film), "--spec", str(sp)])
    # A stale certificate must be revoked on a failed structural check.
    qc_path = tmp_path / "qc_attestation.json"
    qc_path.write_text('{"status":"pass","old":true}')
    assert landed.main() == want
    assert verified == [film]
    assert len(probes) == 1
    assert "逐秒响度" not in capsys.readouterr().out
    if want:
        assert not qc_path.exists()
    else:
        qc = json.loads(qc_path.read_text())
        assert qc["checks"]["loudness_checks"] == "removed_by_owner"
        assert "silence_floor_db" not in qc["checks"]
        assert qc["film_sha256"] == hashlib.sha256(film.read_bytes()).hexdigest()


@pytest.mark.parametrize("duration", ["nan", "inf", "0", "-1", True])
def test_nonfinite_or_nonpositive_audio_duration_is_not_a_valid_track(monkeypatch, duration):
    landed = _tool()
    streams = [dict(codec_type="video", codec_name="h264", width=1080, height=1440, duration="3"),
               dict(codec_type="audio", codec_name="aac", channels=2, sample_rate="48000", duration=duration)]
    monkeypatch.setattr(landed, "sh", lambda *args: json.dumps({"streams": streams}))
    with pytest.raises(ValueError):
        landed.probe_media_streams(Path("unused.mp4"))


def test_finite_stream_fields_cannot_overflow_the_end_time(monkeypatch):
    landed = _tool()
    streams = [dict(codec_type="video", codec_name="h264", width=1080, height=1440,
                    duration="3", start_time="0"),
               dict(codec_type="audio", codec_name="aac", channels=2, sample_rate="48000",
                    duration="1e308", start_time="1e308")]
    monkeypatch.setattr(landed, "sh", lambda *args: json.dumps({"streams": streams}))
    with pytest.raises(ValueError, match="流尾端时间必须有限"):
        landed.probe_media_streams(Path("unused.mp4"))
