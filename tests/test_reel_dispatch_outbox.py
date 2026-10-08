"""Durable dispatch acceptance, tested with fake API and real local Git only."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reel_dispatch_outbox as outbox
from dispatch_reel_queue import QueueRequest


@pytest.fixture(autouse=True)
def specs(tmp_path):
    folder = tmp_path / "specs/reels"
    folder.mkdir(parents=True)
    for slug in ("alpha", "bravo", "charlie", "delta"):
        (folder / f"{slug}.json").write_text(json.dumps({"slug": slug}))
        (folder / f"{slug}.xhs.txt").write_text("reviewed copy")


def request(slugs=("alpha", "bravo", "charlie")):
    return QueueRequest("render", "main", "2026-10-04", slugs)


def test_partial_failure_survives_new_runner_and_skips_accepted_slugs(tmp_path):
    path = outbox.enqueue(request(), origin="queue/reviewed.json", root=tmp_path)
    remote = tmp_path / "persisted.json"
    calls = []

    def fake_api(command, **kwargs):
        slug = next(arg[5:] for arg in command if arg.startswith("slug="))
        calls.append(slug)
        if slug == "bravo":
            raise subprocess.CalledProcessError(1, command)

    failures = outbox.drain(path, root=tmp_path, run=fake_api,
                           checkpoint=lambda p: remote.write_bytes(p.read_bytes()))
    assert failures == ["bravo"]
    assert calls == ["alpha", "bravo", "charlie"]  # One failed API doesn't block siblings.
    assert set(json.loads(remote.read_text())["dispatched"]) == {"alpha", "charlie"}
    # Simulate a new runner loading only the committed receipt.
    path.write_bytes(remote.read_bytes())
    calls.clear()
    assert outbox.drain(path, root=tmp_path,
                        run=lambda cmd, **kw: calls.append(cmd),
                        checkpoint=lambda p: remote.write_bytes(p.read_bytes())) == []
    assert len(calls) == 1 and "slug=bravo" in calls[0]
    assert "received_at=" in " ".join(calls[0])


def test_enqueue_is_idempotent_and_new_explicit_request_can_rerender(tmp_path):
    first = outbox.enqueue(request(), origin="queue/first.json", root=tmp_path)
    original = first.read_bytes()
    assert outbox.enqueue(request(), origin="queue/first.json", root=tmp_path) == first
    assert first.read_bytes() == original
    assert outbox.enqueue(request(), origin="queue/new-request.json", root=tmp_path) != first
    assert outbox.enqueue(request(("delta",)), origin="queue/first.json", root=tmp_path) != first


def test_no_draft_is_needed_to_resume_ready_intent(tmp_path, monkeypatch):
    path = outbox.enqueue(request(("alpha",)), origin="auto-ready/alpha/content-hash",
                          root=tmp_path, push=False)
    monkeypatch.setattr(outbox, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["outbox", "drain-ready"])
    drained = []
    monkeypatch.setattr(outbox, "drain", lambda p: drained.append(p) or [])
    assert not list((tmp_path / "specs").rglob("*.draft.json"))
    assert outbox.main() == 0
    assert drained == [path]


def test_checkpoint_failure_does_not_claim_render_success(tmp_path):
    path = outbox.enqueue(request(), origin="queue/x", root=tmp_path)
    calls = []

    def fail(_path):
        raise RuntimeError("remote push rejected")

    with pytest.raises(RuntimeError, match="remote push rejected"):
        outbox.drain(path, root=tmp_path, run=lambda cmd, **kw: calls.append(cmd),
                     checkpoint=fail)
    assert len(calls) == 1
    data = json.loads(path.read_text())
    assert list(data["dispatched"]) == ["alpha"]
    assert "rendered" not in data and "published" not in data


def test_git_checkpoint_is_recoverable_in_fresh_clone(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    git("remote", "add", "origin", str(remote))
    (repo / "tools").mkdir()
    source = Path(__file__).resolve().parents[1] / "tools/git_push_retry.sh"
    (repo / "tools/git_push_retry.sh").write_bytes(source.read_bytes())
    git("add", "tools")
    git("commit", "-m", "base")
    (repo / "specs/reels").mkdir(parents=True)
    for name in ("alpha.json", "alpha.xhs.txt"):
        (repo / "specs/reels" / name).write_text("reviewed")
    git("add", "specs")
    git("commit", "-m", "reviewed spec")
    path = outbox.enqueue(request(("alpha",)), origin="queue/local-test", root=repo)
    outbox.persist(path, root=repo)
    outbox.drain(path, root=repo, run=lambda *_a, **_k: None)
    restored = tmp_path / "restored"
    subprocess.run(["git", "clone", "-b", "main", str(remote), str(restored)],
                   check=True, capture_output=True)
    data = json.loads((restored / path.relative_to(repo)).read_text())
    assert list(data["dispatched"]) == ["alpha"]


def test_workflows_commit_intents_and_drain_without_new_drafts():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".github/workflows/reel-auto-ready.yml").read_text()
    config = yaml.safe_load(text)
    steps = config["jobs"]["ready"]["steps"]
    enqueue = next(s for s in steps if "enqueue-ready" in s.get("run", ""))
    commit = next(s for s in steps if "git add specs/reels" in s.get("run", ""))
    drain = next(s for s in steps if "drain-ready" in s.get("run", ""))
    assert steps.index(enqueue) < steps.index(commit) < steps.index(drain)
    assert "data/reel-dispatch-outbox" in commit["run"]
    assert "if" not in drain  # No dependency on number promoted in this tick.
    for name in ("reel-auto-ready", "reel-dispatch-queue"):
        wf = yaml.safe_load((root / f".github/workflows/{name}.yml").read_text())
        assert wf["permissions"]["contents"] == "write"
        job = next(iter(wf["jobs"].values()))
        checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["ref"] == "main"


def test_changed_input_is_not_dispatched_under_old_reviewed_intent(tmp_path):
    path = outbox.enqueue(request(("alpha",)), origin="queue/x", root=tmp_path)
    (tmp_path / "specs/reels/alpha.json").write_text('{"slug":"alpha","changed":true}')
    calls = []
    assert outbox.drain(path, root=tmp_path, run=lambda *a, **k: calls.append(a),
                        checkpoint=lambda p: None) == ["alpha"]
    assert calls == []
    assert json.loads(path.read_text())["dispatched"] == {}
    assert "alpha" in json.loads(path.read_text())["invalidated"]
    # Invalidated is a terminal non-success result, not a noisy permanent retry.
    assert outbox.drain(path, root=tmp_path, run=lambda *a, **k: calls.append(a),
                        checkpoint=lambda p: None) == []
    assert calls == []
    fresh = outbox.enqueue(request(("alpha",)), origin="queue/new-review", root=tmp_path)
    assert outbox.drain(fresh, root=tmp_path, run=lambda *a, **k: calls.append(a),
                        checkpoint=lambda p: None) == []
    assert len(calls) == 1


def test_invalidated_input_does_not_block_other_slugs(tmp_path):
    path = outbox.enqueue(request(("alpha", "bravo")), origin="queue/x", root=tmp_path)
    (tmp_path / "specs/reels/alpha.xhs.txt").unlink()
    calls = []
    assert outbox.drain(path, root=tmp_path, run=lambda cmd, **kw: calls.append(cmd),
                        checkpoint=lambda p: None) == ["alpha"]
    assert len(calls) == 1 and "slug=bravo" in calls[0]
    record = json.loads(path.read_text())
    assert set(record["dispatched"]) == {"bravo"}
    assert set(record["invalidated"]) == {"alpha"}


def test_queue_rerun_fetches_both_event_edges():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/reel-dispatch-queue.yml").read_text())
    step = next(s for s in workflow["jobs"]["dispatch"]["steps"]
                if "git fetch" in s.get("run", ""))
    assert step["env"]["BEFORE"] == "${{ github.event.before }}"
    assert step["env"]["AFTER"] == "${{ github.sha }}"
    assert 'origin "$BEFORE" "$AFTER"' in step["run"]


def test_auto_ready_expiry_uses_original_received_at_and_shared_policy(tmp_path):
    from datetime import datetime, timedelta, timezone

    from promote_reel_draft import PENDING_MAX_AGE

    now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    old = now - PENDING_MAX_AGE - timedelta(seconds=1)
    path = outbox.enqueue(request(("alpha",)), origin="auto-ready/alpha/hash", root=tmp_path,
                          received_at=old.isoformat())
    calls = []
    assert outbox.drain(path, root=tmp_path, run=lambda *a, **k: calls.append(a),
                        checkpoint=lambda p: None, now=now) == ["alpha"]
    record = json.loads(path.read_text())
    assert calls == [] and not record["dispatched"]
    assert "expired" in record["invalidated"]["alpha"]["reason"]
    assert outbox.drain(path, root=tmp_path, run=lambda *a, **k: calls.append(a),
                        checkpoint=lambda p: None, now=now) == []


def test_event_inputs_cannot_be_replaced_by_later_main_edits(tmp_path):
    from dispatch_reel_queue import QueueError, verify_event_inputs

    queue = Path("data/reel-dispatch-queue/reviewed.json")
    (tmp_path / queue).parent.mkdir(parents=True)
    (tmp_path / queue).write_text("original reviewed queue")
    baseline = {p: (tmp_path / p).read_bytes() for p in (
        queue, Path("specs/reels/alpha.json"), Path("specs/reels/alpha.xhs.txt"))}

    def original_event(command, **kwargs):
        path = Path(command[-1].split(":", 1)[1])
        return subprocess.CompletedProcess(command, 0, stdout=baseline[path])

    verify_event_inputs(queue, request(("alpha",)), "a" * 40, repo_root=tmp_path, run=original_event)
    for path, original in baseline.items():
        (tmp_path / path).write_bytes(b"modified on later main")
        with pytest.raises(QueueError, match="changed since triggering event"):
            verify_event_inputs(queue, request(("alpha",)), "a" * 40,
                                repo_root=tmp_path, run=original_event)
        (tmp_path / path).write_bytes(original)
