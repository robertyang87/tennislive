"""Exercise render boundaries without fetching production footage or using TTS."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tennislive.video import explainer as E


def test_narration_duration_is_probed_once_and_shared_with_subtitles(tmp_path, monkeypatch):
    probes = []
    cues = []
    durations = [1.23456, 2.34567]

    def runner(cmd, **kwargs):
        if cmd[0] == "ffprobe":
            probes.append(Path(cmd[-1]).name)
            return SimpleNamespace(stdout=str(durations[len(probes) - 1]))
        Path(cmd[-1]).write_bytes(b"video")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(E.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(E, "subtitle_cues", lambda text, seconds, **kw: cues.append(seconds) or [])
    E.assemble_explainer_video(
        [tmp_path / "a.jpg", tmp_path / "b.jpg"],
        [tmp_path / "a.mp3", tmp_path / "b.mp3"],
        tmp_path / "out.mp4", captions=["第一段", "第二段"], runner=runner,
    )
    assert probes == ["a.mp3", "b.mp3"]
    assert cues == durations  # Preserve full precision; don't derive from rounded slide lengths.


@pytest.mark.parametrize("opening, message", [
    ({"intro": "missing.mp4", "intro_url": "https://example.test/video.mp4"}, "只能写"),
    ({"intro": "missing.mp4"}, "找不到"),
    ({"canvas": "1:1"}, "canvas"),
    ({"intro_url": "https://example.test/video.mp4", "intro_start": -1}, "区间"),
    ({"intro_url": "https://example.test/video.mp4", "intro_end": 0}, "区间"),
    ({"intro_url": "https://example.test/video.mp4", "intro_start": "nan"}, "区间"),
    ({"intro_url": "https://example.test/video.mp4", "intro_end": "inf"}, "区间"),
    ({"intro_url": "https://example.test/video.mp4", "intro_start": "bad"}, "秒数"),
    ({"intro_url": "https://example.test/video.mp4", "intro_cx": 0.4}, "固定中间"),
])
def test_invalid_opening_fails_before_render_or_tts(tmp_path, monkeypatch, opening, message):
    monkeypatch.setitem(E._OPENINGS, "test-efficiency", opening)
    monkeypatch.setattr(E, "explainer_script", lambda _: [])
    render, tts = Mock(), Mock()
    monkeypatch.setattr(E, "render_explainer_slides", render)
    monkeypatch.setattr(E, "synthesize_narration", tts)
    with pytest.raises((E.ExplainerVideoError, ValueError), match=message):
        E.generate_explainer_video(SimpleNamespace(slug="test-efficiency"), tmp_path)
    render.assert_not_called()
    tts.assert_not_called()


@pytest.mark.parametrize("failure", ["tiny_download", "metadata", "assembly"])
def test_remote_intro_cleaned_on_every_failure(tmp_path, monkeypatch, failure):
    import requests

    monkeypatch.setitem(E._OPENINGS, "test-efficiency", {
        "intro_url": "https://example.test/video.mp4", "intro_start": 1, "intro_end": 3,
    })
    monkeypatch.setattr(E, "explainer_script", lambda _: [])
    monkeypatch.setattr(E, "render_explainer_slides", lambda *a, **k: [])
    monkeypatch.setattr(E, "synthesize_narration", lambda *a, **k: [])
    monkeypatch.setattr(E, "_render_intro_badge", lambda *a, **k: None)
    monkeypatch.setattr(E, "_build_outro_clip", lambda *a, **k: None)
    monkeypatch.setattr(E.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(E, "assemble_explainer_video", Mock(side_effect=RuntimeError("assembly")))
    temp_dirs = []
    original_tempdir = E.tempfile.TemporaryDirectory

    def tempdir(**kwargs):
        directory = original_tempdir(dir=tmp_path, **kwargs)
        temp_dirs.append(Path(directory.name))
        return directory

    monkeypatch.setattr(E.tempfile, "TemporaryDirectory", tempdir)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, **kwargs):
            yield b"x" * (10 if failure == "tiny_download" else 2048)

    monkeypatch.setattr(requests, "get", lambda *a, **k: Response())
    if failure == "metadata":
        (tmp_path / "narration.json").mkdir()
    error = {"tiny_download": E.ExplainerVideoError, "metadata": OSError, "assembly": RuntimeError}[failure]
    with pytest.raises(error):
        E.generate_explainer_video(SimpleNamespace(slug="test-efficiency"), tmp_path)
    assert len(temp_dirs) == 1
    assert not temp_dirs[0].exists()


def test_import_does_not_open_explainer_photos(tmp_path):
    import os
    import subprocess
    import sys

    env = dict(os.environ, PYTHONPATH=str(E._REPO / "src"))
    result = subprocess.run(
        [sys.executable, "-c", """
from pathlib import Path
from PIL import Image

def forbidden(*args, **kwargs):
    raise AssertionError('import must not read production photos')

Path.read_bytes = forbidden
Image.open = forbidden
from tennislive.video import explainer
assert '<image' in explainer._ACADEMY_SPAN_DIAGRAM
assert explainer._SCRIPTS
"""], cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_lazy_diagrams_embed_identical_image_data_at_render(tmp_path, monkeypatch):
    import base64

    from PIL import Image

    from tennislive.video import masters_grid as M

    monkeypatch.setattr(E, "_REPO", tmp_path)
    monkeypatch.setattr(M, "VENUE_DIR", tmp_path / "assets/venues")
    M.VENUE_DIR.mkdir(parents=True)
    for _, filename, _ in M.NINE_MASTERS:
        Image.new("RGB", (30, 40), "navy").save(M.VENUE_DIR / filename)
    lazy = M.nine_masters_grid(embed_images=False)
    assert "data:image" not in lazy
    assert E._embed_diagram_assets(lazy) == M.nine_masters_grid()

    faces = tmp_path / "assets/explainer/nadal-academy/faces"
    faces.mkdir(parents=True)
    expected = E._ACADEMY_SPAN_DIAGRAM
    for name in ("munar", "eala", "ruud", "landaluce", "wong"):
        path = faces / f"{name}.jpg"
        Image.new("RGB", (20, 20), "navy").save(path)
        uri = "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()
        expected = expected.replace(f"asset://assets/explainer/nadal-academy/faces/{name}.jpg", uri)
    assert E._embed_diagram_assets(E._ACADEMY_SPAN_DIAGRAM) == expected
    (faces / "munar.jpg").unlink()
    with pytest.raises(FileNotFoundError):
        E._embed_diagram_assets(E._ACADEMY_SPAN_DIAGRAM)
