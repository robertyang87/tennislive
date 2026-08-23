from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools import video_sla


def _at(second: int) -> datetime:
    return datetime(2026, 8, 24, tzinfo=timezone.utc) + timedelta(seconds=second)


def test_remaining_counts_from_link_acceptance_not_process_start():
    assert video_sla.remaining_seconds(
        "2026-08-24T00:00:00Z", now=_at(100), reserve_seconds=10
    ) == 490


def test_finish_merges_metadata_and_records_breakdown(tmp_path: Path):
    film = tmp_path / "one.mp4"
    film.write_bytes(b"owned-video")
    meta = tmp_path / "render.json"
    meta.write_text('{"film_seconds": 91.2}', encoding="utf-8")

    record = video_sla.finish(
        received_at="2026-08-24T00:00:00Z",
        render_started_at="2026-08-24T00:01:20Z",
        artifact=film,
        metadata=meta,
        pipeline="interview",
        slug="one",
        now=_at(500),
    )

    assert record["met"] is True
    assert record["elapsed_seconds"] == 500
    assert record["pre_render_seconds"] == 80
    assert record["render_seconds"] == 420
    saved = json.loads(meta.read_text(encoding="utf-8"))
    assert saved["film_seconds"] == 91.2
    assert saved["production_sla"] == record


def test_late_artifact_is_recorded_for_warning_without_discarding_it(tmp_path: Path):
    film = tmp_path / "late.mp4"
    film.write_bytes(b"late")
    record = video_sla.finish(
        received_at="2026-08-24T00:00:00Z",
        artifact=film,
        metadata=tmp_path / "render.json",
        pipeline="reel",
        slug="late",
        now=_at(601),
    )
    assert record["met"] is False


def test_timestamp_and_artifact_contract_is_strict(tmp_path: Path):
    with pytest.raises(video_sla.SlaError, match="timezone"):
        video_sla.parse_instant("2026-08-24T00:00:00")
    with pytest.raises(video_sla.SlaError, match="missing or empty"):
        video_sla.finish(
            received_at="2026-08-24T00:00:00Z",
            artifact=tmp_path / "missing.mp4",
            metadata=tmp_path / "render.json",
            pipeline="reel",
            slug="missing",
            now=_at(1),
        )
