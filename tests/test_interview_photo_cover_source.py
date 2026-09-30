from pathlib import Path

import pytest

from tools import build_interview_clip as clip


def test_explicit_photo_uses_native_cover_and_not_video_frame(tmp_path, monkeypatch):
    photo = tmp_path / "event.jpg"
    photo.write_bytes(b"fixture")
    calls = []
    monkeypatch.setattr(clip, "build_cover", lambda spec, frame, dest, page=None:
                        calls.append((frame, dest)) or dest)
    monkeypatch.setattr(clip.subprocess, "run", lambda *a, **k:
                        pytest.fail("a photograph must not be extracted from video"))
    spec = {"cover": {"photo_path": str(photo), "photo_source": "https://event.test/photo"}}
    assert clip.cover_poster(spec, Path("unused.mp4"), tmp_path) == tmp_path / "poster.jpg"
    assert calls == [(photo, tmp_path / "poster.jpg")]


def test_photo_requires_provenance_and_cannot_claim_video_timestamp(tmp_path):
    spec = {"cover": {"photo_path": "missing.jpg"}}
    with pytest.raises(SystemExit, match="photo_source"):
        clip.cover_poster(spec, Path("unused.mp4"), tmp_path)
    spec["cover"]["photo_source"] = "https://event.test/photo"
    with pytest.raises(SystemExit, match="没有视频抽帧时刻"):
        clip.cover_poster(spec, Path("unused.mp4"), tmp_path, at=2)
    with pytest.raises(SystemExit, match="文件不存在"):
        clip.cover_poster(spec, Path("unused.mp4"), tmp_path)
