"""Offline cross-table audit of player names and the next ranking refresh.

Run with ``python tools/audit_player_name_alignment.py``. No files are written
and no network translation is allowed. Source changes with identical Chinese
names are informational; name drift, conflicting tables and stale review
queues fail the audit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tennislive.zh import _normalize_name, player_zh
from tennislive.zh.players import PLAYER_ZH
from tools.update_player_names import (
    OUTPUT,
    OVERRIDES,
    REVIEW_QUEUE,
    RankedName,
    build_review_queue,
    build_snapshot,
)


def audit_tables(snapshot, overrides, curated, queue, lookup=player_zh):
    """Compare independent persisted inputs with actual user-facing lookup."""
    errors = []
    grouped = {}
    for name, zh in curated.items():
        grouped.setdefault(_normalize_name(name), []).append(("Python", name, zh))
    for name, entry in overrides.get("entries", {}).items():
        grouped.setdefault(_normalize_name(name), []).append(("override", name, entry["zh"]))
    for tour, entries in snapshot.get("tours", {}).items():
        for entry in entries:
            name, zh = entry["name_en"], entry["name_zh"]
            grouped.setdefault(_normalize_name(name), []).append((tour, name, zh))
    for values in grouped.values():
        if len({value[2] for value in values}) > 1:
            errors.append(f"conflicting names: {values!r}")
        for source, name, zh in values:
            actual = lookup(name)
            if actual != zh:
                errors.append(f"lookup mismatch: {source} {name}: {zh!r} -> {actual!r}")
    expected = build_review_queue(snapshot)
    def queue_rows(payload):
        return sorted((row["tour"], row["rank"], row["name_en"], row["current_name_zh"])
                      for row in payload.get("entries", []))
    if queue_rows(queue) != queue_rows(expected):
        errors.append("review queue differs from provisional snapshot names/ranks")
    if queue.get("ranking_date") != snapshot.get("ranking_date"):
        errors.append("review queue ranking_date differs from snapshot")
    return errors


def audit_refresh(snapshot, rebuilt):
    errors, warnings = [], []
    for tour, entries in snapshot["tours"].items():
        after = {_normalize_name(row["name_en"]): row for row in rebuilt["tours"][tour]}
        for before in entries:
            name = before["name_en"]
            row = after.get(_normalize_name(name))
            if row is None or row["name_zh"] != before["name_zh"]:
                errors.append(f"next refresh changes {name}: {before['name_zh']!r} -> {row!r}")
            elif any(before.get(key, "") != row.get(key, "")
                     for key in ("translation_source", "translation_source_url")):
                warnings.append(f"next refresh changes source metadata: {name}")
    return errors, warnings



def _evidence_url(value):
    """Match HTTP/HTTPS versions of one source without counting fragments twice."""
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path, parsed.query, ""))


def audit_review_records(ledger, lookup=player_zh):
    """Check editorial claims against runtime and preserve rejected-source decisions.

    This is an offline structural guard: a URL and excerpt alone cannot prove
    that an article concerns the right person. That remains a source review.
    Native-script excerpts may differ from the simplified display name.
    """
    errors = []
    for row in ledger.get("entries", []):
        name = row.get("name_en", "")
        current = row.get("name_zh", "")
        actual = lookup(name)
        if current != actual:
            errors.append(f"review ledger lookup mismatch: {name}: {current!r} -> {actual!r}")
        changed = row.get("before_zh") != current
        if row.get("changed") is not changed:
            errors.append(f"review ledger changed flag mismatch: {name}")
        rejected = set()
        for record in row.get("rejected_evidence", []):
            raw = record.get("source_url", record.get("url", "")) if isinstance(record, dict) else record
            key = _evidence_url(raw)
            if key:
                rejected.add(key)
        seen, usable = set(), False
        for evidence in row.get("evidence", []):
            key = _evidence_url(evidence.get("source_url"))
            if key and key in seen:
                errors.append(f"review ledger duplicate evidence URL: {name}: {key}")
            if key:
                seen.add(key)
            if key and key in rejected:
                errors.append(f"review ledger rejected evidence revived: {name}: {key}")
            excerpt = str(evidence.get("evidence", "")).strip()
            source_type = str(evidence.get("source_type", ""))
            is_excerpt = source_type not in {
                "search-snippet", "search-result", "search-summary", "identity-only",
                "official-english-identity", "identity-api", "english-ranking",
                "english-match-result", "official-match-api", "official-player-api",
                "official-identity-api",
            }
            if key and excerpt and is_excerpt and key not in rejected:
                usable = True
        if row.get("status") in {"verified-media", "verified-native"} and not usable:
            errors.append(f"review ledger verified without usable source evidence: {name}")
    return errors

def audit_repository():
    snapshot = json.loads(OUTPUT.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    queue = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
    errors = audit_tables(snapshot, overrides, PLAYER_ZH, queue)
    ledger_path = ROOT / "data" / "player_name_audit_2026-10-04.json"
    if ledger_path.is_file():
        errors.extend(audit_review_records(json.loads(ledger_path.read_text(encoding="utf-8"))))
    rows = {tour: [RankedName(tour, row["rank"], row["name_en"],
                              row["name_en"].split()[-1], row.get("country", ""))
                   for row in entries] for tour, entries in snapshot["tours"].items()}
    rebuilt = build_snapshot(rows["ATP"], rows["WTA"],
                             ranking_date=snapshot["ranking_date"], allow_machine=False)
    drift, warnings = audit_refresh(snapshot, rebuilt)
    return errors + drift, warnings


def main():
    errors, warnings = audit_repository()
    for error in errors:
        print(f"ERROR {error}")
    for warning in warnings:
        print(f"WARN {warning}")
    print(f"player-name alignment: {len(errors)} errors, {len(warnings)} metadata warnings")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
