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


def _preview_queue(tmp_path, *, push=None):
    repo, path, payload = _repo(tmp_path)
    payload["mode"] = "preview"
    (repo / path).write_text(json.dumps(payload), encoding="utf-8")
    spec = {"slug": "fritz-oconnell", "push": push if push is not None else {
        "auto": False,
        "_no_auto_why": "先检查实际完整成片，确认后通过原有推送队列发布。",
    }}
    (repo / "specs/reels/fritz-oconnell.json").write_text(json.dumps(spec))
    return repo, path, payload


def test_preview_requires_the_formal_spec_to_disable_automatic_publication(tmp_path):
    repo, path, _ = _preview_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))
    assert request.mode == "preview" and request.slugs == ("fritz-oconnell",)


@pytest.mark.parametrize("auto", [True, None, 0, "false"])
def test_preview_rejects_auto_true_missing_and_false_lookalikes(tmp_path, auto):
    push = {"_no_auto_why": "先检查实际完整成片，然后通过推送队列发布。"}
    if auto is not None:
        push["auto"] = auto
    repo, path, _ = _preview_queue(tmp_path, push=push)
    with pytest.raises(queue.QueueError, match="push.auto to be exactly false"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))


@pytest.mark.parametrize("why", [None, False, "", " \n\t ", "先看看", "TODO fill in reason later"])
def test_preview_requires_an_explanation_in_the_formal_spec(tmp_path, why):
    push = {"auto": False}
    if why is not None:
        push["_no_auto_why"] = why
    repo, path, _ = _preview_queue(tmp_path, push=push)
    with pytest.raises(queue.QueueError, match="meaningful push._no_auto_why"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))


def test_preview_validates_every_spec_before_dispatch(tmp_path):
    repo, path, payload = _preview_queue(tmp_path)
    second = "second-player"
    (repo / f"specs/reels/{second}.json").write_text(json.dumps({
        "slug": second, "push": {"auto": True},
    }))
    (repo / f"specs/reels/{second}.xhs.txt").write_text("copy")
    payload["slugs"].append(second)
    (repo / path).write_text(json.dumps(payload))
    with pytest.raises(queue.QueueError, match="exactly false: second-player"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 8, 21))


@pytest.mark.parametrize(("mode", "push_value"), [("preview", "false"), ("render", "true")])
def test_queue_uses_normal_render_outbox_and_replays_only_pending_slugs(
    tmp_path, monkeypatch, mode, push_value,
):
    import reel_dispatch_outbox as outbox

    repo, path, payload = _preview_queue(tmp_path)
    payload["mode"] = mode
    payload["slugs"].append("second-player")
    (repo / path).write_text(json.dumps(payload))
    first_spec = repo / "specs/reels/fritz-oconnell.json"
    second_spec = json.loads(first_spec.read_text())
    second_spec["slug"] = "second-player"
    (repo / "specs/reels/second-player.json").write_text(json.dumps(second_spec))
    (repo / "specs/reels/second-player.xhs.txt").write_text("copy")
    load = queue.load_queue
    enqueue, drain = outbox.enqueue, outbox.drain
    monkeypatch.setattr(queue, "discover_queue_file", lambda *_: path)
    monkeypatch.setattr(queue, "load_queue", lambda p: load(p, repo_root=repo, today=date(2026, 8, 21)))
    monkeypatch.setattr(queue, "verify_event_inputs", lambda *a: None)
    monkeypatch.setattr(outbox, "enqueue", lambda request, **kw: enqueue(request, root=repo, **kw))
    saved, calls = [], []

    def checkpoint(intent):
        saved.append(json.loads(intent.read_text()))

    def submit(command, **kwargs):
        # Intent is durable before the first API call. Native workflow inputs
        # stay render/push; preview never becomes a new workflow input.
        assert saved and saved[-1]["request"]["mode"] == "render"
        assert saved[-1]["request"]["push"] is (push_value == "true")
        assert "mode=render" in command and f"push={push_value}" in command
        assert command[:6] == ["gh", "workflow", "run", "match-reel.yml", "--ref", "main"]
        assert kwargs == {"check": True, "shell": False}
        calls.append(command)
        if "slug=second-player" in command and len(calls) == 2:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(outbox, "persist", checkpoint)
    monkeypatch.setattr(outbox, "drain", lambda intent: drain(
        intent, root=repo, run=submit, checkpoint=checkpoint,
    ))
    argv = ["--before", "a" * 40, "--after", "b" * 40]
    assert queue.main(argv) == 1
    assert len(calls) == 2
    assert queue.main(argv) == 0
    assert len(calls) == 3 and "slug=second-player" in calls[-1]
    assert [a for a in calls[1] if a.startswith("received_at=")] == [
        a for a in calls[2] if a.startswith("received_at=")
    ]
    assert set(saved[-1]["dispatched"]) == {"fritz-oconnell", "second-player"}
    assert len(list((repo / outbox.DIRECTORY).glob("*.json"))) == 1


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
    # Durable dispatch intents/receipts must be committed before/after the API call.
    assert workflow["permissions"] == {"contents": "write", "actions": "write"}
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
    # reattest 不顶掉在跑的 render（O4 自动换图派的那趟），见 tests/test_reattest.py
    assert ("cancel-in-progress: ${{ github.event.inputs.mode != 'push' && "
            "github.event.inputs.mode != 'reattest' }}") in concurrency


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
    assert "mode == 'render'" in dispatch
    assert "steps.render_auto_gate.outputs.found == 'true'" in dispatch, (
        "表单默认 push=false 不能压掉 spec 的 push.auto=true；质检通过后必须自动派发")
    # ⚠️ 主语 2026-09-09 变了：原来这儿还断言 `inputs.push == 'true'` 也在 `if` 里，
    # 而那一半正是把整套发布门禁旁路掉的那个 `||`（近 10 次失败率 80% 的来路）。
    # 强制推送的意图现在交给上一步的 `--forced`，派发只认门禁的结论。
    # 完整来路和反向验证在 tests/test_auto_push.py::test_派发只认门禁的结论不许再拿表单旁路。
    cond = dispatch[dispatch.index("if:"): dispatch.index("env:")]
    assert "inputs.push" not in cond, (
        "派发条件又拿表单旁路了整套发布门禁")
    assert "gh workflow run match-reel.yml" in dispatch
    assert "-f mode=push" in dispatch and "-f push=true" in dispatch

    send = body[body.index("- name: 推送到微信（可选）") :]
    send = send[: send.index("- name: ", 10)]
    assert "inputs.mode == 'push'" in send and "mode == 'render'" not in send, (
        "render 本趟又直接 POST，会和 push-only 重复发送；本趟只负责质检落库和派发")


def _download_queue(tmp_path, **changes):
    repo = tmp_path / "download-repo"
    path = Path("data/reel-dispatch-queue/2026-10-19-eala-source.json")
    (repo / path).parent.mkdir(parents=True)
    payload = {"version": 2, "mode": "download", "ref": "main",
               "expected_date": "2026-10-19",
               "url": "https://www.youtube.com/watch?v=C3SB38PJjtM"}
    payload.update(changes)
    (repo / path).write_text(json.dumps(payload))
    return repo, path


def test_download_queue_needs_no_spec_and_has_a_separate_exact_schema(tmp_path):
    repo, path = _download_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))
    assert isinstance(request, queue.DownloadRequest)
    assert request.slugs == ()
    assert request.url == "https://www.youtube.com/watch?v=C3SB38PJjtM"


@pytest.mark.parametrize("changes", [
    {"version": 1}, {"version": True}, {"ref": "feature"},
    {"expected_date": "2026-10-18"}, {"slugs": ["eala-parry"]},
    {"workflow": "arbitrary.yml"}, {"push": True},
    {"url": "https://youtube.com.evil.example/watch?v=C3SB38PJjtM"},
    {"url": "https://www.youtube.com@evil.example/watch?v=C3SB38PJjtM"},
    {"url": "https://www.youtube.com/watch?v=C3SB38PJjtM&list=evil"},
    {"url": "https://www.youtube.com/watch?v=C3SB38PJjtM\n$(whoami)"},
    {"url": "http://127.0.0.1/private"}, {"url": "file:///etc/passwd"},
    {"url": "--help"}, {"url": ["C3SB38PJjtM"]},
])
def test_download_queue_rejects_extra_fields_stale_dates_and_unsafe_urls(tmp_path, changes):
    repo, path = _download_queue(tmp_path, **changes)
    with pytest.raises(queue.QueueError):
        queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))


def test_download_dispatch_reserves_then_records_api_acceptance_and_does_not_replay(tmp_path):
    repo, path = _download_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))
    states, calls = [], []

    def checkpoint(receipt):
        states.append(json.loads(receipt.read_text())["status"])

    def submit(command, **kwargs):
        assert states == ["reserved"]
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    kwargs = dict(origin="queue/" + "a" * 40 + "/" + str(path), repo_root=repo,
                  run=submit, checkpoint=checkpoint, today=date(2026, 10, 19))
    receipt = queue.dispatch_download(request, **kwargs)
    assert states == ["reserved", "accepted"]
    assert calls == [(["gh", "workflow", "run", "download-video.yml", "--ref", "main",
                      "-f", "url=https://www.youtube.com/watch?v=C3SB38PJjtM"],
                     {"check": True, "shell": False})]
    assert json.loads(receipt.read_text())["status"] == "accepted"
    assert queue.dispatch_download(request, **kwargs) == receipt
    assert len(calls) == 1


def test_download_uncertain_api_call_is_not_automatically_replayed(tmp_path):
    repo, path = _download_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))
    calls = []

    def interrupted(command, **kwargs):
        calls.append(command)
        raise KeyboardInterrupt()

    kwargs = dict(origin="event", repo_root=repo, run=interrupted,
                  checkpoint=lambda _: None, today=date(2026, 10, 19))
    with pytest.raises(KeyboardInterrupt):
        queue.dispatch_download(request, **kwargs)
    with pytest.raises(queue.QueueError, match="reserved or failed"):
        queue.dispatch_download(request, **kwargs)
    assert len(calls) == 1


def test_download_does_not_submit_if_reservation_cannot_be_persisted(tmp_path):
    repo, path = _download_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))
    calls = []

    def broken(_):
        raise RuntimeError("persistence failed")

    with pytest.raises(RuntimeError, match="persistence failed"):
        queue.dispatch_download(request, origin="event", repo_root=repo,
                                run=lambda *a, **k: calls.append(a), checkpoint=broken,
                                today=date(2026, 10, 19))
    assert calls == []


def test_download_event_only_binds_the_original_queue_file(tmp_path):
    repo, path = _download_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))
    original = (repo / path).read_bytes()
    calls = []

    def show(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=original)

    queue.verify_event_inputs(path, request, "a" * 40, repo_root=repo, run=show)
    assert len(calls) == 1
    (repo / path).write_text("{}")
    with pytest.raises(queue.QueueError, match="changed since triggering event"):
        queue.verify_event_inputs(path, request, "a" * 40, repo_root=repo, run=show)


def test_download_failed_submission_records_failure_without_blind_retry(tmp_path):
    repo, path = _download_queue(tmp_path)
    request = queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))
    states, calls = [], []

    def submit(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    kwargs = dict(origin="event", repo_root=repo, run=submit,
                  checkpoint=lambda p: states.append(json.loads(p.read_text())["status"]),
                  today=date(2026, 10, 19))
    with pytest.raises(subprocess.CalledProcessError):
        queue.dispatch_download(request, **kwargs)
    assert states == ["reserved", "failed"]
    with pytest.raises(queue.QueueError, match="reserved or failed"):
        queue.dispatch_download(request, **kwargs)
    assert len(calls) == 1


def test_download_main_routes_only_to_source_dispatch(monkeypatch):
    path = Path("data/reel-dispatch-queue/one.json")
    request = queue.DownloadRequest("download", "main", "2026-10-19",
                                    "https://www.youtube.com/watch?v=C3SB38PJjtM")
    calls = []
    monkeypatch.setattr(queue, "discover_queue_file", lambda *_: path)
    monkeypatch.setattr(queue, "load_queue", lambda *_: request)
    monkeypatch.setattr(queue, "verify_event_inputs", lambda *a: calls.append("verified"))
    monkeypatch.setattr(queue, "dispatch_download", lambda r, **k: calls.append((r, k)))
    assert queue.main(["--before", "a" * 40, "--after", "b" * 40]) == 0
    assert calls == ["verified", (request, {"origin": "queue/" + "b" * 40 + "/" + str(path)})]


def test_download_queue_shares_bounded_file_and_single_addition_guards(tmp_path):
    repo, path = _download_queue(tmp_path)
    (repo / path).write_bytes(b" " * (queue.MAX_QUEUE_BYTES + 1))
    with pytest.raises(queue.QueueError, match="too large"):
        queue.load_queue(path, repo_root=repo, today=date(2026, 10, 19))

    def two_added(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=(
            "A\0data/reel-dispatch-queue/a.json\0"
            "A\0data/reel-dispatch-queue/b.json\0"))

    with pytest.raises(queue.QueueError, match="exactly one"):
        queue.discover_queue_file("a" * 40, "b" * 40, repo_root=repo, run=two_added)
