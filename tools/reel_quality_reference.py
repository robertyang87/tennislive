"""Locate the immutable published reel used by the model shadow benchmark."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_SLUG = "fils-cobolli-cincinnati-2026-sf"
BENCHMARK_SPEC = ROOT / "specs" / "reels" / f"{BENCHMARK_SLUG}.json"


def benchmark() -> dict:
    return json.loads(BENCHMARK_SPEC.read_text(encoding="utf-8"))
