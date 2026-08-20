#!/usr/bin/env python3
"""Validate one newly-added reel queue file, then dispatch ``match-reel`` runs.

This is deliberately a narrow bridge from a reviewed file on ``main`` to
``workflow_dispatch``.  The queue file is discovered from the push diff rather
than accepted as an arbitrary path, and every field that reaches ``gh`` is
validated before the first run is dispatched.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = Path("data/reel-dispatch-queue")
QUEUE_KEYS = frozenset({"version", "mode", "ref", "expected_date", "slugs"})
MODES = frozenset({"render", "push"})
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
MAX_SLUGS = 8
MAX_SLUG_LENGTH = 80
MAX_QUEUE_BYTES = 64 * 1024

Run = Callable[..., subprocess.CompletedProcess]


class QueueError(ValueError):
    """A queue file or its triggering push does not meet the dispatch contract."""


@dataclass(frozen=True)
class QueueRequest:
    mode: str
    ref: str
    expected_date: str
    slugs: tuple[str, ...]


def beijing_today(now: datetime | None = None) -> date:
    """Return the calendar date at UTC+08:00, independent of runner locale."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise QueueError("beijing_today() requires a timezone-aware datetime")
    return instant.astimezone(BEIJING_TZ).date()


def _queue_path(path: str | Path, repo_root: Path) -> tuple[Path, Path]:
    relative = Path(path)
    if relative.is_absolute() or relative.parent != QUEUE_DIR:
        raise QueueError(
            f"queue file must be directly under {QUEUE_DIR}/: {relative}"
        )
    if relative.suffix != ".json" or relative.name in {".json", "..json"}:
        raise QueueError(f"queue file must have a non-empty .json name: {relative}")

    full = repo_root / relative
    try:
        info = full.lstat()
    except OSError as exc:
        raise QueueError(f"queue file is not readable: {relative}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise QueueError(f"queue file must be a regular file, not a symlink: {relative}")
    if info.st_size > MAX_QUEUE_BYTES:
        raise QueueError(
            f"queue file is too large ({info.st_size} bytes; max {MAX_QUEUE_BYTES})"
        )
    return relative, full


def _read_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QueueError(f"cannot read {label} JSON {path}: {exc}") from exc


def load_queue(
    path: str | Path,
    *,
    repo_root: Path = ROOT,
    today: date | None = None,
) -> QueueRequest:
    """Load and fully validate one queue file and all referenced reel specs."""
    relative, full = _queue_path(path, repo_root)
    payload = _read_json(full, label="queue")
    if not isinstance(payload, dict):
        raise QueueError(f"queue payload must be a JSON object: {relative}")

    keys = set(payload)
    missing = sorted(QUEUE_KEYS - keys)
    extra = sorted(keys - QUEUE_KEYS)
    if missing or extra:
        raise QueueError(f"queue keys mismatch; missing={missing}, extra={extra}")

    if type(payload["version"]) is not int or payload["version"] != 1:
        raise QueueError("queue version must be the integer 1")

    mode = payload["mode"]
    if not isinstance(mode, str) or mode not in MODES:
        raise QueueError(f"mode must be one of {sorted(MODES)}")

    ref = payload["ref"]
    if ref != "main":
        raise QueueError("ref is fixed to 'main'")

    expected_date = payload["expected_date"]
    current_date = (today or beijing_today()).isoformat()
    if not isinstance(expected_date, str) or expected_date != current_date:
        raise QueueError(
            f"expected_date must equal the current Beijing date {current_date}"
        )

    raw_slugs = payload["slugs"]
    if not isinstance(raw_slugs, list) or not 1 <= len(raw_slugs) <= MAX_SLUGS:
        raise QueueError(f"slugs must be a non-empty list of at most {MAX_SLUGS}")

    slugs: list[str] = []
    for slug in raw_slugs:
        if (
            not isinstance(slug, str)
            or len(slug) > MAX_SLUG_LENGTH
            or SLUG_RE.fullmatch(slug) is None
        ):
            raise QueueError(
                "each slug must match [a-z0-9]+(?:-[a-z0-9]+)* "
                f"and be at most {MAX_SLUG_LENGTH} characters: {slug!r}"
            )
        slugs.append(slug)
    if len(set(slugs)) != len(slugs):
        raise QueueError("slugs must be unique")
    if mode == "push" and len(slugs) != 1:
        raise QueueError(
            "push queues must contain exactly one slug so publishing stays serial"
        )

    for slug in slugs:
        spec_path = repo_root / "specs" / "reels" / f"{slug}.json"
        copy_path = repo_root / "specs" / "reels" / f"{slug}.xhs.txt"
        if not spec_path.is_file():
            raise QueueError(f"missing reel spec: {spec_path.relative_to(repo_root)}")
        if not copy_path.is_file():
            raise QueueError(f"missing reel copy: {copy_path.relative_to(repo_root)}")
        spec_payload = _read_json(spec_path, label="reel spec")
        if not isinstance(spec_payload, dict) or spec_payload.get("slug") != slug:
            got = spec_payload.get("slug") if isinstance(spec_payload, dict) else None
            raise QueueError(
                f"spec slug mismatch for {spec_path.relative_to(repo_root)}: {got!r}"
            )

    return QueueRequest(
        mode=mode,
        ref=ref,
        expected_date=expected_date,
        slugs=tuple(slugs),
    )


def discover_queue_file(
    before: str,
    after: str,
    *,
    repo_root: Path = ROOT,
    run: Run = subprocess.run,
) -> Path:
    """Require exactly one queue-path change in the push, and require it be added."""
    for label, value in (("before", before), ("after", after)):
        if SHA_RE.fullmatch(value) is None or value == "0" * 40:
            raise QueueError(f"{label} must be a non-zero 40-character commit SHA")

    command = [
        "git",
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        before,
        after,
        "--",
        ":(glob)data/reel-dispatch-queue/*.json",
    ]
    result = run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    fields = result.stdout.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) != 2 or fields[0] != "A":
        changes = [
            f"{fields[index]} {fields[index + 1]}"
            for index in range(0, len(fields) - 1, 2)
        ]
        raise QueueError(
            "a push must add exactly one queue JSON and make no other queue-file "
            f"changes; found {changes or 'none'}"
        )
    return Path(fields[1])


def dispatch(request: QueueRequest, *, run: Run = subprocess.run) -> None:
    """Dispatch parallel renders or one fail-closed, serial publish run."""
    if request.mode == "push" and len(request.slugs) != 1:
        raise QueueError(
            "push queues must contain exactly one slug so publishing stays serial"
        )
    push = "true" if request.mode == "push" else "false"
    for slug in request.slugs:
        command = [
            "gh",
            "workflow",
            "run",
            "match-reel.yml",
            "--ref",
            request.ref,
            "-f",
            f"slug={slug}",
            "-f",
            f"mode={request.mode}",
            "-f",
            f"push={push}",
        ]
        print(f"[dispatch] match-reel {request.mode} {slug} push={push}")
        run(command, check=True, shell=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--before", required=True, help="github.event.before commit SHA")
    parser.add_argument("--after", required=True, help="github.sha commit SHA")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        queue_file = discover_queue_file(args.before, args.after)
        request = load_queue(queue_file)
        dispatch(request)
    except QueueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"::error::command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
