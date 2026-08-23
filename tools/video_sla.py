#!/usr/bin/env python3
"""Measure and alert on the production-link -> owned-MP4 service-level target.

The clock starts when a production render is dispatched with a usable source link
and an approved spec.  Discovery/editorial preparation and publishing are reported
separately; neither is allowed to silently reset this production clock.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BUDGET_SECONDS = 600


class SlaError(ValueError):
    """The SLA clock or artifact contract is invalid."""


def parse_instant(value: str) -> datetime:
    raw = (value or "").strip()
    if not raw:
        raise SlaError("received_at is empty; the workflow must start the clock explicitly")
    try:
        if raw.replace(".", "", 1).isdigit():
            instant = datetime.fromtimestamp(float(raw), tz=timezone.utc)
        else:
            instant = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (OverflowError, OSError, ValueError) as exc:
        raise SlaError(f"invalid timestamp {value!r}") from exc
    if instant.tzinfo is None:
        raise SlaError("timestamp must include a timezone")
    return instant.astimezone(timezone.utc)


def utc_text(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def elapsed_seconds(received_at: str, *, now: datetime | None = None) -> float:
    start = parse_instant(received_at)
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    elapsed = (end - start).total_seconds()
    if elapsed < -60:
        raise SlaError(
            f"received_at {utc_text(start)} is {abs(elapsed):.1f}s in the future"
        )
    return max(0.0, elapsed)


def remaining_seconds(
    received_at: str,
    *,
    budget_seconds: int = DEFAULT_BUDGET_SECONDS,
    reserve_seconds: int = 0,
    now: datetime | None = None,
) -> int:
    if budget_seconds <= 0 or reserve_seconds < 0:
        raise SlaError("budget must be positive and reserve must be non-negative")
    left = budget_seconds - reserve_seconds - elapsed_seconds(received_at, now=now)
    return max(0, math.floor(left))


def finish(
    *,
    received_at: str,
    artifact: Path,
    metadata: Path,
    pipeline: str,
    slug: str,
    budget_seconds: int = DEFAULT_BUDGET_SECONDS,
    render_started_at: str = "",
    now: datetime | None = None,
) -> dict:
    if not artifact.is_file() or artifact.stat().st_size <= 0:
        raise SlaError(f"owned MP4 is missing or empty: {artifact}")
    ready = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    started = parse_instant(received_at)
    elapsed = max(0.0, (ready - started).total_seconds())
    render_seconds = None
    if render_started_at:
        render_started = parse_instant(render_started_at)
        render_seconds = max(0.0, (ready - render_started).total_seconds())
    record = {
        "version": 1,
        "pipeline": pipeline,
        "slug": slug,
        "received_at": utc_text(started),
        "artifact_ready_at": utc_text(ready),
        "elapsed_seconds": round(elapsed, 3),
        "budget_seconds": int(budget_seconds),
        "met": elapsed <= budget_seconds,
    }
    if render_seconds is not None:
        record["render_seconds"] = round(render_seconds, 3)
        record["pre_render_seconds"] = round(max(0.0, elapsed - render_seconds), 3)

    try:
        payload = json.loads(metadata.read_text(encoding="utf-8")) if metadata.is_file() else {}
    except (OSError, ValueError) as exc:
        raise SlaError(f"cannot merge SLA into {metadata}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SlaError(f"metadata must be a JSON object: {metadata}")
    payload["production_sla"] = record
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def append_summary(path: str, record: dict) -> None:
    if not path:
        return
    status = "PASS" if record["met"] else "FAIL"
    body = (
        "\n### 10-minute production SLA\n\n"
        f"- Status: **{status}**\n"
        f"- Link accepted → owned MP4: **{record['elapsed_seconds']:.1f}s** "
        f"/ {record['budget_seconds']}s\n"
    )
    if "pre_render_seconds" in record:
        body += (
            f"- Runner preparation: {record['pre_render_seconds']:.1f}s\n"
            f"- Render command: {record['render_seconds']:.1f}s\n"
        )
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(body)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)

    remaining = sub.add_parser("remaining", help="print seconds left in the target budget")
    remaining.add_argument("--received-at", required=True)
    remaining.add_argument("--budget", type=int, default=DEFAULT_BUDGET_SECONDS)
    remaining.add_argument("--reserve", type=int, default=0)

    done = sub.add_parser("finish", help="record the owned MP4 time and enforce the budget")
    done.add_argument("--received-at", required=True)
    done.add_argument("--render-started-at", default="")
    done.add_argument("--artifact", type=Path, required=True)
    done.add_argument("--metadata", type=Path, required=True)
    done.add_argument("--pipeline", required=True)
    done.add_argument("--slug", required=True)
    done.add_argument("--budget", type=int, default=DEFAULT_BUDGET_SECONDS)
    done.add_argument("--summary", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "remaining":
            left = remaining_seconds(
                args.received_at,
                budget_seconds=args.budget,
                reserve_seconds=args.reserve,
            )
            print(left)
            if left <= 0:
                print(
                    f"::warning::10-minute production target is already exhausted "
                    f"(budget={args.budget}s, reserve={args.reserve}s)",
                    file=sys.stderr,
                )
            return 0

        record = finish(
            received_at=args.received_at,
            render_started_at=args.render_started_at,
            artifact=args.artifact,
            metadata=args.metadata,
            pipeline=args.pipeline,
            slug=args.slug,
            budget_seconds=args.budget,
        )
        append_summary(args.summary, record)
        print(
            f"[production-sla] {record['elapsed_seconds']:.1f}s / "
            f"{record['budget_seconds']}s ({'PASS' if record['met'] else 'FAIL'})"
        )
        if not record["met"]:
            print(
                "::warning::owned MP4 missed the 10-minute production target; "
                "keep QC/publishing live and schedule a performance fix",
                file=sys.stderr,
            )
        return 0
    except SlaError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
