"""The existing wait-and-recheck policy does not lower unrelated source floors."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel


@pytest.mark.parametrize("url", reel.SINIAKOVA_OSAKA_2026_LOW_RES_SOURCES)
def test_osaka_policy_checks_native_height_before_display_conform(monkeypatch, url):
    spec = {"slug": "siniakova-osaka-title-run-2026", "sources": {"official": url},
            "source_quality_exceptions": {url: {"min_height": 720,
                "approved_by": "user", "reason": "Standing policy; actual channel and HLS rechecked after waiting."}}}
    monkeypatch.setattr(reel, "probe_size", lambda _: (1280, 720))
    reel.check_native_quality_exceptions(spec, {"official": Path("source.mp4")})
    monkeypatch.setattr(reel, "probe_size", lambda _: (640, 360))
    with pytest.raises(reel.ReelError, match="低于明确授权"):
        reel.check_native_quality_exceptions(spec, {"official": Path("source.mp4")})
    spec["slug"] = "unrelated-film"
    with pytest.raises(reel.ReelError, match="仅限"):
        reel.source_quality_exceptions(spec)


def test_osaka_does_not_authorize_other_official_urls():
    url = "https://www.youtube.com/watch?v=not-registered"
    spec = {"slug": "siniakova-osaka-title-run-2026", "sources": {"other": url},
            "source_quality_exceptions": {url: {"min_height": 720,
                "approved_by": "user", "reason": "Different source"}}}
    with pytest.raises(reel.ReelError, match="未授权"):
        reel.source_quality_exceptions(spec)
