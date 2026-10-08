"""Message-only corrections keep video/QC frozen and retain native idempotency."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import auto_push_gate as gate  # noqa: E402
import publication_revision as revision  # noqa: E402
from publication_ledger import load as ledger_load, write as ledger_write  # noqa: E402

SLUG = "demo"
OUT = "output/2026-09-30/reel/demo"
PARENT = "a" * 32
NEXT = "b" * 32
RUN = "https://github.com/o/r/actions/runs/2"
FILM = hashlib.sha256(b"original-film").hexdigest()


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


def commit(repo, message="fixture"):
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=test@example.invalid", "-c", "user.name=Test",
        "commit", "--allow-empty", "-qm", message)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def descriptor(path):
    return {"path": path.name, "sha256": revision.sha(path.read_bytes()),
            "bytes": path.stat().st_size}


def manifest(repo):
    path = repo / OUT / revision.NAME
    return path, json.loads(path.read_text())


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path
    git(repo, "init", "-q")
    out = repo / OUT
    out.mkdir(parents=True)
    spec = repo / "specs/reels/demo.json"
    dump(spec, {"column": "赛场之上", "push": {"auto": True, "summary": "样片"}})
    (spec.with_suffix(".xhs.txt")).write_text("9.30 标题\n\n正文")
    (out / "subtitles.ass").write_text("original-subtitles")
    (out / "copy.html").write_text("original-copy-page")
    (out / "poster.jpg").write_bytes(b"original-poster")
    (out / "stat_card.jpg").write_bytes(b"original-card")
    qc = {"status": "pass", "slug": SLUG, "film_sha256": FILM, "film_bytes": 13,
          "spec_sha256": revision.sha(spec.read_bytes()),
          "ass_sha256": revision.sha((out / "subtitles.ass").read_bytes())}
    dump(out / "qc_attestation.json", qc)
    render = {"video_url": "https://example.invalid/original.mp4", "film_sha256": FILM,
              "video_bytes": 13,
              "qc_attestation_sha256": revision.sha((out / "qc_attestation.json").read_bytes())}
    dump(out / "render.json", render)
    archive = out / "pushed.before-correction.json"
    dump(archive, {"at": "2026-09-30T10:00:00Z", "run": "previous", "pushplus_receipt": PARENT})
    card = out / "stat_card.corrected.jpg"
    card.write_bytes(b"corrected-card")
    source = out / "stats-source.json"
    dump(source, {"source": "TNNS", "winners": [23, 24]})
    for name in revision.THEME_SOURCES:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("frozen-theme:" + name)
    m = {"version": 1, "kind": "message-correction", "slug": SLUG,
         "revision_id": "theme-stats-20260930", "parent_receipt": PARENT,
         "film": {"sha256": FILM, "url": render["video_url"], "bytes": 13},
         "previous_pushed": descriptor(archive), "stat_card": descriptor(card),
         "stats_source": descriptor(source),
         "copy_sha256": revision.sha(spec.with_suffix(".xhs.txt").read_bytes()),
         "copy_page_sha256": revision.sha((out / "copy.html").read_bytes()),
         "theme_sources": {name: revision.sha((repo / name).read_bytes())
                           for name in revision.THEME_SOURCES}}
    dump(out / revision.NAME, m)
    ledger_write(repo, "reel", SLUG, FILM, status="sent", run_url="previous",
                 now="2026-09-30T10:00:00Z", receipt=PARENT)
    commit(repo)
    return repo


def resolve(repo, **kw):
    return revision.resolve(repo, SLUG, Path(OUT), gate.validate_qc(repo, SLUG, repo / OUT), **kw)


def reserve(repo):
    gate.ledger_status(repo, repo / OUT, "sending", RUN, "2026-09-30T11:00:00Z")


def test_exact_revision_uses_separate_delivery_identity_without_changing_video(repo):
    original = {p: (repo / p).read_bytes() for p in [f"{OUT}/stat_card.jpg",
                f"{OUT}/render.json", f"{OUT}/qc_attestation.json", "specs/reels/demo.json"]}
    r = resolve(repo)
    assert r.fingerprint.startswith("content-revision:") and r.fingerprint != FILM
    assert r.stat_card_name == "stat_card.corrected.jpg"
    gate.wants_auto_push(repo, SLUG, repo / OUT)
    reserve(repo)
    with pytest.raises(revision.RevisionError, match="changed after checkout"):
        resolve(repo, phase="send", run_url=RUN)  # local reservation has not reached HEAD
    commit(repo, "durable reservation")
    assert resolve(repo, phase="send", run_url=RUN).fingerprint == r.fingerprint
    gate.ledger_status(repo, repo / OUT, "sent", RUN, "2026-09-30T11:01:00Z", receipt=NEXT)
    gate.record(repo / OUT, RUN, "2026-09-30T11:01:00Z", NEXT)
    rows = ledger_load(repo, "reel", SLUG)["attempts"]
    assert len(rows) == 2 and rows[0]["pushplus_receipt"] == PARENT
    assert rows[1]["pushplus_receipt"] == NEXT and rows[1]["fingerprint"] == r.fingerprint
    assert {p: (repo / p).read_bytes() for p in original} == original
    with pytest.raises(revision.RevisionError, match="already been reserved or sent"):
        resolve(repo)


def test_reservation_belongs_to_exact_run_and_is_not_repeatable(repo):
    with pytest.raises(revision.RevisionError, match="own persisted reservation"):
        resolve(repo, phase="send", run_url=RUN)
    reserve(repo)
    commit(repo)
    with pytest.raises(revision.RevisionError, match="own persisted reservation"):
        resolve(repo, phase="send", run_url=RUN + "9")
    with pytest.raises(SystemExit, match="already been reserved"):
        reserve(repo)


@pytest.mark.parametrize("name", ["stat_card.corrected.jpg", "stats-source.json", "copy.html"])
def test_changed_assets_after_reserve_never_borrow_reservation(repo, name):
    reserve(repo)
    commit(repo)
    (repo / OUT / name).write_bytes(b"tampered")
    with pytest.raises(revision.RevisionError, match="changed after checkout"):
        resolve(repo, phase="send", run_url=RUN)


def test_committed_changed_template_requires_new_explicit_manifest(repo):
    path = repo / "src/tennislive/render/push_style.py"
    path.write_text("changed")
    commit(repo)
    with pytest.raises(revision.RevisionError, match="theme changed"):
        resolve(repo)


@pytest.mark.parametrize("path", ["../stat.jpg", "/tmp/stat.jpg", "a/b.jpg", "stat_card.jpg"])
def test_reject_path_escape_or_overwrite_of_original_card(repo, path):
    p, m = manifest(repo)
    m["stat_card"]["path"] = path
    dump(p, m)
    commit(repo)
    with pytest.raises(revision.RevisionError):
        resolve(repo)


def test_reject_symlink_card(repo, tmp_path):
    path = repo / OUT / "stat_card.corrected.jpg"
    path.unlink()
    path.symlink_to(repo / OUT / "stat_card.jpg")
    commit(repo)
    with pytest.raises(revision.RevisionError, match="escapes repository"):
        resolve(repo)


def test_nonce_does_not_make_identical_content_sendable_again(repo):
    before = resolve(repo).fingerprint
    reserve(repo)
    p, m = manifest(repo)
    m["revision_id"] = "different-label"
    dump(p, m)
    commit(repo)
    with pytest.raises(revision.RevisionError, match="already been reserved"):
        resolve(repo)
    assert resolve(repo, phase="send", run_url=RUN).fingerprint == before


def test_stale_parent_and_unknown_attempt_fail_closed(repo):
    ledger_write(repo, "reel", SLUG, "different", status="sent", run_url="newer",
                 now="2026-09-30T10:59:00Z", receipt="c" * 32)
    with pytest.raises(revision.RevisionError, match="not the latest"):
        resolve(repo)
    ledger_write(repo, "reel", SLUG, "different", status="uncertain", run_url="newer",
                 now="2026-09-30T10:59:00Z")
    with pytest.raises(revision.RevisionError, match="pending or uncertain"):
        resolve(repo)


def test_original_qc_still_blocks_changed_spec(repo):
    (repo / "specs/reels/demo.json").write_text('{}')
    with pytest.raises(gate.Skip, match="spec 在质检后发生过变化"):
        resolve(repo)


def test_missing_local_manifest_is_not_a_sender_bypass(repo):
    (repo / OUT / revision.NAME).unlink()
    assert revision.has_revision(repo, Path(OUT))
    assert resolve(repo).fingerprint.startswith("content-revision:")


def test_uncertain_after_success_preserves_known_receipt(repo):
    reserve(repo)
    commit(repo)
    gate.ledger_status(repo, repo / OUT, "sent", RUN, "now", receipt=NEXT)
    gate.ledger_status(repo, repo / OUT, "uncertain", RUN, "later")
    row = ledger_load(repo, "reel", SLUG)["attempts"][-1]
    assert row["status"] == "sent" and row["pushplus_receipt"] == NEXT


def test_no_manifest_keeps_original_film_gate(repo):
    git(repo, "rm", f"{OUT}/{revision.NAME}")
    commit(repo)
    assert resolve(repo) is None
    with pytest.raises(gate.Skip, match="持久发布账本"):
        gate.wants_auto_push(repo, SLUG, repo / OUT)


def _sender(repo, monkeypatch, *, extra=(), after_wait=None):
    import push_reel
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GITHUB_RUN_ID", "2")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("RUNNER_TEMP", str(repo.parent / (repo.name + "-runner-temp")))
    monkeypatch.setattr(push_reel, "wait_for_copy_page", lambda *a: None)
    monkeypatch.setattr(push_reel, "wait_for_video", lambda *a: after_wait() if after_wait else None)
    sent = []
    monkeypatch.setattr(push_reel, "push", lambda title, body, **kw: sent.append((title, body)) or NEXT)
    monkeypatch.setattr(sys, "argv", ["push_reel.py", "--outdir", OUT,
                                    "--copy", "specs/reels/demo.xhs.txt", *extra])
    return push_reel, sent


def test_sender_uses_corrected_card_and_original_film_once(repo, monkeypatch):
    reserve(repo)
    commit(repo)
    sender, sent = _sender(repo, monkeypatch)
    assert sender.main() == 0
    assert len(sent) == 1
    assert "stat_card.corrected.jpg" in sent[0][1]
    assert "/stat_card.jpg" not in sent[0][1]
    assert "https://example.invalid/original.mp4" in sent[0][1]
    with pytest.raises(revision.RevisionError, match="already started"):
        sender.main()
    assert len(sent) == 1


def test_sender_cannot_override_revision_message(repo, monkeypatch):
    reserve(repo)
    commit(repo)
    sender, sent = _sender(repo, monkeypatch, extra=("--lead", "unapproved text"))
    with pytest.raises(SystemExit, match="不允许临时覆盖"):
        sender.main()
    assert not sent


def test_sender_rechecks_after_network_wait_before_post(repo, monkeypatch):
    reserve(repo)
    commit(repo)
    sender, sent = _sender(repo, monkeypatch, after_wait=lambda:
        (repo / OUT / "stat_card.corrected.jpg").write_bytes(b"changed during wait"))
    with pytest.raises(revision.RevisionError, match="changed after checkout"):
        sender.main()
    assert not sent


def test_archive_time_and_run_must_match_historical_parent(repo):
    p, m = manifest(repo)
    archive = repo / OUT / m["previous_pushed"]["path"]
    data = json.loads(archive.read_text())
    data["run"] = "different-run"
    dump(archive, data)
    m["previous_pushed"] = descriptor(archive)
    dump(p, m)
    commit(repo)
    with pytest.raises(revision.RevisionError, match="exact historical"):
        resolve(repo)


def test_direct_sender_rejects_active_marker_even_with_reservation(repo):
    reserve(repo)
    commit(repo)
    dump(repo / OUT / "pushed.json", {"pushplus_receipt": NEXT})
    with pytest.raises(revision.RevisionError, match="active pushed.json"):
        resolve(repo, phase="send", run_url=RUN)


def test_v1_does_not_accept_unproven_correction_chain(repo):
    ledger_path = repo / "data/reel_publish_ledger/demo.json"
    data = json.loads(ledger_path.read_text())
    data["attempts"][0]["fingerprint"] = "content-revision:" + "f" * 64
    data["attempts"][0]["key"] = "pushplus:reel:demo:" + data["attempts"][0]["fingerprint"]
    dump(ledger_path, data)
    with pytest.raises(revision.RevisionError, match="original film publication"):
        resolve(repo)
