from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reel_delivery_sla as sla

FILM = "f" * 64
SLUG = "one"
OUT = Path("output/2026-10-12/reel/one")
RECEIPT = "1" * 32
NOW = datetime(2026, 10, 12, 21, tzinfo=timezone.utc)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def commit(repo):
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "native proof"],
                   check=True, capture_output=True)


@pytest.fixture
def native(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, value in [("user.name", "test"), ("user.email", "test@example.invalid")]:
        subprocess.run(["git", "-C", str(tmp_path), "config", name, value], check=True)
    spec = tmp_path / "specs/reels/one.json"
    write(spec, {"slug": SLUG, "sources": {"main": "https://www.youtube.com/watch?v=one"}})
    directory = tmp_path / OUT
    directory.mkdir(parents=True)
    ass = directory / "subtitles.ass"
    ass.write_text("actual subtitle fixture")
    qc = {"status": "pass", "slug": SLUG, "film_sha256": FILM, "film_bytes": 30,
          "spec_sha256": hashlib.sha256(spec.read_bytes()).hexdigest(),
          "ass_sha256": hashlib.sha256(ass.read_bytes()).hexdigest()}
    write(directory / "qc_attestation.json", qc)
    write(directory / "render.json", {"film_sha256": FILM, "video_bytes": 30,
          "video_url": "https://example.invalid/one.mp4",
          "qc_attestation_sha256": hashlib.sha256(
              (directory / "qc_attestation.json").read_bytes()).hexdigest()})
    marker = {"at": "2026-10-12T20:20:00Z", "run": "https://example.invalid/runs/1",
              "pushplus_receipt": RECEIPT}
    write(directory / "pushed.json", marker)
    row = {"key": f"pushplus:reel:one:{FILM}", "fingerprint": FILM,
           "status": "sent", **marker}
    write(tmp_path / "data/reel_publish_ledger/one.json",
          {"slug": SLUG, "channel": "pushplus", "attempts": [row]})
    clock = tmp_path / "request-clock.json"
    write(clock, {"started_at_utc": "2026-10-12T20:11:13Z", "target_seconds": 1200,
                  "source_url": "https://youtu.be/one?is=tracking"})
    commit(tmp_path)
    return tmp_path, directory, clock


def get(native):
    repo, directory, clock = native
    return sla.report(repo=repo, slug=SLUG, outdir=directory, clock=clock, now=NOW)


def test_same_native_film_receipt_and_late_receipt_are_truthful_observations(native):
    repo, directory, _ = native
    before = {str(p): p.read_bytes() for p in [directory / "render.json",
              directory / "qc_attestation.json", directory / "pushed.json",
              repo / "data/reel_publish_ledger/one.json"]}
    result = get(native)
    assert result["delivery_confirmed"] and result["met"]
    assert result["elapsed_seconds"] == 527
    assert result["receipt_recorded_at"] == "2026-10-12T20:20:00Z"
    assert result["film_sha256"] == result["publication_fingerprint"] == FILM
    assert all(Path(p).read_bytes() == data for p, data in before.items())
    marker = json.loads((directory / "pushed.json").read_text())
    marker["at"] = "2026-10-12T20:32:00Z"
    write(directory / "pushed.json", marker)
    ledger = repo / "data/reel_publish_ledger/one.json"
    data = json.loads(ledger.read_text()); data["attempts"][0].update(marker)
    write(ledger, data); commit(repo)
    result = get(native)
    assert result["delivery_confirmed"] and not result["met"]
    assert result["elapsed_seconds"] == 1247


@pytest.mark.parametrize("bad", ["missing_receipt", "sending", "uncertain", "old_film",
                                "different_run", "different_at", "old_receipt", "dirty_marker"])
def test_incomplete_ambiguous_or_stale_native_proof_cannot_claim_delivery(native, bad):
    repo, directory, _ = native
    marker_path = directory / "pushed.json"
    ledger_path = repo / "data/reel_publish_ledger/one.json"
    marker = json.loads(marker_path.read_text()); ledger = json.loads(ledger_path.read_text())
    row = ledger["attempts"][0]
    if bad == "missing_receipt":
        marker.pop("pushplus_receipt")
    elif bad in {"sending", "uncertain"}:
        row["status"] = bad
    elif bad == "old_film":
        row.update(fingerprint="a" * 64, key="pushplus:reel:one:" + "a" * 64)
    elif bad == "different_run":
        row["run"] = "https://example.invalid/runs/2"
    elif bad == "different_at":
        row["at"] = "2026-10-12T20:20:01Z"
    elif bad == "old_receipt":
        marker["at"] = row["at"] = "2026-10-12T20:10:00Z"
    else:
        marker["at"] = "2026-10-12T20:20:01Z"
    write(marker_path, marker); write(ledger_path, ledger)
    if bad != "dirty_marker":
        commit(repo)
    result = get(native)
    assert not result["delivery_confirmed"] and not result["met"]
    assert result["elapsed_seconds"] is None and result["receipt_recorded_at"] is None


def test_render_qc_mismatch_and_unvalidated_revision_cannot_reuse_receipt(native):
    repo, directory, _ = native
    render_path = directory / "render.json"
    data = json.loads(render_path.read_text()); data["film_sha256"] = "a" * 64
    write(render_path, data); commit(repo)
    assert not get(native)["delivery_confirmed"]
    data["film_sha256"] = FILM; write(render_path, data)
    # A revision needs the real committed native manifest/assets/parent lineage,
    # not just an invented content-revision fingerprint in a marker.
    write(directory / "publication_revision.json", {"version": 1, "slug": SLUG})
    commit(repo)
    result = get(native)
    assert not result["delivery_confirmed"] and not result["met"]
