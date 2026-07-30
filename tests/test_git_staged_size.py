"""Automatic commits must fail before GitHub rejects an oversized blob."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.check_staged_file_sizes import DEFAULT_MAX_BYTES


SCRIPT = Path("tools/check_staged_file_sizes.py").resolve()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


def _check(repo: Path, limit: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--max-bytes",
            str(limit),
        ],
        capture_output=True,
        text=True,
    )


def test_default_matches_githubs_100_mib_hard_limit():
    assert DEFAULT_MAX_BYTES == 100 * 1024 * 1024


def test_staged_files_at_or_below_limit_pass(tmp_path):
    repo = _repo(tmp_path)
    path = repo / "small file.bin"
    path.write_bytes(b"x" * 10)
    _git(repo, "add", path.name)

    result = _check(repo, 10)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "small file.bin" in result.stdout


def test_oversized_staged_file_fails_with_actionable_error(tmp_path):
    repo = _repo(tmp_path)
    path = repo / "too-big.mp4"
    path.write_bytes(b"x" * 11)
    _git(repo, "add", path.name)

    result = _check(repo, 10)

    assert result.returncode == 1
    assert "::error::" in result.stdout
    assert "too-big.mp4" in result.stdout
    assert "artifact" in result.stdout
    assert "不要降低视频画质" in result.stdout
