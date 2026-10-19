"""The second video sender must not bypass actual voice review."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tennislive import cli


@pytest.mark.parametrize("product", ["metadata", "movie", "link", "video_tag", "player", "player_link"])
def test_video_voice_gate_blocks_before_network(tmp_path, monkeypatch, product):
    import voice_quality_gate

    folder = tmp_path / "video"
    folder.mkdir()
    html = "<div>video package</div>"
    if product == "metadata":
        (folder / "narration.json").write_text("{}")
    elif product == "movie":
        (folder / "film.mp4").write_bytes(b"movie fixture")
    elif product == "link":
        html = '<a href="https://example.test/film.mp4">play</a>'
    elif product == "video_tag":
        html = '<video src="https://example.test/movie"></video>'
    elif product == "player":
        (folder / "watch.html").write_text("<video></video>")
    else:
        html = '<a href="https://example.test/watch.html">play</a>'
    (folder / "push.html").write_text(html)
    checked = []

    def pending(outdir):
        checked.append(outdir)
        raise ValueError("waiting_voice_review: prosody pending")

    def forbidden(*args, **kwargs):
        pytest.fail("network or POST reached before the voice gate")

    monkeypatch.setattr(voice_quality_gate, "require_publish", pending)
    monkeypatch.setattr("tennislive.render.pushmsg.drop_dead_copy_button", forbidden)
    monkeypatch.setattr("tennislive.publish.pushplus.push", forbidden)
    assert cli.cmd_publish_pushplus(SimpleNamespace(dir=str(folder))) == 1
    assert checked == [folder]


def test_image_package_keeps_existing_sender(tmp_path, monkeypatch):
    import voice_quality_gate

    (tmp_path / "push.html").write_text("<div>image package</div>")

    def forbidden(*args, **kwargs):
        pytest.fail("image-only package entered video voice gate")

    monkeypatch.setattr(voice_quality_gate, "require_publish", forbidden)
    monkeypatch.setattr("tennislive.render.pushmsg.drop_dead_copy_button",
                        lambda html, **kwargs: (html, None))
    sent = []
    monkeypatch.setattr("tennislive.publish.pushplus.push",
                        lambda *args, **kwargs: sent.append(args) or "fixture")
    assert cli.cmd_publish_pushplus(SimpleNamespace(dir=str(tmp_path))) == 0
    assert len(sent) == 1


def test_video_changed_during_delivery_wait_is_blocked(tmp_path, monkeypatch):
    import voice_quality_gate

    (tmp_path / "push.html").write_text('<a href="https://example.test/film.mp4">play</a>')
    checks = []

    def review(outdir):
        checks.append(outdir)
        if len(checks) == 2:
            raise ValueError("actual movie changed during deployment wait")

    monkeypatch.setattr(voice_quality_gate, "require_publish", review)
    monkeypatch.setattr("tennislive.render.pushmsg.drop_dead_copy_button",
                        lambda html, **kwargs: (html, None))

    def forbidden(*args, **kwargs):
        pytest.fail("changed movie reached POST")

    monkeypatch.setattr("tennislive.publish.pushplus.push", forbidden)
    assert cli.cmd_publish_pushplus(SimpleNamespace(dir=str(tmp_path))) == 1
    assert len(checks) == 2
