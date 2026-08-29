import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_interview_clip as clip

def test_direct_mp4_bypasses_ytdlp_format_selector(tmp_path, monkeypatch):
    dest = tmp_path / 'lead.mp4'
    seen = []
    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        assert cmd[0] == 'curl'
        out = Path(cmd[cmd.index('-o') + 1])
        out.write_bytes(b'x' * 2048)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(clip.subprocess, 'run', fake_run)
    got = clip.yt_download('https://media.example.test/path/final.mp4', dest, 'bv*+ba/b', {})
    assert got == dest
    assert dest.stat().st_size == 2048
    assert seen and all(cmd[0] != 'yt-dlp' for cmd in seen)
