#!/usr/bin/env python3
"""Fail before commit when a staged file exceeds GitHub's hard size limit."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


DEFAULT_MAX_BYTES = 100 * 1024 * 1024


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        stderr=subprocess.STDOUT,
    )


def staged_blob_sizes(repo: Path) -> list[tuple[str, int]]:
    """Return ``(path, blob size)`` for staged added/changed files."""
    changed = _git(
        repo,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMR",
        "-z",
    )
    results: list[tuple[str, int]] = []
    for raw_path in changed.split(b"\0"):
        if not raw_path:
            continue
        path = os.fsdecode(raw_path)
        entries = _git(repo, "ls-files", "--stage", "-z", "--", path)
        blob_sha = ""
        for entry in entries.split(b"\0"):
            if not entry:
                continue
            metadata, _, listed_path = entry.partition(b"\t")
            mode, sha, stage = metadata.decode("ascii").split()
            del mode
            if stage == "0" and os.fsdecode(listed_path) == path:
                blob_sha = sha
                break
        if not blob_sha:
            raise RuntimeError(f"cannot resolve staged blob for {path}")
        size = int(_git(repo, "cat-file", "-s", blob_sha).strip())
        results.append((path, size))
    return results


def _mib(size: int) -> str:
    return f"{size / 1024 / 1024:.1f} MiB"


def check(repo: Path, max_bytes: int) -> int:
    if max_bytes <= 0:
        raise ValueError("--max-bytes must be positive")

    staged = staged_blob_sizes(repo)
    oversized = [(path, size) for path, size in staged if size > max_bytes]
    if oversized:
        for path, size in oversized:
            print(
                "::error::拒绝提交超大文件："
                f"{path} 为 {_mib(size)}，超过 {_mib(max_bytes)}。"
                "请缩短产物、移出仓库或改用 artifact；不要降低视频画质来绕过。"
            )
        return 1

    if staged:
        path, size = max(staged, key=lambda item: item[1])
        print(
            f"staged-size gate: {len(staged)} 个文件，"
            f"最大 {path}（{_mib(size)}）"
        )
    else:
        print("staged-size gate: 没有新增或修改的 staged 文件")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    return check(args.repo.resolve(), args.max_bytes)


if __name__ == "__main__":
    raise SystemExit(main())
