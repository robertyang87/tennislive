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


def _valid_speech(text, path, *args, **kwargs):
    """A decodable (silent) fixture; no loudness/silence acceptance check."""
    import wave
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\0\0" * 16000)
    return [{"text": text, "offset": 0, "duration": 5_000_000}]


@pytest.fixture
def frozen_speech(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.azure_tts, "available", lambda: False)
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path / "cache"))
    request = tts.tts_request("冻结的这一句。", "zh-CN-YunjianNeural", "+6%")
    bundle = tmp_path / "speech.zip"
    original = tmp_path / "original.mp3"
    with tts.tts_bundle_session(output_path=bundle, expected_requests=[request],
                                metadata={"slug": "frozen-test"}) as session:
        marks = tts.tts_one(request["text"], original, request["voice"], request["rate"],
                            synth=_valid_speech)
    return bundle, request, original.read_bytes(), marks, session.identity


def test_frozen_bundle_captures_actual_cache_hit_and_brand_only(tmp_path, monkeypatch):
    """Finite real calls survive a fresh machine; unrelated cache files are ignored."""
    import hashlib
    from tennislive.video.tts_bundle import validate_bundle
    monkeypatch.setattr(tts.azure_tts, "available", lambda: False)
    cache = tmp_path / "cache"
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(cache))
    body = tts.tts_request("本期正文。", "v", "+6%")
    brand = tts.tts_request("关注网球时差，时差归我，好球归你。", "v", "+6%")
    tts.tts_one(body["text"], tmp_path / "warm.mp3", "v", "+6%", synth=_valid_speech)
    (cache / "unrelated-191-reference-cache.zip").write_bytes(b"not scanned")
    bundle = tmp_path / "frozen.zip"
    def no_synthesis(*args, **kwargs):
        pytest.fail("warm body must capture the actual cache result")
    with tts.tts_bundle_session(output_path=bundle, expected_requests=[body, brand]) as captured:
        bmarks = tts.tts_one(body["text"], tmp_path / "body.mp3", "v", "+6%", synth=no_synthesis)
        omarks = tts.tts_one(brand["text"], tmp_path / "outro.mp3", "v", "+6%", synth=_valid_speech)
    report = validate_bundle(bundle, [brand, body])
    assert report["request_count"] == 2
    assert report["quality_approval"] is False
    assert captured.identity["bundle_sha256"] == hashlib.sha256(bundle.read_bytes()).hexdigest()
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path / "empty-remote-cache"))
    clone = tmp_path / "render-copy.zip"
    with tts.tts_bundle_session(input_path=bundle, output_path=clone,
                                expected_requests=[brand, body]) as restored:
        assert tts.tts_one(brand["text"], tmp_path / "render-brand.mp3", "v", "+6%",
                           synth=no_synthesis) == omarks
        assert tts.tts_one(body["text"], tmp_path / "render-body.mp3", "v", "+6%",
                           synth=no_synthesis) == bmarks
        restored.write()
    assert (tmp_path / "render-body.mp3").read_bytes() == (tmp_path / "body.mp3").read_bytes()
    assert (tmp_path / "render-brand.mp3").read_bytes() == (tmp_path / "outro.mp3").read_bytes()
    assert restored.identity["strict_reused"] is True
    assert clone.read_bytes() == bundle.read_bytes()
    assert not (tmp_path / "empty-remote-cache").exists()


@pytest.mark.parametrize("field,value", [
    ("text", "已经改稿。"), ("voice", "other"), ("rate", "+7%"),
    ("pitch", "+1Hz"), ("style", "cheerful"), ("styledegree", "2"),
    ("lead_pause", .2), ("backend", "azure"),
])
def test_frozen_wrong_current_parameters_fail_before_audio_or_synthesis(
        frozen_speech, tmp_path, monkeypatch, field, value):
    from tennislive.video import tts_bundle
    bundle, request, _, _, _ = frozen_speech
    parameters = {k: v for k, v in request.items() if k != "cache_key"}
    parameters[field] = value
    changed = tts.tts_request(**parameters)
    def unexpected(*args, **kwargs):
        pytest.fail("mismatched requests must fail before even decoding audio")
    monkeypatch.setattr(tts_bundle, "_audio_duration", unexpected)
    with pytest.raises(tts.TTSBundleError, match="request set differs"):
        with tts.tts_bundle_session(input_path=bundle, expected_requests=[changed]):
            pytest.fail("wrong parameters must fail at session entry")
    assert not (tmp_path / "render.mp3").exists()


@pytest.mark.parametrize("damage", ["audio_hash", "marks_hash", "invalid_marks", "undecodable",
                                    "extra_member", "quality_claim", "implementation"])
def test_explicit_bad_bundle_never_silently_resynthesizes(frozen_speech, tmp_path, damage):
    import hashlib
    bundle, request, _, _, _ = frozen_speech
    with zipfile.ZipFile(bundle) as z:
        files = {name: z.read(name) for name in z.namelist()}
    manifest = json.loads(files["manifest.json"])
    entry = manifest["entries"][0]
    prefix = "requests/" + entry["request_id"] + "/"
    if damage == "audio_hash":
        files[prefix + "audio.mp3"] += b"changed"
    elif damage == "marks_hash":
        files[prefix + "marks.json"] += b" "
    elif damage == "invalid_marks":
        files[prefix + "marks.json"] = json.dumps([
            {"text": request["text"], "offset": 999_000_000, "duration": 1}]).encode()
        entry["marks_sha256"] = hashlib.sha256(files[prefix + "marks.json"]).hexdigest()
    elif damage == "undecodable":
        files[prefix + "audio.mp3"] = b"invalid audio with an internally correct hash"
        entry["audio_sha256"] = hashlib.sha256(files[prefix + "audio.mp3"]).hexdigest()
    elif damage == "extra_member":
        files["../../unexpected"] = b"must never extract"
    elif damage == "quality_claim":
        manifest["quality_approval"] = True
    else:
        manifest["implementation"]["tts.py"] = "wrong implementation"
    files["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    target = tmp_path / "bad-result.mp3"
    def unexpected(*args, **kwargs):
        pytest.fail("explicit bad inputs must never synthesize or restore cache")
    with pytest.raises(tts.TTSBundleError):
        with tts.tts_bundle_session(input_path=bundle, expected_requests=[request]):
            tts.tts_one(request["text"], target, request["voice"], request["rate"], synth=unexpected)
    assert not target.exists()


def test_frozen_input_pins_verified_bytes_against_file_replacement(frozen_speech, tmp_path):
    bundle, request, audio, marks, _ = frozen_speech
    copy = tmp_path / "copied.zip"
    original_bundle = bundle.read_bytes()
    with tts.tts_bundle_session(input_path=bundle, output_path=copy,
                                expected_requests=[request]):
        bundle.write_bytes(b"replaced after validation")
        dest = tmp_path / "pinned.mp3"
        assert tts.tts_one(request["text"], dest, request["voice"], request["rate"],
                           synth=lambda *a, **k: pytest.fail("no synthesis")) == marks
    assert dest.read_bytes() == audio
    assert copy.read_bytes() == original_bundle


def test_frozen_incomplete_consumption_and_failed_capture_do_not_publish(frozen_speech, tmp_path):
    bundle, request, _, _, _ = frozen_speech
    clone = tmp_path / "incomplete.zip"
    with pytest.raises(tts.TTSBundleError, match="consume all"):
        with tts.tts_bundle_session(input_path=bundle, output_path=clone,
                                    expected_requests=[request]):
            pass
    assert not clone.exists()
    output = tmp_path / "failed-export.zip"
    with pytest.raises(RuntimeError, match="downstream failed"):
        with tts.tts_bundle_session(output_path=output, expected_requests=[request]):
            tts.tts_one(request["text"], tmp_path / "captured.mp3", request["voice"], request["rate"],
                        synth=_valid_speech)
            raise RuntimeError("downstream failed")
    assert not output.exists()


def test_frozen_cheap_preflight_checks_integrity_without_decode(frozen_speech, monkeypatch):
    from tennislive.video import tts_bundle
    bundle, request, _, _, _ = frozen_speech
    def unexpected(*args, **kwargs):
        pytest.fail("cheap preflight must not start ffprobe/ffmpeg")
    monkeypatch.setattr(tts_bundle, "_audio_duration", unexpected)
    report = tts_bundle.validate_bundle(bundle, [request], decode_audio=False)
    assert report["validation_level"] == "integrity_and_requests"
    assert report["audio_decoding_verified"] is False
    assert report["quality_approval"] is False
    with zipfile.ZipFile(bundle) as z:
        files = {n: z.read(n) for n in z.namelist()}
    name = next(n for n in files if n.endswith("audio.mp3"))
    files[name] += b"tampered after capture"
    with zipfile.ZipFile(bundle, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    with pytest.raises(tts.TTSBundleError, match="hash mismatch"):
        tts_bundle.validate_bundle(bundle, [request], decode_audio=False)
