"""Second ASR processes the interview and boundary context, not the full match."""
import shutil
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_interview_clip as clip


@pytest.mark.parametrize("vad", [True, False])
def test_english_crop_keeps_context_and_restores_source_times(tmp_path, monkeypatch, vad):
    commands = []
    paths = []

    def run(cmd, **kwargs):
        commands.append((cmd, kwargs))
        Path(cmd[-1]).touch()

    class Model:
        def transcribe(self, path, **kwargs):
            paths.append(Path(path))
            assert kwargs == {"language": "en", "task": "transcribe",
                              "word_timestamps": True, "vad_filter": vad}
            # Cropped start is 92; context on both sides must not enter the verdict.
            words = [SimpleNamespace(start=a, end=b, word=text) for a, b, text in [
                (7, 8, "before"), (8, 9, " first "), (17, 18, "middle"),
                (28, 29, "last"), (29, 30, "after")]]
            return iter([SimpleNamespace(words=words)]), None

    monkeypatch.setattr(clip.subprocess, "run", run)
    got = clip.transcribe_source_words(Model(), tmp_path / "source.wav",
                                      {"start": 100, "end": 120, "whisper_vad_filter": vad})
    assert got == [(100.0, 101.0, "first"), (109.0, 110.0, "middle"), (120.0, 121.0, "last")]
    cmd, kwargs = commands[0]
    assert cmd[cmd.index("-ss") + 1] == "92.0"
    assert cmd[cmd.index("-t") + 1] == "36.0"
    assert kwargs["check"] and kwargs["timeout"] == 120
    assert all(not path.exists() for path in paths)


def test_actual_ffmpeg_only_supplies_bounded_pcm_to_model(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")
    audio = tmp_path / "source.wav"
    with wave.open(str(audio), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        out.writeframes(b"\0\0" * 16000 * 100)

    class Model:
        def transcribe(self, path, **kwargs):
            with wave.open(path) as inp:
                assert inp.getframerate() == 16000
                assert inp.getnchannels() == 1
                assert inp.getnframes() / inp.getframerate() == pytest.approx(26.0)
            return iter([SimpleNamespace(words=[SimpleNamespace(start=8, end=9, word="hello")])]), None

    assert clip.transcribe_source_words(Model(), audio, {"start": 60, "end": 70}) == [
        (60.0, 61.0, "hello")]


def test_crop_failure_does_not_call_asr(tmp_path, monkeypatch):
    def fail(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(clip.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        clip.transcribe_source_words(None, tmp_path / "missing.wav", {"start": 100, "end": 120})


@pytest.mark.parametrize("start,end", [(-1, 2), (4, 4), (5, 4), (float("nan"), 4), (0, float("inf"))])
def test_invalid_default_window_fails_before_audio_work(tmp_path, monkeypatch, start, end):
    def unexpected(*args, **kwargs):
        pytest.fail("invalid time range must fail before ffmpeg")

    monkeypatch.setattr(clip.subprocess, "run", unexpected)
    with pytest.raises(SystemExit, match="ASR 需要有效正文"):
        clip.transcribe_source_words(None, tmp_path / "source.wav", {"start": start, "end": end})
