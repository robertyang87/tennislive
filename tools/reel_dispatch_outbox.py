#!/usr/bin/env python3
"""Git-backed render dispatch intents and per-slug API acceptance receipts.

Receipts mean GitHub accepted workflow_dispatch, never that rendering/publishing
succeeded. Commit intents with the promoted specs; retry pending intents on every
scheduler tick. Each request owns a file so unrelated jobs can rebase safely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dispatch_reel_queue import SLUG_RE, QueueRequest, dispatch

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = Path("data/reel-dispatch-outbox")


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def input_digest(root: Path, slug: str) -> str:
    spec = root / "specs" / "reels" / f"{slug}.json"
    return hashlib.sha256(spec.read_bytes() + b"\0" + spec.with_suffix(".xhs.txt").read_bytes()).hexdigest()


def enqueue(request: QueueRequest, *, origin: str, root: Path = ROOT,
            push: bool = True, received_at: str | None = None) -> Path:
    """The caller commits the returned intent before invoking drain()."""
    payload = {"mode": request.mode, "ref": request.ref,
               "expected_date": request.expected_date, "slugs": list(request.slugs),
               "push": push}
    key = hashlib.sha256(json.dumps({"origin": origin, "request": payload},
                                   sort_keys=True).encode()).hexdigest()
    path = root / DIRECTORY / f"{key}.json"
    if not path.exists():
        _write(path, {"version": 1, "origin": origin, "request": payload,
                      "received_at": received_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "inputs": {slug: input_digest(root, slug) for slug in request.slugs},
                      "dispatched": {}, "invalidated": {}})
    return path


def persist(path: Path, *, root: Path = ROOT) -> None:
    """Save one request; stop on persistence failure instead of losing receipts."""
    relative = str(path.relative_to(root))
    subprocess.run(["git", "add", "--", relative], cwd=root, check=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet", "--", relative], cwd=root, check=False)
    if changed.returncode not in (0, 1):
        raise RuntimeError("cannot inspect dispatch receipt changes")
    if changed.returncode:
        subprocess.run(["git", "commit", "-m", "reel: persist dispatch intent/receipt",
                        "--", relative], cwd=root, check=True)
    # Retry even when a preceding attempt already committed the local receipt.
    subprocess.run(["bash", "-c", "source tools/git_push_retry.sh; push_with_rebase_retry main 5"],
                   cwd=root, check=True)


def drain(path: Path, *, root: Path = ROOT, run=subprocess.run,
          checkpoint=None, now: datetime | None = None) -> list[str]:
    """Continue siblings after API failure; persist each accepted slug immediately."""
    record = json.loads(path.read_text())
    payload = record["request"]
    if (record.get("version") != 1 or payload.get("ref") != "main"
            or payload.get("mode") not in {"render", "push"}
            or not isinstance(payload.get("slugs"), list)
            or not payload["slugs"] or len(payload["slugs"]) > 8
            or any(not isinstance(s, str) or not SLUG_RE.fullmatch(s) for s in payload["slugs"])
            or len(set(payload["slugs"])) != len(payload["slugs"])
            or (payload["mode"] == "push" and len(payload["slugs"]) != 1)
            or not isinstance(payload.get("push"), bool)
            or not isinstance(record.get("dispatched"), dict)):
        raise ValueError(f"invalid outbox request: {path}")
    failures = []
    expired = False
    if str(record.get("origin", "")).startswith("auto-ready/"):
        from promote_reel_draft import PENDING_MAX_AGE

        try:
            received = datetime.fromisoformat(record["received_at"].replace("Z", "+00:00"))
            expired = (received.tzinfo is None or
                       (now or datetime.now(timezone.utc)) - received > PENDING_MAX_AGE)
        except (KeyError, TypeError, ValueError):
            expired = True
    checkpoint = checkpoint or (lambda p: persist(p, root=root))
    for slug in payload["slugs"]:
        if slug in record["dispatched"] or slug in record.get("invalidated", {}):
            continue
        try:
            current = input_digest(root, slug)
        except OSError:
            current = None
        if expired or current != (record.get("inputs") or {}).get(slug) or current is None:
            reason = ("automatic request expired beyond PENDING_MAX_AGE or has no valid received_at"
                      if expired else "spec/copy changed or missing since enqueue")
            print(f"::warning::{slug}: {reason}; "
                  "not dispatched. Submit a new reviewed request.", file=sys.stderr)
            record.setdefault("invalidated", {})[slug] = {
                "at": datetime.now(timezone.utc).isoformat(),
                "reason": reason + "; new reviewed request required",
            }
            _write(path, record)
            checkpoint(path)
            failures.append(slug)
            continue
        request = QueueRequest(payload["mode"], payload["ref"],
                               payload["expected_date"], (slug,))
        try:
            dispatch(request, run=run,
                     now=datetime.fromisoformat(record["received_at"].replace("Z", "+00:00")),
                     push=payload["push"])
        except (subprocess.CalledProcessError, OSError) as exc:
            print(f"::warning::{slug}: dispatch failed; remains pending: {exc}", file=sys.stderr)
            failures.append(slug)
            continue
        record["dispatched"][slug] = datetime.now(timezone.utc).isoformat()
        _write(path, record)
        try:
            checkpoint(path)
        except Exception:
            print(f"::error::{slug}: API accepted but receipt persistence failed; "
                  "retry may dispatch again. Rendering success is unknown.", file=sys.stderr)
            raise
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("enqueue-ready")
    add.add_argument("--slug", required=True)
    commands.add_parser("drain-ready")
    args = parser.parse_args()
    if args.command == "enqueue-ready":
        if not SLUG_RE.fullmatch(args.slug):
            parser.error("invalid slug")
        spec = ROOT / "specs" / "reels" / f"{args.slug}.json"
        copy = spec.with_suffix(".xhs.txt")
        identity = hashlib.sha256(spec.read_bytes() + b"\0" + copy.read_bytes()).hexdigest()
        # Content identity, not scheduler date: repeating a tick cannot make a new request.
        request = QueueRequest("render", "main", "", (args.slug,))
        production = json.loads(spec.read_text()).get("_production") or {}
        received = production.get("received_at")
        if not received:
            raise ValueError("automatic ready intent requires original production.received_at")
        print(enqueue(request, origin=f"auto-ready/{args.slug}/{identity}",
                      push=False, received_at=received))
        return 0
    failures = []
    for path in sorted((ROOT / DIRECTORY).glob("*.json")):
        record = json.loads(path.read_text())
        if str(record.get("origin", "")).startswith("auto-ready/"):
            failures.extend(drain(path))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
