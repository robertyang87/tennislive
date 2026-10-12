#!/usr/bin/env python3
"""Read-only source-received -> recorded PushPlus receipt timing for one reel."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from auto_push_gate import Skip, validate_qc
from publication_ledger import key
from publication_revision import RevisionError, _json, _read, resolve
from video_sla import SlaError, parse_instant, utc_text


def _source_identity(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        return "youtube:" + parsed.path.strip("/")
    if parsed.hostname in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
        video = parse_qs(parsed.query).get("v", [""])[0]
        if video:
            return "youtube:" + video
    return url


def report(*, repo: Path, slug: str, outdir: Path, clock: Path,
           now: datetime | None = None) -> dict:
    """Never send, repair or reserve publication; late delivery remains valid data.

    `at` is the native receipt bookkeeping time, not an invented provider-response
    timestamp. Native QC and message-revision validation retain their own rules.
    """
    repo = repo.resolve()
    outdir = (outdir if outdir.is_absolute() else repo / outdir).resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug) or not outdir.is_relative_to(repo):
        raise SlaError("invalid slug or output directory outside repository")
    if not re.fullmatch(r"output/\d{4}-\d{2}-\d{2}/reel/" + re.escape(slug),
                        outdir.relative_to(repo).as_posix()):
        raise SlaError("output must be the exact dated native reel directory")
    raw_clock = clock.read_bytes()
    values = json.loads(raw_clock)
    start = parse_instant(values.get("started_at_utc", ""))
    budget = values.get("target_seconds")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise SlaError("clock target_seconds must be a positive integer")
    if values.get("target_push_deadline_utc"):
        deadline = parse_instant(values["target_push_deadline_utc"])
        if (deadline - start).total_seconds() != budget:
            raise SlaError("clock deadline disagrees with start and budget")
    checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if checked < start:
        raise SlaError("clock starts after report time")
    result = {
        "schema": "tennislive.reel-delivery-sla.v1", "slug": slug,
        "started_at_utc": utc_text(start), "budget_seconds": budget,
        "clock_source": str(clock.resolve()),
        "clock_sha256": hashlib.sha256(raw_clock).hexdigest(),
        "checked_at_utc": utc_text(checked),
        "delivery_confirmed": False, "met": False,
        "elapsed_seconds": None, "receipt_recorded_at": None,
        "film_sha256": None, "publication_fingerprint": None,
        "reason": "native delivery proof not yet available",
        "timestamp_semantics": "native receipt recorded time; not provider response time",
    }
    try:
        film_hash = validate_qc(repo, slug, outdir)
        if not re.fullmatch(r"[a-f0-9]{64}", film_hash):
            raise ValueError("native QC film SHA256 is invalid")
        result["film_sha256"] = film_hash
        spec = json.loads((repo / "specs/reels" / f"{slug}.json").read_text())
        expected_sources = spec.get("sources") or {"main": spec.get("source_url", "")}
        source = values.get("source_url")
        if not source or _source_identity(source) not in {
                _source_identity(url) for url in expected_sources.values()}:
            raise ValueError("clock source does not match this QC-validated reel")
        marker_rel = (outdir.relative_to(repo) / "pushed.json").as_posix()
        pushed = _json(_read(repo, marker_rel), "native pushed.json")
        receipt = pushed.get("pushplus_receipt")
        if not re.fullmatch(r"[a-fA-F0-9]{32}", str(receipt or "")):
            raise ValueError("native pushed.json lacks a valid provider receipt")
        run = pushed.get("run")
        if not isinstance(run, str) or not run.strip():
            raise ValueError("native receipt has no run identity")
        revision = resolve(repo, slug, outdir, film_hash, phase="finish", run_url=run)
        fingerprint = revision.fingerprint if revision else film_hash
        result["publication_fingerprint"] = fingerprint
        ledger = _json(_read(repo, f"data/reel_publish_ledger/{slug}.json"),
                       "native publication ledger")
        if ledger.get("slug") != slug or ledger.get("channel") != "pushplus":
            raise ValueError("native ledger slug/channel mismatch")
        attempts = ledger.get("attempts")
        if not isinstance(attempts, list) or not all(isinstance(row, dict) for row in attempts):
            raise ValueError("invalid native ledger attempts")
        if any(row.get("status") in {"sending", "uncertain"} for row in attempts):
            raise ValueError("publication has a pending or uncertain attempt")
        matches = [row for row in attempts if row.get("key") == key("reel", slug, fingerprint)]
        if len(matches) != 1:
            raise ValueError("no unique ledger attempt for the current film/revision")
        sent = matches[0]
        if sent.get("fingerprint") != fingerprint or sent.get("status") != "sent":
            raise ValueError("current film/revision is not confirmed sent")
        if any(sent.get(field) != pushed.get(field) for field in
               ("pushplus_receipt", "run", "at")):
            raise ValueError("marker and ledger receipt/run/recorded time disagree")
        received = parse_instant(pushed.get("at", ""))
        if received < start or received > checked:
            raise ValueError("receipt time predates request or is after report time")
        elapsed = (received - start).total_seconds()
        result.update(delivery_confirmed=True, met=elapsed <= budget,
                      elapsed_seconds=round(elapsed, 3),
                      receipt_recorded_at=utc_text(received),
                      pushplus_receipt=receipt, run=run,
                      reason="same native QC film/revision, marker and sent ledger receipt",
                      message_url=f"https://www.pushplus.plus/shortMessage/{receipt}")
    except (Skip, RevisionError, SlaError, OSError, ValueError, TypeError) as exc:
        result["reason"] = str(exc)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--slug", required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--clock", type=Path, required=True)
    parser.add_argument("--report", type=Path,
                        help="optional separate report; never write native metadata/ledger")
    args = parser.parse_args(argv)
    try:
        value = report(repo=args.repo, slug=args.slug, outdir=args.outdir, clock=args.clock)
    except (SlaError, OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    body = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        target = args.report.resolve()
        native_dir = (args.outdir if args.outdir.is_absolute() else args.repo / args.outdir).resolve()
        if (target.is_relative_to(args.repo.resolve() / "specs")
                or target.is_relative_to(args.repo.resolve() / "data/audio_reviews")):
            parser.error("report cannot overwrite specs or native audio-review evidence")
        if target.is_relative_to(native_dir) or target.is_relative_to(
                args.repo.resolve() / "data/reel_publish_ledger") or target == args.clock.resolve():
            parser.error("report must be separate from native output, ledger and clock")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    print(body, end="")
    return 0  # a missed budget is an observation, never a quality-gate override


if __name__ == "__main__":
    raise SystemExit(main())
