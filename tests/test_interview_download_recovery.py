"""Failed transfers must not turn into cached media or abort the client ladder."""
import subprocess
from pathlib import Path

import pytest

from tools import build_interview_clip as clip


@pytest.fixture
def ladder(monkeypatch):
    monkeypatch.setattr(clip, "media_url", lambda url: url)
    monkeypatch.setattr(clip, "_ytdlp_ladder", lambda: [("first", []), ("second", [])])


@pytest.mark.parametrize("leftover", ["source.mp4.part", "source.f137.mp4", "source.ytdl", "source.mp4"])
@pytest.mark.parametrize("timed_out", [False, True])
def test_failed_transfer_retries_instead_of_using_partial(tmp_path, monkeypatch, ladder,
                                                         leftover, timed_out):
    dest = tmp_path / "source.mp4"
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            (tmp_path / leftover).write_bytes(b"partial")
            if timed_out:
                raise subprocess.TimeoutExpired(cmd, 240)
            return subprocess.CompletedProcess(cmd, 1, "", "interrupted")
        assert not (tmp_path / leftover).exists()
        dest.write_bytes(b"complete")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(clip.subprocess, "run", run)
    assert clip.yt_download("https://youtube.com/watch?v=x", dest, "bv*+ba/b", {}) == dest
    assert len(calls) == 2
    assert dest.read_bytes() == b"complete"


def test_empty_cached_destination_is_downloaded(tmp_path, monkeypatch, ladder):
    dest = tmp_path / "source.mp4"
    dest.touch()
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        dest.write_bytes(b"complete")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(clip.subprocess, "run", run)
    clip.yt_download("u", dest, "b", {})
    assert len(calls) == 1


@pytest.mark.parametrize("timed_out", [False, True])
def test_direct_transfer_failure_leaves_no_cache(tmp_path, monkeypatch, timed_out):
    dest = tmp_path / "source.mp4"

    def run(cmd, **kwargs):
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x" * 2048)
        assert not dest.exists()
        if timed_out:
            raise subprocess.TimeoutExpired(cmd, 260)
        return subprocess.CompletedProcess(cmd, 22, "", "connection failed")

    monkeypatch.setattr(clip.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired if timed_out else SystemExit):
        clip.yt_download("https://official.example/source.mp4", dest, "b", {})
    assert not dest.exists()
    assert not list(tmp_path.glob("source.*"))


def test_all_timed_out_clients_report_failure(tmp_path, monkeypatch, ladder):
    def run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 240)

    monkeypatch.setattr(clip.subprocess, "run", run)
    with pytest.raises(SystemExit, match="2 档 client 全下不动"):
        clip.yt_download("u", tmp_path / "source.mp4", "b", {})


def test_success_exit_with_only_a_fragment_is_not_media(tmp_path, monkeypatch, ladder):
    def run(cmd, **kwargs):
        (tmp_path / "source.f137.mp4").write_bytes(b"video without merged audio")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(clip.subprocess, "run", run)
    with pytest.raises(SystemExit, match="2 档 client 全下不动"):
        clip.yt_download("u", tmp_path / "source.mp4", "bv*+ba/b", {})


def test_completed_alternate_container_with_sidecar_is_used(tmp_path, monkeypatch, ladder):
    def run(cmd, **kwargs):
        (tmp_path / "source.mkv").write_bytes(b"complete")
        (tmp_path / "source.info.json").write_text("{}")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(clip.subprocess, "run", run)
    assert clip.yt_download("u", tmp_path / "source.mp4", "b", {}) == tmp_path / "source.mkv"


def test_failed_download_preserves_metadata_and_rejects_audio_only(tmp_path, monkeypatch, ladder):
    evidence = [tmp_path / name for name in ("source.json", "source.ass", "source.info.json")]
    for path in evidence:
        path.write_text("evidence")

    def run(cmd, **kwargs):
        (tmp_path / "source.m4a").write_bytes(b"audio only")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(clip.subprocess, "run", run)
    with pytest.raises(SystemExit):
        clip.yt_download("u", tmp_path / "source.mp4", "bv*+ba/b", {})
    assert not (tmp_path / "source.m4a").exists()
    assert all(path.read_text() == "evidence" for path in evidence)
