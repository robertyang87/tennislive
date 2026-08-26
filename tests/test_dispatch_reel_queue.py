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
MATCH_REEL_PATH = ROOT / ".github" / "workflows" / "match-reel.yml"


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


def test_push_queue_requires_exactly_one_slug(tmp_path):
    repo, path, payload = _repo(tmp_path)
    second_slug = "second-player"
    spec_dir = repo / "specs" / "reels"
    (spec_dir / f"{second_slug}.json").write_text(
        json.dumps({"slug": second_slug}), encoding="utf-8"
    )
    (spec_dir / f"{second_slug}.xhs.txt").write_text("copy", encoding="utf-8")
    payload.update({"mode": "push", "slugs": ["fritz-oconnell", second_slug]})
    (repo / path).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(queue.QueueError, match="exactly one slug"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))


def test_render_queue_accepts_multiple_existing_slugs(tmp_path):
    repo, path, payload = _repo(tmp_path)
    second_slug = "second-player"
    spec_dir = repo / "specs" / "reels"
    (spec_dir / f"{second_slug}.json").write_text(
        json.dumps({"slug": second_slug}), encoding="utf-8"
    )
    (spec_dir / f"{second_slug}.xhs.txt").write_text("copy", encoding="utf-8")
    payload["slugs"] = ["fritz-oconnell", second_slug]
    (repo / path).write_text(json.dumps(payload), encoding="utf-8")

    request = queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))
    assert request.slugs == ("fritz-oconnell", second_slug)


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


@pytest.mark.parametrize(
    ("mode", "push", "slugs"),
    [
        ("render", "true", ("first-player", "second-player")),
        ("push", "true", ("first-player",)),
    ],
)
def test_dispatch_uses_argument_arrays_and_mode_fixes_push(mode, push, slugs):
    calls = []

    def record(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    request = queue.QueueRequest(
        mode=mode,
        ref="main",
        expected_date="2026-08-21",
        slugs=slugs,
    )
    queue.dispatch(
        request,
        run=record,
        now=datetime(2026, 8, 24, 1, 2, 3, tzinfo=timezone.utc),
    )
    assert len(calls) == len(slugs)
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
            "-f",
            "received_at=2026-08-24T01:02:03Z",
        ]
        assert kwargs == {"check": True, "shell": False}


def test_dispatch_rejects_bypassed_multi_slug_push_request():
    request = queue.QueueRequest(
        mode="push",
        ref="main",
        expected_date="2026-08-21",
        slugs=("first-player", "second-player"),
    )
    with pytest.raises(queue.QueueError, match="exactly one slug"):
        queue.dispatch(request)


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


def test_match_reel只串行不可撤回发布不串行多场渲染():
    body = MATCH_REEL_PATH.read_text(encoding="utf-8")
    head = body[: body.index("jobs:")]
    concurrency = head[head.index("concurrency:") :]
    assert "match-reel-publish" in concurrency
    assert "github.event.inputs.mode == 'push'" in concurrency
    assert "github.event.inputs.push == 'true'" not in concurrency, (
        "push=true 的生产 render 被全局发布锁串行了；多场应该按 slug 并行，"
        "质检落库后再派 push-only 串行发送")
    assert "cancel-in-progress: ${{ github.event.inputs.mode != 'push' }}" in concurrency


def test_render质检落库后自动派push_only且本趟不直接发送():
    body = MATCH_REEL_PATH.read_text(encoding="utf-8")
    assert body.index("- name: 查成片本身合不合格") < body.index(
        "- name: 成片发到 Release（不进 git）"
    ) < body.index("- name: 提交产物") < body.index(
        "- name: render 质检落库后读取 spec 自动推送规则"
    ) < body.index(
        "- name: render 质检落库后自动派发微信推送"
    ), "自动派发必须在 L2、Release 探活和提交全部成功之后，不能只看 render 成功信号"

    gate = body[body.index("- name: render 质检落库后读取 spec 自动推送规则") :]
    gate = gate[: gate.index("- name: ", 10)]
    assert "mode == 'render'" in gate and "github.ref_name == 'main'" in gate, (
        "spec 自动推送门禁只能在 main 的 render 落库后运行；特性分支要等合并触发")
    assert "auto_push_gate.py" in gate and "--changed" in gate, (
        "render 自动推送必须复用完整发布门禁，不能在 YAML 里另写一份简化判断")

    dispatch = body[body.index("- name: render 质检落库后自动派发微信推送") :]
    dispatch = dispatch[: dispatch.index("- name: ", 10)]
    assert "mode == 'render'" in dispatch and "inputs.push == 'true'" in dispatch
    assert "steps.render_auto_gate.outputs.found == 'true'" in dispatch, (
        "表单默认 push=false 不能压掉 spec 的 push.auto=true；质检通过后必须自动派发")
    assert "gh workflow run match-reel.yml" in dispatch
    assert "-f mode=push" in dispatch and "-f push=true" in dispatch

    send = body[body.index("- name: 推送到微信（可选）") :]
    send = send[: send.index("- name: ", 10)]
    assert "inputs.mode == 'push'" in send and "mode == 'render'" not in send, (
        "render 本趟又直接 POST，会和 push-only 重复发送；本趟只负责质检落库和派发")
