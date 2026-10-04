"""The owner's archival approval preserves native pixels and other reels' gates."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel


def approved(url, height):
    return {
        "slug": "nishikori-career-farewell",
        "sources": {"archive": url},
        "source_quality_exceptions": {
            url: {"min_height": height, "approved_by": "user",
                  "reason": "2026-10-04用户同意无更佳源的低清档案，以保完整赛点。"}},
    }


@pytest.mark.parametrize("url,height", list(reel.NISHIKORI_FAREWELL_LOW_RES_SOURCES.items()))
def test_archival_approval_checks_actual_bytes_height_before_conform(monkeypatch, url, height):
    spec = approved(url, height)
    monkeypatch.setattr(reel, "probe_size", lambda _: (640, height))
    reel.check_native_quality_exceptions(spec, {"archive": Path("actual-source.mp4")})
    monkeypatch.setattr(reel, "probe_size", lambda _: (640, height - 1))
    with pytest.raises(reel.ReelError, match="低于明确授权"):
        reel.check_native_quality_exceptions(spec, {"archive": Path("actual-source.mp4")})


def test_approval_cannot_be_reused_for_a_different_reel_or_unknown_source():
    url = "https://www.nicovideo.jp/watch/sm26897731"
    spec = approved(url, 360)
    spec["slug"] = "another-reel"
    with pytest.raises(reel.ReelError, match="仅限"):
        reel.source_quality_exceptions(spec)
    with pytest.raises(reel.ReelError, match="未授权"):
        reel.source_quality_exceptions(approved("https://example.org/other.mp4", 360))


def test_lower_rendition_and_assistant_approval_remain_rejected():
    url = "https://www.nicovideo.jp/watch/sm26897731"
    for height, by in [(359, "user"), (360, "assistant")]:
        spec = approved(url, height)
        spec["source_quality_exceptions"][url]["approved_by"] = by
        with pytest.raises(reel.ReelError, match="source_quality_exceptions"):
            reel.source_quality_exceptions(spec)


def test_unapproved_native_360p_still_fails_default_probe_gate(monkeypatch):
    url = "https://www.nicovideo.jp/watch/sm26897731"
    spec = {"slug": "another-reel", "sources": {"archive": url},
            "segments": [{"source": "archive", "start": 1, "end": 3}]}
    probes = {url: {"url": url, "width": 640, "height": 360, "duration": 30,
                    "scene_cuts": [], "point_ends": []}}
    monkeypatch.setattr(reel, "probes_for_spec", lambda _: (probes, []))
    segments = reel.parse_segments(spec, {"archive": Path("actual-source.mp4")}, "archive")
    assert reel.probe_dry_run(spec, segments) is True
    assert probes[url]["height"] == 360
