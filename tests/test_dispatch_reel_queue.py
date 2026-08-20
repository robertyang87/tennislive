"""The push-triggered reel queue is deliberately narrow and fail-closed."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "dispatch_reel_queue.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "reel-dispatch-queue.yml"


def _load_tool():
    spec = importlib.util.spec_from_file_location("dispatch_reel_queue", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


queue = _load_tool()


def _repo(tmp_path: Path, *, slug: str = "fritz-oconnell") -> tuple[Path, Path, dict]:
    repo = tmp_path / "repo"
    queue_dir = repo / "data" / "reel-dispatch-queue"
    spec_dir = repo / "specs" / "reels"
    queue_dir.mkdir(parents=True)
    spec_dir.mkdir(parents=True)
    (spec_dir / f"{slug}.json").write_text(
        json.dumps({"slug": slug}), encoding="utf-8"
    )
    (spec_dir / f"{slug}.xhs.txt").write_text("copy", encoding="utf-8")
    payload = {
        "version": 1,
        "mode": "render",
        "ref": "main",
        "expected_date": "2026-08-21",
        "slugs": [slug],
    }
    path = queue_dir / "2026-08-21-render.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return repo, path.relative_to(repo), payload


def test_valid_queue_is_bound_to_today_and_existing_matching_specs(tmp_path):
    repo, path, _ = _repo(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))
    assert request == queue.QueueRequest(
        mode="render",
        ref="main",
        expected_date="2026-08-21",
        slugs=("fritz-oconnell",),
    )
    assert queue.beijing_today(datetime(2026, 8, 20, 16, 30, tzinfo=timezone.utc)) == date(
        2026, 8, 21
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"version": True}, "integer 1"),
        ({"version": 2}, "integer 1"),
        ({"mode": "probe"}, "mode must"),
        ({"ref": "feature"}, "fixed to 'main'"),
        ({"expected_date": "2026-08-20"}, "current Beijing date"),
        ({"slugs": []}, "non-empty list"),
        ({"slugs": [f"player-{n}" for n in range(9)]}, "at most 8"),
        ({"slugs": ["fritz-oconnell", "fritz-oconnell"]}, "unique"),
        ({"slugs": ["../fritz"]}, "must match"),
    ],
)
def test_queue_hard_limits_are_rejected(tmp_path, change, message):
    repo, path, payload = _repo(tmp_path)
    payload.update(change)
    (repo / path).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(queue.QueueError, match=message):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))


def test_missing_copy_and_mismatched_spec_slug_fail_before_dispatch(tmp_path):
    repo, path, _ = _repo(tmp_path)
    copy_path = repo / "specs" / "reels" / "fritz-oconnell.xhs.txt"
    copy_path.unlink()
    with pytest.raises(queue.QueueError, match="missing reel copy"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))

    copy_path.write_text("copy", encoding="utf-8")
    (repo / "specs" / "reels" / "fritz-oconnell.json").write_text(
        json.dumps({"slug": "somebody-else"}), encoding="utf-8"
    )
    with pytest.raises(queue.QueueError, match="spec slug mismatch"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))


def test_push_diff_must_contain_exactly_one_added_queue_file(tmp_path):
    calls = []

    def one_added(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="A\0data/reel-dispatch-queue/one.json\0",
            stderr="",
        )

    before, after = "1" * 40, "2" * 40
    assert queue.discover_queue_file(before, after, repo_root=tmp_path, run=one_added) == Path(
        "data/reel-dispatch-queue/one.json"
    )
    command, kwargs = calls[0]
    assert isinstance(command, list) and command[:3] == ["git", "diff", "--name-status"]
    assert kwargs["shell"] is False

    def added_and_modified(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "A\0data/reel-dispatch-queue/one.json\0"
                "M\0data/reel-dispatch-queue/old.json\0"
            ),
            stderr="",
        )

    with pytest.raises(queue.QueueError, match="exactly one"):
        queue.discover_queue_file(before, after, repo_root=tmp_path, run=added_and_modified)


@pytest.mark.parametrize(("mode", "push"), [("render", "false"), ("push", "true")])
def test_dispatch_uses_argument_arrays_and_mode_fixes_push(mode, push):
    calls = []

    def record(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    request = queue.QueueRequest(
        mode=mode,
        ref="main",
        expected_date="2026-08-21",
        slugs=("first-player", "second-player"),
    )
    queue.dispatch(request, run=record)
    assert len(calls) == 2
    for (command, kwargs), slug in zip(calls, request.slugs):
        assert command == [
            "gh",
            "workflow",
            "run",
            "match-reel.yml",
            "--ref",
            "main",
            "-f",
            f"slug={slug}",
            "-f",
            f"mode={mode}",
            "-f",
            f"push={push}",
        ]
        assert kwargs == {"check": True, "shell": False}


def test_workflow_only_runs_for_main_queue_pushes_with_minimum_permissions():
    workflow = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["on"] == {
        "push": {
            "branches": ["main"],
            "paths": ["data/reel-dispatch-queue/*.json"],
        }
    }
    assert workflow["permissions"] == {"contents": "read", "actions": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    body = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "github.event.before" in body and "github.sha" in body
    assert "python tools/dispatch_reel_queue.py" in body
