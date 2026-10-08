"""A cache must never turn a successful synthesis into broken audio/subtitles."""
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from tennislive.video import tts


def synth(text, path, *args, **kwargs):
    path.write_bytes(text.encode())
    return [{"text": text, "offset": 0, "duration": 1}]


@pytest.mark.parametrize("damage", ["truncated", "empty_audio", "invalid_marks", "invalid_json"])
def test_corrupt_entry_is_regenerated(tmp_path, monkeypatch, damage):
    cache = tmp_path / "cache"
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(cache))
    first = tmp_path / "first.mp3"
    tts.tts_one("hello", first, "v", "+0%", synth=synth)
    entry, = cache.glob("*.zip")
    if damage == "truncated":
        entry.write_bytes(b"PK")
    else:
        with zipfile.ZipFile(entry, "w") as bundle:
            bundle.writestr("audio.mp3", b"" if damage == "empty_audio" else b"old")
            bundle.writestr("marks.json", "{" if damage == "invalid_json" else
                            json.dumps({} if damage == "invalid_marks" else [{"text": "old"}]))
    calls = []
    def fresh(*args, **kwargs):
        calls.append(1)
        return synth(*args, **kwargs)
    target = tmp_path / "new.mp3"
    marks = tts.tts_one("hello", target, "v", "+0%", synth=fresh)
    assert calls == [1]
    assert target.read_bytes() == b"hello" and marks[0]["text"] == "hello"
    assert not list(cache.glob(".tts-*"))


def test_backend_change_does_not_reuse_other_backend_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.azure_tts, "available", lambda: False)
    tts.tts_one("hello", tmp_path / "a.mp3", "v", "+0%", synth=synth)
    monkeypatch.setattr(tts.azure_tts, "available", lambda: True)
    calls = []
    def fresh(*args, **kwargs):
        calls.append(1)
        return synth(*args, **kwargs)
    tts.tts_one("hello", tmp_path / "b.mp3", "v", "+0%", synth=fresh)
    assert calls == [1]


def test_concurrent_writers_publish_matching_audio_and_marks(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(cache))
    barrier = Barrier(2)
    def simultaneous(text, path, *args, **kwargs):
        identity = path.stem
        path.write_bytes(identity.encode())
        barrier.wait(timeout=10)
        return [{"text": identity}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(tts.tts_one, "same", tmp_path / f"{i}.mp3", "v", "+0%",
                               synth=simultaneous) for i in range(2)]
        for future in futures:
            future.result()
    target = tmp_path / "restored.mp3"
    def unexpected(*args, **kwargs):
        pytest.fail("intact entry should be reused")
    marks = tts.tts_one("same", target, "v", "+0%", synth=unexpected)
    assert target.read_text() == marks[0]["text"]
    assert not list(cache.glob(".tts-*"))


def test_failed_cache_publish_preserves_successful_result(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(tts.os, "replace", fail)
    target = tmp_path / "a.mp3"
    assert tts.tts_one("hello", target, "v", "+0%", synth=synth)[0]["text"] == "hello"
    assert target.read_bytes() == b"hello"
