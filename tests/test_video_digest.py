from pathlib import Path

import pytest

from tennislive.render.video_digest import DigestVideoError, generate_digest_video


def test_digest_video_builds_ffmpeg_command_without_a_shell(tmp_path, monkeypatch):
    cards = []
    for index in range(2):
        card = tmp_path / f"card_{index}.png"
        card.write_bytes(b"png")
        cards.append(card)
    output = tmp_path / "video" / "daily.mp4"
    calls = []
    monkeypatch.setattr("tennislive.render.video_digest.shutil.which", lambda _: "ffmpeg")

    def runner(command, check):
        calls.append((command, check))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"mp4")

    assert generate_digest_video(cards, output, runner=runner) == output.resolve()
    command, check = calls[0]
    assert check is True
    assert command[0] == "ffmpeg"
    assert "concat=n=2:v=1:a=0[outv]" in command[command.index("-filter_complex") + 1]
    assert all(isinstance(part, str) for part in command)


def test_digest_video_requires_cards(tmp_path):
    with pytest.raises(DigestVideoError, match="No rendered cards"):
        generate_digest_video([], tmp_path / "daily.mp4")
